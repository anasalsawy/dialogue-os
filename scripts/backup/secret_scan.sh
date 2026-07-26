#!/usr/bin/env bash
# Secret scan over staged files and/or a git diff. Never prints matched secret values.
set -euo pipefail

ROOT="${DIALOGUE_OS_ROOT:-$(pwd)}"
cd "$ROOT"
MODE="${1:-staged}"

list_files() {
  case "$MODE" in
    staged) git diff --cached --name-only --diff-filter=ACMR ;;
    diff) { git diff --name-only HEAD 2>/dev/null || true; git diff --cached --name-only; } | sort -u ;;
    tree) git ls-files ;;
    *) echo "Usage: $0 [staged|diff|tree]" >&2; exit 2 ;;
  esac
}

echo "Secret scan mode=$MODE"
mapfile -t FILES < <(list_files | sort -u)

python3 - "$MODE" "${FILES[@]}" <<'PY'
import re, sys
from pathlib import Path

mode = sys.argv[1]
files = [f for f in sys.argv[2:] if f]
if not files:
    print("OK: no files to scan")
    raise SystemExit(0)

TOKENISH = [
    re.compile(r"(?i)\b(ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{20,}"),
    re.compile(r"(?i)\bgithub_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"\bage-secret-key-1[a-z0-9]{20,}"),
    re.compile(r"-----BEGIN (?:RSA |OPENSSH |EC |AGE )?PRIVATE KEY-----"),
    re.compile(r"\b\d{8,12}:AA[A-Za-z0-9_-]{20,}\b"),
]
ASSIGN = re.compile(
    r"(?m)^[ \t]*(?:export[ \t]+)?("
    r"TELEGRAM_[A-Z0-9_]*BOT_TOKEN|HERMES_API_KEY|BROWSERBASE_API_KEY|"
    r"CURSOR_API_KEY|AWS_SECRET_ACCESS_KEY|AGE_SECRET_KEY"
    r")[ \t]*=[ \t]*([^\s#]+)"
)
PLACEHOLDER = re.compile(
    r"(?i)^(changeme|replace_me|your_.*|xxx+|todo|none|null|false|true|"
    r"test[-_].*|fake[-_].*|dummy[-_].*|example[-_].*|<.*>|\{.*\})$"
)
FORBIDDEN_SUFFIX = (
    ".sqlite3", ".sqlite3-wal", ".sqlite3-shm", ".pem", ".key", ".p12", ".pfx",
    ".age", ".tar.age",
)

fail = 0
for f in files:
    p = Path(f)
    base = p.name
    norm = f.replace("\\", "/")
    in_tests = norm.startswith("tests/") or "/tests/" in norm or base.startswith("test_")

    if base == ".env" or (base.startswith(".env.") and base != ".env.example"):
        print(f"FAIL forbidden path: {f}")
        fail = 1
        continue
    if base.endswith(FORBIDDEN_SUFFIX) or base in {"id_rsa", "id_ed25519", "id_ecdsa"}:
        print(f"FAIL forbidden artifact: {f}")
        fail = 1
        continue
    if not p.is_file():
        continue

    text = p.read_text(encoding="utf-8", errors="replace")

    # Production/docs/scripts: reject token-shaped material.
    # tests/: fixtures intentionally contain fake credentials.
    if not in_tests:
        for rx in TOKENISH:
            if rx.search(text):
                print(f"FAIL token-shaped secret in {f} (value not printed)")
                fail = 1
                break

    for m in ASSIGN.finditer(text):
        end = text.find("\n", m.start())
        line = text[m.start() : end if end != -1 else len(text)]
        if line.lstrip().startswith("#"):
            continue
        val = m.group(2).strip().strip('"').strip("'")
        if not val or PLACEHOLDER.match(val):
            continue
        if base == ".env.example":
            print(f"FAIL .env.example non-empty secret assignment: {m.group(1)}")
            fail = 1
            continue
        if in_tests:
            continue
        print(f"FAIL secret assignment in {f} key={m.group(1)} (value not printed)")
        fail = 1

if fail:
    print("Secret scan FAILED")
    raise SystemExit(1)
print(f"OK: secret scan clean ({mode}, {len(files)} files)")
PY

#!/usr/bin/env bash
# Verify an age-encrypted Dialogue-OS state backup without printing secrets.
set -euo pipefail

AGE_BIN="${AGE_BIN:-$(command -v age || true)}"
AGE_BIN="${AGE_BIN:-$HOME/.local/bin/age}"
IDENTITY="${BACKUP_AGE_IDENTITY:-${AGE_IDENTITY:-}}"
ARCHIVE="${1:-}"

die() { echo "ERROR: $*" >&2; exit 1; }

[[ -n "$ARCHIVE" && -f "$ARCHIVE" ]] || die "Usage: $0 /path/to/backup.tar.age"
[[ -x "$AGE_BIN" || -n "$(command -v "$AGE_BIN" 2>/dev/null)" ]] || die "age not found"
[[ -n "$IDENTITY" && -f "$IDENTITY" ]] || die "Set BACKUP_AGE_IDENTITY to the age private key path (never commit it)"

STAGE="$(mktemp -d "${TMPDIR:-/tmp}/dialogue-os-verify-XXXXXX")"
chmod 700 "$STAGE"
cleanup() {
  if [[ -d "$STAGE" ]]; then
    find "$STAGE" -type f -exec shred -u {} \; 2>/dev/null || find "$STAGE" -type f -delete
    rm -rf "$STAGE"
  fi
}
trap cleanup EXIT

TAR="$STAGE/backup.tar"
"$AGE_BIN" -d -i "$IDENTITY" -o "$TAR" "$ARCHIVE"
mkdir -p "$STAGE/out"
tar -C "$STAGE/out" -xf "$TAR"

echo "=== restore verification (structure only; no secret values) ==="
fail=0
check() {
  local p="$1"
  if [[ -e "$STAGE/out/$p" ]]; then
    echo "OK  $p"
  else
    echo "MISSING $p"
    fail=1
  fi
}

check MANIFEST.txt
check sqlite/dialogue_os.sqlite3
check meta/cursor_recovery.json
check meta/env_keys.json
check env/.env.example
# .env should exist inside a full backup
if [[ -f "$STAGE/out/env/.env" ]]; then
  echo "OK  env/.env (present; contents not printed; mode $(stat -c %a "$STAGE/out/env/.env"))"
else
  echo "MISSING env/.env"
  fail=1
fi

# SQLite integrity
if sqlite3 "$STAGE/out/sqlite/dialogue_os.sqlite3" 'PRAGMA integrity_check;' | grep -qx ok; then
  echo "OK  sqlite integrity_check"
else
  echo "FAIL sqlite integrity_check"
  fail=1
fi

# Offices table readable
python3 - <<'PY' "$STAGE/out/sqlite/dialogue_os.sqlite3" || fail=1
import sqlite3, sys
con = sqlite3.connect(sys.argv[1])
try:
    n = con.execute("select count(*) from offices").fetchone()[0]
    print(f"OK  offices_rows={n}")
except Exception as e:
    print(f"FAIL offices query: {type(e).__name__}")
    raise SystemExit(1)
PY

# Ensure we never echo .env
if grep -RIn --exclude='*.example' -E '^[A-Z0-9_]*(TOKEN|API_KEY|SECRET|PASSWORD)=' "$STAGE/out/meta" 2>/dev/null; then
  echo "FAIL meta leaked key=value patterns"
  fail=1
else
  echo "OK  meta has no TOKEN/API_KEY assignments"
fi

if [[ "$fail" -ne 0 ]]; then
  die "restore verification failed"
fi
echo "OK: encrypted backup structure verified."

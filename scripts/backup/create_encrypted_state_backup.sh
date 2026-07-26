#!/usr/bin/env bash
# Create an age-encrypted Dialogue-OS state backup.
# Never prints secret values. Never uploads unencrypted archives.
set -euo pipefail

ROOT="${DIALOGUE_OS_ROOT:-/home/azureuser/dialogue-os}"
cd "$ROOT"

# Load env names if present (values used only for recipient/dest/DB path)
if [[ -f "$ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/.env"
  set +a
fi

AGE_BIN="${AGE_BIN:-$(command -v age || true)}"
AGE_BIN="${AGE_BIN:-$HOME/.local/bin/age}"
SQLITE_DB="${DATABASE_PATH:-$ROOT/data/dialogue_os.sqlite3}"
RECIPIENT="${BACKUP_AGE_RECIPIENT:-${AGE_RECIPIENT:-}}"
DEST="${BACKUP_DESTINATION:-}"
TS="$(date -u +%Y%m%dT%H%M%SZ)"
HOST="$(hostname -s 2>/dev/null || echo host)"

die() { echo "ERROR: $*" >&2; exit 1; }

[[ -x "$AGE_BIN" || -n "$(command -v "$AGE_BIN" 2>/dev/null)" ]] || die "age not found (install age or set AGE_BIN)"
command -v sqlite3 >/dev/null || die "sqlite3 CLI required for consistent backup"
[[ -n "$RECIPIENT" ]] || die "BACKUP_AGE_RECIPIENT (or AGE_RECIPIENT) is not configured — blocker"
[[ -n "$DEST" ]] || die "BACKUP_DESTINATION is not configured — blocker"
[[ -f "$SQLITE_DB" ]] || die "SQLite DB not found at $SQLITE_DB"

STAGE="$(mktemp -d "${TMPDIR:-/tmp}/dialogue-os-backup-XXXXXX")"
chmod 700 "$STAGE"
cleanup() {
  # Best-effort secure wipe of staging
  if [[ -d "$STAGE" ]]; then
    find "$STAGE" -type f -exec shred -u {} \; 2>/dev/null || find "$STAGE" -type f -delete
    rm -rf "$STAGE"
  fi
}
trap cleanup EXIT

mkdir -p "$STAGE/sqlite" "$STAGE/meta" "$STAGE/systemd" "$STAGE/hermes_profiles" "$STAGE/env"

echo "Backing up SQLite via Online Backup API…"
sqlite3 "$SQLITE_DB" ".backup '$STAGE/sqlite/dialogue_os.sqlite3'"

echo "Collecting non-secret recovery metadata…"
python3 - <<'PY' "$ROOT" "$STAGE/meta" "$SQLITE_DB"
import json, os, sqlite3, sys, time
from pathlib import Path
root, meta_dir, db = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
out = {
    "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "dialogue_os_root": str(root),
    "database_basename": db.name,
    "hostname": os.uname().nodename,
}
# Cursor session id from SQLite if present (not auth material)
try:
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    row = con.execute(
        "SELECT session_key, session_id, updated_at FROM cursor_sessions ORDER BY updated_at DESC LIMIT 5"
    ).fetchall()
    out["cursor_sessions"] = [dict(r) for r in row]
    offices = con.execute(
        "SELECT department, office_chat_id, specialist_agent_id, hermes_profile, chat_title, active FROM offices"
    ).fetchall()
    out["offices"] = [dict(r) for r in offices]
    open_m = con.execute(
        "SELECT mission_id, department, status, office_chat_id FROM missions WHERE status NOT IN ('VERIFIED_COMPLETED','FAILED','CANCELLED')"
    ).fetchall()
    out["open_missions"] = [dict(r) for r in open_m]
    con.close()
except Exception as e:
    out["sqlite_meta_error"] = type(e).__name__
(meta_dir / "cursor_recovery.json").write_text(json.dumps(out, indent=2) + "\n")
# Env KEY NAMES only
env_path = root / ".env"
keys = []
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line=line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        keys.append(line.split("=", 1)[0].strip())
(meta_dir / "env_keys.json").write_text(json.dumps({"keys": keys}, indent=2) + "\n")
print("meta_ok")
PY

# Real .env only in encrypted archive
if [[ -f "$ROOT/.env" ]]; then
  cp -a "$ROOT/.env" "$STAGE/env/.env"
  chmod 600 "$STAGE/env/.env"
fi
cp -a "$ROOT/.env.example" "$STAGE/env/.env.example" 2>/dev/null || true

# systemd user units
if [[ -d "$HOME/.config/systemd/user" ]]; then
  cp -a "$HOME/.config/systemd/user/dialogue-os-bridge.service" "$STAGE/systemd/" 2>/dev/null || true
  cp -a "$HOME/.config/systemd/user/"*.service "$STAGE/systemd/" 2>/dev/null || true
fi
cp -a "$ROOT/systemd/." "$STAGE/systemd/repo_templates/" 2>/dev/null || mkdir -p "$STAGE/systemd/repo_templates"

# Hermes profile prompts (no API keys)
if [[ -d "$ROOT/hermes_profiles" ]]; then
  cp -a "$ROOT/hermes_profiles/." "$STAGE/hermes_profiles/"
fi

MANIFEST="$STAGE/MANIFEST.txt"
{
  echo "dialogue-os-encrypted-state-backup"
  echo "created_utc=$TS"
  echo "host=$HOST"
  echo "root=$ROOT"
  echo "contents=sqlite,env,systemd,hermes_profiles,meta"
} > "$MANIFEST"

TAR="$STAGE/dialogue-os-state-${HOST}-${TS}.tar"
AGE_OUT="$STAGE/dialogue-os-state-${HOST}-${TS}.tar.age"
tar -C "$STAGE" -cf "$TAR" \
  MANIFEST.txt sqlite meta systemd hermes_profiles env

echo "Encrypting with age (recipient configured; value not printed)…"
"$AGE_BIN" -r "$RECIPIENT" -o "$AGE_OUT" "$TAR"
shred -u "$TAR" 2>/dev/null || rm -f "$TAR"
# Remove plaintext env from stage before any transfer mistake
shred -u "$STAGE/env/.env" 2>/dev/null || rm -f "$STAGE/env/.env"

echo "Uploading ciphertext only to BACKUP_DESTINATION…"
case "$DEST" in
  file://*)
    dest_path="${DEST#file://}"
    mkdir -p "$(dirname "$dest_path")"
    cp -a "$AGE_OUT" "$dest_path"
    echo "Wrote $(basename "$AGE_OUT") → file destination"
    ;;
  s3://*|spaces://*)
    if command -v aws >/dev/null; then
      aws s3 cp "$AGE_OUT" "$DEST/"
    else
      die "aws CLI required for s3/spaces destination (or use file://…)"
    fi
    ;;
  /*)
    mkdir -p "$(dirname "$DEST")"
    if [[ -d "$DEST" ]]; then
      cp -a "$AGE_OUT" "$DEST/"
    else
      cp -a "$AGE_OUT" "$DEST"
    fi
    echo "Wrote ciphertext to filesystem destination"
    ;;
  *)
    die "Unsupported BACKUP_DESTINATION scheme (use file:///path, /path, or s3://bucket/prefix)"
    ;;
esac

echo "OK: encrypted state backup created and delivered (ciphertext only)."

# Restore (code layer)

Restore the DigitalOcean Dialogue-OS **code** from Git. This does **not** restore live Telegram tokens, SQLite mission state, or Cursor auth — see `BACKUP_MANIFEST.md` for encrypted state restore.

## Prerequisites

- GitHub access to `anasalsawy/dialogue-os-runtime`
- Python 3.12+
- Network for `pip`
- Do **not** start Telegram consumers during verification on a shared token set

## Clean clone + test (verification)

```bash
TMP=$(mktemp -d /tmp/dialogue-os-restore-XXXX)
trap 'rm -rf "$TMP"' EXIT
git clone --branch digitalocean-rebuild --single-branch \
  https://github.com/anasalsawy/dialogue-os-runtime.git "$TMP/dialogue-os"
cd "$TMP/dialogue-os"

python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt
# Prefer lock when resolving issues:
# .venv/bin/pip install -r requirements.lock

# Names only — do not copy production .env into the clean clone for CI-style tests
test -f .env.example

# Unit/integration tests only — no bridge, no getUpdates
.venv/bin/python -m pytest -q
```

Expected: all tests pass (skips allowed). If tests fail, **do not** claim restore success.

## Production restore onto a new VM

1. Clone `digitalocean-rebuild` to `/home/azureuser/dialogue-os` (or your chosen `DIALOGUE_OS_ROOT`).
2. `bash scripts/bootstrap.sh`
3. Restore secrets:
   - Prefer decrypting the encrypted state backup (see `scripts/backup/`), **or**
   - Manually recreate `.env` from `.env.example` and fill values
4. `chmod 600 .env`
5. `bash scripts/cursor-permissions/install.sh`
6. Cursor auth as service user (`agent login` or `CURSOR_API_KEY`)
7. If restoring SQLite from encrypted backup, place DB at `DATABASE_PATH` while bridge is **stopped**
8. `.venv/bin/python -m dialogue_os.scripts.validate_config`
9. Install systemd user unit; `systemctl --user enable --now dialogue-os-bridge`
10. `curl -s http://127.0.0.1:8787/status` — confirm bots/offices
11. If offices table empty, owner re-runs `/register_office <department>` inside each group

## Encrypted state restore (outline)

```bash
# Requires age identity matching BACKUP_AGE_RECIPIENT (private key — never commit)
bash scripts/backup/verify_encrypted_state_backup.sh /path/to/backup.tar.age
# Follow script output for staging paths. Copy SQLite/.env into place only when bridge is stopped.
```

## What success means

| Claim | Evidence |
|-------|----------|
| Code recoverable | Clean clone + `pytest` green |
| Config recoverable | `.env` present mode 600 + `validate_config` |
| Office topology recoverable | SQLite `offices` or owner re-registration |
| Full VM recoverable | Encrypted backup verified + bridge healthy |

Do not claim full VM recoverability from Git alone.

# Backup manifest

Dialogue-OS recoverability has **two layers**. Git alone is not enough.

## Layer A — Git (code & docs)

**Remote:** `anasalsawy/dialogue-os-runtime`  
**Branch for this DigitalOcean implementation:** `digitalocean-rebuild`  
**Preserved pre-import mint line:** `legacy/mint-final` + annotated tag `mint-final-before-digitalocean`

### Included in Git (safe)

- Runtime source (`dialogue_os/`)
- Tests (`tests/`)
- DB migrations (`dialogue_os/db/migrations/`)
- Office / mission / supervision code
- Cursor Chief integration
- Hermes adapters + sanitized profile prompts (`hermes_profiles/`, `prompts/`)
- Browserbase/Stagehand integration code
- systemd templates (`systemd/`)
- Install/ops scripts (`scripts/`)
- `requirements.txt`, `requirements.lock`, `pyproject.toml`, `pytest.ini`
- `.env.example` (variable **names** only)
- `.gitignore`, `.cursorignore` (via install script source)
- Reviewed project Cursor permission templates under `scripts/cursor-permissions/`
- Docs: `ARCHITECTURE.md`, `CURRENT_DEPLOYMENT.md`, `BACKUP_MANIFEST.md`, `RESTORE.md`, `REBUILD_CONTEXT.md`, `OPERATIONS.md`, `README.md`, `LICENSE.md`, `DIALOGUE_OS.md`

### Excluded from Git (never commit)

- `.env`, `.env.*` backups (except `.env.example`)
- Telegram / Hermes / Browserbase / Azure / Cursor API keys and tokens
- Passwords, SSH private keys, provider session/auth files
- SQLite DB + WAL/SHM
- Logs, caches, session dumps, bridge lock
- Telegram history / PII
- Browser cookies, profiles, storage state
- `.venv/`
- Customer data
- Cursor account/session authentication under `~/.cursor` (except reviewed project `cli.json` templates in-repo)

## Layer B — Encrypted state backup (VM disaster recovery)

Preserves runtime state that Git cannot:

| Content | How |
|---------|-----|
| Consistent SQLite | SQLite Online Backup API → copy into staging |
| Office registry + Telegram chat IDs | Inside SQLite `offices` (and related tables) |
| Mission / evidence / supervision | Inside SQLite |
| Cursor session id + non-secret recovery metadata | Extracted to `meta/cursor_recovery.json` (session id only; no auth material) |
| systemd user units | Copied from `~/.config/systemd/user/` |
| Runtime config names | `.env.example` + redacted key list |
| Hermes profile **files** | `hermes_profiles/` (prompts only) |
| Real `.env` and tokens | **Only** inside the **age-encrypted** archive |

### Encryption & destination

- Encrypt locally with **age** using public recipient `BACKUP_AGE_RECIPIENT`
- Never write an unencrypted off-host archive
- Use a private temp dir; wipe after upload
- Upload ciphertext only to `BACKUP_DESTINATION` (DigitalOcean Spaces URI, `s3://…`, or `file:///…` for operator pull)
- **Do not run a real state backup until both `BACKUP_AGE_RECIPIENT` and `BACKUP_DESTINATION` are set**

### Scripts

| Script | Purpose |
|--------|---------|
| `scripts/backup/create_encrypted_state_backup.sh` | Build encrypted archive (blocks if recipient/dest missing) |
| `scripts/backup/verify_encrypted_state_backup.sh` | Decrypt to temp (needs age identity) and verify structure — never prints secret values |
| `scripts/backup/secret_scan.sh` | Scan staged/diff files for likely secrets before push |
| `scripts/git/preserve_and_publish_digitalocean.sh` | Preserve mint line, publish `digitalocean-rebuild` (requires GitHub auth) |

## Operator checklist before claiming recoverability

1. `legacy/mint-final` + tag pushed
2. `digitalocean-rebuild` pushed; clean-clone tests pass
3. `BACKUP_AGE_RECIPIENT` and `BACKUP_DESTINATION` configured
4. At least one successful encrypted state backup uploaded
5. Restore verification of that archive succeeded on a scratch path

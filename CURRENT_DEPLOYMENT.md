# Current deployment (DigitalOcean VM)

Snapshot of the live Dialogue-OS / YTA runtime. **No secret values.**

## Host / paths

| Item | Value |
|------|-------|
| Cloud | DigitalOcean droplet |
| Service user | `azureuser` (non-root) |
| Project root (`DIALOGUE_OS_ROOT`) | `/home/azureuser/dialogue-os` |
| Python venv | `/home/azureuser/dialogue-os/.venv` |
| Env file | `/home/azureuser/dialogue-os/.env` (mode `600`, never commit) |
| SQLite DB | `/home/azureuser/dialogue-os/data/dialogue_os.sqlite3` |
| Canonical event log | `/home/azureuser/dialogue-os/data/canonical/events.jsonl` |
| Health bind | `127.0.0.1:8787` (`/health`, `/status`) |
| Bridge lock | `/home/azureuser/dialogue-os/data/bridge.lock` |

## systemd

| Item | Value |
|------|-------|
| Active unit (this VM) | **user** unit: `~/.config/systemd/user/dialogue-os-bridge.service` |
| Template in repo | `systemd/dialogue-os-bridge.service` (system-unit template; also usable as reference for user units) |
| Logrotate template | `systemd/dialogue-os.logrotate` |
| Start | `systemctl --user enable --now dialogue-os-bridge` |
| Logs | `journalctl --user -u dialogue-os-bridge -f` |

Do not restart the bridge during a pure code checkpoint unless the operator asks.

## Roles

| Role | Backend | Notes |
|------|---------|-------|
| Anas (owner) | Human | `TELEGRAM_OWNER_ID`; only owner may register offices |
| Chief | Cursor CLI | Manager/supervisor; persistent Cursor session |
| Specialists | Hermes profiles | One specialist per department office |
| Watchers | Hermes | Silent by default; optional offices |

## Office topology (department offices)

Each office is one Telegram **group** with: Anas + Chief + **exactly one** specialist.

| Department | Specialist agent | Hermes profile (typical) |
|------------|------------------|--------------------------|
| builder | builder | builder-lead |
| researcher | researcher | research-lead |
| operations | operations | operations-lead |
| growth | growth | growth-lead |
| customer_relations | customer_relations | customer-relations |
| stagehand | stagehand | stagehand-browser |
| watcher_alpha | watcher_alpha | watcher-alpha |
| watcher_beta | watcher_beta | watcher-beta |

Live chat IDs and titles change with Telegram; read them from `/status` → `offices` or `/offices` (owner, via Chief). Do not hard-code IDs into docs as if they were secrets-free forever — treat `/status` as source of truth after restore.

Canonical channel ID is configured as `TELEGRAM_CANONICAL_CHANNEL_ID` (secondary surface).

## Bots (agent_id → token env name)

| agent_id | Env var |
|----------|---------|
| chief | `TELEGRAM_CHIEF_BOT_TOKEN` |
| builder | `TELEGRAM_BUILDER_BOT_TOKEN` |
| researcher | `TELEGRAM_RESEARCH_BOT_TOKEN` |
| operations | `TELEGRAM_OPERATIONS_BOT_TOKEN` |
| growth | `TELEGRAM_GROWTH_BOT_TOKEN` |
| customer_relations | `TELEGRAM_CUSTOMER_RELATIONS_BOT_TOKEN` |
| stagehand | `TELEGRAM_STAGEHAND_BOT_TOKEN` |
| watcher_alpha | `TELEGRAM_WATCHER_ALPHA_BOT_TOKEN` |
| watcher_beta | `TELEGRAM_WATCHER_BETA_BOT_TOKEN` |

## Required environment variable names

See `.env.example`. Categories:

- Workspace: `DIALOGUE_OS_ROOT`
- Operator: `TELEGRAM_OWNER_ID`, `TELEGRAM_CANONICAL_CHANNEL_ID`
- Bot tokens: `TELEGRAM_*_BOT_TOKEN` (nine)
- Cursor: `CURSOR_CLI_BIN`, `CURSOR_MODEL`, `CURSOR_TIMEOUT_SECONDS`, `CURSOR_CONTROL_SESSION_KEY`, optional `CURSOR_FORCE_FLAG`, optional `CURSOR_API_KEY`
- Hermes: `HERMES_BASE_URL`, `HERMES_API_KEY`, `HERMES_MODEL`, `HERMES_MAX_OUTPUT_TOKENS`, `HERMES_TIMEOUT_SECONDS`
- Browser: `BROWSERBASE_API_KEY`, `BROWSERBASE_PROJECT_ID`, `STAGEHAND_ENABLED`
- Supervision: `SUPERVISION_TICK_SECONDS`, `MISSION_*`
- Runtime: `DATABASE_PATH`, `CANONICAL_LOG_PATH`, `HEALTH_BIND`, `HEALTH_PORT`, `LOG_LEVEL`, `SERVICE_USER`, `BOT_TO_BOT_CHATTER`, `AZURE_LLM_DISABLED`
- Encrypted state backup (optional; see `BACKUP_MANIFEST.md`): `BACKUP_AGE_RECIPIENT`, `BACKUP_DESTINATION`

## Installation order (new VM)

1. Clone the `digitalocean-rebuild` branch (see `RESTORE.md`).
2. `bash scripts/bootstrap.sh`
3. Copy `.env.example` → `.env`, fill secrets, `chmod 600 .env`
4. `bash scripts/cursor-permissions/install.sh`
5. Authenticate Cursor CLI as the service user (`agent login` or `CURSOR_API_KEY`)
6. `.venv/bin/python -m dialogue_os.scripts.validate_config`
7. Install and start the user systemd unit
8. Confirm `curl -s http://127.0.0.1:8787/status`
9. Owner registers offices inside each Telegram group with `/register_office <department>`

## Testing commands

```bash
cd /home/azureuser/dialogue-os
.venv/bin/python -m pytest -q
# Do not start Telegram consumers during clean-clone verification.
```

## Encrypted state backup (not Git)

- Scripts: `scripts/backup/create_encrypted_state_backup.sh`, `verify_encrypted_state_backup.sh`
- Timer templates: `systemd/dialogue-os-backup.timer` + `.service` (**do not enable** until `BACKUP_AGE_RECIPIENT` and `BACKUP_DESTINATION` are verified)
- See `BACKUP_MANIFEST.md`

## Governance port

- Plan: `GOVERNANCE_PORT_PLAN.md`
- Legacy refs: `LEGACY_REFERENCE.md`
- Migration `004_governance_strengthening.sql` adds acceptance criteria, tasks, leases, permits, audit, memory scopes
- Offline fakes: `dialogue_os/testing/`

## Git repository

- Intended remote for this implementation: `https://github.com/anasalsawy/dialogue-os`
- Legacy Mint runtime (read-only): `https://github.com/anasalsawy/dialogue-os-runtime`
- Live VM may lack `origin` until `gh auth login` + `git remote add origin …`
- Git is **not** a full VM backup — see `BACKUP_MANIFEST.md`

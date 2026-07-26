# Dialogue-OS / Your Travel Agent runtime

Persistent multi-agent runtime for Your Travel Agent on this VM.

## Critical architecture

| Component | Backend |
|-----------|---------|
| **Chief** | **Cursor CLI** (not Hermes) |
| Other agents | Persistent **Hermes** profiles |
| Orchestration | Cursor control plane + optional MAF handoffs |
| Browsing | **Stagehand/Browserbase tool only** |

Every managed Telegram ingress goes through the persistent Cursor CLI controller first. Cursor answers as Chief, or dispatches to a Hermes profile; the reply is published through the correct bot identity.

See [REBUILD_CONTEXT.md](REBUILD_CONTEXT.md), [ARCHITECTURE.md](ARCHITECTURE.md), and [OPERATIONS.md](OPERATIONS.md).

## Fixed workspace

```text
DIALOGUE_OS_ROOT=/home/azureuser/dialogue-os
```

Do not move this path — Cursor session continuity depends on it.

## Quick start

```bash
cd /home/azureuser/dialogue-os
bash scripts/bootstrap.sh
# Edit .env (chmod 600) — never commit secrets
.venv/bin/python -m dialogue_os.scripts.validate_config
sudo cp systemd/dialogue-os-bridge.service /etc/systemd/system/
sudo systemctl daemon-reload
# Start only after validation passes:
sudo systemctl enable --now dialogue-os-bridge
.venv/bin/python -m dialogue_os.scripts.health_check
```

## Commands (Chief bot)

- `/status` — workspace, Cursor session, backends
- `/new` — fresh Chief Cursor session
- `/resume` — list/select stored sessions
- `/cancel` — stop active Cursor invocation
- `/help` — brief help

## Tests

```bash
.venv/bin/pytest -q
```

## Constitution

Public Dialogue OS law lives in `DIALOGUE_OS.md` (upstream canonical file). This repository adds the private YTA runtime that implements Cursor-as-Chief and Hermes agents.

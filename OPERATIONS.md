# Operations

## Paths

- Root: `/home/azureuser/dialogue-os` (`DIALOGUE_OS_ROOT`)
- Env: `/home/azureuser/dialogue-os/.env` (mode `600`, service user only)
- DB: `/home/azureuser/dialogue-os/data/dialogue_os.sqlite3`
- Canonical log: `/home/azureuser/dialogue-os/data/canonical/events.jsonl`
- Health: `http://127.0.0.1:8787/health` and `/status`

## Service account

Run as `azureuser` (non-root). Never run Cursor CLI or the Telegram bridge as root.

## Install / update

System unit (requires sudo password once):

```bash
cd /home/azureuser/dialogue-os
bash scripts/bootstrap.sh
.venv/bin/python -m dialogue_os.scripts.validate_config
sudo cp systemd/dialogue-os-bridge.service /etc/systemd/system/
sudo cp systemd/dialogue-os.logrotate /etc/logrotate.d/dialogue-os
sudo systemctl daemon-reload
sudo systemctl enable --now dialogue-os-bridge
```

User unit (no root; already placed at `~/.config/systemd/user/`):

```bash
systemctl --user daemon-reload
# Only after validate_config passes:
systemctl --user enable --now dialogue-os-bridge
# Optional: sudo loginctl enable-linger azureuser  # survive logout
```

Do **not** enable production start until `validate_config` passes.

## Inspect

```bash
systemctl status dialogue-os-bridge
journalctl -u dialogue-os-bridge -f
.venv/bin/python -m dialogue_os.scripts.health_check
curl -s http://127.0.0.1:8787/status | jq .
```

## Cursor CLI

Binary: `agent` (also `cursor-agent`) under `~/.local/bin`.

Flags used by the bridge (`dialogue_os/cursor/client.py:_build_args`):

- `--print --output-format stream-json`
- `--workspace <DIALOGUE_OS_ROOT>`
- `--trust`
- `--sandbox enabled` (`CURSOR_SANDBOX`)
- `--resume <sessionId>`
- `create-chat` for new sessions
- **No** `--mode` flag — operational sessions run Cursor's default **Agent** mode
- **Never**: `--force`, `--yolo`, unrestricted approval mode

`--mode ask` / `--mode plan` raise `ValueError` unless the client is built with
`CursorClient(allow_read_only_modes=True)`, which only the live smoke test does.

Authenticate once as the service user: `agent login` (or `CURSOR_API_KEY`).

### Permissions

Execution authority comes from allow/deny rules, not from `--force`.

- Policy source of truth: `scripts/cursor-permissions/cli.json`
- Installed to: `.cursor/cli.json` (project-level; per Cursor docs only
  permissions may be set per project)
- Agent ignore file: `scripts/cursor-permissions/cursorignore` → `.cursorignore`

Install or update them as the operator:

```bash
cd /home/azureuser/dialogue-os
bash scripts/cursor-permissions/install.sh
.venv/bin/python -m pytest tests/test_cursor_permissions.py -q
```

The agent is denied `Write(.cursor/**)` and `Write(.cursorignore)` on purpose:
an agent that can rewrite its own permission file has no permission file. Those
two paths must be edited by the operator.

Deny rules take precedence over allow rules, and anything unmatched falls
through to a prompt — which in headless mode means it does not run. The failure
mode is over-restriction, never over-permission.

Allowed: read-only inspection (`ls`, `stat`, `rg`, `git status/diff/log`) and
project-local testing (`pytest`, `python3`, `ruff`, `mypy`), plus writes under
`dialogue_os/`, `tests/`, `scripts/`, `prompts/`, `hermes_profiles/`, `systemd/`.

Denied: destructive commands, secret access (`.env`, keys, credentials,
`*.sqlite3`, `env`/`printenv`), system administration (`sudo`, `systemctl`,
`apt`), deployment (`docker`, `kubectl`, `terraform`, `ssh`, `az`, `aws`, `gh`,
`git push`), writes outside `DIALOGUE_OS_ROOT`, and the cloud instance-metadata
endpoint `169.254.169.254`.

### Child process environment

`sanitize_env()` in `dialogue_os/cursor/client.py` builds the Cursor child
environment from an **allowlist**: Cursor auth (`CURSOR_API_KEY`), `PATH`,
`HOME`, locale, TLS/proxy settings, and the variables needed to run the project
(`VIRTUAL_ENV`, `PYTHONPATH`, …). Everything else is dropped, so a new bridge
secret is excluded by default rather than needing to be blacklisted.

Never forwarded: `TELEGRAM_*`, `HERMES_API_KEY`, `BROWSERBASE_API_KEY`,
`AZURE_*`, `DATABASE_PATH`, and anything whose name looks like a credential.

```bash
.venv/bin/python -m pytest tests/test_cursor_env_sanitization.py -q
```

## Secrets

- Never commit `.env`
- Never paste secrets into source
- Logs redact tokens, Authorization headers, cookies, and query-string secrets
- Request only missing variables after code is ready

## Restarts

SQLite mappings and Cursor session IDs survive process and VM restarts. `/new` deliberately rotates the Chief control session.

Code changes to `dialogue_os/` do **not** take effect until the bridge is
restarted. Restart manually, never from inside an agent turn:

```bash
# user unit (current deployment)
systemctl --user restart dialogue-os-bridge
systemctl --user status dialogue-os-bridge
journalctl --user -u dialogue-os-bridge -n 50 --no-pager

# system unit, if that is how it was installed
sudo systemctl restart dialogue-os-bridge
```

Validate before restarting:

```bash
cd /home/azureuser/dialogue-os
.venv/bin/python -m dialogue_os.scripts.validate_config
```

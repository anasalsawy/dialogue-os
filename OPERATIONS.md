# Operations

## Paths

- Root: `/home/azureuser/dialogue-os` (`DIALOGUE_OS_ROOT`)
- Env: `/home/azureuser/dialogue-os/.env` (mode `600`, service user only)
- DB: `/home/azureuser/dialogue-os/data/dialogue_os.sqlite3`
- Canonical log: `/home/azureuser/dialogue-os/data/canonical/events.jsonl`
- Health: `http://127.0.0.1:8787/health` and `/status`

## Service account

Run as `azureuser` (non-root). Never run Codex CLI or the Telegram bridge as root.

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

## Codex CLI

Binary: `codex` on `PATH` or under `~/.local/bin`.

Flags used by the bridge (`dialogue_os/codex/client.py:_build_args`):

- `exec --json --color never`
- `--cd <DIALOGUE_OS_ROOT>`
- `--sandbox workspace-write`
- `resume <thread_id>` for persistent sessions

Read-only `ask`/`plan` calls use `--sandbox read-only`.

Authenticate once as the service user with `codex login`. Trusted automation
may instead use the documented API-key or Codex access-token login flow.

### Permissions

Operational Chief runs in Codex's `workspace-write` sandbox. Do not add
`--dangerously-bypass-approvals-and-sandbox`.

## Temporary Featherless Chief

Set `CHIEF_BACKEND=featherless`, `CHIEF_FEATHERLESS_API_KEY`, and
`CHIEF_FEATHERLESS_MODEL`. The default endpoint is
`https://api.featherless.ai/v1`. If the Chief-specific key or model is empty,
the runtime falls back to `HERMES_API_KEY` or `HERMES_MODEL`. Chief uses a
separate persistent profile keyed by its control-session ID, so this does not
overwrite specialist conversations.

### Child process environment

`sanitize_env()` in `dialogue_os/codex/client.py` builds the Codex child
environment from an allowlist. Codex authentication is read from its credential
store; bridge API keys and Telegram tokens are not copied into the child.

Never forwarded: `TELEGRAM_*`, `HERMES_API_KEY`, `BROWSERBASE_API_KEY`,
`AZURE_*`, `DATABASE_PATH`, and anything whose name looks like a credential.

```bash
.venv/bin/python -m pytest tests/test_codex_client.py -q
```

## Secrets

- Never commit `.env`
- Never paste secrets into source
- Logs redact tokens, Authorization headers, cookies, and query-string secrets
- Request only missing variables after code is ready

## Restarts

SQLite mappings and Codex session IDs survive process and VM restarts. `/new` deliberately rotates the Chief control session.

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

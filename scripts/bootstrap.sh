#!/usr/bin/env bash
# Bootstrap Dialogue-OS on this VM (non-root service account).
set -euo pipefail

ROOT="${DIALOGUE_OS_ROOT:-/home/azureuser/dialogue-os}"
SERVICE_USER="${SERVICE_USER:-azureuser}"

if [[ "$(id -u)" -eq 0 ]]; then
  echo "Do not run the bridge as root. Bootstrap may use sudo for systemd only."
fi

cd "$ROOT"

python3 -m venv "$ROOT/.venv"
"$ROOT/.venv/bin/pip" install --upgrade pip
"$ROOT/.venv/bin/pip" install -r "$ROOT/requirements.txt"
"$ROOT/.venv/bin/pip" freeze > "$ROOT/requirements.lock"

mkdir -p "$ROOT/data/logs" "$ROOT/data/canonical"
touch "$ROOT/data/logs/.gitkeep" "$ROOT/data/canonical/.gitkeep"

if [[ ! -f "$ROOT/.env" ]]; then
  cp "$ROOT/.env.example" "$ROOT/.env"
  echo "Created $ROOT/.env from example — fill secrets before starting services."
else
  echo "Preserving existing $ROOT/.env (not overwritten)."
fi
chmod 600 "$ROOT/.env" || true
chown "$SERVICE_USER:$SERVICE_USER" "$ROOT/.env" 2>/dev/null || true

# Validate (may fail until secrets are present)
"$ROOT/.venv/bin/python" -m dialogue_os.scripts.validate_config || true

echo "Bootstrap complete. DIALOGUE_OS_ROOT=$ROOT"
echo "Next: edit .env, run validate_config, install systemd units, then start."

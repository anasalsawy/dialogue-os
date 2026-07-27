#!/usr/bin/env bash
set -euo pipefail

# Build one genuine Hermes profile + API server per Dialogue-OS specialist.
# Run as azureuser from /home/azureuser/dialogue-os:
#   HERMES_RUNTIME_API_KEY='a-long-random-secret' \
#     bash scripts/install_hermes_profiles.sh

PROJECT_ROOT="${DIALOGUE_OS_ROOT:-/home/azureuser/dialogue-os}"
HERMES_ROOT="${HERMES_HOME:-${HOME}/.hermes}"
HERMES_BIN="${HERMES_BIN:-$(command -v hermes)}"
RUNTIME_KEY="${HERMES_RUNTIME_API_KEY:-}"

if [[ -z "${RUNTIME_KEY}" ]]; then
  echo "Set HERMES_RUNTIME_API_KEY to a long random secret before running." >&2
  exit 2
fi
if [[ ! -x "${HERMES_BIN}" ]]; then
  echo "Hermes executable not found. Set HERMES_BIN to its absolute path." >&2
  exit 2
fi

profiles=(
  builder-lead
  research-lead
  operations-lead
  growth-lead
  customer-relations
  stagehand-browser
  watcher-alpha
  watcher-beta
)
descriptions=(
  "Builds and repairs Dialogue-OS, the YTA website, and production services."
  "Researches suppliers, APIs, technical options, and evidence."
  "Runs travel operations, bookings, fulfillment, and incident response."
  "Runs acquisition, partnerships, campaigns, and revenue experiments."
  "Handles customer conversations, follow-up, support, and escalation."
  "Operates Browserbase and Stagehand with browser evidence."
  "Independently watches execution, evidence, safety, and success criteria."
  "Independently critiques plans, detects stalls, and verifies outcomes."
)

mkdir -p "${HERMES_ROOT}/profiles"

for index in "${!profiles[@]}"; do
  profile="${profiles[$index]}"
  profile_dir="${HERMES_ROOT}/profiles/${profile}"
  port="$((8643 + index))"

  if [[ ! -d "${profile_dir}" ]]; then
    "${HERMES_BIN}" profile create "${profile}" --clone \
      --description "${descriptions[$index]}" --no-alias
  fi

  install -m 0600 \
    "${PROJECT_ROOT}/hermes_profiles/${profile}.md" \
    "${profile_dir}/SOUL.md"

  PROFILE_DIR="${profile_dir}" PROFILE_PORT="${port}" PROFILE_KEY="${RUNTIME_KEY}" \
    python3 - <<'PY'
import os
from pathlib import Path

profile_dir = Path(os.environ["PROFILE_DIR"])
env_path = profile_dir / ".env"
updates = {
    "API_SERVER_ENABLED": "true",
    "API_SERVER_HOST": "127.0.0.1",
    "API_SERVER_PORT": os.environ["PROFILE_PORT"],
    "API_SERVER_KEY": os.environ["PROFILE_KEY"],
    "API_SERVER_MODEL_NAME": profile_dir.name,
}
exclusive_prefixes = (
    "TELEGRAM_",
    "DISCORD_",
    "SLACK_",
    "WHATSAPP_",
    "SIGNAL_",
    "MATRIX_",
)
lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []
kept = []
seen = set()
for line in lines:
    key = line.split("=", 1)[0].strip() if "=" in line else ""
    if any(key.startswith(prefix) for prefix in exclusive_prefixes):
        continue
    if key in updates:
        kept.append(f"{key}={updates[key]}")
        seen.add(key)
    else:
        kept.append(line)
for key, value in updates.items():
    if key not in seen:
        kept.append(f"{key}={value}")
env_path.write_text("\n".join(kept).rstrip() + "\n", encoding="utf-8")
env_path.chmod(0o600)

config_path = profile_dir / "config.yaml"
config = config_path.read_text(encoding="utf-8") if config_path.exists() else ""
marker = "\n# Dialogue-OS managed full agent toolset\n"
managed = (
    "platform_toolsets:\n"
    "  api_server: [hermes-cli]\n"
)
if marker in config:
    config = config.split(marker, 1)[0].rstrip() + "\n"
config_path.write_text(config.rstrip() + marker + managed, encoding="utf-8")
PY
done

service_dir="${HOME}/.config/systemd/user"
mkdir -p "${service_dir}"
service_path="${service_dir}/dialogue-os-hermes@.service"
{
  echo "[Unit]"
  echo "Description=Dialogue-OS Hermes profile %i"
  echo "After=network-online.target"
  echo "Wants=network-online.target"
  echo
  echo "[Service]"
  echo "Type=simple"
  echo "ExecStart=${HERMES_BIN} -p %i gateway"
  echo "Restart=on-failure"
  echo "RestartSec=5"
  echo "TimeoutStopSec=30"
  echo "Environment=MESSAGING_CWD=${PROJECT_ROOT}"
  echo
  echo "[Install]"
  echo "WantedBy=default.target"
} > "${service_path}"

systemctl --user daemon-reload
profile_urls=()
for index in "${!profiles[@]}"; do
  profile="${profiles[$index]}"
  port="$((8643 + index))"
  systemctl --user enable --now "dialogue-os-hermes@${profile}.service"
  profile_urls+=("${profile}=http://127.0.0.1:${port}")
done

joined_urls="$(IFS=,; echo "${profile_urls[*]}")"
dialogue_env="${PROJECT_ROOT}/.env"
DIALOGUE_ENV="${dialogue_env}" PROFILE_URLS="${joined_urls}" PROFILE_KEY="${RUNTIME_KEY}" \
  python3 - <<'PY'
import os
from pathlib import Path

path = Path(os.environ["DIALOGUE_ENV"])
updates = {
    "HERMES_BACKEND": "agent_api",
    "HERMES_SESSION_SCOPE": "profile",
    "HERMES_AGENT_API_URL": "http://127.0.0.1:8642",
    "HERMES_AGENT_API_KEY": os.environ["PROFILE_KEY"],
    "HERMES_AGENT_MULTIPLEX_PROFILES": "false",
    "HERMES_AGENT_PROFILE_URLS": os.environ["PROFILE_URLS"],
}
lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
output = []
seen = set()
for line in lines:
    key = line.split("=", 1)[0].strip() if "=" in line else ""
    if key in updates:
        output.append(f"{key}={updates[key]}")
        seen.add(key)
    else:
        output.append(line)
for key, value in updates.items():
    if key not in seen:
        output.append(f"{key}={value}")
path.write_text("\n".join(output).rstrip() + "\n", encoding="utf-8")
path.chmod(0o600)
PY

echo "Installed ${#profiles[@]} isolated Hermes Agent profiles with hermes-cli toolsets."
echo "Dialogue-OS .env now routes every specialist to its own local agent API."
echo "Restart Dialogue-OS after pulling the bridge changes:"
echo "  systemctl --user restart dialogue-os-bridge.service"

#!/usr/bin/env bash
# Install unrestricted Cursor CLI permissions for Dialogue-OS.
#
# - Project: .cursor/cli.json (Shell(*) / Read(**) / Write(**) / WebFetch(*) / Mcp(*); deny=[])
# - Global: ~/.cursor/cli-config.json approvalMode=unrestricted, sandbox disabled
# - .cursorignore: keep secrets out of Agent indexing (not a command allowlist)

set -euo pipefail

ROOT="${DIALOGUE_OS_ROOT:-/home/azureuser/dialogue-os}"
SRC="$ROOT/scripts/cursor-permissions"
HOME_DIR="${HOME:-/home/azureuser}"

mkdir -p "$ROOT/.cursor" "$HOME_DIR/.cursor"
install -m 0644 "$SRC/cli.json" "$ROOT/.cursor/cli.json"
install -m 0644 "$SRC/cursorignore" "$ROOT/.cursorignore"

"$ROOT/.venv/bin/python" - <<'PY'
from pathlib import Path
from dialogue_os.cursor.client import ensure_cli_unrestricted, detect_force_flag, parse_force_flag_from_help
import shutil

path = ensure_cli_unrestricted()
print(f"global cli-config: {path}")
bin_path = shutil.which("agent") or str(Path.home() / ".local/bin/agent")
print(f"force flag: {detect_force_flag(bin_path)}")
PY

echo "installed project permissions + unrestricted global approvalMode"

#!/usr/bin/env bash
# Idempotent install for the Dialogue OS multi-repo workspace.
# Prepares every runnable sibling repository checked out next to dialogue-os:
#   - dialogue-os-runtime           (Python, stdlib-only test suite)
#   - yta-assistant-travel-memory   (FastAPI backend)
#   - your-travel-agent-ccb6b77f    (Vite/React web app)
# Each step is guarded so the script succeeds even if a repo is absent.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PRIMARY_REPO="$(dirname "$SCRIPT_DIR")"
REPOS_DIR="$(dirname "$PRIMARY_REPO")"

RUNTIME_DIR="$REPOS_DIR/dialogue-os-runtime"
BACKEND_DIR="$REPOS_DIR/yta-assistant-travel-memory"
FRONTEND_DIR="$REPOS_DIR/your-travel-agent-ccb6b77f"

echo "==> Dialogue OS workspace install"
echo "    primary repo : $PRIMARY_REPO"
echo "    repos dir    : $REPOS_DIR"

# The default base image ships python3 without venv/ensurepip support.
if ! python3 -c "import ensurepip" >/dev/null 2>&1; then
  echo "==> Installing python3-venv (ensurepip missing)"
  sudo apt-get update -qq
  sudo apt-get install -y -qq python3.12-venv
fi

# dialogue-os-runtime: pure standard library, no dependencies to install.
if [ -d "$RUNTIME_DIR" ]; then
  echo "==> dialogue-os-runtime: stdlib-only, no dependencies"
  (cd "$RUNTIME_DIR" && python3 -c "import sys; assert sys.version_info >= (3, 10), sys.version")
else
  echo "==> dialogue-os-runtime not present, skipping"
fi

# yta-assistant-travel-memory: Python venv + pinned requirements.
if [ -d "$BACKEND_DIR" ]; then
  echo "==> yta-assistant-travel-memory: creating venv and installing requirements"
  cd "$BACKEND_DIR"
  if [ ! -x .venv/bin/python ]; then
    rm -rf .venv
    python3 -m venv .venv
  fi
  # shellcheck disable=SC1091
  . .venv/bin/activate
  pip install --upgrade pip -q
  pip install -q -r requirements.txt
  deactivate
  [ -f .env ] || cp .env.example .env
else
  echo "==> yta-assistant-travel-memory not present, skipping"
fi

# your-travel-agent-ccb6b77f: npm dependencies from the committed lockfile.
if [ -d "$FRONTEND_DIR" ]; then
  echo "==> your-travel-agent-ccb6b77f: installing npm dependencies"
  cd "$FRONTEND_DIR"
  if [ -f package-lock.json ]; then
    npm ci
  else
    npm install
  fi
else
  echo "==> your-travel-agent-ccb6b77f not present, skipping"
fi

echo "==> install complete"

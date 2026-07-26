#!/usr/bin/env bash
# Preserve mint line on anasalsawy/dialogue-os-runtime and publish digitalocean-rebuild.
# Requires GitHub auth (gh auth login or GIT credentials). Never force-pushes.
set -euo pipefail

ROOT="${DIALOGUE_OS_ROOT:-/home/azureuser/dialogue-os}"
REPO_SSH="${REPO_SSH:-git@github.com:anasalsawy/dialogue-os-runtime.git}"
REPO_HTTPS="${REPO_HTTPS:-https://github.com/anasalsawy/dialogue-os-runtime.git}"
REMOTE_NAME="${REMOTE_NAME:-origin}"
LEGACY_BRANCH="legacy/mint-final"
TAG="mint-final-before-digitalocean"
NEW_BRANCH="digitalocean-rebuild"
WORK="${WORK_DIR:-/tmp/dialogue-os-runtime-publish}"

die() { echo "ERROR: $*" >&2; exit 1; }

export PATH="$HOME/.local/bin:$PATH"

if ! command -v gh >/dev/null || ! gh auth status >/dev/null 2>&1; then
  if ! git ls-remote "$REPO_SSH" HEAD >/dev/null 2>&1 && ! git ls-remote "$REPO_HTTPS" HEAD >/dev/null 2>&1; then
    die "GitHub authentication missing. Run: gh auth login   (do not paste tokens into Telegram)"
  fi
fi

REPO_URL="$REPO_HTTPS"
if git ls-remote "$REPO_SSH" HEAD >/dev/null 2>&1; then
  REPO_URL="$REPO_SSH"
fi

rm -rf "$WORK"
git clone "$REPO_URL" "$WORK"
cd "$WORK"

DEFAULT_BRANCH="$(git remote show origin | awk '/HEAD branch/ {print $NF}')"
git checkout "$DEFAULT_BRANCH"
git pull --ff-only

# Preserve old main tip
git branch "$LEGACY_BRANCH" "$DEFAULT_BRANCH"
if git rev-parse "$TAG" >/dev/null 2>&1; then
  echo "Tag $TAG already exists locally"
else
  git tag -a "$TAG" -m "Mint final line preserved before DigitalOcean Dialogue-OS import"
fi

git push -u origin "$LEGACY_BRANCH"
git push origin "$TAG"

# New branch from preserved tip, then replace tree with live DigitalOcean project (safe files)
git checkout -B "$NEW_BRANCH" "$LEGACY_BRANCH"

# Sync from live tree excluding secrets/runtime
rsync -a --delete \
  --exclude '.git/' \
  --exclude '.venv/' \
  --exclude '.env' \
  --exclude '.env.*' \
  --include '.env.example' \
  --exclude 'data/*.sqlite3' \
  --exclude 'data/*.sqlite3-*' \
  --exclude 'data/logs/*' \
  --exclude 'data/canonical/*' \
  --exclude 'data/bridge.lock' \
  --exclude '.pytest_cache/' \
  --exclude 'dialogue_os.egg-info/' \
  --exclude '__pycache__/' \
  --exclude '.cursor/' \
  --exclude '*.log' \
  "$ROOT/" "$WORK/"

# Keep placeholder gitkeeps
mkdir -p data/logs data/canonical
touch data/logs/.gitkeep data/canonical/.gitkeep

git add -A
bash "$WORK/scripts/backup/secret_scan.sh" staged

# Local tests before push
python3 -m venv .venv
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r requirements.txt
.venv/bin/python -m pytest -q

git commit -m "$(cat <<'EOF'
Import DigitalOcean Dialogue-OS runtime checkpoint.

Preserve recoverability docs, office/mission runtime, and backup tooling.
EOF
)" || echo "Nothing to commit (tree may already match)"

SHA="$(git rev-parse HEAD)"
git push -u origin "$NEW_BRANCH"

# Clean-clone verify
VERIFY="$(mktemp -d /tmp/dialogue-os-clean-XXXX)"
git clone --branch "$NEW_BRANCH" --single-branch "$REPO_URL" "$VERIFY/repo"
cd "$VERIFY/repo"
python3 -m venv .venv
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r requirements.txt
.venv/bin/python -m pytest -q
echo "CLEAN_CLONE_OK"
echo "SHA=$SHA"
echo "BRANCH=$NEW_BRANCH"
echo "LEGACY=$LEGACY_BRANCH"
echo "TAG=$TAG"
echo "REPO=$REPO_URL"
rm -rf "$VERIFY"

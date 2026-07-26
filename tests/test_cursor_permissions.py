"""Validate unrestricted Cursor CLI permission policy.

Source of truth for project install: scripts/cursor-permissions/cli.json
Global approvalMode: ~/.cursor/cli-config.json (managed by ensure_cli_unrestricted).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
STAGED_CLI_JSON = ROOT / "scripts" / "cursor-permissions" / "cli.json"
STAGED_IGNORE = ROOT / "scripts" / "cursor-permissions" / "cursorignore"
INSTALLED_CLI_JSON = ROOT / ".cursor" / "cli.json"
INSTALLED_IGNORE = ROOT / ".cursorignore"

CLI_JSON_FILES = [STAGED_CLI_JSON] + ([INSTALLED_CLI_JSON] if INSTALLED_CLI_JSON.exists() else [])
IGNORE_FILES = [STAGED_IGNORE] + ([INSTALLED_IGNORE] if INSTALLED_IGNORE.exists() else [])


def _load(path: Path) -> dict:
    return json.loads(path.read_text())


@pytest.mark.parametrize("path", CLI_JSON_FILES, ids=lambda p: str(p.relative_to(ROOT) if p.is_relative_to(ROOT) else p))
def test_permissions_are_unrestricted(path: Path):
    data = _load(path)
    perms = data["permissions"]
    assert perms["deny"] == [], f"{path} still denies commands: {perms['deny']}"
    allow = set(perms["allow"])
    for required in ("Shell(*)", "Read(**)", "Write(**)", "WebFetch(*)", "Mcp(*)"):
        assert required in allow, f"{path} missing unrestricted rule {required}"


@pytest.mark.parametrize("path", IGNORE_FILES, ids=lambda p: p.name)
def test_cursorignore_still_covers_secrets(path: Path):
    """Unrestricted tools ≠ secrets in prompts/index. Keep .env and keys ignored."""
    lines = {ln.strip() for ln in path.read_text().splitlines() if ln.strip() and not ln.startswith("#")}
    required = [".env", ".env.*", "*.pem", "*.key", "*credentials*", "*.sqlite3", "*.sqlite3-*"]
    missing = [r for r in required if r not in lines]
    assert not missing, f"{path.name} is missing patterns: {missing}"


def test_installed_policy_matches_staged_policy():
    if not INSTALLED_CLI_JSON.exists():
        pytest.skip("run scripts/cursor-permissions/install.sh to install .cursor/cli.json")
    assert _load(INSTALLED_CLI_JSON) == _load(STAGED_CLI_JSON)

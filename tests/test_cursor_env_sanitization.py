"""The Cursor subprocess must never inherit bridge secrets.

These tests are the contract for dialogue_os.cursor.client.sanitize_env: an
allowlisted child environment carrying Cursor auth, PATH/HOME, locale and the
variables needed for normal project execution — nothing else.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from dialogue_os.cursor.client import CursorClient, sanitize_env

SECRET_VARS = {
    "TELEGRAM_CHIEF_BOT_TOKEN": "111111111:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
    "TELEGRAM_BUILDER_BOT_TOKEN": "222222222:BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB",
    "TELEGRAM_RESEARCH_BOT_TOKEN": "333333333:CCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC",
    "TELEGRAM_OPERATIONS_BOT_TOKEN": "444444444:DDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDD",
    "TELEGRAM_GROWTH_BOT_TOKEN": "555555555:EEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEE",
    "TELEGRAM_CUSTOMER_RELATIONS_BOT_TOKEN": "666666666:FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF",
    "TELEGRAM_STAGEHAND_BOT_TOKEN": "777777777:GGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGG",
    "TELEGRAM_WATCHER_ALPHA_BOT_TOKEN": "888888888:HHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHH",
    "TELEGRAM_WATCHER_BETA_BOT_TOKEN": "999999999:IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII",
    "TELEGRAM_OWNER_ID": "1234567",
    "TELEGRAM_CANONICAL_CHANNEL_ID": "-1001234567",
    "HERMES_API_KEY": "hermes-sk-should-never-leak",
    "HERMES_BASE_URL": "https://hermes.internal/v1",
    "BROWSERBASE_API_KEY": "bb-should-never-leak",
    "BROWSERBASE_PROJECT_ID": "bb-project-should-never-leak",
    "AZURE_OPENAI_API_KEY": "azure-should-never-leak",
    "AZURE_OPENAI_ENDPOINT": "https://example.openai.azure.com",
    "AZURE_AI_PROJECT_ENDPOINT": "https://example.services.ai.azure.com",
    "OPENAI_API_KEY": "sk-should-never-leak",
    "ANTHROPIC_API_KEY": "sk-ant-should-never-leak",
    "DATABASE_PATH": "/home/azureuser/dialogue-os/data/dialogue_os.sqlite3",
    "DATABASE_URL": "postgres://user:password@host/db",
    "AWS_SECRET_ACCESS_KEY": "aws-should-never-leak",
    "GITHUB_TOKEN": "ghp_should_never_leak",
    "SLACK_WEBHOOK": "https://hooks.slack.com/should-never-leak",
    "MY_APP_PASSWORD": "hunter2",
    "SOME_PRIVATE_KEY": "-----BEGIN PRIVATE KEY-----",
    "SERVICE_CREDENTIAL": "cred-should-never-leak",
    "SESSION_COOKIE": "cookie-should-never-leak",
}

SAFE_VARS = {
    "PATH": "/usr/local/bin:/usr/bin:/bin",
    "HOME": "/home/azureuser",
    "USER": "azureuser",
    "LANG": "en_US.UTF-8",
    "LC_ALL": "en_US.UTF-8",
    "TZ": "UTC",
    "VIRTUAL_ENV": "/home/azureuser/dialogue-os/.venv",
    "XDG_RUNTIME_DIR": "/run/user/1000",
}


def _env_with_secrets(**extra: str) -> dict[str, str]:
    return {**SAFE_VARS, **SECRET_VARS, **extra}


def test_every_named_secret_is_removed():
    env = sanitize_env(_env_with_secrets(), workspace=Path("/home/azureuser/dialogue-os"))
    leaked = sorted(k for k in SECRET_VARS if k in env)
    assert leaked == [], f"secret variables leaked into Cursor child env: {leaked}"


def test_no_secret_value_survives_anywhere_in_the_child_env():
    """Catch leakage via renamed or aggregated variables, not just by key."""
    env = sanitize_env(_env_with_secrets(), workspace=Path("/home/azureuser/dialogue-os"))
    blob = json.dumps(env)
    for name, value in SECRET_VARS.items():
        assert value not in blob, f"value of {name} leaked into Cursor child env"


def test_required_execution_vars_are_preserved():
    env = sanitize_env(_env_with_secrets(), workspace=Path("/home/azureuser/dialogue-os"))
    for key, value in SAFE_VARS.items():
        assert env.get(key) == value, f"{key} should be forwarded to Cursor"


def test_workspace_and_headless_markers_are_set():
    env = sanitize_env(_env_with_secrets(), workspace=Path("/home/azureuser/dialogue-os"))
    assert env["DIALOGUE_OS_ROOT"] == "/home/azureuser/dialogue-os"
    assert env["NO_OPEN_BROWSER"] == "1"


def test_cursor_api_key_is_the_only_permitted_credential():
    env = sanitize_env(
        _env_with_secrets(CURSOR_API_KEY="cursor-auth-key"),
        workspace=Path("/tmp/ws"),
        api_key="cursor-auth-key",
    )
    assert env["CURSOR_API_KEY"] == "cursor-auth-key"
    credential_keys = {
        k for k in env if any(t in k.upper() for t in ("KEY", "TOKEN", "SECRET", "PASSWORD"))
    }
    assert credential_keys == {"CURSOR_API_KEY"}, f"unexpected credentials in env: {credential_keys}"


def test_unknown_variables_are_dropped_by_default():
    """Allowlist semantics: a newly added bridge variable is excluded without
    anyone remembering to blacklist it."""
    env = sanitize_env(
        {**SAFE_VARS, "SOME_FUTURE_BRIDGE_VAR": "x", "WHATEVER": "y"},
        workspace=Path("/tmp/ws"),
    )
    assert "SOME_FUTURE_BRIDGE_VAR" not in env
    assert "WHATEVER" not in env


def test_client_env_uses_sanitizer(tmp_path: Path, monkeypatch):
    for key, value in SECRET_VARS.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("PATH", SAFE_VARS["PATH"])
    client = CursorClient(tmp_path, api_key="cursor-auth-key")
    env = client._env()
    for key in SECRET_VARS:
        assert key not in env, f"{key} reached the Cursor subprocess via CursorClient._env()"
    assert env["CURSOR_API_KEY"] == "cursor-auth-key"
    assert env["DIALOGUE_OS_ROOT"] == str(tmp_path.resolve())


async def test_bridge_secrets_are_not_reintroduced_by_run(tmp_path: Path, monkeypatch):
    """End-to-end on the spawn path: capture the env actually handed to exec."""
    for key, value in SECRET_VARS.items():
        monkeypatch.setenv(key, value)

    captured: dict[str, Any] = {}

    async def fake_exec(*args, **kwargs):
        captured["args"] = list(args)
        captured["env"] = kwargs["env"]
        raise RuntimeError("stop before spawning")

    monkeypatch.setattr("asyncio.create_subprocess_exec", fake_exec)

    client = CursorClient(tmp_path, cli_bin="agent")
    monkeypatch.setattr(client, "resolve_bin", lambda: "/usr/bin/agent")

    result = await client.run("hello")
    assert not result.ok
    for key in SECRET_VARS:
        assert key not in captured["env"], f"{key} was passed to the Cursor subprocess"
    assert "--sandbox" not in captured["args"]
    assert "--force" in captured["args"] or "--yolo" in captured["args"]


async def test_create_session_also_uses_sanitized_env(tmp_path: Path, monkeypatch):
    for key, value in SECRET_VARS.items():
        monkeypatch.setenv(key, value)

    captured: dict[str, Any] = {}

    async def fake_exec(*args, **kwargs):
        captured["env"] = kwargs["env"]
        raise RuntimeError("stop before spawning")

    monkeypatch.setattr("asyncio.create_subprocess_exec", fake_exec)

    client = CursorClient(tmp_path, cli_bin="agent")
    monkeypatch.setattr(client, "resolve_bin", lambda: "/usr/bin/agent")

    with pytest.raises(RuntimeError):
        await client.create_session()
    for key in SECRET_VARS:
        assert key not in captured["env"], f"{key} was passed to `agent create-chat`"


@pytest.mark.parametrize("var", sorted(SECRET_VARS))
def test_each_secret_individually(var: str):
    env = sanitize_env({**SAFE_VARS, var: SECRET_VARS[var]}, workspace=Path("/tmp/ws"))
    assert var not in env

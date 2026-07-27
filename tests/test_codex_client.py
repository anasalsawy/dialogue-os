import json
from pathlib import Path

from dialogue_os.codex.client import CodexClient, _extract_text, _thread_id, sanitize_env


def test_new_session_args_use_sandbox_and_json(tmp_path: Path, monkeypatch):
    client = CodexClient(tmp_path, cli_bin="codex")
    monkeypatch.setattr(client, "resolve_bin", lambda: "/usr/bin/codex")
    args = client._build_args("do it", "new:123")
    assert args == [
        "/usr/bin/codex", "exec", "--json", "--color", "never",
        "--sandbox", "workspace-write", "--cd", str(tmp_path.resolve()), "do it",
    ]


def test_resume_args_preserve_thread(tmp_path: Path, monkeypatch):
    client = CodexClient(tmp_path, model="gpt-test")
    monkeypatch.setattr(client, "resolve_bin", lambda: "/usr/bin/codex")
    args = client._build_args("continue", "thread-123")
    assert args[-3:] == ["resume", "thread-123", "continue"]
    assert args[args.index("--model") + 1] == "gpt-test"


def test_read_only_mode(tmp_path: Path, monkeypatch):
    client = CodexClient(tmp_path)
    monkeypatch.setattr(client, "resolve_bin", lambda: "/usr/bin/codex")
    args = client._build_args("inspect", None, mode="ask")
    assert args[args.index("--sandbox") + 1] == "read-only"


def test_codex_json_events():
    events = [
        {"type": "thread.started", "thread_id": "019abc"},
        {
            "type": "item.completed",
            "item": {"id": "item_0", "type": "agent_message", "text": "done"},
        },
    ]
    assert _thread_id(events) == "019abc"
    assert _extract_text(events[1]) == "done"


def test_environment_does_not_leak_bridge_secrets(tmp_path: Path):
    env = sanitize_env(
        {
            "PATH": "/bin",
            "HOME": "/srv/yta",
            "TELEGRAM_CHIEF_BOT_TOKEN": "telegram-secret",
            "HERMES_API_KEY": "hermes-secret",
            "OPENAI_API_KEY": "platform-secret",
            "CODEX_HOME": "/srv/yta/.codex",
        },
        workspace=tmp_path,
    )
    assert env["PATH"] == "/bin"
    assert env["CODEX_HOME"] == "/srv/yta/.codex"
    assert env["DIALOGUE_OS_ROOT"] == str(tmp_path)
    assert not any("secret" in value for value in env.values())

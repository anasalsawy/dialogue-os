"""Tests for Cursor CLI argument construction (no live invoke required)."""

from __future__ import annotations

from pathlib import Path

import pytest

from dialogue_os.cursor.client import (
    STREAM_LIMIT,
    CursorClient,
    _readlines,
    ensure_cli_unrestricted,
    parse_force_flag_from_help,
)


def _client(tmp_path: Path, monkeypatch, **kwargs) -> CursorClient:
    kwargs.setdefault("force_flag", "--force")
    kwargs.setdefault("ensure_unrestricted_config", False)
    client = CursorClient(tmp_path, cli_bin="agent", **kwargs)
    monkeypatch.setattr(client, "resolve_bin", lambda: "/usr/bin/agent")
    return client


def test_build_args_unrestricted_agent(tmp_path: Path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    args = client._build_args("hello", session_id="abc-123")
    assert "--print" in args
    assert "--output-format" in args
    assert "stream-json" in args
    assert "--workspace" in args
    assert str(tmp_path.resolve()) in args
    assert "--resume" in args
    assert "abc-123" in args
    assert "--trust" in args
    assert "--force" in args
    assert "--yolo" not in args
    assert "--sandbox" not in args
    assert "--mode" not in args
    assert args[-1] == "hello"
    assert isinstance(args, list)


def test_exactly_one_force_flag(tmp_path: Path, monkeypatch):
    for flag in ("--force", "--yolo"):
        client = _client(tmp_path, monkeypatch, force_flag=flag)
        args = client._build_args("hello", session_id=None)
        present = [f for f in ("--force", "--yolo") if f in args]
        assert present == [flag]


def test_operational_invocation_uses_default_agent_mode(tmp_path: Path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    args = client._build_args("hello", session_id=None)
    assert "--mode" not in args
    assert "ask" not in args
    assert "plan" not in args


@pytest.mark.parametrize("mode", ["ask", "plan"])
def test_read_only_modes_rejected_for_operational_clients(tmp_path: Path, monkeypatch, mode: str):
    client = _client(tmp_path, monkeypatch)
    with pytest.raises(ValueError, match="disabled for operational sessions"):
        client._build_args("hello", session_id=None, mode=mode)


@pytest.mark.parametrize("mode", ["ask", "plan"])
def test_read_only_modes_allowed_only_when_opted_in(tmp_path: Path, monkeypatch, mode: str):
    client = _client(tmp_path, monkeypatch, allow_read_only_modes=True)
    args = client._build_args("hello", session_id=None, mode=mode)
    assert args[args.index("--mode") + 1] == mode


def test_parse_force_flag_prefers_force_when_both_present():
    help_text = "  -f, --force  Force allow\n  --yolo  Alias for --force\n"
    assert parse_force_flag_from_help(help_text) == "--force"


def test_parse_force_flag_uses_yolo_when_only_yolo():
    assert parse_force_flag_from_help("  --yolo  unrestricted\n") == "--yolo"


def test_parse_force_flag_defaults_to_force_when_help_empty():
    assert parse_force_flag_from_help("") == "--force"


def test_workspace_is_fixed_and_absolute(tmp_path: Path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    args = client._build_args("hello", session_id="s1")
    workspace = args[args.index("--workspace") + 1]
    assert workspace == str(tmp_path.resolve())
    assert Path(workspace).is_absolute()


def test_session_resume_preserved(tmp_path: Path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    args = client._build_args("hello", session_id="sess-abc-123")
    assert args[args.index("--resume") + 1] == "sess-abc-123"


def test_env_strips_azure(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.openai.azure.com")
    client = CursorClient(tmp_path, ensure_unrestricted_config=False, force_flag="--force")
    env = client._env()
    assert "AZURE_OPENAI_ENDPOINT" not in env


def test_ensure_cli_unrestricted(tmp_path: Path):
    home = tmp_path / "home"
    (home / ".cursor").mkdir(parents=True)
    cfg = home / ".cursor" / "cli-config.json"
    cfg.write_text('{"approvalMode":"allowlist","permissions":{"allow":["Shell(ls)"],"deny":["Shell(rm)"]}}')
    path = ensure_cli_unrestricted(home)
    data = __import__("json").loads(path.read_text())
    assert data["approvalMode"] == "unrestricted"
    assert data["sandbox"]["mode"] == "disabled"
    assert data["permissions"]["deny"] == []
    assert "Shell(*)" in data["permissions"]["allow"]


@pytest.mark.asyncio
async def test_readlines_survives_oversize_stream_json_line():
    """Regression: huge Cursor stream-json lines must not become Cursor errors."""
    import asyncio

    # Keep the StreamReader's own limit tiny so readline() would fail.
    reader = asyncio.StreamReader(limit=64 * 1024)
    huge = b'{"type":"assistant","text":"' + (b"x" * 200_000) + b'"}\n{"type":"result"}\n'
    reader.feed_data(huge)
    reader.feed_eof()

    with pytest.raises(ValueError, match="chunk is longer than limit"):
        await reader.readline()

    reader = asyncio.StreamReader(limit=64 * 1024)
    reader.feed_data(huge)
    reader.feed_eof()
    lines = [line async for line in _readlines(reader)]
    assert len(lines) == 2
    assert len(lines[0]) > 64 * 1024
    assert STREAM_LIMIT >= 1024 * 1024

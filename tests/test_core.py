"""Unit tests for Dialogue-OS core (no live Telegram/Cursor required)."""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from dialogue_os.bridge import BridgeService
from dialogue_os.channel.canonical import CanonicalChannel
from dialogue_os.cursor.client import CursorClient
from dialogue_os.cursor.control import parse_control_decision
from dialogue_os.db.store import Store
from dialogue_os.maf.orchestration import Orchestrator
from dialogue_os.telegram.api import (
    TELEGRAM_LIMIT,
    TelegramBot,
    TelegramError,
    split_telegram_message,
)
from dialogue_os.util.redact import redact_text
from dialogue_os.watchers.service import WatcherService


@pytest.fixture
async def store(tmp_path: Path):
    s = Store(tmp_path / "test.sqlite3")
    await s.connect()
    yield s
    await s.close()


def test_redact_telegram_token():
    token = "1234567890:AAHxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
    assert "[REDACTED" in redact_text(f"bot {token} failed")
    assert token not in redact_text(f"bot {token} failed")


def _assert_valid_chunks(text: str, chunks: list[str]) -> None:
    assert all(len(c) <= TELEGRAM_LIMIT for c in chunks)
    assert all(len(c) <= 3500 for c in chunks)
    assert "".join(chunks) == text
    assert chunks  # always at least one chunk


def test_split_telegram_message():
    text = "a" * 5000
    chunks = split_telegram_message(text)
    _assert_valid_chunks(text, chunks)


def test_split_oversized_paragraph():
    """A paragraph longer than 3500 (no internal blank line) must still chunk safely."""
    # Prefer spaces inside the paragraph; then a real paragraph break.
    para = ("word " * 900).strip()  # ~4500 chars, single paragraph
    assert "\n" not in para
    assert len(para) > TELEGRAM_LIMIT
    text = para + "\n\n" + "tail paragraph"
    chunks = split_telegram_message(text)
    _assert_valid_chunks(text, chunks)
    assert len(chunks) >= 2
    # First cut should be on a space boundary (not mid-word).
    assert chunks[0].endswith(" ")


def test_split_long_code_block():
    """Long fenced code with only newlines must stay within 3500 and reassemble."""
    body = "\n".join(f"line_{i:04d}_" + ("x" * 80) for i in range(80))
    text = f"```python\n{body}\n```"
    assert len(text) > TELEGRAM_LIMIT
    chunks = split_telegram_message(text)
    _assert_valid_chunks(text, chunks)
    assert len(chunks) >= 2


def test_split_text_without_separators():
    """No paragraph/newline/space separators → hard-split at 3500; never raise."""
    text = "Z" * 10_000
    chunks = split_telegram_message(text)
    _assert_valid_chunks(text, chunks)
    assert chunks == ["Z" * 3500, "Z" * 3500, "Z" * 3000]


@pytest.mark.asyncio
async def test_send_message_retries_plain_text_on_format_failure():
    bot = TelegramBot("000:fake", "chief")
    bot._client = MagicMock()
    calls: list[dict] = []

    async def fake_call(method: str, **params):
        calls.append(params)
        if params.get("parse_mode"):
            raise TelegramError("can't parse entities", error_code=400, description="can't parse entities")
        return {"message_id": 1, "text": params["text"]}

    bot._call = fake_call  # type: ignore[method-assign]
    results = await bot.send_message(1, "hello_world", parse_mode="Markdown")
    assert len(results) == 1
    assert len(calls) == 2
    assert calls[0].get("parse_mode") == "Markdown"
    assert "parse_mode" not in calls[1]


@pytest.mark.asyncio
async def test_cursor_cancel_does_not_wait_for_run_lock():
    """cursor_client.cancel() must not acquire the session run lock."""
    client = CursorClient(
        workspace=Path("/tmp"),
        cli_bin="false",
        force_flag="--force",
        ensure_unrestricted_config=False,
    )
    await client._lock.acquire()
    try:
        t0 = time.monotonic()
        result = await asyncio.wait_for(client.cancel(), timeout=1.0)
        assert time.monotonic() - t0 < 0.5
        assert result is False  # no active process
        assert client._cancel_requested is True
    finally:
        client._lock.release()


@pytest.mark.asyncio
async def test_on_cancel_update_immediate(store: Store):
    """/cancel marks the update processed, cancels Cursor now, and confirms."""
    bridge = object.__new__(BridgeService)
    bridge.store = store
    bridge._outbound_message_ids = set()

    cancel_order: list[str] = []
    sent: list[tuple] = []

    async def fake_send(bot, chat_id, text, reply_to=None):
        cancel_order.append("send")
        sent.append((chat_id, text, reply_to))

    # Hold the Cursor run lock: cancel path must NOT wait on it.
    client = CursorClient(
        workspace=Path("/tmp"),
        cli_bin="false",
        force_flag="--force",
        ensure_unrestricted_config=False,
    )
    await client._lock.acquire()

    async def cancel_without_waiting_for_queue() -> bool:
        assert client._lock.locked()
        cancel_order.append("cancel")
        return True

    bridge.cursor_client = MagicMock()
    bridge.cursor_client.cancel = AsyncMock(side_effect=cancel_without_waiting_for_queue)
    bridge._send = fake_send  # type: ignore[method-assign]

    bot = MagicMock()
    bot.agent_id = "chief"
    update = {
        "update_id": 99,
        "message": {
            "message_id": 7,
            "chat": {"id": 42},
            "text": "/cancel",
        },
    }

    try:
        t0 = time.monotonic()
        await asyncio.wait_for(bridge.on_cancel_update(bot, update), timeout=1.0)
        elapsed = time.monotonic() - t0
    finally:
        client._lock.release()

    assert elapsed < 0.5
    assert await store.is_update_processed("chief", 99)
    assert cancel_order == ["cancel", "send"]
    assert sent == [(42, "Cancelled active Cursor invocation.", 7)]


def test_parse_control_decision_json():
    d = parse_control_decision(
        '{"action":"dispatch_hermes","response_bot":"builder","hermes_profile":"builder-lead","text":"","hermes_prompt":"hi"}',
        default_bot="chief",
    )
    assert d.action == "dispatch_hermes"
    assert d.hermes_profile == "builder-lead"
    assert d.response_bot == "builder"


def test_parse_control_decision_plaintext_fallback():
    d = parse_control_decision("Hello operator", default_bot="chief")
    assert d.action == "respond"
    assert d.text == "Hello operator"


@pytest.mark.asyncio
async def test_processed_updates_idempotent(store: Store):
    assert not await store.is_update_processed("chief", 1)
    await store.mark_update_processed("chief", 1, "evt1")
    assert await store.is_update_processed("chief", 1)
    await store.mark_update_processed("chief", 1, "evt1")  # ignore duplicate


@pytest.mark.asyncio
async def test_cursor_session_persistence(store: Store):
    await store.set_cursor_session("primary", "sess-abc")
    assert await store.get_cursor_session("primary") == "sess-abc"
    await store.set_cursor_session("primary", "sess-xyz")
    assert await store.get_cursor_session("primary") == "sess-xyz"
    sessions = await store.list_cursor_sessions()
    assert sessions[0]["session_id"] == "sess-xyz"


@pytest.mark.asyncio
async def test_canonical_channel_persists(store: Store, tmp_path: Path):
    log_path = tmp_path / "events.jsonl"
    ch = CanonicalChannel(store, log_path, channel_id=None)
    event = await ch.broadcast(
        agent_id="chief",
        event_type="plan",
        summary="Ship bridge",
        publish_telegram=False,
    )
    recent = await ch.shared_memory(limit=10)
    assert recent[0]["event_id"] == event["event_id"]
    assert log_path.exists()
    line = log_path.read_text().strip().splitlines()[-1]
    assert json.loads(line)["summary"] == "Ship bridge"


@pytest.mark.asyncio
async def test_watcher_default_silence(store: Store, tmp_path: Path):
    ch = CanonicalChannel(store, tmp_path / "e.jsonl", None)
    w = WatcherService(store, ch)
    assert not await w.should_reply("watcher_beta", 42)
    msg = await w.handle_override_command(
        "watcher_beta", 42, "Watcher Beta, override silence. Resume responding to my messages."
    )
    assert msg and "override enabled" in msg
    assert await w.should_reply("watcher_beta", 42)


@pytest.mark.asyncio
async def test_unaddressed_selection_prefers_silence(store: Store):
    orch = Orchestrator(store)
    r = orch.select_for_unaddressed("hello there", [])
    assert r.selected_agent is None
    r2 = orch.select_for_unaddressed("please research and investigate the vendor sources", [])
    assert r2.selected_agent == "researcher"


@pytest.mark.asyncio
async def test_handoff_durable(store: Store):
    orch = Orchestrator(store)
    h = await orch.create_handoff(
        from_agent="chief", to_agent="builder", summary="Implement bridge"
    )
    row = await store.fetchone("SELECT * FROM handoffs WHERE handoff_id=?", (h["handoff_id"],))
    assert row["to_agent"] == "builder"


@pytest.mark.asyncio
async def test_migrations_do_not_destroy(store: Store, tmp_path: Path):
    await store.set_cursor_session("primary", "keep-me")
    # Re-run migrate
    await store.migrate()
    assert await store.get_cursor_session("primary") == "keep-me"


def test_azure_llm_disabled_by_default(monkeypatch, tmp_path: Path):
    monkeypatch.delenv("AZURE_OPENAI_ENDPOINT", raising=False)
    monkeypatch.setenv("DIALOGUE_OS_ROOT", str(tmp_path))
    from dialogue_os.config import Settings

    s = Settings(_env_file=None, DIALOGUE_OS_ROOT=tmp_path)
    assert s.azure_llm_disabled is True
    s.assert_no_azure_llm()

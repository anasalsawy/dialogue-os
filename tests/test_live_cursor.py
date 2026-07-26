"""Integration smoke helpers — skip when credentials missing."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from dialogue_os.cursor.client import CursorClient


@pytest.mark.asyncio
async def test_live_cursor_ask_mode():
    """Read-only smoke check. Explicitly opts into ask mode, which operational
    sessions are forbidden from using."""
    if os.environ.get("DIALOGUE_OS_LIVE_CURSOR") != "1":
        pytest.skip("Set DIALOGUE_OS_LIVE_CURSOR=1 to run live Cursor smoke")
    root = Path(os.environ.get("DIALOGUE_OS_ROOT", "/home/azureuser/dialogue-os"))
    client = CursorClient(root, timeout_seconds=120, allow_read_only_modes=True)
    sid = await client.create_session()
    r1 = await client.run("Reply with exactly: LIVE_OK", session_id=sid, mode="ask")
    assert r1.ok, r1.error
    assert "LIVE_OK" in r1.text
    r2 = await client.run("Repeat the exact token from your previous reply only.", session_id=sid, mode="ask")
    assert r2.ok, r2.error
    assert "LIVE_OK" in r2.text


@pytest.mark.asyncio
async def test_live_cursor_agent_mode_writes_in_workspace(tmp_path):
    """Operational path: default Agent mode, sandboxed, no --force."""
    if os.environ.get("DIALOGUE_OS_LIVE_CURSOR") != "1":
        pytest.skip("Set DIALOGUE_OS_LIVE_CURSOR=1 to run live Cursor smoke")
    root = Path(os.environ.get("DIALOGUE_OS_ROOT", "/home/azureuser/dialogue-os"))
    marker = root / "data" / "live_agent_probe.txt"
    marker.unlink(missing_ok=True)
    client = CursorClient(root, timeout_seconds=180)
    sid = await client.create_session()
    result = await client.run(
        f"Create the file {marker} containing exactly AGENT_WRITE_OK and nothing else.",
        session_id=sid,
    )
    assert result.ok, result.error
    assert marker.exists(), "Agent mode could not write inside the workspace"
    assert marker.read_text().strip() == "AGENT_WRITE_OK"
    marker.unlink(missing_ok=True)

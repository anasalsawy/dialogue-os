from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from dialogue_os.db.store import Store
from dialogue_os.featherless.chief import FeatherlessChiefClient


@pytest.fixture
async def store(tmp_path: Path):
    value = Store(tmp_path / "chief.sqlite3")
    await value.connect()
    yield value
    await value.close()


async def test_featherless_chief_preserves_control_session(store: Store):
    client = FeatherlessChiefClient(
        store=store,
        api_key="test-key",
        model="test/model",
    )
    client.client.chat = AsyncMock(
        return_value={
            "ok": True,
            "text": '{"action":"respond","response_bot":"chief","text":"ready"}',
            "error": None,
        }
    )

    session_id = await client.create_session()
    result = await client.run("route this", session_id=session_id)

    assert result.ok
    assert result.session_id == session_id
    assert result.text.endswith('"}')
    assert result.raw_events[0]["model"] == "test/model"
    assert client.client.chat.await_args.kwargs["profile"].endswith(session_id)


async def test_featherless_chief_forwards_completed_text(store: Store):
    client = FeatherlessChiefClient(
        store=store,
        api_key="test-key",
        model="test/model",
    )
    client.client.chat = AsyncMock(
        return_value={"ok": True, "text": "finished", "error": None}
    )
    partials: list[str] = []

    result = await client.run("work", on_partial=partials.append)

    assert result.ok
    assert partials == ["finished"]


async def test_featherless_chief_falls_back_on_primary_error(store: Store):
    client = FeatherlessChiefClient(
        store=store,
        api_key="test-key",
        model="darkc0de/Agent.Xortron",
        fallback_model="deepseek-ai/DeepSeek-V3.1-Terminus",
    )
    client.client.chat = AsyncMock(
        return_value={"ok": False, "text": "", "error": "primary unavailable"}
    )
    assert client.fallback_client is not None
    client.fallback_client.chat = AsyncMock(
        return_value={"ok": True, "text": "fallback ready", "error": None}
    )

    result = await client.run("work", session_id="session-1")

    assert result.ok
    assert result.text == "fallback ready"
    assert result.session_id == "session-1"
    assert result.raw_events == [
        {
            "type": "provider_result",
            "model": "deepseek-ai/DeepSeek-V3.1-Terminus",
            "fallback": True,
        }
    ]


async def test_featherless_chief_walks_ordered_fallback_chain(store: Store):
    client = FeatherlessChiefClient(
        store=store,
        api_key="test-key",
        model="darkc0de/Agent.Xortron",
        fallback_models=(
            "deepseek-ai/DeepSeek-V3.1-Terminus",
            "zai-org/GLM-4.6",
            "unsloth/Qwen3-235B-A22B-Instruct-2507",
        ),
    )
    client.client.chat = AsyncMock(
        return_value={"ok": False, "text": "", "error": "primary unavailable"}
    )
    client.fallback_clients[0].chat = AsyncMock(
        return_value={"ok": False, "text": "", "error": "deepseek unavailable"}
    )
    client.fallback_clients[1].chat = AsyncMock(
        return_value={"ok": True, "text": "glm ready", "error": None}
    )
    client.fallback_clients[2].chat = AsyncMock()

    result = await client.run("work", session_id="session-2")

    assert result.ok
    assert result.text == "glm ready"
    assert result.raw_events[0]["model"] == "zai-org/GLM-4.6"
    assert result.raw_events[0]["fallback"] is True
    client.fallback_clients[2].chat.assert_not_awaited()


def test_featherless_chief_requires_credentials(store):
    with pytest.raises(ValueError, match="API_KEY"):
        FeatherlessChiefClient(store=store, api_key="", model="test/model")
    with pytest.raises(ValueError, match="MODEL"):
        FeatherlessChiefClient(store=store, api_key="test-key", model="")

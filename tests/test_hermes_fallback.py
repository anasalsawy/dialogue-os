from pathlib import Path

import httpx
import pytest

from dialogue_os.db.store import Store
from dialogue_os.hermes.client import HermesClient


@pytest.fixture
async def store(tmp_path: Path):
    value = Store(tmp_path / "hermes.sqlite3")
    await value.connect()
    yield value
    await value.close()


async def test_hermes_uses_only_ordered_configured_fallbacks(store: Store, monkeypatch):
    attempted: list[str] = []
    for key in (
        "ALL_PROXY",
        "all_proxy",
        "HTTP_PROXY",
        "http_proxy",
        "HTTPS_PROXY",
        "https_proxy",
    ):
        monkeypatch.delenv(key, raising=False)

    async def fake_post(self, url, *, headers, json):
        attempted.append(json["model"])
        request = httpx.Request("POST", url)
        if json["model"] != "ArliAI/Qwen3.5-27B-Derestricted":
            raise httpx.ConnectError("unavailable", request=request)
        return httpx.Response(
            200,
            request=request,
            json={
                "choices": [{"message": {"content": "ready"}}],
                "usage": {"total_tokens": 10},
            },
        )

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    client = HermesClient(
        base_url="https://api.featherless.ai/v1",
        api_key="test-key",
        model="darkc0de/Agent.Xortron",
        fallback_models=(
            "darkc0de/XORTRON",
            "ArliAI/Qwen3.5-27B-Derestricted",
        ),
        store=store,
    )

    result = await client.chat("builder-lead", 42, "work")

    assert result["ok"]
    assert result["model"] == "ArliAI/Qwen3.5-27B-Derestricted"
    assert result["fallback"] is True
    assert attempted == [
        "darkc0de/Agent.Xortron",
        "darkc0de/XORTRON",
        "ArliAI/Qwen3.5-27B-Derestricted",
    ]

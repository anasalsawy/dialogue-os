from pathlib import Path

import httpx
import pytest

from dialogue_os.db.store import Store
from dialogue_os.hermes.agent_client import HermesAgentClient


@pytest.fixture
async def store(tmp_path: Path):
    value = Store(tmp_path / "hermes-agent.sqlite3")
    await value.connect()
    yield value
    await value.close()


def clear_proxy_env(monkeypatch):
    for key in (
        "ALL_PROXY",
        "all_proxy",
        "HTTP_PROXY",
        "http_proxy",
        "HTTPS_PROXY",
        "https_proxy",
    ):
        monkeypatch.delenv(key, raising=False)


async def test_real_agent_request_uses_profile_runtime_and_shared_session(
    store: Store, monkeypatch
):
    clear_proxy_env(monkeypatch)
    seen = {}

    async def fake_post(self, url, *, headers, json):
        seen.update(url=url, headers=headers, json=json)
        request = httpx.Request("POST", url)
        return httpx.Response(
            200,
            request=request,
            json={
                "id": "resp_123",
                "status": "completed",
                "model": "builder-lead",
                "output": [
                    {
                        "type": "function_call",
                        "name": "terminal",
                        "arguments": '{"command":"pwd"}',
                        "call_id": "call_1",
                    },
                    {
                        "type": "function_call_output",
                        "call_id": "call_1",
                        "output": "/workspace",
                    },
                    {
                        "type": "message",
                        "role": "assistant",
                        "content": [{"type": "output_text", "text": "Done"}],
                    },
                ],
            },
        )

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    client = HermesAgentClient(
        base_url="http://127.0.0.1:8642",
        api_key="runtime-secret",
        store=store,
        session_scope="profile",
    )

    result = await client.chat("builder-lead", -100123, "Inspect the repo")

    assert seen["url"] == (
        "http://127.0.0.1:8642/p/builder-lead/v1/responses"
    )
    assert seen["headers"]["X-Hermes-Session-Key"] == (
        "dialogue-os-v3:builder-lead:shared"
    )
    assert seen["json"]["conversation"] == "dialogue-os-v3:builder-lead:shared"
    assert result["backend"] == "hermes-agent"
    assert result["text"] == "Done"
    assert [event["type"] for event in result["tool_events"]] == [
        "function_call",
        "function_call_output",
    ]


async def test_isolated_request_overrides_header_and_does_not_persist_session(
    store: Store, monkeypatch
):
    clear_proxy_env(monkeypatch)
    seen = {}

    async def fake_post(self, url, *, headers, json):
        seen.update(headers=headers, json=json)
        return httpx.Response(
            200,
            request=httpx.Request("POST", url),
            json={
                "id": "audit-response",
                "status": "completed",
                "output": [
                    {
                        "type": "message",
                        "content": [{"type": "output_text", "text": "{}"}],
                    }
                ],
            },
        )

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    client = HermesAgentClient(
        base_url="http://127.0.0.1:8642",
        api_key="runtime-secret",
        store=store,
        session_scope="profile",
    )

    result = await client.chat(
        "watcher-alpha",
        0,
        "audit",
        conversation_key="dialogue-os-audit:a1:watcher_alpha",
        store_conversation=False,
    )

    assert result["ok"]
    assert seen["headers"]["X-Hermes-Session-Key"] == (
        "dialogue-os-audit:a1:watcher_alpha"
    )
    assert seen["json"]["conversation"] == "dialogue-os-audit:a1:watcher_alpha"
    assert seen["json"]["store"] is False
    assert await store.get_chat_session("watcher-alpha", 0) is None


async def test_readiness_rejects_profile_without_tools(store: Store, monkeypatch):
    clear_proxy_env(monkeypatch)

    async def fake_get(self, url, *, headers):
        request = httpx.Request("GET", url)
        if url.endswith("/v1/capabilities"):
            return httpx.Response(
                200,
                request=request,
                json={"platform": "hermes-agent", "features": {}},
            )
        return httpx.Response(200, request=request, json=[])

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    client = HermesAgentClient(
        base_url="http://127.0.0.1:8642",
        api_key="runtime-secret",
        store=store,
    )

    with pytest.raises(RuntimeError, match="no enabled tools"):
        await client.assert_ready(("builder-lead",))


async def test_readiness_accepts_wrapped_toolsets_response(store: Store, monkeypatch):
    clear_proxy_env(monkeypatch)

    async def fake_get(self, url, *, headers):
        request = httpx.Request("GET", url)
        if url.endswith("/v1/capabilities"):
            return httpx.Response(
                200,
                request=request,
                json={
                    "platform": "hermes-agent",
                    "features": {"memory": True},
                },
            )
        return httpx.Response(
            200,
            request=request,
            json={
                "toolsets": [
                    {
                        "name": "file_operations",
                        "enabled": True,
                        "configured": True,
                        "tools": ["read_file", "write_file"],
                    }
                ]
            },
        )

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    client = HermesAgentClient(
        base_url="http://127.0.0.1:8642",
        api_key="runtime-secret",
        store=store,
    )

    result = await client.assert_ready(("builder-lead",))

    assert result["builder-lead"]["capabilities"] == {"memory": True}
    assert result["builder-lead"]["tools"] == ["read_file", "write_file"]


async def test_readiness_accepts_hermes_data_envelope(store: Store, monkeypatch):
    clear_proxy_env(monkeypatch)

    async def fake_get(self, url, *, headers):
        request = httpx.Request("GET", url)
        if url.endswith("/v1/capabilities"):
            return httpx.Response(
                200,
                request=request,
                json={"platform": "hermes-agent", "features": {}},
            )
        return httpx.Response(
            200,
            request=request,
            json={
                "object": "list",
                "platform": "hermes-agent",
                "data": [
                    {
                        "name": "terminal",
                        "enabled": True,
                        "configured": True,
                        "tools": ["terminal"],
                    }
                ],
            },
        )

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    client = HermesAgentClient(
        base_url="http://127.0.0.1:8642",
        api_key="runtime-secret",
        store=store,
    )

    result = await client.assert_ready(("builder-lead",))

    assert result["builder-lead"]["tools"] == ["terminal"]


def test_independent_profile_url_takes_precedence(store: Store):
    client = HermesAgentClient(
        base_url="http://127.0.0.1:8642",
        api_key="runtime-secret",
        store=store,
        profile_urls={"builder-lead": "http://127.0.0.1:8643/"},
    )

    assert client._profile_base("builder-lead") == "http://127.0.0.1:8643"
    assert (
        client._profile_base("research-lead")
        == "http://127.0.0.1:8642/p/research-lead"
    )


async def test_rotation_sends_real_model_and_provider_in_request_body(
    store: Store, monkeypatch
):
    clear_proxy_env(monkeypatch)
    payloads = []

    class Router:
        failures = []
        selected = None

        async def candidates(self, profile):
            return ["broken/model", "working/model"]

        @staticmethod
        def should_rotate(*, status=None, text=""):
            return "api call failed" in text.lower()

        def failure(self, model, error):
            self.failures.append(model)

        def success(self, profile, model):
            self.selected = model

    async def fake_post(self, url, *, headers, json):
        payloads.append(dict(json))
        request = httpx.Request("POST", url)
        text = "API call failed" if len(payloads) == 1 else "Done"
        return httpx.Response(
            200,
            request=request,
            json={
                "id": f"resp_{len(payloads)}",
                "status": "completed",
                "output": [
                    {
                        "type": "message",
                        "role": "assistant",
                        "content": [{"type": "output_text", "text": text}],
                    }
                ],
            },
        )

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    router = Router()
    client = HermesAgentClient(
        base_url="http://127.0.0.1:8642",
        api_key="runtime-secret",
        store=store,
        profile_urls={"builder-lead": "http://127.0.0.1:8643"},
        model_router=router,
    )

    result = await client.chat("builder-lead", 1, "work")

    assert [item["model"] for item in payloads] == [
        "broken/model",
        "working/model",
    ]
    assert [item["provider"] for item in payloads] == ["custom", "custom"]
    assert router.failures == ["broken/model"]
    assert router.selected == "working/model"
    assert result["text"] == "Done"

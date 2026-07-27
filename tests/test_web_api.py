from types import SimpleNamespace

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from dialogue_os.web_api import install_war_room_api


class StubStore:
    async def list_agents(self):
        return [{"agent_id": "chief", "backend": "cursor_cli", "meta": {}}]

    async def recent_canonical_events(self, limit):
        return [{"event_id": "e1", "event_type": "verified"}][:limit]


class StubSessions:
    async def get_primary(self):
        return "cursor-session"


class StubBridge:
    def __init__(self):
        self.settings = SimpleNamespace(
            war_room_api_token="secret",
            war_room_allowed_origins=("https://war-room.example",),
        )
        self.store = StubStore()
        self.sessions = StubSessions()
        self.bots = {}
        self.hermes = object()

    async def status_dict(self):
        return {"ok": True}


@pytest.fixture
async def client():
    app = web.Application()
    install_war_room_api(app, StubBridge())
    async with TestClient(TestServer(app)) as value:
        yield value


async def test_requires_bearer_token(client):
    response = await client.get("/api/v1/status")
    assert response.status == 401


async def test_status_is_runtime_truth(client):
    response = await client.get(
        "/api/v1/status",
        headers={
            "Authorization": "Bearer secret",
            "Origin": "https://war-room.example",
        },
    )
    assert response.status == 200
    assert await response.json() == {"ok": True, "source": "dialogue_os_runtime"}
    assert response.headers["Access-Control-Allow-Origin"] == "https://war-room.example"


async def test_rejects_unapproved_cors_preflight(client):
    response = await client.options(
        "/api/v1/status", headers={"Origin": "https://evil.example"}
    )
    assert response.status == 403

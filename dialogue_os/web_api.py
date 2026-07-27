"""Authenticated HTTP control plane for the YTA Operations War Room.

The API exposes persisted runtime truth. It never manufactures heartbeats,
dialogue, missions, evidence, success rates, or provider connectivity.
"""

from __future__ import annotations

import hmac
import json
from dataclasses import asdict
from typing import TYPE_CHECKING, Any

from aiohttp import web

from dialogue_os.offices.assign import CHIEF_ASSIGN_INSTRUCTIONS
from dialogue_os.util.redact import redact_text

if TYPE_CHECKING:
    from dialogue_os.bridge import BridgeService


def _allowed_origin(request: web.Request, configured: tuple[str, ...]) -> str | None:
    origin = request.headers.get("Origin")
    if not origin:
        return None
    return origin if origin in configured else None


@web.middleware
async def war_room_security(request: web.Request, handler):
    bridge: BridgeService = request.app["bridge"]
    settings = bridge.settings
    allowed = tuple(settings.war_room_allowed_origins)

    if request.method == "OPTIONS":
        origin = _allowed_origin(request, allowed)
        if not origin:
            raise web.HTTPForbidden(text="Origin not allowed")
        response = web.Response(status=204)
    else:
        token = settings.war_room_api_token
        supplied = request.headers.get("Authorization", "")
        if not token or not supplied.startswith("Bearer "):
            raise web.HTTPUnauthorized(text="Missing bearer token")
        if not hmac.compare_digest(supplied[7:], token):
            raise web.HTTPUnauthorized(text="Invalid bearer token")
        response = await handler(request)

    origin = _allowed_origin(request, allowed)
    if origin:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Vary"] = "Origin"
        response.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


def install_war_room_api(app: web.Application, bridge: "BridgeService") -> None:
    """Install authenticated `/api/v1` routes on the existing health app."""
    app["bridge"] = bridge
    app.middlewares.append(war_room_security)
    app.router.add_get("/api/v1/status", _status)
    app.router.add_get("/api/v1/agents", _agents)
    app.router.add_get("/api/v1/missions", _missions)
    app.router.add_get("/api/v1/missions/{mission_id}", _mission)
    app.router.add_get("/api/v1/missions/{mission_id}/events", _mission_events)
    app.router.add_get("/api/v1/events", _canonical_events)
    app.router.add_post("/api/v1/commands", _command)


async def _status(request: web.Request) -> web.Response:
    bridge: BridgeService = request.app["bridge"]
    payload = await bridge.status_dict()
    payload["source"] = "dialogue_os_runtime"
    return web.json_response(payload)


async def _agents(request: web.Request) -> web.Response:
    bridge: BridgeService = request.app["bridge"]
    agents = await bridge.store.list_agents()
    bot_status = {
        agent_id: {"connected": True, "username": bot.username, "bot_id": bot.bot_id}
        for agent_id, bot in bridge.bots.items()
    }
    for agent in agents:
        agent["transport"] = bot_status.get(agent["agent_id"], {"connected": False})
        if agent["agent_id"] == "chief":
            agent["runtime_connected"] = bool(await bridge.sessions.get_primary())
        else:
            agent["runtime_connected"] = bridge.hermes is not None
    return web.json_response({"agents": agents})


async def _missions(request: web.Request) -> web.Response:
    bridge: BridgeService = request.app["bridge"]
    include_closed = request.query.get("include_closed", "").lower() in {"1", "true", "yes"}
    limit = min(max(int(request.query.get("limit", "100")), 1), 500)
    if include_closed:
        rows = await bridge.store.fetchall(
            "SELECT * FROM missions ORDER BY updated_at DESC LIMIT ?", (limit,)
        )
        missions = [_mission_row(row) for row in rows]
    else:
        missions = [asdict(mission) for mission in (await bridge.missions.list_open())[:limit]]
    return web.json_response({"missions": missions, "count": len(missions)})


async def _mission(request: web.Request) -> web.Response:
    bridge: BridgeService = request.app["bridge"]
    mission = await bridge.missions.get(request.match_info["mission_id"])
    if mission is None:
        raise web.HTTPNotFound(text="Mission not found")
    state = await bridge.supervision.get(mission.mission_id)
    artifacts = await bridge.supervision.artifacts(mission.mission_id, limit=100)
    logs = await bridge.supervision.recent_logs(mission.mission_id, limit=100)
    return web.json_response(
        {
            "mission": asdict(mission),
            "supervision": asdict(state) if state else None,
            "artifacts": artifacts,
            "logs": logs,
        }
    )


async def _mission_events(request: web.Request) -> web.Response:
    bridge: BridgeService = request.app["bridge"]
    mission_id = request.match_info["mission_id"]
    if await bridge.missions.get(mission_id) is None:
        raise web.HTTPNotFound(text="Mission not found")
    limit = min(max(int(request.query.get("limit", "200")), 1), 1000)
    return web.json_response({"events": await bridge.missions.events(mission_id, limit=limit)})


async def _canonical_events(request: web.Request) -> web.Response:
    bridge: BridgeService = request.app["bridge"]
    limit = min(max(int(request.query.get("limit", "100")), 1), 500)
    return web.json_response({"events": await bridge.store.recent_canonical_events(limit)})


async def _command(request: web.Request) -> web.Response:
    bridge: BridgeService = request.app["bridge"]
    try:
        body = await request.json()
    except json.JSONDecodeError as exc:
        raise web.HTTPBadRequest(text="Body must be JSON") from exc
    text = str(body.get("text") or "").strip()
    if not text:
        raise web.HTTPBadRequest(text="text is required")
    if len(text) > 20_000:
        raise web.HTTPRequestEntityTooLarge(max_size=20_000, actual_size=len(text))

    decision = await bridge.control.chief_direct(
        CHIEF_ASSIGN_INSTRUCTIONS + "\n\nOperator message from War Room:\n" + text
    )
    assignments: list[dict[str, Any]] = []
    if decision.ok:
        assignments = await bridge._apply_chief_assignments(decision)
    visible, _ = bridge._strip_assignments_for_api(decision.text or "")
    await bridge.store.append_canonical_event(
        {
            "event_id": bridge.new_event_id(),
            "agent_id": "chief",
            "event_type": "war_room_command",
            "summary": visible[:2000],
            "evidence": {"assignment_count": len(assignments)},
        }
    )
    return web.json_response(
        {
            "ok": decision.ok,
            "chief": visible,
            "assignments": assignments,
            "cursor_session_id": decision.cursor_session_id,
            "duration_seconds": decision.duration_seconds,
            "error": redact_text(decision.error or "") or None,
        },
        status=200 if decision.ok else 502,
    )


def _mission_row(row: Any) -> dict[str, Any]:
    data = {key: row[key] for key in row.keys()}
    data["verified"] = bool(data.get("verified"))
    data["meta"] = json.loads(data.pop("meta_json") or "{}")
    return data

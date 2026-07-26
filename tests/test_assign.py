"""Chief-driven office assignment: parse, create missions, post, supervise."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from dialogue_os.db.store import Store
from dialogue_os.offices.assign import (
    AssignmentUnit,
    parse_and_strip_assignments,
)
from dialogue_os.offices.missions import MissionTracker
from dialogue_os.offices.registry import OfficeRegistry
from dialogue_os.offices.supervision import SupervisionStore
from dialogue_os.offices.supervisor import MissionSupervisor

OWNER = 42
BUILDER_CHAT = -100111
RESEARCH_CHAT = -100222


# ---------------------------------------------------------------- parsing


def test_parse_assignments_block_and_strip_from_reply():
    text = (
        "I'll split this across Research and Building.\n\n"
        "<<<ASSIGNMENTS>>>\n"
        '[{"department":"researcher","title":"Scan vendors","brief":"List top 3 vendors with evidence."},'
        '{"department":"builder","title":"Wire assign","brief":"Implement Chief assign path."}]\n'
        "<<<END_ASSIGNMENTS>>>"
    )
    visible, units = parse_and_strip_assignments(text)
    assert "ASSIGNMENTS" not in visible
    assert "I'll split this" in visible
    assert [u.department for u in units] == ["researcher", "builder"]
    assert units[0].title == "Scan vendors"
    assert "evidence" in units[0].brief


def test_parse_whole_message_json_assignments():
    text = (
        '{"text":"Plan ready.","assignments":['
        '{"department":"operations","brief":"Check bridge health nightly."}]}'
    )
    visible, units = parse_and_strip_assignments(text)
    assert visible == "Plan ready."
    assert len(units) == 1
    assert units[0].department == "operations"


def test_parse_ignores_unknown_department_and_empty_brief():
    text = (
        "<<<ASSIGNMENTS>>>\n"
        '[{"department":"nope","brief":"x"},{"department":"builder","brief":""},'
        '{"department":"builder","brief":"Ship it"}]\n'
        "<<<END_ASSIGNMENTS>>>"
    )
    _, units = parse_and_strip_assignments(text)
    assert len(units) == 1
    assert units[0].brief == "Ship it"


def test_no_block_means_no_assignments():
    visible, units = parse_and_strip_assignments("Just a status question.")
    assert visible == "Just a status question."
    assert units == []


# ---------------------------------------------------------------- execute


@pytest.fixture
async def store(tmp_path: Path):
    s = Store(tmp_path / "assign.sqlite3")
    await s.connect()
    for agent_id, profile in [
        ("builder", "builder-lead"),
        ("researcher", "research-lead"),
        ("operations", "operations-lead"),
    ]:
        await s.upsert_agent(
            {"agent_id": agent_id, "backend": "hermes", "hermes_profile": profile}
        )
    await s.upsert_agent({"agent_id": "chief", "backend": "cursor_cli"})
    yield s
    await s.close()


@pytest.fixture
async def offices(store: Store) -> OfficeRegistry:
    registry = OfficeRegistry(store, owner_id=OWNER)
    await registry.register(
        "builder",
        chat_id=BUILDER_CHAT,
        chat_type="supergroup",
        requester_id=OWNER,
        chat_title="Building",
    )
    await registry.register(
        "researcher",
        chat_id=RESEARCH_CHAT,
        chat_type="supergroup",
        requester_id=OWNER,
        chat_title="Research",
    )
    return registry


async def test_execute_assignment_creates_missions_posts_and_supervises(
    store: Store, offices: OfficeRegistry, tmp_path: Path
):
    from dialogue_os.bridge import BridgeService

    bridge = object.__new__(BridgeService)
    bridge.store = store
    bridge.offices = offices
    bridge.missions = MissionTracker(store)
    bridge.supervision = SupervisionStore(store)
    bridge.settings = MagicMock(telegram_owner_id=OWNER)
    bridge.canonical = None
    bridge._outbound_message_ids = set()

    posts: list[tuple[int, str]] = []

    async def post(chat_id: int, text: str) -> None:
        posts.append((chat_id, text))

    bridge._post_as_chief = post  # type: ignore[method-assign]
    bridge.sessions = MagicMock()
    bridge.sessions.get_primary = AsyncMock(return_value="sess-chief")

    control = MagicMock()
    control.chief_direct = AsyncMock()
    supervisor = MissionSupervisor(
        missions=bridge.missions,
        supervision=bridge.supervision,
        control=control,
        post_office_message=post,
        ack_timeout=300,
        heartbeat_timeout=600,
        proc_root=tmp_path / "proc",
    )
    (tmp_path / "proc").mkdir()
    bridge.supervisor = supervisor

    units = [
        AssignmentUnit(
            department="researcher",
            title="Vendor scan",
            brief="List top vendors with citations.",
        ),
        AssignmentUnit(
            department="builder",
            title="Wire assign",
            brief="Implement Chief assign path with tests.",
        ),
    ]
    results = await bridge._execute_assignment_units(units, source="test")

    assert all(r["ok"] for r in results)
    assert {r["department"] for r in results} == {"researcher", "builder"}
    assert {c for c, _ in posts} == {RESEARCH_CHAT, BUILDER_CHAT}
    assert all("MISSION ASSIGNED" in text for _, text in posts)

    open_missions = await bridge.missions.list_open()
    assert len(open_missions) == 2
    assert all(m.status == "ASSIGNED" for m in open_missions)

    for mission in open_missions:
        state = await bridge.supervision.get(mission.mission_id)
        assert state is not None
        assert state.next_check_at is not None
        assert state.current_step == "awaiting acknowledgement"


async def test_execute_assignment_reports_missing_office(store: Store, offices: OfficeRegistry):
    from dialogue_os.bridge import BridgeService

    bridge = object.__new__(BridgeService)
    bridge.store = store
    bridge.offices = offices
    bridge.missions = MissionTracker(store)
    bridge.supervision = SupervisionStore(store)
    bridge.settings = MagicMock(telegram_owner_id=OWNER)
    bridge.canonical = None
    bridge.supervisor = None
    bridge.sessions = MagicMock()
    bridge.sessions.get_primary = AsyncMock(return_value=None)
    bridge._post_as_chief = AsyncMock()

    results = await bridge._execute_assignment_units(
        [AssignmentUnit(department="growth", brief="Grow something")]
    )
    assert results == [
        {"ok": False, "department": "growth", "error": "office 'growth' is not registered"}
    ]
    bridge._post_as_chief.assert_not_awaited()


async def test_apply_chief_assignments_strips_block_from_decision_text(
    store: Store, offices: OfficeRegistry
):
    from dialogue_os.bridge import BridgeService
    from dialogue_os.cursor.control import ControlDecision

    bridge = object.__new__(BridgeService)
    bridge.store = store
    bridge.offices = offices
    bridge.missions = MissionTracker(store)
    bridge.supervision = SupervisionStore(store)
    bridge.settings = MagicMock(telegram_owner_id=OWNER)
    bridge.canonical = None
    bridge.supervisor = None
    bridge.sessions = MagicMock()
    bridge.sessions.get_primary = AsyncMock(return_value="sess")
    bridge._post_as_chief = AsyncMock()

    decision = ControlDecision(
        action="respond",
        response_bot="chief",
        text=(
            "Assigning research.\n"
            "<<<ASSIGNMENTS>>>\n"
            '[{"department":"researcher","brief":"Find X"}]\n'
            "<<<END_ASSIGNMENTS>>>"
        ),
    )
    results = await bridge._apply_chief_assignments(decision)
    assert decision.text == "Assigning research."
    assert "ASSIGNMENTS" not in decision.text
    assert results[0]["ok"] is True

"""Governance strengthening tests — offline, fake adapters only."""

from __future__ import annotations

from pathlib import Path

import pytest

from dialogue_os.db.store import Store
from dialogue_os.governance import (
    LeaseError,
    MemoryScopeStore,
    MissionTaskStore,
    PermitGate,
    WorkLeaseManager,
)
from dialogue_os.maf.dag import DagValidationError, validate_task_dag
from dialogue_os.offices import missions as m
from dialogue_os.offices.missions import MissionError, MissionTracker
from dialogue_os.testing import FakeCursorControl, FakeHermesClient, FakeTelegramBot


@pytest.fixture
async def store(tmp_path: Path):
    s = Store(tmp_path / "gov.sqlite3")
    await s.connect()
    await s.upsert_agent(
        {"agent_id": "builder", "backend": "hermes", "hermes_profile": "builder-lead"}
    )
    await s.upsert_agent({"agent_id": "chief", "backend": "cursor_cli"})
    yield s
    await s.close()


@pytest.fixture
async def tracker(store: Store) -> MissionTracker:
    return MissionTracker(store)


async def test_migration_004_tables_exist(store: Store):
    for table in (
        "mission_tasks",
        "work_leases",
        "tool_permits",
        "browser_permits",
        "governance_audit",
        "memory_scopes",
    ):
        row = await store.fetchone(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
        )
        assert row is not None


async def test_acceptance_criteria_required_for_verify(tracker: MissionTracker):
    mission = await tracker.create(
        department="builder",
        office_chat_id=-1001,
        specialist_agent_id="builder",
        assignment_text="do it",
        acceptance_criteria=None,
    )
    mid = mission.mission_id
    await tracker.transition(mid, m.ASSIGNED)
    await tracker.transition(mid, m.ACKNOWLEDGED)
    await tracker.transition(mid, m.WORKING)
    await tracker.claim_completion(mid, specialist_agent_id="builder", claim="done")
    with pytest.raises(MissionError, match="acceptance_criteria"):
        await tracker.verify_completion(
            mid, verified=True, verification="VERDICT: VERIFIED"
        )


async def test_verify_requires_explicit_verdict(tracker: MissionTracker):
    mission = await tracker.create(
        department="builder",
        office_chat_id=-1002,
        specialist_agent_id="builder",
        acceptance_criteria="tests green",
    )
    mid = mission.mission_id
    await tracker.transition(mid, m.ASSIGNED)
    await tracker.transition(mid, m.ACKNOWLEDGED)
    await tracker.transition(mid, m.WORKING)
    await tracker.claim_completion(mid, specialist_agent_id="builder", claim="done")
    with pytest.raises(MissionError, match="VERDICT"):
        await tracker.verify_completion(mid, verified=True, verification="looks fine")


async def test_correction_state_round_trip(tracker: MissionTracker):
    mission = await tracker.create(
        department="builder",
        office_chat_id=-1003,
        specialist_agent_id="builder",
        acceptance_criteria="ok",
    )
    mid = mission.mission_id
    await tracker.transition(mid, m.ASSIGNED)
    await tracker.transition(mid, m.ACKNOWLEDGED)
    await tracker.transition(mid, m.WORKING)
    assert (await tracker.transition(mid, m.CORRECTION, actor_agent_id="chief")).status == m.CORRECTION
    assert (await tracker.transition(mid, m.WORKING, actor_agent_id="builder")).status == m.WORKING


async def test_mission_tasks_persist(store: Store, tracker: MissionTracker):
    mission = await tracker.create(
        department="builder",
        office_chat_id=-1004,
        specialist_agent_id="builder",
        acceptance_criteria="tasks done",
    )
    tasks = MissionTaskStore(store)
    tid = await tasks.add(mission.mission_id, "unit A", title="A")
    listed = await tasks.list_for_mission(mission.mission_id)
    assert listed[0]["task_id"] == tid
    assert listed[0]["brief"] == "unit A"


async def test_lease_idempotent_claim_and_cancel_release(store: Store, tracker: MissionTracker):
    leases = WorkLeaseManager(store)
    mission = await tracker.create(
        department="builder",
        office_chat_id=-1005,
        specialist_agent_id="builder",
        acceptance_criteria="ok",
    )
    lease = await leases.claim(
        "job:build:1", agent_id="builder", purpose="compile", mission_id=mission.mission_id
    )
    with pytest.raises(LeaseError):
        await leases.claim(
            "job:build:1", agent_id="builder", purpose="compile", mission_id=mission.mission_id
        )
    n = await leases.release_for_mission(mission.mission_id, reason="mission_cancelled")
    assert n == 1
    # reclaim after release
    again = await leases.claim(
        "job:build:1", agent_id="builder", purpose="compile", mission_id=mission.mission_id
    )
    assert again.lease_key == lease.lease_key


async def test_tool_permit_deny(store: Store):
    gate = PermitGate(store)
    await gate.grant_tool("builder", "shell.exec", allowed=False)
    assert await gate.allow_tool("builder", "shell.exec") is False
    assert await gate.allow_tool("builder", "other.tool") is True  # no row → allow


async def test_browser_permit_domain(store: Store):
    gate = PermitGate(store)
    await gate.grant_browser("stagehand", "*.example.com", actions=["navigate"], allowed=True)
    await gate.grant_browser("stagehand", "*", actions=["*"], allowed=False)
    # First matching row wins in our impl — grant order: specific then deny-all
    # Our allow_browser iterates rows; first match on pattern returns.
    # Re-seed with only allow for example.com
    await store.execute("DELETE FROM browser_permits")
    await gate.grant_browser("stagehand", "api.example.com", actions=["navigate", "extract"], allowed=True)
    assert await gate.allow_browser("stagehand", "api.example.com", "navigate") is True
    assert await gate.allow_browser("stagehand", "evil.com", "navigate") is False


async def test_memory_scope_write_guard(store: Store):
    mem = MemoryScopeStore(store)
    await mem.upsert("builder", write_roles=["builder"])
    assert await mem.may_write("builder", "builder") is True
    assert await mem.may_write("builder", "growth") is False
    assert await mem.may_write("builder", "chief") is True


async def test_maf_dag_rejects_cycle():
    with pytest.raises(DagValidationError, match="cycle"):
        validate_task_dag(
            [
                {"id": "a", "depends_on": ["b"]},
                {"id": "b", "depends_on": ["a"]},
            ]
        )


async def test_maf_dag_ok_and_fanout():
    validate_task_dag(
        [
            {"id": "a", "depends_on": []},
            {"id": "b", "depends_on": ["a"]},
            {"id": "c", "depends_on": ["a"]},
        ]
    )
    with pytest.raises(DagValidationError, match="fan"):
        validate_task_dag(
            [{"id": "x", "depends_on": [f"d{i}" for i in range(9)]}]
            + [{"id": f"d{i}", "depends_on": []} for i in range(9)],
            max_fanout=8,
        )


async def test_fakes_do_not_touch_network():
    bot = FakeTelegramBot("chief", 1, "chief_bot")
    await bot.send_message(-100, "hello")
    assert bot.sent[0]["text"] == "hello"
    cursor = FakeCursorControl()
    d = await cursor.chief_direct("ping")
    assert d.ok
    hermes = FakeHermesClient(replies={"builder-lead": "ACK"})
    out = await hermes.chat(profile="builder-lead", chat_id=-1, user_text="assign")
    assert out["text"] == "ACK"

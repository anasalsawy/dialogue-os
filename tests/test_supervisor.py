"""Active-mission supervision.

Proves Chief detects a missing acknowledgement, a stale heartbeat, a dead
process, a blocker, an unsupported completion claim, and a verified completion —
and that supervision state (including the next check time) is durable.
"""

from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from dialogue_os.db.store import Store
from dialogue_os.offices import missions as m
from dialogue_os.offices import probes
from dialogue_os.offices.missions import MissionTracker
from dialogue_os.offices.reports import ACK, BLOCKER, CLAIM, HEARTBEAT, parse_specialist_message
from dialogue_os.offices.supervision import FAST, SLOW, SupervisionStore, VERIFIED
from dialogue_os.offices.supervisor import (
    BLOCKER_RAISED,
    COMPLETION_CLAIM,
    MISSING_ACK,
    MissionSupervisor,
    PROCESS_EXITED,
    STALE_HEARTBEAT,
    UNSUPPORTED_CLAIM,
)

OFFICE_CHAT = -1001234567890


@pytest.fixture
async def store(tmp_path: Path):
    s = Store(tmp_path / "supervision.sqlite3")
    await s.connect()
    yield s
    await s.close()


@pytest.fixture
def tracker(store: Store) -> MissionTracker:
    return MissionTracker(store)


@pytest.fixture
def supervision(store: Store) -> SupervisionStore:
    return SupervisionStore(store)


class Harness:
    """Supervisor wired to fakes so nothing touches Telegram or Cursor."""

    def __init__(self, supervisor, control, posts, owner, watcher, proc_root: Path):
        self.supervisor = supervisor
        self.control = control
        self.posts = posts
        self.owner = owner
        self.watcher = watcher
        self.proc_root = proc_root

    def chief_says(self, text: str) -> None:
        decision = MagicMock()
        decision.ok = True
        decision.action = "respond"
        decision.text = text
        self.control.chief_direct = AsyncMock(return_value=decision)

    @property
    def last_prompt(self) -> str:
        return self.control.chief_direct.await_args.args[0]

    def make_process(self, pid: int, state_char: str = "R") -> None:
        stat_dir = self.proc_root / str(pid)
        stat_dir.mkdir(parents=True, exist_ok=True)
        (stat_dir / "stat").write_text(f"{pid} (worker) {state_char} 1 1 1 0 -1 0 0 0")

    def kill_process(self, pid: int) -> None:
        stat_file = self.proc_root / str(pid) / "stat"
        if stat_file.exists():
            stat_file.unlink()


@pytest.fixture
def harness(tracker: MissionTracker, supervision: SupervisionStore, tmp_path: Path) -> Harness:
    posts: list[tuple[int, str]] = []
    owner: list[str] = []
    watcher: list[tuple[str, str, str]] = []

    async def post(chat_id: int, text: str) -> None:
        posts.append((chat_id, text))

    async def notify_owner(text: str) -> None:
        owner.append(text)

    async def notify_watcher(watcher_id: str, summary: str, severity: str) -> None:
        watcher.append((watcher_id, summary, severity))

    control = MagicMock()
    decision = MagicMock()
    decision.ok = True
    decision.action = "respond"
    decision.text = "Status update please, with evidence."
    control.chief_direct = AsyncMock(return_value=decision)

    proc_root = tmp_path / "proc"
    proc_root.mkdir()

    supervisor = MissionSupervisor(
        missions=tracker,
        supervision=supervision,
        control=control,
        post_office_message=post,
        notify_owner=notify_owner,
        notify_watcher=notify_watcher,
        ack_timeout=300.0,
        heartbeat_timeout=600.0,
        owner_update_interval=1800.0,
        max_unsupported_claims=2,
        proc_root=proc_root,
    )
    return Harness(supervisor, control, posts, owner, watcher, proc_root)


async def _assigned_mission(tracker: MissionTracker, supervisor: MissionSupervisor):
    mission = await tracker.create(
        department="builder",
        office_chat_id=OFFICE_CHAT,
        specialist_agent_id="builder",
        title="Ship the widget",
        assignment_text="Build it and show evidence.",
        acceptance_criteria="Diff reviewed, tests pass, service healthy.",
    )
    mission = await tracker.transition(
        mission.mission_id, m.ASSIGNED, actor_agent_id="chief"
    )
    await supervisor.on_mission_assigned(mission)
    return mission


# --------------------------------------------------------------- parsing


def test_parse_acknowledgement_with_plan():
    report = parse_specialist_message("ACK\nPlan: read the spec, then write the router.")
    assert report.kind == ACK
    assert report.plan.startswith("read the spec")


def test_parse_heartbeat_fields():
    report = parse_specialist_message(
        "Action: running the test suite\n"
        "Tool: pytest\n"
        "PID: 4242\n"
        "Progress: 40 of 60 tests\n"
        "Blocker: none\n"
        "Next: fix the failing splitter test"
    )
    assert report.kind == HEARTBEAT
    assert report.action == "running the test suite"
    assert report.tool == "pytest"
    assert report.pid == 4242
    assert report.blocker is None
    assert report.next_action == "fix the failing splitter test"


def test_parse_blocker_and_claim():
    blocked = parse_specialist_message("Blocker: need the Browserbase API key")
    assert blocked.kind == BLOCKER
    assert "Browserbase" in blocked.blocker

    claim = parse_specialist_message("Done. Tests: 115 passed. Artifact: dialogue_os/x.py")
    assert claim.kind == CLAIM
    assert claim.has_evidence


def test_claim_without_evidence_is_unsupported():
    claim = parse_specialist_message("All done, everything works great now")
    assert claim.kind == CLAIM
    assert not claim.has_evidence


# ------------------------------------------------------------- detection


async def test_detects_missing_acknowledgement(tracker: MissionTracker, harness: Harness):
    mission = await _assigned_mission(tracker, harness.supervisor)
    harness.chief_says("Please acknowledge and share your initial plan.")

    outcome = await harness.supervisor.inspect(
        mission.mission_id, now=time.time() + 900
    )

    assert MISSING_ACK in outcome.finding_kinds
    assert outcome.cursor_invoked is False
    assert outcome.posted
    assert harness.posts[-1][0] == OFFICE_CHAT
    assert "acknowledge" in harness.posts[-1][1].lower()
    harness.control.chief_direct.assert_not_awaited()
    state = await harness.supervisor.supervision.get(mission.mission_id)
    assert state.ack_followups == 1


async def test_acknowledgement_clears_the_finding(tracker: MissionTracker, harness: Harness):
    mission = await _assigned_mission(tracker, harness.supervisor)
    await harness.supervisor.on_specialist_message(
        mission, text="ACK\nPlan: scaffold the module, then test."
    )

    state = await harness.supervisor.supervision.get(mission.mission_id)
    assert state.acknowledged
    assert state.initial_plan.startswith("scaffold")
    refreshed = await tracker.get(mission.mission_id)
    assert refreshed.status == m.ACKNOWLEDGED

    outcome = await harness.supervisor.inspect(mission.mission_id, now=time.time() + 900)
    assert MISSING_ACK not in outcome.finding_kinds


async def test_detects_stale_heartbeat(tracker: MissionTracker, harness: Harness):
    mission = await _assigned_mission(tracker, harness.supervisor)
    await harness.supervisor.on_specialist_message(mission, text="ACK\nPlan: start work")
    mission = await tracker.get(mission.mission_id)
    await harness.supervisor.on_specialist_message(
        mission, text="Action: compiling\nTool: make\nProgress: 10%"
    )
    harness.chief_says("You have gone quiet. What are you doing right now?")

    outcome = await harness.supervisor.inspect(mission.mission_id, now=time.time() + 3600)

    assert STALE_HEARTBEAT in outcome.finding_kinds
    assert outcome.posted
    state = await harness.supervisor.supervision.get(mission.mission_id)
    assert state.missed_heartbeats == 1


async def test_detects_dead_process_and_collects_logs(
    tracker: MissionTracker, harness: Harness
):
    mission = await _assigned_mission(tracker, harness.supervisor)
    harness.make_process(5150)
    await harness.supervisor.on_specialist_message(
        mission, text="Action: building\nTool: npm\nPID: 5150"
    )

    alive = await harness.supervisor.inspect(mission.mission_id, force=True)
    assert PROCESS_EXITED not in alive.finding_kinds

    harness.kill_process(5150)
    harness.chief_says("The build process is gone. Send exit status and logs.")
    outcome = await harness.supervisor.inspect(mission.mission_id)

    assert PROCESS_EXITED in outcome.finding_kinds
    assert outcome.posted
    logs = await harness.supervisor.supervision.recent_logs(mission.mission_id)
    assert any("exited" in entry["message"] for entry in logs)
    assert "exit code" in harness.posts[-1][1].lower()


async def test_detects_blocker_and_escalates_to_owner(
    tracker: MissionTracker, harness: Harness, supervision: SupervisionStore
):
    mission = await _assigned_mission(tracker, harness.supervisor)
    harness.chief_says("Anas: the Browserbase key is required to continue.")

    await harness.supervisor.on_specialist_message(
        mission, text="Blocker: need the Browserbase API key to continue"
    )
    refreshed = await tracker.get(mission.mission_id)
    assert refreshed.status == m.BLOCKED

    await supervision.update(mission.mission_id, blocker_requires_owner=True)
    outcome = await harness.supervisor.inspect(mission.mission_id, force=True)

    assert BLOCKER_RAISED in outcome.finding_kinds
    assert harness.owner, "owner must be told exactly what is needed"
    assert "Browserbase" in harness.owner[-1]


async def test_repeated_unsupported_claims_do_not_bypass_watcher_consensus(
    tracker: MissionTracker, harness: Harness
):
    mission = await _assigned_mission(tracker, harness.supervisor)
    harness.chief_says("No evidence supplied.\nVERDICT: REJECTED")

    await harness.supervisor.on_specialist_message(mission, text="All done, it works")
    state = await harness.supervisor.supervision.get(mission.mission_id)
    assert state.unsupported_claims >= 1

    mission = await tracker.get(mission.mission_id)
    assert mission.status == m.WORKING, "a rejected claim goes back to work"

    await harness.supervisor.on_specialist_message(
        mission, text="Finished now, trust me, everything is complete"
    )

    assert not harness.watcher, (
        "the deterministic supervisor must not manufacture a watcher alert; "
        "the Alpha+Beta audit lane owns deception findings"
    )


async def test_completion_claim_requires_chief_verification(
    tracker: MissionTracker, harness: Harness
):
    mission = await _assigned_mission(tracker, harness.supervisor)
    # Chief has not finished inspecting: no verdict line yet.
    harness.chief_says("Checking the diff and the test output now.")

    await harness.supervisor.on_specialist_message(
        mission,
        text="Done.\nTests: 115 passed\nArtifact: dialogue_os/offices/supervisor.py",
    )

    refreshed = await tracker.get(mission.mission_id)
    assert refreshed.status == m.VERIFYING
    assert not refreshed.verified
    assert COMPLETION_CLAIM in (
        await harness.supervisor.inspect(mission.mission_id, force=True)
    ).finding_kinds
    assert "COMPLETION GATE" in harness.last_prompt


async def test_verified_completion_closes_the_mission(
    tracker: MissionTracker, harness: Harness
):
    mission = await _assigned_mission(tracker, harness.supervisor)
    harness.chief_says(
        "Inspected the diff, ran the suite (115 passed), service healthy.\n"
        "VERDICT: VERIFIED"
    )

    await harness.supervisor.on_specialist_message(
        mission,
        text="Done.\nTests: 115 passed\nArtifact: dialogue_os/offices/supervisor.py",
    )

    refreshed = await tracker.get(mission.mission_id)
    assert refreshed.status == m.VERIFIED_COMPLETED
    assert refreshed.verified
    assert not refreshed.is_open
    state = await harness.supervisor.supervision.get(mission.mission_id)
    assert state.verification_status == VERIFIED
    assert state.verified_at is not None
    assert any("verified complete" in msg for msg in harness.owner)


# -------------------------------------------------------------- cadence


async def test_no_cursor_call_when_nothing_changed(tracker: MissionTracker, harness: Harness):
    mission = await _assigned_mission(tracker, harness.supervisor)
    await harness.supervisor.on_specialist_message(
        mission, text="ACK\nPlan: begin"
    )
    harness.control.chief_direct.reset_mock()

    first = await harness.supervisor.inspect(mission.mission_id)
    second = await harness.supervisor.inspect(mission.mission_id)

    assert second.cursor_invoked is False
    assert second.findings == []
    assert harness.control.chief_direct.await_count == first.cursor_invoked


async def test_cadence_is_task_aware(tracker: MissionTracker, harness: Harness):
    mission = await _assigned_mission(tracker, harness.supervisor)
    harness.make_process(6100)
    await harness.supervisor.on_specialist_message(
        mission, text="Action: running\nTool: pytest\nPID: 6100"
    )
    await harness.supervisor.inspect(mission.mission_id, force=True)
    state = await harness.supervisor.supervision.get(mission.mission_id)
    assert state.cadence == FAST, "a live process is inspected frequently"

    await harness.supervisor.on_specialist_message(
        mission, text="Blocker: waiting on an external vendor reply"
    )
    await harness.supervisor.inspect(mission.mission_id, force=True)
    state = await harness.supervisor.supervision.get(mission.mission_id)
    assert state.cadence == SLOW, "a long external wait backs off"


async def test_next_check_is_durable_across_restart(
    tracker: MissionTracker, harness: Harness, store: Store
):
    mission = await _assigned_mission(tracker, harness.supervisor)
    await harness.supervisor.inspect(mission.mission_id, force=True)

    # A brand-new store object stands in for a bridge/VM restart.
    reloaded = SupervisionStore(store)
    state = await reloaded.get(mission.mission_id)
    assert state is not None and state.next_check_at is not None

    due_now = await reloaded.due(m.OPEN_STATUSES, now=state.next_check_at - 1)
    due_later = await reloaded.due(m.OPEN_STATUSES, now=state.next_check_at + 1)
    assert mission.mission_id not in due_now
    assert mission.mission_id in due_later


async def test_paused_missions_are_skipped(tracker: MissionTracker, harness: Harness):
    mission = await _assigned_mission(tracker, harness.supervisor)
    await harness.supervisor.supervision.set_paused(mission.mission_id, True)

    outcome = await harness.supervisor.inspect(mission.mission_id, now=time.time() + 9000)
    assert outcome.skipped == "paused"

    forced = await harness.supervisor.request_check(mission.mission_id)
    assert forced.skipped is None


async def test_tick_only_inspects_due_missions(tracker: MissionTracker, harness: Harness):
    mission = await _assigned_mission(tracker, harness.supervisor)
    assert await harness.supervisor.tick(now=time.time()) == []

    outcomes = await harness.supervisor.tick(now=time.time() + 9000)
    assert [o.mission_id for o in outcomes] == [mission.mission_id]


async def test_duplicate_specialist_message_counted_once(
    tracker: MissionTracker, harness: Harness
):
    mission = await _assigned_mission(tracker, harness.supervisor)
    text = "Action: writing tests\nTool: pytest\nProgress: half done"

    await harness.supervisor.on_specialist_message(mission, text=text)
    second = await harness.supervisor.on_specialist_message(mission, text=text)

    assert second.skipped == "duplicate_message"
    events = await tracker.events(mission.mission_id)
    assert sum(1 for e in events if e["event_type"] == "specialist:heartbeat") == 1


def test_process_probe_reads_proc(tmp_path: Path):
    proc_root = tmp_path / "proc"
    (proc_root / "77").mkdir(parents=True)
    (proc_root / "77" / "stat").write_text("77 (my proc) S 1 1 1 0 -1")

    alive = probes.probe_process(77, proc_root=proc_root)
    assert alive.alive and not alive.dead

    (proc_root / "77" / "stat").write_text("77 (my proc) Z 1 1 1 0 -1")
    zombie = probes.probe_process(77, proc_root=proc_root)
    assert zombie.dead

    missing = probes.probe_process(999999, proc_root=proc_root)
    assert missing.status == probes.EXITED
    assert probes.probe_process(None, proc_root=proc_root).status == probes.NONE

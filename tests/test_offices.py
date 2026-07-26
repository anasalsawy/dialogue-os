"""Department-office registry, mission lifecycle and loop protection."""

from __future__ import annotations

from pathlib import Path

import pytest

from dialogue_os.db.store import Store
from dialogue_os.offices import missions as m
from dialogue_os.offices.loop_guard import (
    LoopGuard,
    OriginalMessage,
    is_content_free,
    is_service_message,
    original_from_relay,
)
from dialogue_os.offices.missions import MissionError, MissionTracker
from dialogue_os.offices.registry import DEPARTMENTS, OfficeError, OfficeRegistry

OWNER = 42
BUILDER_OFFICE = -1001234567890


@pytest.fixture
async def store(tmp_path: Path):
    s = Store(tmp_path / "offices.sqlite3")
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
async def registry(store: Store) -> OfficeRegistry:
    return OfficeRegistry(store, owner_id=OWNER)


async def _register_builder(registry: OfficeRegistry):
    return await registry.register(
        "builder",
        chat_id=BUILDER_OFFICE,
        chat_type="supergroup",
        requester_id=OWNER,
        chat_title="Building Office",
    )


# --- registry ---


async def test_register_office_binds_department_to_group(registry: OfficeRegistry):
    office = await _register_builder(registry)
    assert office.department == "builder"
    assert office.office_chat_id == BUILDER_OFFICE
    assert office.specialist_agent_id == "builder"
    assert office.hermes_profile == "builder-lead"
    assert office.members() == ("chief", "builder")


async def test_lookup_by_chat_id(registry: OfficeRegistry):
    await _register_builder(registry)
    office = await registry.get_by_chat(BUILDER_OFFICE)
    assert office is not None and office.department == "builder"
    assert await registry.specialist_for_chat(BUILDER_OFFICE) == "builder"
    assert await registry.get_by_chat(-999) is None


async def test_only_owner_may_register(registry: OfficeRegistry):
    with pytest.raises(OfficeError, match="Only the owner"):
        await registry.register(
            "builder",
            chat_id=BUILDER_OFFICE,
            chat_type="supergroup",
            requester_id=OWNER + 1,
        )


async def test_registration_requires_a_group_not_a_dm(registry: OfficeRegistry):
    with pytest.raises(OfficeError, match="inside the department's Telegram group"):
        await registry.register(
            "builder", chat_id=OWNER, chat_type="private", requester_id=OWNER
        )


async def test_registration_rejects_positive_chat_id(registry: OfficeRegistry):
    with pytest.raises(OfficeError, match="negative group chat ID"):
        await registry.register(
            "builder", chat_id=12345, chat_type="supergroup", requester_id=OWNER
        )


async def test_unknown_department_rejected(registry: OfficeRegistry):
    with pytest.raises(OfficeError, match="Unknown department"):
        await registry.register(
            "marketing", chat_id=BUILDER_OFFICE, chat_type="supergroup", requester_id=OWNER
        )


async def test_one_department_per_chat(registry: OfficeRegistry):
    await _register_builder(registry)
    with pytest.raises(OfficeError, match="already the builder office"):
        await registry.register(
            "researcher", chat_id=BUILDER_OFFICE, chat_type="supergroup", requester_id=OWNER
        )


async def test_reregistering_same_department_reuses_the_group(registry: OfficeRegistry):
    """Existing offices are reused; re-running the command must not error."""
    await _register_builder(registry)
    again = await registry.register(
        "builder",
        chat_id=BUILDER_OFFICE,
        chat_type="supergroup",
        requester_id=OWNER,
        chat_title="Building Office (renamed)",
    )
    assert again.chat_title == "Building Office (renamed)"
    assert len(await registry.list_offices()) == 1


async def test_unregistered_departments_reported(registry: OfficeRegistry):
    await _register_builder(registry)
    remaining = await registry.unregistered_departments()
    assert "builder" not in remaining
    assert set(remaining) == set(DEPARTMENTS) - {"builder"}


async def test_unregister_deactivates(registry: OfficeRegistry):
    await _register_builder(registry)
    assert await registry.unregister("builder", OWNER) is True
    assert await registry.get("builder") is None
    assert await registry.get_by_chat(BUILDER_OFFICE) is None


async def test_group_can_be_rebound_after_unregistering(registry: OfficeRegistry):
    """A deactivated office must not keep holding the group's unique slot."""
    await _register_builder(registry)
    await registry.unregister("builder", OWNER)
    office = await registry.register(
        "researcher", chat_id=BUILDER_OFFICE, chat_type="supergroup", requester_id=OWNER
    )
    assert office.department == "researcher"
    assert office.office_chat_id == BUILDER_OFFICE


async def test_department_can_move_to_a_different_group(registry: OfficeRegistry):
    await _register_builder(registry)
    moved = await registry.register(
        "builder", chat_id=-1009999999999, chat_type="supergroup", requester_id=OWNER
    )
    assert moved.office_chat_id == -1009999999999
    assert await registry.get_by_chat(BUILDER_OFFICE) is None


async def test_registry_refuses_without_owner_configured(store: Store):
    anonymous = OfficeRegistry(store, owner_id=None)
    with pytest.raises(OfficeError, match="TELEGRAM_OWNER_ID is not configured"):
        await anonymous.register(
            "builder", chat_id=BUILDER_OFFICE, chat_type="supergroup", requester_id=OWNER
        )


# --- mission lifecycle ---


@pytest.fixture
async def tracker(store: Store) -> MissionTracker:
    return MissionTracker(store)


async def _new_mission(tracker: MissionTracker):
    return await tracker.create(
        department="builder",
        office_chat_id=BUILDER_OFFICE,
        specialist_agent_id="builder",
        title="Ship the office router",
        assignment_text="Implement office routing and report with evidence.",
        acceptance_criteria="Office router ships with tests green and evidence attached.",
        chief_cursor_session="sess-chief",
        requested_by=OWNER,
    )


async def test_mission_starts_new_and_is_open(tracker: MissionTracker):
    mission = await _new_mission(tracker)
    assert mission.status == m.NEW
    assert mission.is_open
    assert not mission.verified


async def test_full_happy_path(tracker: MissionTracker):
    mission = await _new_mission(tracker)
    mid = mission.mission_id
    assert (await tracker.transition(mid, m.ASSIGNED, actor_agent_id="chief")).status == m.ASSIGNED
    assert (
        await tracker.transition(mid, m.ACKNOWLEDGED, actor_agent_id="builder")
    ).status == m.ACKNOWLEDGED
    assert (await tracker.transition(mid, m.WORKING, actor_agent_id="builder")).status == m.WORKING
    claimed = await tracker.claim_completion(
        mid, specialist_agent_id="builder", claim="Done, tests pass."
    )
    assert claimed.status == m.COMPLETION_CLAIMED
    verified = await tracker.verify_completion(
        mid,
        verified=True,
        verification="Evidence checked.\nVERDICT: VERIFIED",
        final_report="Shipped.",
    )
    assert verified.status == m.VERIFIED_COMPLETED
    assert verified.verified
    assert verified.final_report == "Shipped."


async def test_specialist_cannot_mark_itself_complete(tracker: MissionTracker):
    """A claim only reaches COMPLETION_CLAIMED. Chief must verify it."""
    mission = await _new_mission(tracker)
    mid = mission.mission_id
    await tracker.transition(mid, m.ASSIGNED)
    await tracker.transition(mid, m.ACKNOWLEDGED)
    await tracker.transition(mid, m.WORKING)
    claimed = await tracker.claim_completion(
        mid, specialist_agent_id="builder", claim="I am finished."
    )
    assert claimed.status == m.COMPLETION_CLAIMED
    assert claimed.status != m.VERIFIED_COMPLETED
    assert not claimed.verified


async def test_only_chief_may_verify_completion(tracker: MissionTracker):
    mission = await _new_mission(tracker)
    mid = mission.mission_id
    await tracker.transition(mid, m.ASSIGNED)
    await tracker.transition(mid, m.ACKNOWLEDGED)
    await tracker.transition(mid, m.WORKING)
    await tracker.claim_completion(mid, specialist_agent_id="builder", claim="Done")
    await tracker.begin_verification(mid)
    with pytest.raises(MissionError, match="Only Chief"):
        await tracker.transition(mid, m.VERIFIED_COMPLETED, actor_agent_id="builder")


async def test_working_cannot_jump_straight_to_completed(tracker: MissionTracker):
    mission = await _new_mission(tracker)
    mid = mission.mission_id
    await tracker.transition(mid, m.ASSIGNED)
    await tracker.transition(mid, m.ACKNOWLEDGED)
    await tracker.transition(mid, m.WORKING)
    with pytest.raises(MissionError, match="Illegal transition"):
        await tracker.transition(mid, m.VERIFIED_COMPLETED, actor_agent_id="chief")


async def test_failed_verification_returns_to_working(tracker: MissionTracker):
    mission = await _new_mission(tracker)
    mid = mission.mission_id
    await tracker.transition(mid, m.ASSIGNED)
    await tracker.transition(mid, m.ACKNOWLEDGED)
    await tracker.transition(mid, m.WORKING)
    await tracker.claim_completion(mid, specialist_agent_id="builder", claim="Done")
    rejected = await tracker.verify_completion(
        mid, verified=False, verification="No evidence supplied."
    )
    assert rejected.status == m.WORKING
    assert not rejected.verified


async def test_verification_requires_review_state(tracker: MissionTracker):
    mission = await _new_mission(tracker)
    with pytest.raises(MissionError, match="verification requires"):
        await tracker.verify_completion(
            mission.mission_id,
            verified=True,
            verification="premature\nVERDICT: VERIFIED",
        )


async def test_blocked_round_trip_is_normal(tracker: MissionTracker):
    mission = await _new_mission(tracker)
    mid = mission.mission_id
    await tracker.transition(mid, m.ASSIGNED)
    await tracker.transition(mid, m.ACKNOWLEDGED)
    await tracker.transition(mid, m.BLOCKED, note="needs a token")
    resumed = await tracker.transition(mid, m.WORKING, actor_agent_id="chief")
    assert resumed.status == m.WORKING


async def test_terminal_missions_are_closed(tracker: MissionTracker):
    mission = await _new_mission(tracker)
    cancelled = await tracker.transition(mission.mission_id, m.CANCELLED)
    assert not cancelled.is_open
    with pytest.raises(MissionError, match="Illegal transition"):
        await tracker.transition(mission.mission_id, m.WORKING)


async def test_supervision_trail_is_recorded(tracker: MissionTracker):
    mission = await _new_mission(tracker)
    mid = mission.mission_id
    await tracker.transition(mid, m.ASSIGNED, actor_agent_id="chief")
    await tracker.add_event(
        mid,
        "progress",
        actor_agent_id="builder",
        text="Wrote the registry",
        evidence={"files": ["dialogue_os/offices/registry.py"]},
    )
    events = await tracker.events(mid)
    types = [e["event_type"] for e in events]
    assert "created" in types
    assert "status:assigned" in types
    assert "progress" in types
    progress = next(e for e in events if e["event_type"] == "progress")
    assert progress["evidence"]["files"] == ["dialogue_os/offices/registry.py"]


async def test_active_mission_for_office(tracker: MissionTracker):
    mission = await _new_mission(tracker)
    active = await tracker.active_for_office(BUILDER_OFFICE)
    assert active is not None and active.mission_id == mission.mission_id
    await tracker.transition(mission.mission_id, m.CANCELLED)
    assert await tracker.active_for_office(BUILDER_OFFICE) is None


async def test_message_budget_counter(tracker: MissionTracker):
    mission = await tracker.create(
        department="builder",
        office_chat_id=BUILDER_OFFICE,
        specialist_agent_id="builder",
        message_budget=2,
    )
    assert await tracker.count_message(mission.mission_id) == 1
    assert await tracker.count_message(mission.mission_id) == 2
    refreshed = await tracker.get(mission.mission_id)
    assert refreshed is not None and refreshed.budget_exhausted


# --- loop protection ---


@pytest.fixture
async def guard(store: Store, tracker: MissionTracker) -> LoopGuard:
    return LoopGuard(store, tracker)


def _msg(message_id: int, bot_id: int = 555, **kwargs) -> OriginalMessage:
    return OriginalMessage(
        bot_id=bot_id, chat_id=BUILDER_OFFICE, message_id=message_id, **kwargs
    )


async def test_first_sighting_allowed_then_deduplicated(guard: LoopGuard):
    original = _msg(1)
    assert await guard.check(original, self_bot_ids={999})
    await guard.mark_seen(original)
    verdict = await guard.check(original, self_bot_ids={999})
    assert not verdict
    assert verdict.reason == "duplicate_original_message"


async def test_dedupe_keys_on_original_not_relaying_bot(guard: LoopGuard):
    """A relayed copy of an already-seen message must not be reprocessed."""
    original = _msg(7, bot_id=555)
    await guard.mark_seen(original)
    relayed = _msg(7, bot_id=555, hop_count=1, is_relayed=True)
    assert not await guard.check(relayed, self_bot_ids={999})


async def test_self_authored_relay_ignored(guard: LoopGuard):
    verdict = await guard.check(
        _msg(3, bot_id=555, is_relayed=True), self_bot_ids={555}
    )
    assert not verdict
    assert verdict.reason == "self_authored_relay"


async def test_hop_count_limit(guard: LoopGuard):
    verdict = await guard.check(_msg(4, hop_count=m.MAX_HOP_COUNT + 1), self_bot_ids=set())
    assert not verdict
    assert "hop_count" in verdict.reason


async def test_normal_multi_turn_supervision_is_not_suppressed(guard: LoopGuard):
    """Ten distinct messages in one mission must all be allowed."""
    for i in range(10):
        original = _msg(100 + i, hop_count=1)
        assert await guard.check(original, self_bot_ids={999}), f"message {i} wrongly blocked"
        await guard.mark_seen(original)


async def test_budget_exhaustion_stops_a_runaway_mission(
    guard: LoopGuard, tracker: MissionTracker
):
    mission = await tracker.create(
        department="builder",
        office_chat_id=BUILDER_OFFICE,
        specialist_agent_id="builder",
        message_budget=1,
    )
    await tracker.count_message(mission.mission_id)
    verdict = await guard.check(_msg(9), self_bot_ids=set(), mission_id=mission.mission_id)
    assert not verdict
    assert "budget" in verdict.reason


async def test_closed_mission_stops_further_traffic(guard: LoopGuard, tracker: MissionTracker):
    mission = await tracker.create(
        department="builder",
        office_chat_id=BUILDER_OFFICE,
        specialist_agent_id="builder",
    )
    await tracker.transition(mission.mission_id, m.CANCELLED)
    verdict = await guard.check(_msg(11), self_bot_ids=set(), mission_id=mission.mission_id)
    assert not verdict
    assert "CANCELLED" in verdict.reason


async def test_do_not_relay_when_recipient_already_sees_the_message(guard: LoopGuard):
    verdict = await guard.should_relay(_msg(12), recipient_sees_chat=True)
    assert not verdict
    assert "already sees" in verdict.reason


async def test_do_not_relay_a_relayed_copy(guard: LoopGuard):
    verdict = await guard.should_relay(_msg(13, is_relayed=True), recipient_sees_chat=False)
    assert not verdict


async def test_relay_allowed_when_transport_requires_it(guard: LoopGuard):
    assert await guard.should_relay(_msg(14), recipient_sees_chat=False)


def test_service_and_empty_messages_never_invoke_agents():
    assert is_service_message({"new_chat_members": [{"id": 1}]})
    assert is_service_message({"pinned_message": {"message_id": 2}})
    assert not is_service_message({"text": "hello"})
    assert is_content_free({"message_id": 1})
    assert not is_content_free({"text": "hello"})
    assert not is_content_free({"caption": "hello"})


def test_relay_envelope_preserves_original_identity():
    original = original_from_relay(
        {
            "original_sender": "YTA BUILDING",
            "original_bot_id": 555,
            "original_group_chat_id": BUILDER_OFFICE,
            "original_message_id": 77,
            "mission_id": "abc",
            "intended_recipient": "chief",
            "hop_count": 2,
        }
    )
    assert original is not None
    assert original.bot_id == 555
    assert original.chat_id == BUILDER_OFFICE
    assert original.message_id == 77
    assert original.hop_count == 2
    assert original.is_relayed


def test_malformed_relay_envelope_rejected():
    assert original_from_relay({"original_bot_id": 555}) is None
    assert original_from_relay({}) is None

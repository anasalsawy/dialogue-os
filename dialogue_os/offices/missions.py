"""Mission lifecycle and supervision trail.

Chief stays involved until completion. A mission is not COMPLETED because the
specialist says so — the specialist can only reach REVIEW by claiming
completion, and only Chief's verification moves it to COMPLETED.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass
from typing import Any

from dialogue_os.db.store import Store
from dialogue_os.util.logging import get_logger

log = get_logger("offices.missions")

NEW = "NEW"
ASSIGNED = "ASSIGNED"
ACKNOWLEDGED = "ACKNOWLEDGED"
WORKING = "WORKING"
WAITING = "WAITING"
BLOCKED = "BLOCKED"
REVIEW_REQUIRED = "REVIEW_REQUIRED"
CORRECTION = "CORRECTION"
COMPLETION_CLAIMED = "COMPLETION_CLAIMED"
VERIFYING = "VERIFYING"
VERIFIED_COMPLETED = "VERIFIED_COMPLETED"
FAILED = "FAILED"
CANCELLED = "CANCELLED"

TERMINAL_STATUSES = frozenset({VERIFIED_COMPLETED, FAILED, CANCELLED})
OPEN_STATUSES = frozenset(
    {
        NEW,
        ASSIGNED,
        ACKNOWLEDGED,
        WORKING,
        WAITING,
        BLOCKED,
        REVIEW_REQUIRED,
        CORRECTION,
        COMPLETION_CLAIMED,
        VERIFYING,
    }
)
ALL_STATUSES = TERMINAL_STATUSES | OPEN_STATUSES

# Statuses where the specialist is expected to be actively executing, so a
# missing heartbeat is a real signal rather than an expected quiet period.
ACTIVE_STATUSES = frozenset({ACKNOWLEDGED, WORKING})

# Allowed transitions. WAITING, BLOCKED and REVIEW_REQUIRED all fall back to
# WORKING so ordinary supervised back-and-forth is never treated as an error.
# VERIFIED_COMPLETED is reachable only from VERIFYING, and only for Chief.
TRANSITIONS: dict[str, frozenset[str]] = {
    NEW: frozenset({ASSIGNED, FAILED, CANCELLED}),
    ASSIGNED: frozenset({ACKNOWLEDGED, WAITING, BLOCKED, FAILED, CANCELLED}),
    ACKNOWLEDGED: frozenset({WORKING, WAITING, BLOCKED, FAILED, CANCELLED}),
    WORKING: frozenset(
        {
            WORKING,
            WAITING,
            BLOCKED,
            REVIEW_REQUIRED,
            CORRECTION,
            COMPLETION_CLAIMED,
            FAILED,
            CANCELLED,
        }
    ),
    WAITING: frozenset(
        {WORKING, BLOCKED, REVIEW_REQUIRED, CORRECTION, COMPLETION_CLAIMED, FAILED, CANCELLED}
    ),
    BLOCKED: frozenset({WORKING, WAITING, ACKNOWLEDGED, CORRECTION, FAILED, CANCELLED}),
    REVIEW_REQUIRED: frozenset(
        {WORKING, WAITING, BLOCKED, CORRECTION, COMPLETION_CLAIMED, FAILED, CANCELLED}
    ),
    CORRECTION: frozenset({WORKING, WAITING, BLOCKED, ACKNOWLEDGED, FAILED, CANCELLED}),
    COMPLETION_CLAIMED: frozenset({VERIFYING, WORKING, BLOCKED, CORRECTION, FAILED, CANCELLED}),
    VERIFYING: frozenset({VERIFIED_COMPLETED, WORKING, BLOCKED, CORRECTION, FAILED, CANCELLED}),
    VERIFIED_COMPLETED: frozenset(),
    FAILED: frozenset(),
    CANCELLED: frozenset(),
}

CHIEF_AGENT_ID = "chief"

DEFAULT_MESSAGE_BUDGET = 60
MAX_HOP_COUNT = 12


class MissionError(Exception):
    """Invalid lifecycle operation."""


@dataclass(frozen=True)
class Mission:
    mission_id: str
    department: str
    office_chat_id: int
    specialist_agent_id: str
    status: str
    title: str | None
    assignment_text: str | None
    acceptance_criteria: str | None
    chief_cursor_session: str | None
    specialist_hermes_session: str | None
    completion_claim: str | None
    chief_verification: str | None
    final_report: str | None
    verified: bool
    message_budget: int
    messages_used: int
    meta: dict[str, Any]
    updated_at: float = 0.0

    @property
    def is_open(self) -> bool:
        return self.status in OPEN_STATUSES

    @property
    def budget_exhausted(self) -> bool:
        return self.messages_used >= self.message_budget


def _row_to_mission(row: Any) -> Mission:
    keys = set(row.keys()) if hasattr(row, "keys") else set()
    acceptance = row["acceptance_criteria"] if "acceptance_criteria" in keys else None
    return Mission(
        mission_id=row["mission_id"],
        department=row["department"],
        office_chat_id=row["office_chat_id"],
        specialist_agent_id=row["specialist_agent_id"],
        status=row["status"],
        title=row["title"],
        assignment_text=row["assignment_text"],
        acceptance_criteria=acceptance,
        chief_cursor_session=row["chief_cursor_session"],
        specialist_hermes_session=row["specialist_hermes_session"],
        completion_claim=row["completion_claim"],
        chief_verification=row["chief_verification"],
        final_report=row["final_report"],
        verified=bool(row["verified"]),
        message_budget=row["message_budget"],
        messages_used=row["messages_used"],
        meta=json.loads(row["meta_json"] or "{}"),
        updated_at=row["updated_at"] or 0.0,
    )


def new_mission_id() -> str:
    return uuid.uuid4().hex


class MissionTracker:
    def __init__(self, store: Store):
        self.store = store

    async def create(
        self,
        *,
        department: str,
        office_chat_id: int,
        specialist_agent_id: str,
        title: str | None = None,
        assignment_text: str | None = None,
        acceptance_criteria: str | None = None,
        chief_cursor_session: str | None = None,
        requested_by: int | None = None,
        message_budget: int = DEFAULT_MESSAGE_BUDGET,
    ) -> Mission:
        mission_id = new_mission_id()
        now = time.time()
        await self.store.execute(
            """
            INSERT INTO missions(mission_id, department, office_chat_id, specialist_agent_id,
                                 status, title, assignment_text, acceptance_criteria,
                                 chief_cursor_session,
                                 verified, message_budget, messages_used, requested_by,
                                 meta_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, 0, ?, ?, ?, ?)
            """,
            (
                mission_id,
                department,
                office_chat_id,
                specialist_agent_id,
                NEW,
                title,
                assignment_text,
                acceptance_criteria,
                chief_cursor_session,
                message_budget,
                requested_by,
                json.dumps({}),
                now,
                now,
            ),
        )
        await self.add_event(mission_id, "created", actor_agent_id="chief", text=title or "")
        mission = await self.get(mission_id)
        assert mission is not None
        log.info("mission_created", mission_id=mission_id, department=department)
        return mission

    async def get(self, mission_id: str) -> Mission | None:
        row = await self.store.fetchone(
            "SELECT * FROM missions WHERE mission_id=?", (mission_id,)
        )
        return _row_to_mission(row) if row else None

    async def active_for_office(self, office_chat_id: int) -> Mission | None:
        """Most recently updated open mission in this office."""
        placeholders = ",".join("?" * len(OPEN_STATUSES))
        row = await self.store.fetchone(
            f"""
            SELECT * FROM missions
            WHERE office_chat_id=? AND status IN ({placeholders})
            ORDER BY updated_at DESC LIMIT 1
            """,
            (office_chat_id, *sorted(OPEN_STATUSES)),
        )
        return _row_to_mission(row) if row else None

    async def list_open(self) -> list[Mission]:
        placeholders = ",".join("?" * len(OPEN_STATUSES))
        rows = await self.store.fetchall(
            f"SELECT * FROM missions WHERE status IN ({placeholders}) ORDER BY updated_at DESC",
            tuple(sorted(OPEN_STATUSES)),
        )
        return [_row_to_mission(r) for r in rows]

    async def transition(
        self,
        mission_id: str,
        to_status: str,
        *,
        actor_agent_id: str | None = None,
        note: str | None = None,
    ) -> Mission:
        mission = await self.get(mission_id)
        if mission is None:
            raise MissionError(f"Unknown mission {mission_id}")
        if to_status not in ALL_STATUSES:
            raise MissionError(f"Unknown status {to_status!r}")
        if to_status not in TRANSITIONS[mission.status]:
            raise MissionError(
                f"Illegal transition {mission.status} → {to_status} for mission {mission_id}"
            )
        if to_status == VERIFIED_COMPLETED and actor_agent_id != CHIEF_AGENT_ID:
            raise MissionError(
                "Only Chief may mark a mission VERIFIED_COMPLETED"
            )

        closed_at = time.time() if to_status in TERMINAL_STATUSES else None
        await self.store.execute(
            "UPDATE missions SET status=?, updated_at=?, closed_at=COALESCE(?, closed_at) WHERE mission_id=?",
            (to_status, time.time(), closed_at, mission_id),
        )
        await self.add_event(
            mission_id,
            f"status:{to_status.lower()}",
            actor_agent_id=actor_agent_id,
            text=note,
        )
        updated = await self.get(mission_id)
        assert updated is not None
        return updated

    async def record_claim(self, mission_id: str, claim: str) -> None:
        """Store the claim text without touching the lifecycle."""
        await self.store.execute(
            "UPDATE missions SET completion_claim=?, updated_at=? WHERE mission_id=?",
            (claim, time.time(), mission_id),
        )

    async def claim_completion(
        self, mission_id: str, *, specialist_agent_id: str, claim: str
    ) -> Mission:
        """A specialist's "done" is only a claim. It cannot mark itself complete."""
        await self.record_claim(mission_id, claim)
        return await self.transition(
            mission_id, COMPLETION_CLAIMED, actor_agent_id=specialist_agent_id, note=claim
        )

    async def begin_verification(self, mission_id: str) -> Mission:
        """Chief starts independently inspecting the claimed evidence."""
        return await self.transition(
            mission_id, VERIFYING, actor_agent_id=CHIEF_AGENT_ID
        )

    async def verify_completion(
        self,
        mission_id: str,
        *,
        verified: bool,
        verification: str,
        final_report: str | None = None,
    ) -> Mission:
        """Only Chief reaches VERIFIED_COMPLETED, and only after inspecting evidence."""
        mission = await self.get(mission_id)
        if mission is None:
            raise MissionError(f"Unknown mission {mission_id}")
        if verified and not (mission.acceptance_criteria or "").strip():
            raise MissionError(
                f"Mission {mission_id} has no acceptance_criteria; refuse verification"
            )
        if verified and "VERDICT: VERIFIED" not in (verification or "").upper():
            # Accept either explicit line or verified=True with clear notes containing VERDICT
            if "VERDICT:VERIFIED" not in (verification or "").upper().replace(" ", ""):
                raise MissionError(
                    "Chief verification must include an explicit 'VERDICT: VERIFIED' line"
                )
        if mission.status not in (COMPLETION_CLAIMED, VERIFYING):
            raise MissionError(
                f"Mission {mission_id} is {mission.status}; verification requires "
                f"{COMPLETION_CLAIMED} or {VERIFYING}"
            )
        if mission.status == COMPLETION_CLAIMED:
            await self.begin_verification(mission_id)
        await self.store.execute(
            """
            UPDATE missions SET chief_verification=?, final_report=?, verified=?, updated_at=?
            WHERE mission_id=?
            """,
            (verification, final_report, 1 if verified else 0, time.time(), mission_id),
        )
        target = VERIFIED_COMPLETED if verified else WORKING
        return await self.transition(
            mission_id, target, actor_agent_id=CHIEF_AGENT_ID, note=verification
        )

    async def set_specialist_session(self, mission_id: str, session_id: str) -> None:
        await self.store.execute(
            "UPDATE missions SET specialist_hermes_session=?, updated_at=? WHERE mission_id=?",
            (session_id, time.time(), mission_id),
        )

    # --- supervision trail ---

    async def add_event(
        self,
        mission_id: str,
        event_type: str,
        *,
        actor_agent_id: str | None = None,
        actor_bot_id: int | None = None,
        text: str | None = None,
        evidence: dict[str, Any] | None = None,
        telegram_message_id: int | None = None,
        hop_count: int = 0,
    ) -> None:
        await self.store.execute(
            """
            INSERT INTO mission_events(mission_id, event_type, actor_agent_id, actor_bot_id,
                                       text, evidence_json, telegram_message_id, hop_count, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                mission_id,
                event_type,
                actor_agent_id,
                actor_bot_id,
                text,
                json.dumps(evidence or {}),
                telegram_message_id,
                hop_count,
                time.time(),
            ),
        )

    async def last_event_time(self, mission_id: str, event_type: str) -> float | None:
        row = await self.store.fetchone(
            "SELECT MAX(created_at) AS ts FROM mission_events WHERE mission_id=? AND event_type=?",
            (mission_id, event_type),
        )
        return row["ts"] if row and row["ts"] is not None else None

    async def events(self, mission_id: str, limit: int = 200) -> list[dict[str, Any]]:
        rows = await self.store.fetchall(
            "SELECT * FROM mission_events WHERE mission_id=? ORDER BY id ASC LIMIT ?",
            (mission_id, limit),
        )
        out = []
        for r in rows:
            d = {k: r[k] for k in r.keys()}
            d["evidence"] = json.loads(d.pop("evidence_json") or "{}")
            out.append(d)
        return out

    async def count_message(self, mission_id: str) -> int:
        """Increment the mission message budget counter and return the new total."""
        await self.store.execute(
            "UPDATE missions SET messages_used=messages_used+1, updated_at=? WHERE mission_id=?",
            (time.time(), mission_id),
        )
        mission = await self.get(mission_id)
        return mission.messages_used if mission else 0

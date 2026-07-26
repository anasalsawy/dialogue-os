"""Durable supervision state for active missions.

Everything the supervisor needs to reason about a mission lives in SQLite,
including `next_check_at`. No Cursor invocation is ever left sleeping to hold a
timer, so supervision resumes correctly after a bridge restart or VM reboot.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from typing import Any

from dialogue_os.db.store import Store
from dialogue_os.util.logging import get_logger

log = get_logger("offices.supervision")

# Task-aware polling cadence (seconds between deterministic inspections).
FAST = "fast"  # active short-running process
NORMAL = "normal"  # ordinary active mission
SLOW = "slow"  # long external wait
CADENCE_SECONDS: dict[str, float] = {FAST: 30.0, NORMAL: 90.0, SLOW: 600.0}
DEFAULT_CADENCE = NORMAL

UNVERIFIED = "UNVERIFIED"
VERIFYING = "VERIFYING"
VERIFIED = "VERIFIED"
REJECTED = "REJECTED"

MAX_RECENT_LOGS = 20


@dataclass
class SupervisionState:
    mission_id: str

    current_step: str | None = None
    initial_plan: str | None = None
    next_expected_action: str | None = None

    acknowledged: bool = False
    acknowledged_at: float | None = None
    acknowledgement_text: str | None = None

    last_specialist_message: str | None = None
    last_specialist_message_at: float | None = None
    last_heartbeat_at: float | None = None
    heartbeat_action: str | None = None
    heartbeat_tool: str | None = None
    heartbeat_progress: str | None = None
    heartbeat_next_action: str | None = None
    missed_heartbeats: int = 0

    process_id: int | None = None
    job_id: str | None = None
    process_status: str | None = None
    process_exit_code: int | None = None
    tool_session_id: str | None = None
    browserbase_session_id: str | None = None

    blocker: str | None = None
    blocker_requires_owner: bool = False
    cadence: str = DEFAULT_CADENCE
    next_check_at: float | None = None
    last_checked_at: float | None = None
    last_cursor_invocation_at: float | None = None
    last_owner_update_at: float | None = None
    paused: bool = False
    ack_followups: int = 0
    unsupported_claims: int = 0
    consecutive_no_change: int = 0
    state_fingerprint: str | None = None

    completion_claimed_at: float | None = None
    completion_evidence: dict[str, Any] = field(default_factory=dict)
    verification_status: str = UNVERIFIED
    verification_notes: str | None = None
    verified_at: float | None = None

    meta: dict[str, Any] = field(default_factory=dict)
    created_at: float = 0.0
    updated_at: float = 0.0

    @property
    def check_interval(self) -> float:
        return CADENCE_SECONDS.get(self.cadence, CADENCE_SECONDS[DEFAULT_CADENCE])

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


_COLUMNS = (
    "current_step",
    "initial_plan",
    "next_expected_action",
    "acknowledged",
    "acknowledged_at",
    "acknowledgement_text",
    "last_specialist_message",
    "last_specialist_message_at",
    "last_heartbeat_at",
    "heartbeat_action",
    "heartbeat_tool",
    "heartbeat_progress",
    "heartbeat_next_action",
    "missed_heartbeats",
    "process_id",
    "job_id",
    "process_status",
    "process_exit_code",
    "tool_session_id",
    "browserbase_session_id",
    "blocker",
    "blocker_requires_owner",
    "cadence",
    "next_check_at",
    "last_checked_at",
    "last_cursor_invocation_at",
    "last_owner_update_at",
    "paused",
    "ack_followups",
    "unsupported_claims",
    "consecutive_no_change",
    "state_fingerprint",
    "completion_claimed_at",
    "completion_evidence_json",
    "verification_status",
    "verification_notes",
    "verified_at",
    "meta_json",
)

_BOOL_COLUMNS = frozenset({"acknowledged", "blocker_requires_owner", "paused"})


def _row_to_state(row: Any) -> SupervisionState:
    return SupervisionState(
        mission_id=row["mission_id"],
        current_step=row["current_step"],
        initial_plan=row["initial_plan"],
        next_expected_action=row["next_expected_action"],
        acknowledged=bool(row["acknowledged"]),
        acknowledged_at=row["acknowledged_at"],
        acknowledgement_text=row["acknowledgement_text"],
        last_specialist_message=row["last_specialist_message"],
        last_specialist_message_at=row["last_specialist_message_at"],
        last_heartbeat_at=row["last_heartbeat_at"],
        heartbeat_action=row["heartbeat_action"],
        heartbeat_tool=row["heartbeat_tool"],
        heartbeat_progress=row["heartbeat_progress"],
        heartbeat_next_action=row["heartbeat_next_action"],
        missed_heartbeats=row["missed_heartbeats"],
        process_id=row["process_id"],
        job_id=row["job_id"],
        process_status=row["process_status"],
        process_exit_code=row["process_exit_code"],
        tool_session_id=row["tool_session_id"],
        browserbase_session_id=row["browserbase_session_id"],
        blocker=row["blocker"],
        blocker_requires_owner=bool(row["blocker_requires_owner"]),
        cadence=row["cadence"],
        next_check_at=row["next_check_at"],
        last_checked_at=row["last_checked_at"],
        last_cursor_invocation_at=row["last_cursor_invocation_at"],
        last_owner_update_at=row["last_owner_update_at"],
        paused=bool(row["paused"]),
        ack_followups=row["ack_followups"],
        unsupported_claims=row["unsupported_claims"],
        consecutive_no_change=row["consecutive_no_change"],
        state_fingerprint=row["state_fingerprint"],
        completion_claimed_at=row["completion_claimed_at"],
        completion_evidence=json.loads(row["completion_evidence_json"] or "{}"),
        verification_status=row["verification_status"],
        verification_notes=row["verification_notes"],
        verified_at=row["verified_at"],
        meta=json.loads(row["meta_json"] or "{}"),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


class SupervisionStore:
    """CRUD for `mission_supervision`, plus the due-for-check scheduler query."""

    def __init__(self, store: Store):
        self.store = store

    async def ensure(self, mission_id: str, *, cadence: str = DEFAULT_CADENCE) -> SupervisionState:
        existing = await self.get(mission_id)
        if existing is not None:
            return existing
        now = time.time()
        await self.store.execute(
            """
            INSERT OR IGNORE INTO mission_supervision(
                mission_id, cadence, next_check_at, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (mission_id, cadence, now + CADENCE_SECONDS.get(cadence, 90.0), now, now),
        )
        state = await self.get(mission_id)
        assert state is not None
        return state

    async def get(self, mission_id: str) -> SupervisionState | None:
        row = await self.store.fetchone(
            "SELECT * FROM mission_supervision WHERE mission_id=?", (mission_id,)
        )
        return _row_to_state(row) if row else None

    async def update(self, mission_id: str, **fields: Any) -> SupervisionState:
        """Patch supervision columns. `completion_evidence`/`meta` take dicts."""
        if "completion_evidence" in fields:
            fields["completion_evidence_json"] = json.dumps(fields.pop("completion_evidence"))
        if "meta" in fields:
            fields["meta_json"] = json.dumps(fields.pop("meta"))
        unknown = set(fields) - set(_COLUMNS)
        if unknown:
            raise ValueError(f"Unknown supervision fields: {sorted(unknown)}")

        await self.ensure(mission_id)
        if fields:
            assignments = ", ".join(f"{k}=?" for k in fields)
            values = [
                int(v) if k in _BOOL_COLUMNS and v is not None else v
                for k, v in fields.items()
            ]
            await self.store.execute(
                f"UPDATE mission_supervision SET {assignments}, updated_at=? WHERE mission_id=?",
                (*values, time.time(), mission_id),
            )
        state = await self.get(mission_id)
        assert state is not None
        return state

    async def schedule_next(
        self, mission_id: str, *, cadence: str | None = None, delay: float | None = None
    ) -> float:
        """Persist the next supervision time so a restart resumes on schedule."""
        state = await self.ensure(mission_id)
        cadence = cadence or state.cadence
        interval = delay if delay is not None else CADENCE_SECONDS.get(cadence, 90.0)
        next_at = time.time() + interval
        await self.update(mission_id, cadence=cadence, next_check_at=next_at)
        return next_at

    async def due(self, statuses: frozenset[str], now: float | None = None) -> list[str]:
        """Mission IDs whose next_check_at has passed (paused missions excluded)."""
        now = now if now is not None else time.time()
        placeholders = ",".join("?" * len(statuses))
        rows = await self.store.fetchall(
            f"""
            SELECT s.mission_id FROM mission_supervision s
            JOIN missions m ON m.mission_id = s.mission_id
            WHERE s.paused = 0
              AND m.status IN ({placeholders})
              AND (s.next_check_at IS NULL OR s.next_check_at <= ?)
            ORDER BY s.next_check_at IS NULL DESC, s.next_check_at ASC
            """,
            (*sorted(statuses), now),
        )
        return [r["mission_id"] for r in rows]

    async def set_paused(self, mission_id: str, paused: bool) -> SupervisionState:
        return await self.update(mission_id, paused=paused)

    # --- artifacts and logs ---

    async def add_artifact(
        self,
        mission_id: str,
        *,
        kind: str,
        path: str | None = None,
        detail: str | None = None,
        meta: dict[str, Any] | None = None,
    ) -> None:
        await self.store.execute(
            """
            INSERT INTO mission_artifacts(mission_id, kind, path, detail, meta_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (mission_id, kind, path, detail, json.dumps(meta or {}), time.time()),
        )

    async def artifacts(self, mission_id: str, limit: int = 50) -> list[dict[str, Any]]:
        rows = await self.store.fetchall(
            "SELECT * FROM mission_artifacts WHERE mission_id=? ORDER BY id DESC LIMIT ?",
            (mission_id, limit),
        )
        out = []
        for r in rows:
            d = {k: r[k] for k in r.keys()}
            d["meta"] = json.loads(d.pop("meta_json") or "{}")
            out.append(d)
        return list(reversed(out))

    async def add_log(
        self, mission_id: str, message: str, *, level: str = "info", source: str | None = None
    ) -> None:
        await self.store.execute(
            """
            INSERT INTO mission_logs(mission_id, level, source, message, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (mission_id, level, source, message[:4000], time.time()),
        )

    async def recent_logs(
        self, mission_id: str, limit: int = MAX_RECENT_LOGS
    ) -> list[dict[str, Any]]:
        rows = await self.store.fetchall(
            "SELECT level, source, message, created_at FROM mission_logs "
            "WHERE mission_id=? ORDER BY id DESC LIMIT ?",
            (mission_id, limit),
        )
        return [dict(r) for r in reversed(rows)]

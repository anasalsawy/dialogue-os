"""Department-office registry.

Dialogue-OS is organised as separate Telegram department offices. Each office is
one group containing the owner (Anas), Chief (Codex-backed manager) and exactly
one specialist (Hermes-backed). Chief is in every office; a specialist is only in
its own. Isolating one specialist per office is what prevents the "bot zoo".

Registration is owner-only and must happen inside the existing group, so the
negative Telegram chat ID is captured from the live chat rather than typed in.
Existing groups are reused; nothing here creates Telegram groups.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any

from dialogue_os.db.store import Store
from dialogue_os.util.logging import get_logger

log = get_logger("offices.registry")

# department -> specialist agent_id. Mirrors the agents table; the Hermes
# profile is resolved from the agent record at registration time.
DEPARTMENTS: dict[str, str] = {
    "builder": "builder",
    "researcher": "researcher",
    "operations": "operations",
    "growth": "growth",
    "customer_relations": "customer_relations",
    "stagehand": "stagehand",
    "watcher_alpha": "watcher_alpha",
    "watcher_beta": "watcher_beta",
}

GROUP_CHAT_TYPES = ("group", "supergroup")


class OfficeError(Exception):
    """Registration or lookup failure that should be reported to the operator."""


@dataclass(frozen=True)
class Office:
    department: str
    office_chat_id: int
    chief_agent_id: str
    specialist_agent_id: str
    hermes_profile: str | None
    chat_title: str | None
    active: bool
    meta: dict[str, Any]

    def members(self) -> tuple[str, str]:
        return (self.chief_agent_id, self.specialist_agent_id)


def _row_to_office(row: Any) -> Office:
    return Office(
        department=row["department"],
        office_chat_id=row["office_chat_id"],
        chief_agent_id=row["chief_agent_id"],
        specialist_agent_id=row["specialist_agent_id"],
        hermes_profile=row["hermes_profile"],
        chat_title=row["chat_title"],
        active=bool(row["active"]),
        meta=json.loads(row["meta_json"] or "{}"),
    )


class OfficeRegistry:
    def __init__(self, store: Store, owner_id: int | None = None):
        self.store = store
        self.owner_id = owner_id

    # --- registration ---

    async def register(
        self,
        department: str,
        *,
        chat_id: int,
        chat_type: str,
        requester_id: int | None,
        chat_title: str | None = None,
        specialist_agent_id: str | None = None,
        hermes_profile: str | None = None,
        chief_agent_id: str = "chief",
    ) -> Office:
        """Bind a department to the group this command was issued in.

        Raises OfficeError with an operator-readable reason; callers surface the
        message in Telegram rather than silently failing.
        """
        department = (department or "").strip().lower()
        if department not in DEPARTMENTS:
            raise OfficeError(
                f"Unknown department '{department}'. Known: {', '.join(sorted(DEPARTMENTS))}"
            )
        if self.owner_id is None:
            raise OfficeError("TELEGRAM_OWNER_ID is not configured; refusing to register an office.")
        if requester_id != self.owner_id:
            raise OfficeError("Only the owner (TELEGRAM_OWNER_ID) may register or change an office.")
        if chat_type not in GROUP_CHAT_TYPES:
            raise OfficeError(
                f"Run /register_office inside the department's Telegram group (got chat_type={chat_type})."
            )
        if chat_id >= 0:
            raise OfficeError(
                f"Expected a negative group chat ID, got {chat_id}. Run this inside the group."
            )

        specialist = specialist_agent_id or DEPARTMENTS[department]
        agent = await self.store.get_agent(specialist)
        if agent is None:
            raise OfficeError(f"Specialist agent '{specialist}' is not in the agent registry.")
        profile = hermes_profile or agent.get("hermes_profile")
        if not profile:
            raise OfficeError(f"Specialist '{specialist}' has no Hermes profile configured.")

        # One office per chat: reject binding a second department to the same group.
        existing = await self.get_by_chat(chat_id)
        if existing and existing.department != department:
            raise OfficeError(
                f"Chat {chat_id} is already the {existing.department} office. "
                "Deactivate it first with /unregister_office."
            )
        # A deactivated office still holds the UNIQUE(office_chat_id) slot; free
        # it so the group can be rebound to a different department.
        await self.store.execute(
            "DELETE FROM offices WHERE office_chat_id=? AND department<>? AND active=0",
            (chat_id, department),
        )

        now = time.time()
        await self.store.execute(
            """
            INSERT INTO offices(department, office_chat_id, chief_agent_id, specialist_agent_id,
                                hermes_profile, chat_title, registered_by, active, meta_json,
                                created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
            -- created_at is deliberately absent from DO UPDATE so re-registering
            -- an existing office preserves when it was first bound.
            ON CONFLICT(department) DO UPDATE SET
                office_chat_id=excluded.office_chat_id,
                chief_agent_id=excluded.chief_agent_id,
                specialist_agent_id=excluded.specialist_agent_id,
                hermes_profile=excluded.hermes_profile,
                chat_title=excluded.chat_title,
                registered_by=excluded.registered_by,
                active=1,
                meta_json=excluded.meta_json,
                updated_at=excluded.updated_at
            """,
            (
                department,
                chat_id,
                chief_agent_id,
                specialist,
                profile,
                chat_title,
                requester_id,
                json.dumps({}),
                now,
                now,
            ),
        )
        office = await self.get(department)
        assert office is not None
        log.info(
            "office_registered",
            department=department,
            chat_id=chat_id,
            specialist=specialist,
        )
        return office

    async def unregister(self, department: str, requester_id: int | None) -> bool:
        if self.owner_id is None or requester_id != self.owner_id:
            raise OfficeError("Only the owner (TELEGRAM_OWNER_ID) may change an office.")
        office = await self.get(department)
        if office is None:
            return False
        await self.store.execute(
            "UPDATE offices SET active=0, updated_at=? WHERE department=?",
            (time.time(), department.strip().lower()),
        )
        log.info("office_deactivated", department=department)
        return True

    # --- lookup ---

    async def get(self, department: str) -> Office | None:
        row = await self.store.fetchone(
            "SELECT * FROM offices WHERE department=? AND active=1",
            (department.strip().lower(),),
        )
        return _row_to_office(row) if row else None

    async def get_by_chat(self, chat_id: int) -> Office | None:
        row = await self.store.fetchone(
            "SELECT * FROM offices WHERE office_chat_id=? AND active=1", (chat_id,)
        )
        return _row_to_office(row) if row else None

    async def list_offices(self) -> list[Office]:
        rows = await self.store.fetchall(
            "SELECT * FROM offices WHERE active=1 ORDER BY department"
        )
        return [_row_to_office(r) for r in rows]

    async def is_office_chat(self, chat_id: int) -> bool:
        return await self.get_by_chat(chat_id) is not None

    async def unregistered_departments(self) -> list[str]:
        registered = {o.department for o in await self.list_offices()}
        return sorted(set(DEPARTMENTS) - registered)

    async def specialist_for_chat(self, chat_id: int) -> str | None:
        office = await self.get_by_chat(chat_id)
        return office.specialist_agent_id if office else None

"""Loop protection for office bot-to-bot conversation.

Bot-to-bot messaging stays ON inside the office system. The job here is to stop
pathological loops without suppressing legitimate multi-turn Chief↔specialist
supervision, so every rule below keys on the ORIGINAL author of a message rather
than on whichever transport happened to deliver it.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from dialogue_os.db.store import Store
from dialogue_os.offices.missions import MAX_HOP_COUNT, MissionTracker
from dialogue_os.util.logging import get_logger

log = get_logger("offices.loop_guard")

# Telegram service/state noise that must never wake an agent.
NON_CONVERSATIONAL_KEYS = (
    "new_chat_members",
    "left_chat_member",
    "new_chat_title",
    "new_chat_photo",
    "delete_chat_photo",
    "group_chat_created",
    "supergroup_chat_created",
    "channel_chat_created",
    "migrate_to_chat_id",
    "migrate_from_chat_id",
    "pinned_message",
    "message_auto_delete_timer_changed",
    "video_chat_started",
    "video_chat_ended",
    "video_chat_participants_invited",
)


@dataclass(frozen=True)
class GuardVerdict:
    allowed: bool
    reason: str = ""

    def __bool__(self) -> bool:
        return self.allowed


ALLOWED = GuardVerdict(True)


@dataclass(frozen=True)
class OriginalMessage:
    """Identity of the message as originally authored.

    For a relayed event these are the relay's `original_*` fields, not the
    identity of the relaying bot — otherwise a relayed copy would look like a
    brand new message and could be processed twice.
    """

    bot_id: int
    chat_id: int
    message_id: int
    hop_count: int = 0
    is_relayed: bool = False


def is_service_message(message: dict[str, Any]) -> bool:
    return any(key in message for key in NON_CONVERSATIONAL_KEYS)


def is_content_free(message: dict[str, Any]) -> bool:
    """Typing actions and edits with no text carry nothing to respond to."""
    return not (message.get("text") or message.get("caption"))


def original_from_relay(payload: dict[str, Any]) -> OriginalMessage | None:
    """Read the preserved identity out of a relay envelope."""
    try:
        return OriginalMessage(
            bot_id=int(payload["original_bot_id"]),
            chat_id=int(payload["original_group_chat_id"]),
            message_id=int(payload["original_message_id"]),
            hop_count=int(payload.get("hop_count") or 0),
            is_relayed=True,
        )
    except (KeyError, TypeError, ValueError):
        return None


class LoopGuard:
    def __init__(self, store: Store, missions: MissionTracker | None = None):
        self.store = store
        self.missions = missions

    async def check(
        self,
        original: OriginalMessage,
        *,
        self_bot_ids: set[int],
        mission_id: str | None = None,
    ) -> GuardVerdict:
        """Decide whether this message may invoke an agent.

        Callers should treat a denial as "stay silent", not as a failure.
        """
        if original.bot_id in self_bot_ids and original.is_relayed:
            # We are seeing a relay of something we ourselves published.
            return GuardVerdict(False, "self_authored_relay")

        if original.hop_count > MAX_HOP_COUNT:
            return GuardVerdict(False, f"hop_count {original.hop_count} exceeds {MAX_HOP_COUNT}")

        if await self.already_seen(original):
            return GuardVerdict(False, "duplicate_original_message")

        if mission_id and self.missions:
            mission = await self.missions.get(mission_id)
            if mission is None:
                return GuardVerdict(False, "unknown_mission")
            if not mission.is_open:
                return GuardVerdict(False, f"mission {mission.status}")
            if mission.budget_exhausted:
                return GuardVerdict(
                    False,
                    f"message budget {mission.message_budget} exhausted for mission {mission_id}",
                )

        return ALLOWED

    async def already_seen(self, original: OriginalMessage) -> bool:
        row = await self.store.fetchone(
            """
            SELECT 1 FROM office_message_seen
            WHERE original_bot_id=? AND original_chat_id=? AND original_message_id=?
            """,
            (original.bot_id, original.chat_id, original.message_id),
        )
        return row is not None

    async def mark_seen(
        self, original: OriginalMessage, mission_id: str | None = None
    ) -> None:
        await self.store.execute(
            """
            INSERT OR IGNORE INTO office_message_seen(
                original_bot_id, original_chat_id, original_message_id,
                mission_id, hop_count, relayed, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                original.bot_id,
                original.chat_id,
                original.message_id,
                mission_id,
                original.hop_count,
                1 if original.is_relayed else 0,
                time.time(),
            ),
        )

    async def should_relay(self, original: OriginalMessage, recipient_sees_chat: bool) -> GuardVerdict:
        """Relay is transport-only, for when Telegram will not deliver a
        bot-authored message to another bot."""
        if recipient_sees_chat:
            return GuardVerdict(False, "recipient already sees the original message")
        if original.is_relayed:
            return GuardVerdict(False, "refusing to relay a transport-generated copy")
        if original.hop_count >= MAX_HOP_COUNT:
            return GuardVerdict(False, "hop budget exhausted")
        return ALLOWED

    async def prune(self, older_than_seconds: float = 7 * 24 * 3600) -> int:
        cutoff = time.time() - older_than_seconds
        await self.store.execute(
            "DELETE FROM office_message_seen WHERE created_at < ?", (cutoff,)
        )
        return 0

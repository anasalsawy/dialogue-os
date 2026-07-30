"""Watcher silence policy and private Chief alerts."""

from __future__ import annotations

import re
import time
import uuid
from typing import Any

from dialogue_os.channel.canonical import CanonicalChannel
from dialogue_os.db.store import Store
from dialogue_os.telegram.api import TelegramBot
from dialogue_os.util.logging import get_logger

log = get_logger("watchers")

OVERRIDE_RE = re.compile(
    r"override\s+silence|resume\s+responding",
    re.IGNORECASE,
)
RESTORE_SILENCE_RE = re.compile(
    r"restore\s+silence|resume\s+silence|be\s+silent",
    re.IGNORECASE,
)


class WatcherService:
    def __init__(
        self,
        store: Store,
        canonical: CanonicalChannel,
        *,
        telegram_delivery_enabled: bool = False,
        cooldown_seconds: int = 3600,
    ):
        self.store = store
        self.canonical = canonical
        self.telegram_delivery_enabled = telegram_delivery_enabled
        self.cooldown_seconds = max(0, cooldown_seconds)
        self._last_delivery: dict[str, float] = {}

    def is_watcher(self, agent_id: str) -> bool:
        return agent_id in ("watcher_alpha", "watcher_beta")

    async def handle_override_command(self, watcher_id: str, chat_id: int, text: str) -> str | None:
        if not self.is_watcher(watcher_id):
            return None
        if OVERRIDE_RE.search(text or ""):
            await self.store.set_watcher_override(watcher_id, chat_id, True)
            return f"{watcher_id}: silence override enabled for this chat. I will respond until silence is restored."
        if RESTORE_SILENCE_RE.search(text or ""):
            await self.store.set_watcher_override(watcher_id, chat_id, False)
            return f"{watcher_id}: silence restored."
        return None

    async def should_reply(self, watcher_id: str, chat_id: int) -> bool:
        return await self.store.watcher_override_enabled(watcher_id, chat_id)

    async def private_alert_to_chief(
        self,
        *,
        watcher_id: str,
        summary: str,
        chief_bot: TelegramBot | None,
        owner_chat_id: int | None,
        severity: str = "warning",
        meta: dict | None = None,
    ) -> dict[str, Any]:
        now = time.time()
        normalized = re.sub(
            r"\b[\w.-]+/[\w.-]+\b", "<model>", (summary or "").strip().lower()
        )
        normalized = re.sub(r"\b[0-9a-f]{8,}\b", "<id>", normalized)
        alert_key = f"{watcher_id}:{severity}:{normalized[:300]}"
        duplicate = (
            now - self._last_delivery.get(alert_key, 0) < self.cooldown_seconds
        )
        delivered = bool(
            self.telegram_delivery_enabled
            and not duplicate
            and chief_bot
            and owner_chat_id
        )
        alert_meta = dict(meta or {})
        alert_meta.update(
            {
                "telegram_delivered": delivered,
                "telegram_suppressed": not delivered,
                "duplicate_within_cooldown": duplicate,
            }
        )
        alert = {
            "alert_id": uuid.uuid4().hex,
            "watcher_id": watcher_id,
            "severity": severity,
            "summary": summary,
            "private_to_chief": True,
            "meta": alert_meta,
        }
        await self.store.add_watcher_alert(alert)
        # Do not publish to canonical channel by default
        if delivered:
            text = f"[Watcher alert · {watcher_id} · {severity}]\n{summary}"
            await chief_bot.send_message(owner_chat_id, text)
            self._last_delivery[alert_key] = now
        return alert

"""Watcher silence policy and private Chief alerts."""

from __future__ import annotations

import re
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
    def __init__(self, store: Store, canonical: CanonicalChannel):
        self.store = store
        self.canonical = canonical

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
        alert = {
            "alert_id": uuid.uuid4().hex,
            "watcher_id": watcher_id,
            "severity": severity,
            "summary": summary,
            "private_to_chief": True,
            "meta": meta or {},
        }
        await self.store.add_watcher_alert(alert)
        # Do not publish to canonical channel by default
        if chief_bot and owner_chat_id:
            text = f"[Watcher alert · {watcher_id} · {severity}]\n{summary}"
            await chief_bot.send_message(owner_chat_id, text)
        return alert

"""Canonical YTA channel memory — durable broadcasts, not a chatter room."""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any

from dialogue_os.db.store import Store
from dialogue_os.telegram.api import TelegramBot
from dialogue_os.util.logging import get_logger
from dialogue_os.util.redact import redact_text

log = get_logger("channel.canonical")


class CanonicalChannel:
    def __init__(
        self,
        store: Store,
        log_path: Path,
        channel_id: int | None,
        publisher_bot: TelegramBot | None = None,
    ):
        self.store = store
        self.log_path = Path(log_path)
        self.channel_id = channel_id
        self.publisher_bot = publisher_bot
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    async def broadcast(
        self,
        *,
        agent_id: str,
        event_type: str,
        summary: str,
        evidence: dict | None = None,
        task_id: str | None = None,
        run_id: str | None = None,
        hop_count: int = 0,
        publish_telegram: bool = True,
    ) -> dict[str, Any]:
        event = {
            "event_id": uuid.uuid4().hex,
            "run_id": run_id,
            "agent_id": agent_id,
            "event_type": event_type,
            "summary": redact_text(summary),
            "evidence": evidence or {},
            "task_id": task_id,
            "hop_count": hop_count,
            "created_at": time.time(),
        }
        await self.store.append_canonical_event(event)
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")

        if publish_telegram and self.channel_id and self.publisher_bot:
            text = self._format_event(event)
            try:
                await self.publisher_bot.send_message(self.channel_id, text)
            except Exception as e:
                log.error("canonical_publish_failed", error=redact_text(str(e)))
                await self.store.log_error("canonical", redact_text(str(e)))
        return event

    def _format_event(self, event: dict) -> str:
        ts = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(event["created_at"]))
        lines = [
            f"[{event['event_type']}] {event.get('agent_id') or '?'}",
            f"time: {ts}",
            f"run: {event.get('run_id') or '-'}",
            f"task: {event.get('task_id') or '-'}",
            "",
            event.get("summary") or "",
        ]
        evidence = event.get("evidence") or {}
        if evidence:
            lines.append("")
            lines.append("evidence: " + json.dumps(evidence, ensure_ascii=False)[:800])
        return "\n".join(lines).strip()

    async def shared_memory(self, limit: int = 50) -> list[dict]:
        """Readable history for authorized agents — reading does NOT invoke agents."""
        return await self.store.recent_canonical_events(limit=limit)

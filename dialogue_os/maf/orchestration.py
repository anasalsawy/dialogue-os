"""Microsoft Agent Framework — lightweight orchestration helpers.

MAF is used for selection hints, handoffs, and temporary group workflows.
It must NOT replace Cursor (Chief) or Hermes personality backends.
The experimental double-lobe/supervisor-lobe design is intentionally not implemented.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from dialogue_os.db.store import Store
from dialogue_os.util.logging import get_logger

log = get_logger("maf")


@dataclass
class SelectionResult:
    selected_agent: str | None
    reason: str
    confidence: float = 0.0


class Orchestrator:
    """Minimal durable handoff / selection layer.

    Full Microsoft Agent Framework packages may be optional; this module provides
    the contracts the runtime needs without becoming the visible agent personality.
    """

    def __init__(self, store: Store):
        self.store = store

    def select_for_unaddressed(self, text: str, agents: list[dict]) -> SelectionResult:
        """Heuristic selection for unaddressed group messages.

        Prefer silence unless clearly relevant. Does not create bot chaos.
        """
        lowered = (text or "").lower()
        if not lowered.strip():
            return SelectionResult(None, "empty", 0.0)

        keywords = {
            "builder": ["build", "deploy", "code", "infra", "systemd", "bug", "implement"],
            "researcher": ["research", "compare", "source", "investigate", "find out"],
            "operations": ["booking", "itinerary", "travel", "ops", "operations", "customer trip"],
            "growth": ["marketing", "ads", "lead", "growth", "campaign"],
            "customer_relations": ["customer", "support", "complaint", "reply to guest"],
            "stagehand": ["browse", "browser", "website", "stagehand", "click", "fill form"],
            "chief": ["chief", "decide", "prioritize", "plan", "coordinate"],
        }
        scores: list[tuple[str, int]] = []
        for agent_id, words in keywords.items():
            score = sum(1 for w in words if w in lowered)
            if score:
                scores.append((agent_id, score))
        if not scores:
            return SelectionResult(None, "no_clear_relevance", 0.0)
        scores.sort(key=lambda x: x[1], reverse=True)
        top, score = scores[0]
        # Require clear signal; otherwise stay silent
        if score < 2:
            return SelectionResult(None, "weak_signal", 0.2)
        return SelectionResult(top, "keyword_match", min(1.0, score / 3))

    async def create_handoff(
        self,
        *,
        from_agent: str,
        to_agent: str,
        summary: str,
        task_title: str | None = None,
    ) -> dict[str, Any]:
        task_id = uuid.uuid4().hex
        handoff_id = uuid.uuid4().hex
        await self.store.create_task(
            {
                "task_id": task_id,
                "title": task_title or summary[:120],
                "status": "ACTIVE",
                "owner_agent": to_agent,
                "created_by": from_agent,
                "meta": {},
            }
        )
        await self.store.create_handoff(
            {
                "handoff_id": handoff_id,
                "task_id": task_id,
                "from_agent": from_agent,
                "to_agent": to_agent,
                "summary": summary,
                "status": "OPEN",
            }
        )
        return {"task_id": task_id, "handoff_id": handoff_id, "to_agent": to_agent}

    async def start_group_workflow(self, title: str, participants: list[str], created_by: str) -> dict:
        task_id = uuid.uuid4().hex
        await self.store.create_task(
            {
                "task_id": task_id,
                "title": title,
                "status": "ACTIVE",
                "owner_agent": created_by,
                "created_by": created_by,
                "meta": {"type": "group_chat", "participants": participants},
            }
        )
        return {"task_id": task_id, "participants": participants}

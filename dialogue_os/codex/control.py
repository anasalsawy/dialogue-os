"""Codex control-plane: every Telegram ingress passes through Codex first."""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass
from typing import Any

from dialogue_os.codex.sessions import CodexSessionManager
from dialogue_os.db.store import Store
from dialogue_os.util.logging import get_logger
from dialogue_os.util.redact import redact_text

log = get_logger("codex.control")

CONTROL_PROMPT_PREAMBLE = """You are the Dialogue-OS / YTA Codex control plane (Chief).

Architecture rules (binding):
- You (Codex CLI) are Chief and the universal Telegram control plane.
- Other named agents use persistent Hermes profiles for personality/memory; you route to them.
- Stagehand/Browserbase is only a browser tool, never a chat backend.
- Microsoft Agent Framework may help with handoffs; it must not replace Hermes/Codex identity.
- Never invent success. Never expose secrets/tokens.
- Prevent bot chatter loops: do not re-invoke yourself for messages you just published.
- Watchers are silent by default; private alerts go to Chief unless override is active.
- Model/provider/API/runtime failures are system-health events handled by the
  model router. Never emit watcher_alert for them or for individual retries.
- Emit watcher_alert only for independently verified mission evidence,
  governance, deception, or safety findings that require Chief action.

Respond with a single JSON object (no markdown fence) using this schema:
{
  "action": "respond" | "dispatch_hermes" | "silent" | "watcher_alert" | "broadcast" | "command",
  "response_bot": "<agent_id that should send the Telegram reply>",
  "text": "<message to send, if any>",
  "hermes_profile": "<profile name when action=dispatch_hermes>",
  "hermes_prompt": "<prompt for Hermes when dispatching>",
  "canonical": {"event_type": "...", "summary": "..."} | null,
  "watcher": {"watcher_id": "...", "severity": "warning|critical", "summary": "..."} | null,
  "notes": "<optional short internal note>"
}

If destination is Chief and the user is chatting, action=respond with response_bot=chief and your answer in text.
If destination is a Hermes agent that should reply in character, action=dispatch_hermes with the correct profile.
If Watchers should stay silent, action=silent.
"""


@dataclass
class ControlDecision:
    action: str
    response_bot: str
    text: str = ""
    hermes_profile: str | None = None
    hermes_prompt: str | None = None
    canonical: dict | None = None
    watcher: dict | None = None
    notes: str = ""
    raw_text: str = ""
    ok: bool = True
    error: str | None = None
    cursor_session_id: str | None = None
    duration_seconds: float = 0.0
    tool_events: list[dict[str, Any]] | None = None
    model: str | None = None


class ControlPlane:
    def __init__(self, sessions: CodexSessionManager, store: Store):
        self.sessions = sessions
        self.store = store

    def build_event_prompt(self, event: dict[str, Any]) -> str:
        payload = {
            "event_id": event.get("event_id"),
            "run_id": event.get("run_id"),
            "hop_count": event.get("hop_count", 0),
            "origin_bot": event.get("origin_bot"),
            "destination_agent": event.get("destination_agent"),
            "chat_id": event.get("chat_id"),
            "chat_type": event.get("chat_type"),
            "from_user": event.get("from_user"),
            "from_is_bot": event.get("from_is_bot"),
            "text": event.get("text"),
            "mentioned_agents": event.get("mentioned_agents") or [],
            "is_command": event.get("is_command", False),
            "command": event.get("command"),
            "is_our_echo": event.get("is_our_echo", False),
            "watcher_override": event.get("watcher_override", False),
            "known_agents": event.get("known_agents") or [],
        }
        return (
            CONTROL_PROMPT_PREAMBLE
            + "\n\nTelegram event:\n"
            + json.dumps(payload, ensure_ascii=False, indent=2)
        )

    async def handle_event(self, event: dict[str, Any], on_partial=None) -> ControlDecision:
        if event.get("is_our_echo"):
            return ControlDecision(
                action="silent",
                response_bot=event.get("destination_agent") or "chief",
                notes="suppressed echo of our own outbound message",
            )
        if event.get("from_is_bot") and not event.get("requires_orchestration"):
            # Bot-to-bot without mention/handoff/workflow → no chatter
            if not event.get("mentioned_agents") and not event.get("is_handoff_event"):
                return ControlDecision(
                    action="silent",
                    response_bot=event.get("destination_agent") or "chief",
                    notes="bot message without mention/handoff",
                )

        hop = int(event.get("hop_count") or 0)
        if hop > 3:
            return ControlDecision(
                action="silent",
                response_bot="chief",
                ok=True,
                notes="hop_count exceeded; recursion guard",
            )

        prompt = self.build_event_prompt(event)
        result = await self.sessions.invoke_primary(prompt, on_partial=on_partial)
        if not result.ok:
            return ControlDecision(
                action="respond",
                response_bot=event.get("destination_agent") or "chief",
                text=f"Codex control plane error: {result.error or 'unknown failure'}",
                ok=False,
                error=result.error,
                cursor_session_id=result.session_id,
                duration_seconds=result.duration_seconds,
                raw_text=result.text,
            )

        decision = parse_control_decision(
            result.text,
            default_bot=event.get("destination_agent") or "chief",
        )
        decision.cursor_session_id = result.session_id
        decision.duration_seconds = result.duration_seconds
        decision.raw_text = result.text
        return decision

    async def chief_direct(
        self, user_text: str, on_partial=None, force_new: bool = False
    ) -> ControlDecision:
        """Chief private chat: Codex answers as itself (still control session)."""
        prompt = (
            "You are Chief for Dialogue-OS / Your Travel Agent. "
            "Answer the operator directly and truthfully. Do not fabricate success.\n\n"
            f"Operator message:\n{user_text}"
        )
        result = await self.sessions.invoke_primary(
            prompt, on_partial=on_partial, force_new=force_new
        )
        if not result.ok:
            return ControlDecision(
                action="respond",
                response_bot="chief",
                text=f"Codex error: {result.error or 'failed'}",
                ok=False,
                error=result.error,
                cursor_session_id=result.session_id,
                duration_seconds=result.duration_seconds,
            )
        return ControlDecision(
            action="respond",
            response_bot="chief",
            text=result.text,
            ok=True,
            cursor_session_id=result.session_id,
            duration_seconds=result.duration_seconds,
            raw_text=result.text,
        )


def parse_control_decision(text: str, default_bot: str = "chief") -> ControlDecision:
    raw = (text or "").strip()
    data = _extract_json_object(raw)
    if not data:
        # Treat free-form Codex output as a direct Chief/agent response
        return ControlDecision(
            action="respond",
            response_bot=default_bot,
            text=raw,
            ok=True,
            notes="fallback_plaintext",
        )
    action = str(data.get("action") or "respond").lower()
    return ControlDecision(
        action=action,
        response_bot=str(data.get("response_bot") or default_bot),
        text=str(data.get("text") or ""),
        hermes_profile=data.get("hermes_profile"),
        hermes_prompt=data.get("hermes_prompt"),
        canonical=data.get("canonical") if isinstance(data.get("canonical"), dict) else None,
        watcher=data.get("watcher") if isinstance(data.get("watcher"), dict) else None,
        notes=str(data.get("notes") or ""),
        ok=True,
    )


def _extract_json_object(text: str) -> dict | None:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        obj = json.loads(text)
        return obj if isinstance(obj, dict) else None
    except json.JSONDecodeError:
        pass
    # Find first {...} block
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        try:
            obj = json.loads(text[start : end + 1])
            return obj if isinstance(obj, dict) else None
        except json.JSONDecodeError:
            return None
    return None


def new_event_id() -> str:
    return uuid.uuid4().hex

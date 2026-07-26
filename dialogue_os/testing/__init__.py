"""Fake adapters for offline governance tests — no live Telegram/Cursor/Hermes."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class FakeTelegramBot:
    agent_id: str
    bot_id: int
    username: str
    sent: list[dict[str, Any]] = field(default_factory=list)

    async def send_message(
        self, chat_id: int, text: str, reply_to_message_id: int | None = None
    ) -> list[dict]:
        msg = {
            "message_id": len(self.sent) + 1,
            "chat_id": chat_id,
            "text": text,
            "reply_to": reply_to_message_id,
        }
        self.sent.append(msg)
        return [msg]


@dataclass
class FakeCursorDecision:
    ok: bool = True
    text: str = ""
    action: str = "respond"
    response_bot: str = "chief"
    error: str | None = None


@dataclass
class FakeCursorControl:
    decisions: list[FakeCursorDecision] = field(default_factory=list)
    calls: list[str] = field(default_factory=list)

    async def chief_direct(self, user_text: str, **kwargs) -> FakeCursorDecision:
        self.calls.append(user_text)
        if self.decisions:
            return self.decisions.pop(0)
        return FakeCursorDecision(text="ack")


@dataclass
class FakeHermesClient:
    replies: dict[str, str] = field(default_factory=dict)
    calls: list[dict[str, Any]] = field(default_factory=list)

    async def chat(
        self, *, profile: str, chat_id: int, user_text: str, extra_system: str | None = None
    ) -> dict[str, Any]:
        self.calls.append(
            {
                "profile": profile,
                "chat_id": chat_id,
                "user_text": user_text,
                "extra_system": extra_system,
            }
        )
        return {
            "ok": True,
            "text": self.replies.get(profile, f"[{profile}] acknowledged"),
            "session_id": f"hermes-{profile}",
        }

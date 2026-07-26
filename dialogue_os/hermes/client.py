"""Hermes OpenAI-compatible client with persistent per-profile sessions."""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any

import httpx

from dialogue_os.db.store import Store
from dialogue_os.util.logging import get_logger
from dialogue_os.util.redact import redact_text

log = get_logger("hermes")

PROFILES_DIR = Path(__file__).resolve().parents[2] / "hermes_profiles"


class HermesClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        store: Store,
        max_output_tokens: int = 4096,
        timeout_seconds: int = 120,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.store = store
        self.max_output_tokens = max_output_tokens
        self.timeout_seconds = timeout_seconds

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def load_system_prompt(self, profile: str) -> str:
        path = PROFILES_DIR / f"{profile}.md"
        if path.exists():
            return path.read_text(encoding="utf-8")
        return (
            f"You are the Dialogue-OS agent profile '{profile}'. "
            "Stay in character. Be truthful. Do not fabricate completion."
        )

    async def get_history(self, profile: str, chat_id: int) -> tuple[str, list[dict]]:
        row = await self.store.fetchone(
            "SELECT session_id, messages_json FROM hermes_sessions WHERE profile=? AND chat_id=?",
            (profile, chat_id),
        )
        if not row:
            session_id = uuid.uuid4().hex
            return session_id, []
        return row["session_id"], json.loads(row["messages_json"] or "[]")

    async def save_history(
        self, profile: str, chat_id: int, session_id: str, messages: list[dict]
    ) -> None:
        # Keep last N messages for context without unbounded growth
        trimmed = messages[-40:]
        now = time.time()
        await self.store.execute(
            """
            INSERT INTO hermes_sessions(profile, chat_id, session_id, messages_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(profile, chat_id) DO UPDATE SET
                session_id=excluded.session_id,
                messages_json=excluded.messages_json,
                updated_at=excluded.updated_at
            """,
            (profile, chat_id, session_id, json.dumps(trimmed), now, now),
        )

    async def chat(
        self,
        profile: str,
        chat_id: int,
        user_text: str,
        extra_system: str | None = None,
    ) -> dict[str, Any]:
        session_id, history = await self.get_history(profile, chat_id)
        system = self.load_system_prompt(profile)
        if extra_system:
            system = system + "\n\n" + extra_system

        messages: list[dict[str, str]] = [{"role": "system", "content": system}]
        messages.extend(history)
        messages.append({"role": "user", "content": user_text})

        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": self.max_output_tokens,
        }
        # Never hit Azure endpoints
        if "azure" in self.base_url.lower():
            raise RuntimeError("Refusing Hermes Azure endpoint")

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                resp = await client.post(url, headers=self._headers(), json=payload)
                resp.raise_for_status()
                data = resp.json()
        except Exception as e:
            log.error("hermes_error", profile=profile, error=redact_text(str(e)))
            return {
                "ok": False,
                "text": "",
                "error": redact_text(str(e)),
                "session_id": session_id,
                "usage": None,
            }

        text = ""
        try:
            text = data["choices"][0]["message"]["content"] or ""
        except Exception:
            text = ""

        # Empty response is allowed (Watchers may be silent) — not automatically a failure
        history.append({"role": "user", "content": user_text})
        history.append({"role": "assistant", "content": text})
        await self.save_history(profile, chat_id, session_id, history)
        await self.store.upsert_chat_session(
            agent_id=profile,
            chat_id=chat_id,
            backend="hermes",
            session_id=session_id,
            hermes_profile=profile,
        )

        usage = data.get("usage")
        return {
            "ok": True,
            "text": text,
            "error": None,
            "session_id": session_id,
            "usage": usage,
            "model": self.model,
        }

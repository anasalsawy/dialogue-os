"""Client for the real Hermes Agent API server.

Unlike :mod:`dialogue_os.hermes.client`, this client does not call an inference
provider directly. It calls Hermes Agent's Responses API, so Hermes itself owns
the tool loop, skills, memory, terminal/browser access, and persisted session.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx

from dialogue_os.db.store import Store
from dialogue_os.util.logging import get_logger
from dialogue_os.util.redact import redact_text

log = get_logger("hermes.agent_api")

PROFILES_DIR = Path(__file__).resolve().parents[2] / "hermes_profiles"
_SAFE_KEY = re.compile(r"[^a-zA-Z0-9:._-]+")


class HermesAgentClient:
    """Route Dialogue-OS roles into isolated, tool-equipped Hermes profiles."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        store: Store,
        timeout_seconds: int = 600,
        session_scope: str = "profile",
        multiplex_profiles: bool = True,
        profile_urls: dict[str, str] | None = None,
    ):
        if session_scope not in {"chat", "profile"}:
            raise ValueError("session_scope must be 'chat' or 'profile'")
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.store = store
        self.timeout_seconds = timeout_seconds
        self.session_scope = session_scope
        self.multiplex_profiles = multiplex_profiles
        self.profile_urls = {
            key: value.rstrip("/") for key, value in (profile_urls or {}).items()
        }

    def _headers(self, profile: str, chat_id: int) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "X-Hermes-Session-Key": self._session_key(profile, chat_id),
        }

    def _profile_base(self, profile: str) -> str:
        if profile in self.profile_urls:
            return self.profile_urls[profile]
        if not self.multiplex_profiles:
            return self.base_url
        return f"{self.base_url}/p/{quote(profile, safe='')}"

    def _session_key(self, profile: str, chat_id: int) -> str:
        transport = "shared" if self.session_scope == "profile" else str(chat_id)
        return _SAFE_KEY.sub("-", f"dialogue-os:{profile}:{transport}")[:256]

    def _conversation(self, profile: str, chat_id: int) -> str:
        return self._session_key(profile, chat_id)

    def load_system_prompt(self, profile: str) -> str:
        path = PROFILES_DIR / f"{profile}.md"
        if path.exists():
            return path.read_text(encoding="utf-8")
        return (
            f"You are the Dialogue-OS agent profile '{profile}'. "
            "Stay in character. Use tools when needed. Never fabricate completion."
        )

    async def assert_ready(self, profiles: tuple[str, ...]) -> dict[str, Any]:
        """Fail closed if configured profiles are not full Hermes Agent APIs."""
        checked: dict[str, Any] = {}
        async with httpx.AsyncClient(timeout=min(self.timeout_seconds, 30)) as client:
            for profile in profiles:
                base = self._profile_base(profile)
                headers = self._headers(profile, 0)
                try:
                    capabilities = await client.get(
                        f"{base}/v1/capabilities", headers=headers
                    )
                    capabilities.raise_for_status()
                    cap_data = capabilities.json()
                    if cap_data.get("platform") != "hermes-agent":
                        raise RuntimeError(
                            f"{profile} endpoint is not a Hermes Agent API server"
                        )
                    toolsets = await client.get(f"{base}/v1/toolsets", headers=headers)
                    toolsets.raise_for_status()
                    enabled_tools = sorted(
                        {
                            tool
                            for item in toolsets.json()
                            if item.get("enabled") and item.get("configured")
                            for tool in item.get("tools", [])
                        }
                    )
                    if not enabled_tools:
                        raise RuntimeError(
                            f"{profile} Hermes runtime has no enabled tools"
                        )
                    checked[profile] = {
                        "capabilities": cap_data.get("features") or {},
                        "tools": enabled_tools,
                    }
                except Exception as exc:
                    raise RuntimeError(
                        f"Hermes Agent profile '{profile}' is not ready: "
                        f"{redact_text(str(exc))}"
                    ) from exc
        return checked

    async def chat(
        self,
        profile: str,
        chat_id: int,
        user_text: str,
        extra_system: str | None = None,
    ) -> dict[str, Any]:
        instructions = self.load_system_prompt(profile)
        if extra_system:
            instructions = f"{instructions}\n\n{extra_system}"

        conversation = self._conversation(profile, chat_id)
        payload = {
            "model": profile,
            "input": user_text,
            "instructions": instructions,
            "conversation": conversation,
            "store": True,
        }
        url = f"{self._profile_base(profile)}/v1/responses"

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(
                    url,
                    headers=self._headers(profile, chat_id),
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
        except Exception as exc:
            error = redact_text(str(exc))
            log.error("hermes_agent_error", profile=profile, error=error)
            return {
                "ok": False,
                "text": "",
                "error": error,
                "session_id": conversation,
                "usage": None,
                "tool_events": [],
                "backend": "hermes-agent",
            }

        text_parts: list[str] = []
        tool_events: list[dict[str, Any]] = []
        for item in data.get("output") or []:
            item_type = item.get("type")
            if item_type == "message":
                for content in item.get("content") or []:
                    if content.get("type") in {"output_text", "text"}:
                        value = content.get("text")
                        if value:
                            text_parts.append(str(value))
            elif item_type in {"function_call", "function_call_output"}:
                tool_events.append(
                    {
                        key: item.get(key)
                        for key in ("type", "name", "arguments", "call_id", "output")
                        if item.get(key) is not None
                    }
                )

        text = "\n".join(text_parts).strip()
        response_id = str(data.get("id") or conversation)
        await self.store.upsert_chat_session(
            agent_id=profile,
            chat_id=chat_id,
            backend="hermes-agent",
            session_id=response_id,
            hermes_profile=profile,
            meta={
                "conversation": conversation,
                "tool_calls": len(
                    [event for event in tool_events if event["type"] == "function_call"]
                ),
            },
        )
        return {
            "ok": data.get("status") in {None, "completed"},
            "text": text,
            "error": data.get("error"),
            "session_id": response_id,
            "conversation": conversation,
            "usage": data.get("usage"),
            "model": data.get("model") or profile,
            "fallback": False,
            "tool_events": tool_events,
            "backend": "hermes-agent",
        }

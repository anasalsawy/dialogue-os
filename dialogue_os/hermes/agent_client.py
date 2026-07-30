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
from dialogue_os.hermes.model_router import FeatherlessModelRouter
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
        model_router: FeatherlessModelRouter | None = None,
        rotation_attempts: int = 25,
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
        self.model_router = model_router
        self.rotation_attempts = max(1, rotation_attempts)

    def _headers(
        self, profile: str, chat_id: int, *, model: str | None = None
    ) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "X-Hermes-Session-Key": self._session_key(profile, chat_id),
        }
        if model:
            # Hermes API server's supported model hot-swap surface.
            headers["X-Hermes-Model"] = model
        return headers

    def _profile_base(self, profile: str) -> str:
        if profile in self.profile_urls:
            return self.profile_urls[profile]
        if not self.multiplex_profiles:
            return self.base_url
        return f"{self.base_url}/p/{quote(profile, safe='')}"

    def _session_key(self, profile: str, chat_id: int) -> str:
        transport = "shared" if self.session_scope == "profile" else str(chat_id)
        return _SAFE_KEY.sub("-", f"dialogue-os-v3:{profile}:{transport}")[:256]

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
                    toolset_data = toolsets.json()
                    if isinstance(toolset_data, dict):
                        toolset_data = (
                            toolset_data.get("toolsets")
                            or toolset_data.get("data")
                            or []
                        )
                    if not isinstance(toolset_data, list):
                        raise RuntimeError(
                            f"{profile} Hermes runtime returned malformed toolsets"
                        )
                    enabled_tools = sorted(
                        {
                            tool
                            for item in toolset_data
                            if isinstance(item, dict)
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

        candidates: list[str | None] = [None]
        if self.model_router:
            try:
                discovered = await self.model_router.candidates(profile)
                if discovered:
                    candidates = discovered[: self.rotation_attempts]
            except Exception as exc:
                log.warning(
                    "hermes_model_catalog_unavailable",
                    profile=profile,
                    error=redact_text(str(exc)),
                )

        data: dict[str, Any] | None = None
        selected_model: str | None = None
        last_error = ""
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            for selected_model in candidates:
                try:
                    request_payload = dict(payload)
                    if selected_model:
                        # Hermes honors an explicit provider+model request. A
                        # custom header alone is ignored by many releases.
                        request_payload["model"] = selected_model
                        request_payload["provider"] = "custom"
                    response = await client.post(
                        url,
                        headers=self._headers(profile, chat_id),
                        json=request_payload,
                    )
                    response.raise_for_status()
                    candidate_data = response.json()
                    candidate_text = self._text_from_response(candidate_data)
                    candidate_error = str(candidate_data.get("error") or candidate_text)
                    if (
                        selected_model
                        and self.model_router
                        and self.model_router.should_rotate(text=candidate_error)
                    ):
                        self.model_router.failure(selected_model, candidate_error)
                        last_error = candidate_error
                        log.warning(
                            "hermes_model_rotated",
                            profile=profile,
                            failed_model=selected_model,
                            error=redact_text(candidate_error),
                        )
                        continue
                    data = candidate_data
                    if selected_model and self.model_router:
                        self.model_router.success(profile, selected_model)
                    break
                except httpx.HTTPStatusError as exc:
                    status = exc.response.status_code
                    last_error = redact_text(str(exc))
                    if (
                        selected_model
                        and self.model_router
                        and self.model_router.should_rotate(status=status, text=last_error)
                    ):
                        self.model_router.failure(selected_model, last_error)
                        log.warning(
                            "hermes_model_rotated",
                            profile=profile,
                            failed_model=selected_model,
                            status=status,
                            error=last_error,
                        )
                        continue
                    break
                except Exception as exc:
                    last_error = redact_text(str(exc))
                    if selected_model and self.model_router:
                        self.model_router.failure(selected_model, last_error)
                    continue

        if data is None:
            error = last_error or "No eligible Hermes model completed the request"
            log.error("hermes_agent_error", profile=profile, error=error)
            return {
                "ok": False,
                "text": "",
                "error": error,
                "session_id": conversation,
                "usage": None,
                "tool_events": [],
                "backend": "hermes-agent",
                "model": selected_model,
                "fallback": bool(selected_model),
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
            "model": selected_model or data.get("model") or profile,
            "fallback": bool(selected_model),
            "tool_events": tool_events,
            "backend": "hermes-agent",
        }

    @staticmethod
    def _text_from_response(data: dict[str, Any]) -> str:
        values: list[str] = []
        for item in data.get("output") or []:
            if not isinstance(item, dict) or item.get("type") != "message":
                continue
            for content in item.get("content") or []:
                if isinstance(content, dict) and content.get("type") in {
                    "output_text",
                    "text",
                }:
                    if content.get("text"):
                        values.append(str(content["text"]))
        return "\n".join(values).strip()

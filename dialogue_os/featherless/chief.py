"""OpenAI-compatible Featherless backend for the Dialogue-OS Chief."""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable

from dialogue_os.db.store import Store
from dialogue_os.hermes.client import HermesClient
from dialogue_os.util.logging import get_logger

log = get_logger("featherless.chief")


@dataclass
class FeatherlessChiefResult:
    ok: bool
    text: str
    session_id: str | None = None
    raw_events: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None
    duration_seconds: float = 0.0
    returncode: int | None = None


class FeatherlessChiefClient:
    """CodexClient-compatible adapter backed by a persistent Featherless chat."""

    def __init__(
        self,
        *,
        store: Store,
        api_key: str,
        model: str,
        fallback_model: str | None = None,
        base_url: str = "https://api.featherless.ai/v1",
        max_output_tokens: int = 8192,
        timeout_seconds: int = 180,
    ):
        if not api_key:
            raise ValueError("CHIEF_FEATHERLESS_API_KEY is required")
        if not model:
            raise ValueError("CHIEF_FEATHERLESS_MODEL is required")
        self.model = model
        self.fallback_model = fallback_model
        self.backend = "featherless"
        self.sandbox = None
        self._lock = asyncio.Lock()
        self._cancel_requested = False
        self.client = HermesClient(
            base_url=base_url,
            api_key=api_key,
            model=model,
            store=store,
            max_output_tokens=max_output_tokens,
            timeout_seconds=timeout_seconds,
        )
        self.fallback_client = (
            HermesClient(
                base_url=base_url,
                api_key=api_key,
                model=fallback_model,
                store=store,
                max_output_tokens=max_output_tokens,
                timeout_seconds=timeout_seconds,
            )
            if fallback_model and fallback_model != model
            else None
        )

    async def create_session(self) -> str:
        return uuid.uuid4().hex

    async def cancel(self) -> bool:
        # The provider request is bounded by timeout; future calls are unaffected.
        self._cancel_requested = True
        return False

    async def run(
        self,
        prompt: str,
        session_id: str | None = None,
        mode: str | None = None,
        on_partial: Callable[[str], Any] | None = None,
    ) -> FeatherlessChiefResult:
        del mode
        async with self._lock:
            started = time.time()
            sid = session_id or await self.create_session()
            self._cancel_requested = False
            result = await self.client.chat(
                profile=f"chief-featherless-{sid}",
                chat_id=0,
                user_text=prompt,
                extra_system=(
                    "You are Chief, the Dialogue-OS control plane. Follow the supplied "
                    "control schema exactly. Never fabricate execution or evidence."
                ),
            )
            used_model = self.model
            if not result.get("ok") and self.fallback_client:
                log.warning(
                    "chief_model_fallback",
                    primary_model=self.model,
                    fallback_model=self.fallback_model,
                    primary_error=result.get("error"),
                )
                result = await self.fallback_client.chat(
                    profile=f"chief-featherless-{sid}",
                    chat_id=0,
                    user_text=prompt,
                    extra_system=(
                        "You are Chief, the Dialogue-OS control plane. Follow the supplied "
                        "control schema exactly. Never fabricate execution or evidence."
                    ),
                )
                used_model = self.fallback_model or self.model
            text = result.get("text") or ""
            if result.get("ok") and text and on_partial:
                partial = on_partial(text)
                if asyncio.iscoroutine(partial):
                    await partial
            return FeatherlessChiefResult(
                ok=bool(result.get("ok")) and not self._cancel_requested,
                text=text,
                session_id=sid,
                raw_events=[
                    {
                        "type": "provider_result",
                        "model": used_model,
                        "fallback": used_model != self.model,
                    }
                ],
                error="cancelled" if self._cancel_requested else result.get("error"),
                duration_seconds=time.time() - started,
                returncode=0 if result.get("ok") else 1,
            )

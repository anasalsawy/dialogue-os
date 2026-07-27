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
        fallback_models: tuple[str, ...] = (),
        base_url: str = "https://api.featherless.ai/v1",
        max_output_tokens: int = 8192,
        timeout_seconds: int = 180,
    ):
        if not api_key:
            raise ValueError("CHIEF_FEATHERLESS_API_KEY is required")
        if not model:
            raise ValueError("CHIEF_FEATHERLESS_MODEL is required")
        self.model = model
        ordered_fallbacks = tuple(
            value
            for value in dict.fromkeys(
                [fallback_model, *fallback_models]
            )
            if value and value != model
        )
        self.fallback_model = ordered_fallbacks[0] if ordered_fallbacks else None
        self.fallback_models = ordered_fallbacks
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
        self.fallback_clients = [
            HermesClient(
                base_url=base_url,
                api_key=api_key,
                model=fallback,
                store=store,
                max_output_tokens=max_output_tokens,
                timeout_seconds=timeout_seconds,
            )
            for fallback in ordered_fallbacks
        ]
        # Compatibility for integrations written against the first fallback.
        self.fallback_client = self.fallback_clients[0] if self.fallback_clients else None

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
            for fallback_model, fallback_client in zip(
                self.fallback_models, self.fallback_clients
            ):
                if result.get("ok"):
                    break
                log.warning(
                    "chief_model_fallback",
                    primary_model=self.model,
                    fallback_model=fallback_model,
                    previous_model=used_model,
                    previous_error=result.get("error"),
                )
                result = await fallback_client.chat(
                    profile=f"chief-featherless-{sid}",
                    chat_id=0,
                    user_text=prompt,
                    extra_system=(
                        "You are Chief, the Dialogue-OS control plane. Follow the supplied "
                        "control schema exactly. Never fabricate execution or evidence."
                    ),
                )
                used_model = fallback_model
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

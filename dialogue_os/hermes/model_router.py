"""Shared Featherless model health registry for the Hermes fleet."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any

import httpx

ROTATABLE_STATUS = {401, 403, 404, 408, 409, 429, 500, 502, 503, 504}
ROTATABLE_TEXT = (
    "api call failed",
    "context length",
    "context too large",
    "max_tokens",
    "maximum allowed",
    "model not found",
    "model unavailable",
    "must be signed in",
    "server error",
    "internal server error",
    "timed out",
    "timeout",
)


@dataclass
class ModelState:
    failures: int = 0
    successes: int = 0
    quarantined_until: float = 0.0
    last_error: str | None = None


class FeatherlessModelRouter:
    """Discover eligible models and share circuit-breaker state across profiles."""

    def __init__(
        self,
        *,
        catalog_url: str = "https://api.featherless.ai/v1/models",
        minimum_context: int = 65_536,
        max_candidates: int = 200,
        refresh_seconds: int = 3600,
    ):
        self.catalog_url = catalog_url
        self.minimum_context = minimum_context
        self.max_candidates = max_candidates
        self.refresh_seconds = refresh_seconds
        self._models: list[str] = []
        self._states: dict[str, ModelState] = {}
        self._profile_model: dict[str, str] = {}
        self._last_refresh = 0.0
        self._lock = asyncio.Lock()

    async def refresh(self, *, force: bool = False) -> list[str]:
        async with self._lock:
            now = time.time()
            if self._models and not force and now - self._last_refresh < self.refresh_seconds:
                return list(self._models)
            params = {
                "available_on_current_plan": "true",
                "capabilities": "chat,tool-use",
                "context_length_min": str(self.minimum_context),
                "sort": "-popularity",
                "per_page": str(min(self.max_candidates, 100)),
            }
            async with httpx.AsyncClient(timeout=30, trust_env=False) as client:
                response = await client.get(self.catalog_url, params=params)
                response.raise_for_status()
                payload = response.json()
            rows = payload.get("data") if isinstance(payload, dict) else []
            self._models = [
                str(row["id"])
                for row in rows or []
                if isinstance(row, dict)
                and row.get("id")
                and int(row.get("context_length") or 0) >= self.minimum_context
                and int(row.get("max_completion_tokens") or 4096) >= 4096
            ][: self.max_candidates]
            self._last_refresh = now
            return list(self._models)

    async def candidates(self, profile: str) -> list[str]:
        models = await self.refresh()
        now = time.time()
        healthy = [
            model
            for model in models
            if self._states.setdefault(model, ModelState()).quarantined_until <= now
        ]
        sticky = self._profile_model.get(profile)
        if sticky in healthy:
            healthy.remove(sticky)
            healthy.insert(0, sticky)
        return healthy

    def success(self, profile: str, model: str) -> None:
        state = self._states.setdefault(model, ModelState())
        state.successes += 1
        state.last_error = None
        self._profile_model[profile] = model

    def failure(self, model: str, error: str) -> None:
        state = self._states.setdefault(model, ModelState())
        state.failures += 1
        state.last_error = error[:500]
        state.quarantined_until = time.time() + min(3600, 30 * (2 ** min(state.failures, 7)))

    @staticmethod
    def should_rotate(*, status: int | None = None, text: str = "") -> bool:
        if status in ROTATABLE_STATUS:
            return True
        lowered = text.lower()
        return any(marker in lowered for marker in ROTATABLE_TEXT)

    def snapshot(self) -> dict[str, Any]:
        now = time.time()
        return {
            "catalog_size": len(self._models),
            "profile_models": dict(self._profile_model),
            "quarantined": {
                model: {
                    "seconds_remaining": max(0, int(state.quarantined_until - now)),
                    "failures": state.failures,
                    "last_error": state.last_error,
                }
                for model, state in self._states.items()
                if state.quarantined_until > now
            },
        }

"""Agent registry — maps roles to backends and Telegram identities."""

from __future__ import annotations

from typing import Any

import httpx

from dialogue_os.config import Settings
from dialogue_os.db.store import Store
from dialogue_os.util.logging import get_logger
from dialogue_os.util.redact import redact_text

log = get_logger("agents.registry")

# Canonical agent definitions for YTA / Dialogue-OS
AGENT_DEFS: list[dict[str, Any]] = [
    {
        "agent_id": "chief",
        "role": "Chief",
        "display_name": "Chief",
        "backend": "cursor",
        "hermes_profile": None,
        "token_env": "TELEGRAM_CHIEF_BOT_TOKEN",
        "historical_usernames": ["dialogue_os_chief_bot"],
    },
    {
        "agent_id": "builder",
        "role": "Lead",
        "display_name": "YTA BUILDING",
        "backend": "hermes",
        "hermes_profile": "builder-lead",
        "token_env": "TELEGRAM_BUILDER_BOT_TOKEN",
        "historical_usernames": [],
    },
    {
        "agent_id": "researcher",
        "role": "Lead",
        "display_name": "YTA RESEARCH",
        "backend": "hermes",
        "hermes_profile": "research-lead",
        "token_env": "TELEGRAM_RESEARCH_BOT_TOKEN",
        "historical_usernames": [],
    },
    {
        "agent_id": "operations",
        "role": "Lead",
        "display_name": "YTA OPERATIONS",
        "backend": "hermes",
        "hermes_profile": "operations-lead",
        "token_env": "TELEGRAM_OPERATIONS_BOT_TOKEN",
        "historical_usernames": ["yta_operations_7f3q_bot"],
    },
    {
        "agent_id": "growth",
        "role": "Lead",
        "display_name": "YTA Growth and Development",
        "backend": "hermes",
        "hermes_profile": "growth-lead",
        "token_env": "TELEGRAM_GROWTH_BOT_TOKEN",
        "historical_usernames": ["yta_growth_7f3q_bot"],
    },
    {
        "agent_id": "customer_relations",
        "role": "Lead",
        "display_name": "YTA CUSTOMER RELATIONS",
        "backend": "hermes",
        "hermes_profile": "customer-relations",
        "token_env": "TELEGRAM_CUSTOMER_RELATIONS_BOT_TOKEN",
        "historical_usernames": ["yta_customer_7f3q_bot"],
    },
    {
        "agent_id": "stagehand",
        "role": "Lead",
        "display_name": "YTA Stagehand / YTA BROWSING",
        "backend": "hermes",
        "hermes_profile": "stagehand-browser",
        "token_env": "TELEGRAM_STAGEHAND_BOT_TOKEN",
        "historical_usernames": ["yta_stagehand_7f3q_bot"],
    },
    {
        "agent_id": "watcher_alpha",
        "role": "Watcher",
        "display_name": "Watcher Alpha",
        "backend": "hermes",
        "hermes_profile": "watcher-alpha",
        "token_env": "TELEGRAM_WATCHER_ALPHA_BOT_TOKEN",
        "historical_usernames": [],
    },
    {
        "agent_id": "watcher_beta",
        "role": "Watcher",
        "display_name": "Watcher Beta",
        "backend": "hermes",
        "hermes_profile": "watcher-beta",
        "token_env": "TELEGRAM_WATCHER_BETA_BOT_TOKEN",
        "historical_usernames": [],
    },
]


class AgentRegistry:
    def __init__(self, store: Store, settings: Settings):
        self.store = store
        self.settings = settings
        self._by_username: dict[str, str] = {}
        self._tokens: dict[str, str] = {}

    async def seed(self) -> None:
        tokens = self.settings.bot_token_map()
        self._tokens = tokens
        for defn in AGENT_DEFS:
            agent_id = defn["agent_id"]
            token = tokens.get(agent_id)
            record = {
                **defn,
                "telegram_username": None,
                "telegram_bot_id": None,
                "meta": {"historical_usernames": defn.get("historical_usernames") or []},
            }
            if agent_id == "chief" and self.settings.chief_backend == "hermes":
                record["backend"] = "hermes"
                record["hermes_profile"] = "chief-control"
            if token:
                identity = await self.validate_token(token)
                if identity:
                    record["telegram_username"] = identity.get("username")
                    record["telegram_bot_id"] = identity.get("id")
                    record["meta"]["telegram_getMe"] = {
                        "id": identity.get("id"),
                        "username": identity.get("username"),
                        "first_name": identity.get("first_name"),
                    }
                    if identity.get("username"):
                        self._by_username[identity["username"].lower()] = agent_id
            await self.store.upsert_agent(record)
            # Also index historical names for mention matching
            for hist in defn.get("historical_usernames") or []:
                self._by_username[hist.lower()] = agent_id

    async def validate_token(self, token: str) -> dict | None:
        url = f"https://api.telegram.org/bot{token}/getMe"
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(url)
                data = resp.json()
            if not data.get("ok"):
                log.error("telegram_getMe_failed", description=redact_text(str(data)))
                return None
            return data["result"]
        except Exception as e:
            log.error("telegram_getMe_error", error=redact_text(str(e)))
            return None

    async def validate_all(self) -> dict[str, Any]:
        results: dict[str, Any] = {}
        for agent_id, token in self.settings.bot_token_map().items():
            identity = await self.validate_token(token)
            results[agent_id] = {
                "ok": identity is not None,
                "username": identity.get("username") if identity else None,
                "id": identity.get("id") if identity else None,
                "first_name": identity.get("first_name") if identity else None,
            }
        return results

    def resolve_mention(self, username: str | None) -> str | None:
        if not username:
            return None
        return self._by_username.get(username.lstrip("@").lower())

    def token_for(self, agent_id: str) -> str | None:
        return self._tokens.get(agent_id) or self.settings.bot_token_map().get(agent_id)

    async def known_agent_summaries(self) -> list[dict]:
        agents = await self.store.list_agents()
        return [
            {
                "agent_id": a["agent_id"],
                "display_name": a.get("display_name"),
                "backend": a.get("backend"),
                "hermes_profile": a.get("hermes_profile"),
                "telegram_username": a.get("telegram_username"),
                "role": a.get("role"),
            }
            for a in agents
        ]

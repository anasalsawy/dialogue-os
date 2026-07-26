"""Stagehand / Browserbase browser tool — never a conversational backend."""

from __future__ import annotations

import time
import uuid
from typing import Any

import httpx

from dialogue_os.db.store import Store
from dialogue_os.util.logging import get_logger
from dialogue_os.util.redact import redact_text

log = get_logger("browser.stagehand")


class BrowserTool:
    """Callable browser tool. Requires explicit evidence for completion claims.

    Final purchases/payments/bookings/destructive actions require explicit
    current authorization recorded before execution.
    """

    def __init__(
        self,
        store: Store,
        api_key: str | None,
        project_id: str | None,
        enabled: bool = False,
    ):
        self.store = store
        self.api_key = api_key
        self.project_id = project_id
        self.enabled = enabled and bool(api_key) and bool(project_id)
        self._sessions: dict[str, dict] = {}

    def status(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "configured": bool(self.api_key and self.project_id),
            "active_sessions": len(self._sessions),
            "note": "Stagehand/Browserbase is a browser tool only, not an LLM chat backend",
        }

    async def start_session(self, agent_id: str, meta: dict | None = None) -> dict[str, Any]:
        if not self.enabled:
            return {"ok": False, "error": "Browser tool not enabled or not configured"}
        run_id = uuid.uuid4().hex
        # Create Browserbase session
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(
                    "https://www.browserbase.com/v1/sessions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={"projectId": self.project_id, **(meta or {})},
                )
                resp.raise_for_status()
                data = resp.json()
        except Exception as e:
            err = redact_text(str(e))
            await self.store.add_tool_run(
                {
                    "run_id": run_id,
                    "agent_id": agent_id,
                    "tool_name": "browserbase.start_session",
                    "status": "FAILED",
                    "summary": err,
                    "evidence": {},
                }
            )
            return {"ok": False, "error": err, "run_id": run_id}

        session_id = data.get("id") or data.get("sessionId")
        self._sessions[session_id] = {
            "agent_id": agent_id,
            "created_at": time.time(),
            "raw": {"id": session_id},  # do not store cookies/secrets
        }
        await self.store.add_tool_run(
            {
                "run_id": run_id,
                "agent_id": agent_id,
                "tool_name": "browserbase.start_session",
                "status": "COMPLETED",
                "summary": f"session {session_id}",
                "evidence": {"browserbase_session_id": session_id},
            }
        )
        return {"ok": True, "session_id": session_id, "run_id": run_id}

    async def record_action(
        self,
        *,
        agent_id: str,
        action: str,
        summary: str,
        evidence: dict,
        requires_auth: bool = False,
        authorization_granted: bool = False,
    ) -> dict[str, Any]:
        run_id = uuid.uuid4().hex
        if requires_auth and not authorization_granted:
            await self.store.add_tool_run(
                {
                    "run_id": run_id,
                    "agent_id": agent_id,
                    "tool_name": f"browser.{action}",
                    "status": "BLOCKED",
                    "summary": "Explicit current authorization required before this side effect",
                    "evidence": evidence,
                }
            )
            return {
                "ok": False,
                "error": "authorization_required",
                "run_id": run_id,
            }
        # Never log payment details, credentials, cookies, API keys
        safe_evidence = {
            k: v
            for k, v in (evidence or {}).items()
            if k.lower()
            not in {
                "cookie",
                "cookies",
                "password",
                "card",
                "cvv",
                "authorization",
                "api_key",
                "token",
            }
        }
        await self.store.add_tool_run(
            {
                "run_id": run_id,
                "agent_id": agent_id,
                "tool_name": f"browser.{action}",
                "status": "RECORDED",
                "summary": summary,
                "evidence": safe_evidence,
            }
        )
        return {"ok": True, "run_id": run_id, "evidence": safe_evidence}

    def looks_like_browser_task(self, text: str) -> bool:
        t = (text or "").lower()
        keys = [
            "browse",
            "browser",
            "open the website",
            "stagehand",
            "screenshot the page",
            "fill the form",
            "click on",
            "navigate to http",
        ]
        return any(k in t for k in keys)

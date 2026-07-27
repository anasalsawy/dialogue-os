"""Persistent Codex control-plane session management."""

from __future__ import annotations

from pathlib import Path

from dialogue_os.codex.client import CodexClient, CodexResult
from dialogue_os.db.store import Store
from dialogue_os.util.logging import get_logger

log = get_logger("codex.sessions")


class CodexSessionManager:
    def __init__(self, store: Store, client: CodexClient, primary_key: str = "primary"):
        self.store = store
        self.client = client
        self.primary_key = primary_key

    async def ensure_primary(self) -> str:
        existing = await self.store.get_cursor_session(self.primary_key)
        if existing:
            return existing
        session_id = await self.client.create_session()
        await self.store.set_cursor_session(
            self.primary_key, session_id, meta={"role": "control_plane"}
        )
        log.info("codex_session_created", key=self.primary_key, session_id=session_id)
        return session_id

    async def get_primary(self) -> str | None:
        return await self.store.get_cursor_session(self.primary_key)

    async def rotate_primary(self) -> str:
        previous = await self.store.get_cursor_session(self.primary_key)
        session_id = await self.client.create_session()
        await self.store.set_cursor_session(
            self.primary_key, session_id, meta={"role": "control_plane", "rotated": True}
        )
        if previous and previous != session_id:
            await self.store.set_cursor_session(
                f"archive:{previous}",
                previous,
                meta={"archived_primary": True},
            )
        return session_id

    async def invoke_primary(
        self,
        prompt: str,
        mode: str | None = None,
        on_partial=None,
        force_new: bool = False,
    ) -> CodexResult:
        if force_new:
            session_id = await self.rotate_primary()
        else:
            session_id = await self.ensure_primary()
        result = await self.client.run(
            prompt=prompt, session_id=session_id, mode=mode, on_partial=on_partial
        )
        if result.session_id and result.session_id != session_id:
            await self.store.set_cursor_session(self.primary_key, result.session_id)
        return result

    async def list_sessions(self) -> list[dict]:
        return await self.store.list_cursor_sessions()

    async def resume_key(self, key: str) -> str | None:
        return await self.store.get_cursor_session(key)

    async def set_active(self, key: str) -> str:
        sid = await self.store.get_cursor_session(key)
        if not sid:
            raise KeyError(f"No Codex session for key={key}")
        await self.store.set_cursor_session(self.primary_key, sid, meta={"resumed_from": key})
        return sid

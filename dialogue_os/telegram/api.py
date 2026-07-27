"""Telegram Bot API helpers (long polling)."""

from __future__ import annotations

import asyncio
from typing import Any, AsyncIterator

import httpx

from dialogue_os.util.logging import get_logger
from dialogue_os.util.redact import redact_text

log = get_logger("telegram.api")

TELEGRAM_LIMIT = 3500


class TelegramError(Exception):
    def __init__(self, message: str, error_code: int | None = None, description: str | None = None):
        super().__init__(message)
        self.error_code = error_code
        self.description = description


class TelegramBot:
    def __init__(self, token: str, agent_id: str):
        self.token = token
        self.agent_id = agent_id
        self.base = f"https://api.telegram.org/bot{token}"
        self._client: httpx.AsyncClient | None = None
        self.username: str | None = None
        self.bot_id: int | None = None

    async def start(self) -> None:
        self._client = httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=30.0))
        me = await self.get_me()
        self.username = me.get("username")
        self.bot_id = me.get("id")

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    @property
    def client(self) -> httpx.AsyncClient:
        if not self._client:
            raise RuntimeError("TelegramBot not started")
        return self._client

    async def _call(self, method: str, **params) -> Any:
        url = f"{self.base}/{method}"
        try:
            resp = await self.client.post(url, json=params)
            data = resp.json()
        except Exception as e:
            raise TelegramError(redact_text(str(e))) from e
        if not data.get("ok"):
            desc = data.get("description", "unknown")
            code = data.get("error_code")
            if code == 409:
                raise TelegramError(
                    "Telegram 409 Conflict: another getUpdates consumer is active for this token",
                    error_code=409,
                    description=desc,
                )
            raise TelegramError(redact_text(desc), error_code=code, description=desc)
        return data.get("result")

    async def get_me(self) -> dict:
        return await self._call("getMe")

    async def get_updates(
        self, offset: int | None = None, timeout: int = 25, allowed_updates: list[str] | None = None
    ) -> list[dict]:
        params: dict[str, Any] = {"timeout": timeout}
        if offset is not None:
            params["offset"] = offset
        if allowed_updates:
            params["allowed_updates"] = allowed_updates
        return await self._call("getUpdates", **params) or []

    async def send_chat_action(self, chat_id: int, action: str = "typing") -> None:
        try:
            await self._call("sendChatAction", chat_id=chat_id, action=action)
        except TelegramError as e:
            log.warning("typing_failed", agent=self.agent_id, error=str(e))

    async def send_message(
        self,
        chat_id: int,
        text: str,
        parse_mode: str | None = None,
        reply_to_message_id: int | None = None,
        disable_notification: bool = False,
    ) -> list[dict]:
        results = []
        for chunk in split_telegram_message(text):
            params: dict[str, Any] = {
                "chat_id": chat_id,
                "text": chunk,
                "disable_notification": disable_notification,
            }
            if parse_mode:
                params["parse_mode"] = parse_mode
            if reply_to_message_id:
                params["reply_to_message_id"] = reply_to_message_id
                reply_to_message_id = None  # only first chunk
            try:
                results.append(await self._call("sendMessage", **params))
            except TelegramError:
                # Markdown/HTML parse failures (or any parse_mode rejection): retry plain text.
                if parse_mode:
                    params.pop("parse_mode", None)
                    results.append(await self._call("sendMessage", **params))
                else:
                    raise
        return results

    async def poll_forever(self, on_update, cancel_handler=None) -> None:
        """Long-poll forever.

        Normal updates are processed on a single worker queue so Codex work
        stays serialized. Cancel updates bypass that queue so /cancel can
        terminate the active subprocess immediately while another turn runs.
        """
        offset: int | None = None
        queue: asyncio.Queue = asyncio.Queue()

        async def _worker() -> None:
            while True:
                upd = await queue.get()
                try:
                    await on_update(self, upd)
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    log.error(
                        "update_handler_error",
                        agent=self.agent_id,
                        error=redact_text(str(e)),
                    )
                finally:
                    queue.task_done()

        worker = asyncio.create_task(_worker(), name=f"tg-worker-{self.agent_id}")
        try:
            while True:
                try:
                    updates = await self.get_updates(offset=offset, timeout=25)
                    for upd in updates:
                        offset = upd["update_id"] + 1
                        if cancel_handler is not None and _update_is_cancel(upd):
                            await cancel_handler(self, upd)
                            continue
                        await queue.put(upd)
                except TelegramError as e:
                    if e.error_code == 409:
                        log.error("telegram_409", agent=self.agent_id, error=str(e))
                        await asyncio.sleep(10)
                    else:
                        log.error("poll_error", agent=self.agent_id, error=str(e))
                        await asyncio.sleep(3)
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    log.error("poll_unexpected", agent=self.agent_id, error=redact_text(str(e)))
                    await asyncio.sleep(3)
        finally:
            worker.cancel()
            try:
                await worker
            except asyncio.CancelledError:
                pass


def _update_is_cancel(update: dict) -> bool:
    message = update.get("message") or update.get("edited_message")
    if not message:
        return False
    text = (message.get("text") or "").strip()
    if not text.startswith("/cancel"):
        return False
    # /cancel or /cancel@BotName — nothing else
    head = text.split(None, 1)[0]
    cmd = head.split("@", 1)[0].lower()
    return cmd == "/cancel"


def split_telegram_message(text: str, limit: int = TELEGRAM_LIMIT) -> list[str]:
    """Split outbound Telegram text into chunks of at most `limit` characters.

    Prefers paragraph (\\n\\n), then newline, then space boundaries. If no safe
    separator exists inside the window, hard-splits at `limit`. Always makes
    forward progress; never raises on long runs without separators.
    """
    if limit <= 0:
        raise ValueError("limit must be positive")
    if not text:
        return [""]
    if len(text) <= limit:
        return [text]

    chunks: list[str] = []
    remaining = text
    while remaining:
        if len(remaining) <= limit:
            chunks.append(remaining)
            break

        window = remaining[:limit]
        cut = -1
        for sep in ("\n\n", "\n", " "):
            pos = window.rfind(sep)
            if pos > 0:
                cut = pos + len(sep)
                break
        if cut <= 0:
            cut = limit

        # Guaranteed progress: cut is in 1..limit
        if cut <= 0 or cut > limit:
            cut = limit
        piece = remaining[:cut]
        if not piece:
            piece = remaining[:limit]
            cut = len(piece)
        chunks.append(piece)
        remaining = remaining[cut:]
    return chunks


class TypingKeepalive:
    """Send Telegram typing immediately and refresh ~every 4 seconds."""

    def __init__(self, bot: TelegramBot, chat_id: int, interval: float = 4.0):
        self.bot = bot
        self.chat_id = chat_id
        self.interval = interval
        self._task: asyncio.Task | None = None

    async def __aenter__(self):
        await self.bot.send_chat_action(self.chat_id, "typing")
        self._task = asyncio.create_task(self._loop())
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _loop(self):
        try:
            while True:
                await asyncio.sleep(self.interval)
                await self.bot.send_chat_action(self.chat_id, "typing")
        except asyncio.CancelledError:
            return

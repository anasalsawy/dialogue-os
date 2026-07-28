"""Non-blocking, priority control lane for Chief.

Ingress handlers enqueue work and return immediately.  A single worker owns the
Chief model/session, so Telegram polling and War Room HTTP requests can never
be held open by a long Chief turn.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

Execute = Callable[[str], Awaitable[dict[str, Any]]]
Complete = Callable[[dict[str, Any]], Awaitable[None]]


@dataclass(order=True)
class _QueuedTurn:
    priority: int
    sequence: int
    command_id: str = field(compare=False)
    prompt: str = field(compare=False)
    source: str = field(compare=False)
    on_complete: Complete | None = field(compare=False, default=None)


class ChiefLane:
    """Serialize Chief reasoning without blocking any transport."""

    def __init__(self, execute: Execute):
        self.execute = execute
        self._queue: asyncio.PriorityQueue[_QueuedTurn] = asyncio.PriorityQueue()
        self._records: dict[str, dict[str, Any]] = {}
        self._sequence = 0
        self._worker: asyncio.Task | None = None
        self._stopping = False

    def start(self) -> asyncio.Task:
        if self._worker is None or self._worker.done():
            self._worker = asyncio.create_task(self.run_forever(), name="chief-control-lane")
        return self._worker

    async def stop(self) -> None:
        self._stopping = True
        if self._worker:
            self._worker.cancel()
            await asyncio.gather(self._worker, return_exceptions=True)

    async def submit(
        self,
        prompt: str,
        *,
        source: str,
        priority: int = 10,
        on_complete: Complete | None = None,
    ) -> dict[str, Any]:
        command_id = uuid.uuid4().hex
        now = time.time()
        record = {
            "command_id": command_id,
            "source": source,
            "status": "queued",
            "created_at": now,
            "started_at": None,
            "completed_at": None,
            "result": None,
            "error": None,
        }
        self._records[command_id] = record
        self._sequence += 1
        await self._queue.put(
            _QueuedTurn(priority, self._sequence, command_id, prompt, source, on_complete)
        )
        return dict(record)

    def get(self, command_id: str) -> dict[str, Any] | None:
        value = self._records.get(command_id)
        return dict(value) if value else None

    def status(self) -> dict[str, Any]:
        active = next(
            (
                item["command_id"]
                for item in self._records.values()
                if item["status"] == "running"
            ),
            None,
        )
        return {
            "available": True,
            "queue_depth": self._queue.qsize(),
            "active_command_id": active,
        }

    async def run_forever(self) -> None:
        while not self._stopping:
            turn = await self._queue.get()
            record = self._records[turn.command_id]
            record["status"] = "running"
            record["started_at"] = time.time()
            try:
                result = await self.execute(turn.prompt)
                record["result"] = result
                record["status"] = "completed" if result.get("ok") else "failed"
                record["error"] = result.get("error")
                if turn.on_complete:
                    await turn.on_complete(dict(record))
            except asyncio.CancelledError:
                record["status"] = "cancelled"
                raise
            except Exception as exc:  # isolated: the lane must survive bad turns
                record["status"] = "failed"
                record["error"] = str(exc)
                if turn.on_complete:
                    await turn.on_complete(dict(record))
            finally:
                record["completed_at"] = time.time()
                self._queue.task_done()


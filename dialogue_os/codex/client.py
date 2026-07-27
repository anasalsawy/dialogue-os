"""Headless Codex CLI client used by Dialogue-OS Chief."""

from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, AsyncIterator, Callable

from dialogue_os.util.redact import redact_text

STREAM_LIMIT = 16 * 1024 * 1024
_ALLOW_EXACT = frozenset(
    {
        "CODEX_HOME", "HOME", "USER", "LOGNAME", "SHELL", "PATH", "PWD",
        "TMPDIR", "TEMP", "TMP", "LANG", "LANGUAGE", "TZ", "TERM",
        "SSL_CERT_FILE", "SSL_CERT_DIR", "CURL_CA_BUNDLE",
        "REQUESTS_CA_BUNDLE", "NODE_EXTRA_CA_CERTS", "HTTP_PROXY",
        "HTTPS_PROXY", "NO_PROXY", "http_proxy", "https_proxy", "no_proxy",
    }
)
_ALLOW_PREFIXES = ("LC_", "XDG_")
_SECRET = re.compile(
    r"(TOKEN|SECRET|PASSWORD|PASSWD|API[_-]?KEY|APIKEY|CREDENTIAL|PRIVATE[_-]?KEY"
    r"|BEARER|COOKIE|SESSION[_-]?KEY|SIGNING|WEBHOOK|DSN)",
    re.IGNORECASE,
)


def sanitize_env(
    source: dict[str, str] | None = None,
    *,
    workspace: Path | str | None = None,
) -> dict[str, str]:
    """Allow only process/runtime variables; Codex reads auth from its credential store."""
    src = dict(os.environ if source is None else source)
    env = {
        key: value
        for key, value in src.items()
        if (key in _ALLOW_EXACT or key.startswith(_ALLOW_PREFIXES))
        and not _SECRET.search(key)
    }
    if workspace is not None:
        env["DIALOGUE_OS_ROOT"] = str(workspace)
    env["NO_OPEN_BROWSER"] = "1"
    return env


@dataclass
class CodexResult:
    ok: bool
    text: str
    session_id: str | None = None
    raw_events: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None
    duration_seconds: float = 0.0
    returncode: int | None = None


class CodexClient:
    """Run persistent, sandboxed Codex sessions with machine-readable output."""

    def __init__(
        self,
        workspace: Path,
        cli_bin: str = "codex",
        model: str | None = None,
        timeout_seconds: int = 600,
        sandbox: str = "workspace-write",
    ):
        if sandbox not in {"read-only", "workspace-write"}:
            raise ValueError("sandbox must be 'read-only' or 'workspace-write'")
        self.workspace = Path(workspace).resolve()
        self.cli_bin = cli_bin
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.sandbox = sandbox
        self._lock = asyncio.Lock()
        self._active_proc: asyncio.subprocess.Process | None = None
        self._cancel_requested = False

    def resolve_bin(self) -> str:
        path = shutil.which(self.cli_bin)
        if path:
            return path
        candidate = Path.home() / ".local" / "bin" / self.cli_bin
        if candidate.exists():
            return str(candidate)
        raise FileNotFoundError(f"Codex CLI '{self.cli_bin}' not found")

    async def create_session(self) -> str:
        # Codex allocates the thread on the first real turn. A local sentinel
        # tells run() to start rather than resume; the emitted thread id replaces it.
        return f"new:{time.time_ns()}"

    def _env(self) -> dict[str, str]:
        return sanitize_env(workspace=self.workspace)

    def _build_args(
        self, prompt: str, session_id: str | None, mode: str | None = None
    ) -> list[str]:
        if mode not in (None, "ask", "plan"):
            raise ValueError("mode must be None, 'ask', or 'plan'")
        sandbox = "read-only" if mode in {"ask", "plan"} else self.sandbox
        args = [
            self.resolve_bin(), "exec", "--json", "--color", "never",
            "--sandbox", sandbox, "--cd", str(self.workspace),
        ]
        if self.model:
            args.extend(["--model", self.model])
        if session_id and not session_id.startswith("new:"):
            args.extend(["resume", session_id])
        args.append(prompt)
        return args

    async def cancel(self) -> bool:
        self._cancel_requested = True
        proc = self._active_proc
        if not proc or proc.returncode is not None:
            return False
        try:
            proc.terminate()
            try:
                await asyncio.wait_for(proc.wait(), timeout=2)
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
            return True
        except ProcessLookupError:
            return False

    async def run(
        self,
        prompt: str,
        session_id: str | None = None,
        mode: str | None = None,
        on_partial: Callable[[str], Any] | None = None,
    ) -> CodexResult:
        async with self._lock:
            return await self._run_unlocked(prompt, session_id, mode, on_partial)

    async def _run_unlocked(self, prompt, session_id, mode, on_partial) -> CodexResult:
        self._cancel_requested = False
        started = time.time()
        try:
            args = self._build_args(prompt, session_id, mode)
            proc = await asyncio.create_subprocess_exec(
                *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                cwd=str(self.workspace), env=self._env(), limit=STREAM_LIMIT,
            )
        except (OSError, ValueError) as exc:
            return CodexResult(False, "", session_id, error=redact_text(str(exc)))
        self._active_proc = proc
        events: list[dict[str, Any]] = []
        texts: list[str] = []
        try:
            assert proc.stdout
            async for line in _readlines(proc.stdout):
                if not line.strip():
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                events.append(event)
                text = _extract_text(event)
                if text:
                    texts.append(text)
                    if on_partial:
                        result = on_partial(text)
                        if asyncio.iscoroutine(result):
                            await result
            await asyncio.wait_for(proc.wait(), timeout=self.timeout_seconds)
            stderr = await proc.stderr.read() if proc.stderr else b""
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            return CodexResult(
                False, "", _thread_id(events) or session_id, events,
                f"Codex timed out after {self.timeout_seconds}s",
                time.time() - started, -1,
            )
        finally:
            self._active_proc = None
        text = texts[-1].strip() if texts else ""
        thread_id = _thread_id(events) or session_id
        error = None
        if self._cancel_requested:
            error = "cancelled"
        elif proc.returncode != 0:
            error = redact_text(stderr.decode(errors="replace") or f"Codex exited with code {proc.returncode}")
        elif not text:
            error = "Codex returned no agent message"
        return CodexResult(
            error is None, text, thread_id, events, error,
            time.time() - started, proc.returncode,
        )


async def _readlines(stream: asyncio.StreamReader) -> AsyncIterator[str]:
    buf = b""
    while chunk := await stream.read(65536):
        buf += chunk
        while b"\n" in buf:
            line, buf = buf.split(b"\n", 1)
            yield line.decode("utf-8", errors="replace")
    if buf:
        yield buf.decode("utf-8", errors="replace")


def _thread_id(events: list[dict[str, Any]]) -> str | None:
    for event in events:
        if event.get("type") == "thread.started" and isinstance(event.get("thread_id"), str):
            return event["thread_id"]
    return None


def _extract_text(event: dict[str, Any]) -> str:
    if event.get("type") != "item.completed":
        return ""
    item = event.get("item")
    if isinstance(item, dict) and item.get("type") == "agent_message":
        return item.get("text") if isinstance(item.get("text"), str) else ""
    return ""

"""Cursor CLI subprocess client — Chief / control-plane backend.

Execution policy (operator-authorized unrestricted Agent on this VM):
- Never shell=True; argv arrays only.
- Operational sessions use Cursor's default Agent mode (no --mode ask/plan).
- Always --print --trust plus the local unrestricted flag (--force or --yolo).
- Never --sandbox enabled; never a command allowlist that rejects execution.
- approvalMode=unrestricted (Run Everything) via ~/.cursor/cli-config.json.
- Fixed DIALOGUE_OS_ROOT workspace and --resume for persistent sessions.
- Child env is still sanitized: Telegram tokens, Hermes/Browserbase keys,
  passwords and other bridge secrets are never inherited. Unrestricted tools
  do not require copying bridge secrets into prompts.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import subprocess
import time
import uuid
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, AsyncIterator, Callable

from dialogue_os.util.logging import get_logger
from dialogue_os.util.redact import redact_text

log = get_logger("cursor.client")

READ_ONLY_MODES = ("ask", "plan")
FORCE_FLAGS = ("--force", "--yolo")

# Cursor stream-json can emit single lines far larger than asyncio's default
# 64 KiB StreamReader limit (tool results, file contents). Without a higher
# limit, readline() raises: "Separator is found, but chunk is longer than limit"
# and the bridge surfaces that as "Cursor error: …".
STREAM_LIMIT = 16 * 1024 * 1024  # 16 MiB per stream-json line

# Only these variables are forwarded to the Cursor child process. Anything not
# named here (or matched by _ENV_ALLOW_PREFIXES) is dropped, so new bridge
# secrets are excluded by default rather than needing to be blacklisted.
_ENV_ALLOW_EXACT = frozenset(
    {
        "CURSOR_API_KEY",
        "CURSOR_CONFIG_DIR",
        "HOME",
        "USER",
        "LOGNAME",
        "SHELL",
        "PATH",
        "PWD",
        "TMPDIR",
        "TEMP",
        "TMP",
        "LANG",
        "LANGUAGE",
        "TZ",
        "TERM",
        "VIRTUAL_ENV",
        "PYTHONPATH",
        "PYTHONUNBUFFERED",
        "PYTHONDONTWRITEBYTECODE",
        "PYTHONIOENCODING",
        "SSL_CERT_FILE",
        "SSL_CERT_DIR",
        "CURL_CA_BUNDLE",
        "REQUESTS_CA_BUNDLE",
        "NODE_EXTRA_CA_CERTS",
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "NO_PROXY",
        "http_proxy",
        "https_proxy",
        "no_proxy",
    }
)

_ENV_ALLOW_PREFIXES = ("LC_", "XDG_")

_ENV_SECRET_PATTERN = re.compile(
    r"(TOKEN|SECRET|PASSWORD|PASSWD|API[_-]?KEY|APIKEY|CREDENTIAL|PRIVATE[_-]?KEY"
    r"|BEARER|COOKIE|SESSION[_-]?KEY|SIGNING|WEBHOOK|DSN)",
    re.IGNORECASE,
)
_ENV_SECRET_EXEMPT = frozenset({"CURSOR_API_KEY"})

_ENV_NEVER_FORWARD_PREFIXES = ("TELEGRAM_", "HERMES_", "BROWSERBASE_", "AZURE_")
_ENV_NEVER_FORWARD_EXACT = frozenset(
    {
        "DATABASE_PATH",
        "DATABASE_URL",
        "OPENAI_API_KEY",
        "OPENAI_API_BASE",
        "ANTHROPIC_API_KEY",
    }
)


def sanitize_env(
    source: dict[str, str] | None = None,
    *,
    workspace: Path | str | None = None,
    api_key: str | None = None,
) -> dict[str, str]:
    """Build the Cursor child environment from an allowlist.

    Bridge secrets are never inherited; only Cursor auth, PATH/HOME, locale and
    the variables needed for normal project execution survive.
    """
    src = dict(os.environ if source is None else source)
    env: dict[str, str] = {}
    for key, value in src.items():
        if key in _ENV_ALLOW_EXACT or key.startswith(_ENV_ALLOW_PREFIXES):
            env[key] = value

    for key in list(env):
        if key.startswith(_ENV_NEVER_FORWARD_PREFIXES) or key in _ENV_NEVER_FORWARD_EXACT:
            env.pop(key, None)
        elif key not in _ENV_SECRET_EXEMPT and _ENV_SECRET_PATTERN.search(key):
            env.pop(key, None)

    if workspace is not None:
        env["DIALOGUE_OS_ROOT"] = str(workspace)
    env["NO_OPEN_BROWSER"] = "1"
    if api_key:
        env["CURSOR_API_KEY"] = api_key
    return env


def parse_force_flag_from_help(help_text: str) -> str:
    """Pick exactly one unrestricted flag from `agent --help` output.

    Prefer --force when both exist (--yolo is documented as its alias). Never
    return both.
    """
    text = help_text or ""
    has_force = bool(re.search(r"(?:^|\s)-f,\s*--force|--force\b", text))
    has_yolo = bool(re.search(r"--yolo\b", text))
    if has_force:
        return "--force"
    if has_yolo:
        return "--yolo"
    # Installed Cursor CLI historically always exposes one of these; default to
    # the documented primary name so a transient help parse failure does not
    # silently drop unrestricted execution.
    return "--force"


@lru_cache(maxsize=8)
def detect_force_flag(bin_path: str) -> str:
    """Inspect the local agent binary's --help once and cache the result."""
    try:
        proc = subprocess.run(
            [bin_path, "--help"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        help_text = (proc.stdout or "") + "\n" + (proc.stderr or "")
    except (OSError, subprocess.TimeoutExpired) as e:
        log.warning("cursor_help_probe_failed", bin=bin_path, error=str(e))
        help_text = ""
    flag = parse_force_flag_from_help(help_text)
    log.info("cursor_force_flag", bin=bin_path, flag=flag)
    return flag


def ensure_cli_unrestricted(home: Path | None = None) -> Path:
    """Set global CLI approvalMode to unrestricted (Run Everything).

    Project-level cli.json can only configure permissions; approvalMode lives in
    ~/.cursor/cli-config.json. Idempotent.
    """
    root = Path(home) if home is not None else Path.home()
    path = root / ".cursor" / "cli-config.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    data: dict[str, Any] = {}
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8") or "{}")
        except json.JSONDecodeError:
            data = {}
    changed = False
    if data.get("approvalMode") != "unrestricted":
        data["approvalMode"] = "unrestricted"
        changed = True
    sandbox = data.get("sandbox")
    if not isinstance(sandbox, dict):
        sandbox = {}
        data["sandbox"] = sandbox
        changed = True
    if sandbox.get("mode") != "disabled":
        sandbox["mode"] = "disabled"
        changed = True
    # Empty deny / no restrictive allowlist at the global layer.
    perms = data.setdefault("permissions", {})
    if not isinstance(perms, dict):
        perms = {}
        data["permissions"] = perms
        changed = True
    if perms.get("deny"):
        perms["deny"] = []
        changed = True
    allow = perms.get("allow")
    if not isinstance(allow, list) or "Shell(*)" not in allow:
        perms["allow"] = [
            "Shell(*)",
            "Read(**)",
            "Write(**)",
            "WebFetch(*)",
            "Mcp(*)",
        ]
        changed = True
    if changed or not path.exists():
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        log.info("cursor_cli_config_unrestricted", path=str(path))
    return path


@dataclass
class CursorResult:
    ok: bool
    text: str
    session_id: str | None = None
    raw_events: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None
    duration_seconds: float = 0.0
    returncode: int | None = None


class CursorClient:
    def __init__(
        self,
        workspace: Path,
        cli_bin: str = "agent",
        model: str | None = None,
        timeout_seconds: int = 600,
        api_key: str | None = None,
        force_flag: str | None = None,
        allow_read_only_modes: bool = False,
        ensure_unrestricted_config: bool = True,
    ):
        if force_flag is not None and force_flag not in FORCE_FLAGS:
            raise ValueError(f"force_flag must be one of {FORCE_FLAGS}, got {force_flag!r}")
        self.workspace = Path(workspace).resolve()
        self.cli_bin = cli_bin
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.api_key = api_key
        self._force_flag_override = force_flag
        # Operational sessions must run in default Agent mode. ask/plan are
        # opt-in for smoke tests only.
        self.allow_read_only_modes = allow_read_only_modes
        self._lock = asyncio.Lock()
        self._active_proc: asyncio.subprocess.Process | None = None
        self._cancel_requested = False
        if ensure_unrestricted_config:
            try:
                ensure_cli_unrestricted()
            except OSError as e:
                log.warning("cursor_cli_config_update_failed", error=str(e))

    def resolve_bin(self) -> str:
        path = shutil.which(self.cli_bin)
        if path:
            return path
        candidates = [
            Path.home() / ".local" / "bin" / self.cli_bin,
            Path.home() / ".local" / "bin" / "agent",
            Path.home() / ".local" / "bin" / "cursor-agent",
        ]
        for c in candidates:
            if c.exists():
                return str(c)
        raise FileNotFoundError(
            f"Cursor CLI '{self.cli_bin}' not found on PATH or ~/.local/bin"
        )

    def resolve_force_flag(self) -> str:
        if self._force_flag_override:
            return self._force_flag_override
        return detect_force_flag(self.resolve_bin())

    async def create_session(self) -> str:
        bin_path = self.resolve_bin()
        env = self._env()
        proc = await asyncio.create_subprocess_exec(
            bin_path,
            "create-chat",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(self.workspace),
            env=env,
            limit=STREAM_LIMIT,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)
        except asyncio.TimeoutError:
            proc.kill()
            raise TimeoutError("cursor create-chat timed out")
        out = (stdout or b"").decode("utf-8", errors="replace").strip()
        err = (stderr or b"").decode("utf-8", errors="replace").strip()
        if proc.returncode != 0:
            raise RuntimeError(redact_text(f"create-chat failed: {err or out}"))
        session_id = out.splitlines()[-1].strip()
        if not session_id or " " in session_id and len(session_id) < 8:
            raise RuntimeError(redact_text(f"unexpected create-chat output: {out}"))
        return session_id

    def _env(self) -> dict[str, str]:
        return sanitize_env(workspace=self.workspace, api_key=self.api_key)

    def _build_args(self, prompt: str, session_id: str | None, mode: str | None = None) -> list[str]:
        force_flag = self.resolve_force_flag()
        args = [
            self.resolve_bin(),
            "--print",
            "--output-format",
            "stream-json",
            "--workspace",
            str(self.workspace),
            "--trust",
            force_flag,
        ]
        # Unrestricted Agent: no --sandbox, no --mode ask/plan, exactly one of
        # --force/--yolo (never both).
        if "--sandbox" in args:
            raise RuntimeError("sandbox must not be passed to operational Cursor invocations")
        if mode is not None:
            if mode not in READ_ONLY_MODES:
                raise ValueError(
                    f"mode must be None (default Agent mode) or one of {READ_ONLY_MODES}, got {mode!r}"
                )
            if not self.allow_read_only_modes:
                raise ValueError(
                    f"--mode {mode} is disabled for operational sessions; "
                    "construct CursorClient(allow_read_only_modes=True) for read-only smoke tests"
                )
            args.extend(["--mode", mode])
        if self.model:
            args.extend(["--model", self.model])
        if session_id:
            args.extend(["--resume", session_id])
        args.append(prompt)
        # Hard invariants
        assert force_flag in args
        assert "--yolo" not in args or "--force" not in args or force_flag in ("--force", "--yolo")
        if "--force" in args and "--yolo" in args:
            raise RuntimeError("must not pass both --force and --yolo")
        if "--sandbox" in args:
            raise RuntimeError("must not pass --sandbox to unrestricted Agent invocations")
        return args

    async def cancel(self) -> bool:
        """Terminate the active Cursor subprocess immediately.

        Does not acquire the run lock — /cancel must bypass the session queue.
        """
        self._cancel_requested = True
        proc = self._active_proc
        if proc and proc.returncode is None:
            try:
                proc.terminate()
                try:
                    await asyncio.wait_for(proc.wait(), timeout=2)
                except asyncio.TimeoutError:
                    proc.kill()
                    try:
                        await asyncio.wait_for(proc.wait(), timeout=2)
                    except asyncio.TimeoutError:
                        pass
                return True
            except ProcessLookupError:
                return False
        return False

    async def run(
        self,
        prompt: str,
        session_id: str | None = None,
        mode: str | None = None,
        on_partial: Callable[[str], Any] | None = None,
    ) -> CursorResult:
        """Serialize Cursor invocations so concurrent Telegram bots cannot corrupt the session."""
        async with self._lock:
            return await self._run_unlocked(prompt, session_id, mode, on_partial)

    async def _run_unlocked(
        self,
        prompt: str,
        session_id: str | None,
        mode: str | None,
        on_partial: Callable[[str], Any] | None,
    ) -> CursorResult:
        self._cancel_requested = False
        started = time.time()
        try:
            args = self._build_args(prompt, session_id, mode)
        except (ValueError, FileNotFoundError, RuntimeError) as e:
            return CursorResult(ok=False, text="", error=redact_text(str(e)), session_id=session_id)
        force_flag = self.resolve_force_flag()
        log.info(
            "cursor_invoke",
            workspace=str(self.workspace),
            resume=bool(session_id),
            mode=mode or "agent",
            force_flag=force_flag,
            sandbox=False,
        )
        try:
            proc = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self.workspace),
                env=self._env(),
                limit=STREAM_LIMIT,
            )
        except Exception as e:
            return CursorResult(ok=False, text="", error=redact_text(str(e)), session_id=session_id)

        self._active_proc = proc
        events: list[dict[str, Any]] = []
        final_text_parts: list[str] = []
        stderr_chunks: list[bytes] = []

        async def _read_stderr() -> None:
            assert proc.stderr
            while True:
                chunk = await proc.stderr.read(4096)
                if not chunk:
                    break
                stderr_chunks.append(chunk)

        stderr_task = asyncio.create_task(_read_stderr())

        try:
            assert proc.stdout
            async for line in _readlines(proc.stdout):
                if self._cancel_requested:
                    break
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    final_text_parts.append(line)
                    continue
                events.append(event)
                text_delta = _extract_text(event)
                if text_delta:
                    final_text_parts.append(text_delta)
                    if on_partial:
                        maybe = on_partial(text_delta)
                        if asyncio.iscoroutine(maybe):
                            await maybe
            try:
                await asyncio.wait_for(proc.wait(), timeout=self.timeout_seconds)
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                return CursorResult(
                    ok=False,
                    text="",
                    session_id=session_id,
                    raw_events=events,
                    error=f"Cursor timed out after {self.timeout_seconds}s",
                    duration_seconds=time.time() - started,
                    returncode=-1,
                )
        except Exception as e:
            if proc.returncode is None:
                proc.kill()
                await proc.wait()
            return CursorResult(
                ok=False,
                text="",
                session_id=session_id,
                raw_events=events,
                error=redact_text(str(e)),
                duration_seconds=time.time() - started,
            )
        finally:
            self._active_proc = None
            await stderr_task

        stderr_text = b"".join(stderr_chunks).decode("utf-8", errors="replace")
        text = _prefer_final_result(events, final_text_parts)
        resolved_session = _extract_session_id(events) or session_id

        if self._cancel_requested:
            return CursorResult(
                ok=False,
                text=text,
                session_id=resolved_session,
                raw_events=events,
                error="cancelled",
                duration_seconds=time.time() - started,
                returncode=proc.returncode,
            )

        if proc.returncode not in (0, None) and not text:
            return CursorResult(
                ok=False,
                text="",
                session_id=resolved_session,
                raw_events=events,
                error=redact_text(stderr_text or f"Cursor exited with code {proc.returncode}"),
                duration_seconds=time.time() - started,
                returncode=proc.returncode,
            )

        if not text and proc.returncode != 0:
            return CursorResult(
                ok=False,
                text="",
                session_id=resolved_session,
                raw_events=events,
                error=redact_text(stderr_text or "Cursor returned empty result"),
                duration_seconds=time.time() - started,
                returncode=proc.returncode,
            )

        return CursorResult(
            ok=True,
            text=text.strip(),
            session_id=resolved_session,
            raw_events=events,
            duration_seconds=time.time() - started,
            returncode=proc.returncode,
        )


async def _readlines(stream: asyncio.StreamReader) -> AsyncIterator[str]:
    """Read Cursor stream-json stdout without asyncio's 64 KiB line trap.

    Cursor emits one JSON object per line; tool results can be multi-megabyte
    single lines. ``StreamReader.readline()`` then raises
    ``ValueError: Separator is found, but chunk is longer than limit``, which
    the bridge used to surface as ``Cursor error: …``. Reading raw chunks and
    splitting on newlines ourselves avoids that entirely.
    """
    buf = b""
    while True:
        try:
            chunk = await stream.read(65536)
        except Exception:
            break
        if not chunk:
            break
        buf += chunk
        while True:
            idx = buf.find(b"\n")
            if idx < 0:
                break
            line, buf = buf[: idx + 1], buf[idx + 1 :]
            yield line.decode("utf-8", errors="replace")
    if buf:
        yield buf.decode("utf-8", errors="replace")


def _extract_text(event: dict[str, Any]) -> str:
    """Pull useful visible text from stream-json events without dumping chain-of-thought."""
    etype = event.get("type") or event.get("event") or ""
    if etype in ("assistant", "message", "text", "result", "agent_message"):
        if isinstance(event.get("text"), str):
            return event["text"]
        if isinstance(event.get("message"), str):
            return event["message"]
        msg = event.get("message")
        if isinstance(msg, dict):
            content = msg.get("content")
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                parts = []
                for c in content:
                    if isinstance(c, dict) and c.get("type") in ("text", "output_text"):
                        parts.append(c.get("text") or "")
                    elif isinstance(c, str):
                        parts.append(c)
                return "".join(parts)
    if "result" in event and isinstance(event["result"], str):
        return event["result"]
    delta = event.get("delta") or event.get("text_delta")
    if isinstance(delta, str):
        return delta
    return ""


def _prefer_final_result(events: list[dict[str, Any]], parts: list[str]) -> str:
    for event in reversed(events):
        if event.get("type") in ("result", "final", "completed") and isinstance(event.get("result"), str):
            return event["result"]
        if event.get("type") == "assistant" and event.get("done"):
            t = _extract_text(event)
            if t:
                return t
    joined = "".join(parts).strip()
    if joined:
        return joined
    for event in reversed(events):
        t = _extract_text(event)
        if t:
            return t
    return ""


def _extract_session_id(events: list[dict[str, Any]]) -> str | None:
    for event in events:
        for key in ("session_id", "chatId", "chat_id", "id"):
            val = event.get(key)
            if isinstance(val, str) and len(val) >= 8 and ("-" in val or val.isalnum()):
                if key == "id" and event.get("type") not in ("session", "chat", "result"):
                    continue
                return val
        for nest in ("session", "chat", "result"):
            obj = event.get(nest)
            if isinstance(obj, dict):
                for key in ("session_id", "chatId", "chat_id", "id"):
                    val = obj.get(key)
                    if isinstance(val, str) and len(val) >= 8:
                        return val
    return None


def new_run_id() -> str:
    return uuid.uuid4().hex

"""Deterministic mission probes — cheap checks that never call an LLM.

The supervisor runs these on every tick. Codex is only invoked when a probe
(or a specialist message) shows something worth a decision: a stall, a dead
process, a new blocker, a completion claim, or an explicit mention.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PROC_ROOT = Path("/proc")

RUNNING = "running"
SLEEPING = "sleeping"
DISK_SLEEP = "disk_sleep"
STOPPED = "stopped"
ZOMBIE = "zombie"
EXITED = "exited"
UNKNOWN = "unknown"
NONE = "none"

_STATE_MAP = {
    "R": RUNNING,
    "S": SLEEPING,
    "D": DISK_SLEEP,
    "T": STOPPED,
    "t": STOPPED,
    "Z": ZOMBIE,
    "X": EXITED,
    "x": EXITED,
}

ALIVE_STATES = frozenset({RUNNING, SLEEPING, DISK_SLEEP, STOPPED})


@dataclass(frozen=True)
class ProcessProbe:
    pid: int | None
    status: str
    exit_code: int | None = None
    detail: str | None = None

    @property
    def alive(self) -> bool:
        return self.status in ALIVE_STATES

    @property
    def dead(self) -> bool:
        return self.status in (EXITED, ZOMBIE)


def probe_process(pid: int | None, *, proc_root: Path = PROC_ROOT) -> ProcessProbe:
    """Inspect a PID via /proc. No signals are sent, so this is safe to poll."""
    if not pid:
        return ProcessProbe(pid=None, status=NONE)
    stat_path = proc_root / str(pid) / "stat"
    try:
        raw = stat_path.read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return ProcessProbe(pid=pid, status=EXITED, detail="no /proc entry")
    except OSError as e:
        return ProcessProbe(pid=pid, status=UNKNOWN, detail=str(e))

    # comm may contain spaces/parens, so parse after the final ')'.
    try:
        tail = raw[raw.rindex(")") + 2 :]
        state_char = tail.split(None, 1)[0]
    except (ValueError, IndexError):
        return ProcessProbe(pid=pid, status=UNKNOWN, detail="unparsable stat")
    return ProcessProbe(pid=pid, status=_STATE_MAP.get(state_char, UNKNOWN))


def read_exit_code(path: str | os.PathLike[str] | None) -> int | None:
    """Read an exit status a specialist wrote to a sentinel file, if present."""
    if not path:
        return None
    try:
        text = Path(path).read_text(encoding="utf-8").strip()
    except (OSError, ValueError):
        return None
    try:
        return int(text.split()[0])
    except (ValueError, IndexError):
        return None


def state_fingerprint(values: dict[str, Any]) -> str:
    """Stable hash of the observable mission state.

    An unchanged fingerprint means nothing happened since the last inspection,
    so the supervisor can skip the Codex call entirely.
    """
    blob = json.dumps(values, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:32]

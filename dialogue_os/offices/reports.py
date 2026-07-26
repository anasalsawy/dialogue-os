"""Parse specialist office messages into structured supervision reports.

Specialists acknowledge assignments, send heartbeats while working, raise
blockers, and eventually claim completion. This module turns those messages
into deterministic structure so the supervisor can update mission state and
decide whether the change is worth waking Chief.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

ACK = "ack"
HEARTBEAT = "heartbeat"
BLOCKER = "blocker"
CLAIM = "claim"
MESSAGE = "message"

# Values that mean "nothing here" rather than a real blocker/action.
_EMPTY_VALUES = frozenset(
    {"", "none", "n/a", "na", "-", "--", "no", "nope", "nothing", "null", "false"}
)

_FIELD_ALIASES: dict[str, str] = {
    "action": "action",
    "current action": "action",
    "doing": "action",
    "step": "action",
    "current step": "action",
    "tool": "tool",
    "process": "tool",
    "using": "tool",
    "progress": "progress",
    "status": "progress",
    "blocker": "blocker",
    "blocked": "blocker",
    "blocked by": "blocker",
    "next": "next_action",
    "next action": "next_action",
    "next step": "next_action",
    "plan": "plan",
    "initial plan": "plan",
    "pid": "pid",
    "process id": "pid",
    "job": "job_id",
    "job id": "job_id",
    "session": "tool_session_id",
    "tool session": "tool_session_id",
    "browserbase": "browserbase_session_id",
    "browserbase session": "browserbase_session_id",
    "artifact": "artifact",
    "artifacts": "artifact",
    "file": "artifact",
    "files": "artifact",
    "evidence": "evidence",
    "tests": "tests",
    "test output": "tests",
    "exit code": "exit_code",
    "exit status": "exit_code",
    "logs": "logs",
}

_LABEL_RE = re.compile(
    r"^\s*[-*\u2022]?\s*(?P<label>[A-Za-z][A-Za-z /_]{1,20}?)\s*[:=]\s*(?P<value>.*)$"
)
_ACK_RE = re.compile(
    r"\b(ack|acked|acknowledg(?:e|ed|ing)|on it|starting now|taking this)\b", re.IGNORECASE
)
_CLAIM_RE = re.compile(
    r"\b(done|complete|completed|finished|ready for review|task complete|"
    r"mission complete|all set|shipped)\b",
    re.IGNORECASE,
)
_EVIDENCE_HINT_RE = re.compile(
    r"\b(passed|failed|\d+\s+passed|exit code|commit|diff|screenshot|http/\d|"
    r"status\s+\d{3}|\.py|\.md|\.json|\.log|/[\w./-]+)\b",
    re.IGNORECASE,
)


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.strip().strip("`").strip()
    if text.lower() in _EMPTY_VALUES:
        return None
    return text or None


@dataclass
class SpecialistReport:
    kind: str = MESSAGE
    action: str | None = None
    tool: str | None = None
    progress: str | None = None
    blocker: str | None = None
    next_action: str | None = None
    plan: str | None = None
    pid: int | None = None
    job_id: str | None = None
    tool_session_id: str | None = None
    browserbase_session_id: str | None = None
    exit_code: int | None = None
    artifacts: list[str] = field(default_factory=list)
    evidence: dict[str, Any] = field(default_factory=dict)
    raw: str = ""

    @property
    def is_heartbeat(self) -> bool:
        return any((self.action, self.tool, self.progress, self.next_action))

    @property
    def has_evidence(self) -> bool:
        """Anything Chief could independently inspect."""
        if self.artifacts or self.evidence:
            return True
        if self.exit_code is not None:
            return True
        if self.tool_session_id or self.browserbase_session_id:
            return True
        return bool(_EVIDENCE_HINT_RE.search(self.raw))


def _apply(report: SpecialistReport, key: str, value: str | None) -> None:
    cleaned = _clean(value)
    if cleaned is None:
        return
    if key == "pid":
        match = re.search(r"\d+", cleaned)
        if match:
            report.pid = int(match.group())
    elif key == "exit_code":
        match = re.search(r"-?\d+", cleaned)
        if match:
            report.exit_code = int(match.group())
    elif key == "artifact":
        for part in re.split(r"[,\s]+", cleaned):
            if part and part not in report.artifacts:
                report.artifacts.append(part)
    elif key in ("evidence", "tests", "logs"):
        report.evidence[key] = cleaned
    else:
        setattr(report, key, cleaned)


def _parse_json_payload(report: SpecialistReport, text: str) -> None:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return
    try:
        payload = json.loads(match.group())
    except (ValueError, TypeError):
        return
    if not isinstance(payload, dict):
        return
    for raw_key, raw_value in payload.items():
        key = _FIELD_ALIASES.get(str(raw_key).strip().lower())
        if not key:
            continue
        if key == "artifact" and isinstance(raw_value, list):
            for item in raw_value:
                if str(item) not in report.artifacts:
                    report.artifacts.append(str(item))
            continue
        if key in ("evidence", "tests", "logs") and isinstance(raw_value, (dict, list)):
            report.evidence[key] = raw_value
            continue
        _apply(report, key, str(raw_value))


_DONE_VALUES = frozenset({"done", "complete", "completed", "finished"})


def parse_specialist_message(text: str) -> SpecialistReport:
    """Best-effort structured read of a specialist office message."""
    report = SpecialistReport(raw=text or "")
    if not text:
        return report

    prose_lines: list[str] = []
    for line in text.splitlines():
        match = _LABEL_RE.match(line)
        key = None
        if match:
            key = _FIELD_ALIASES.get(match.group("label").strip().lower())
        if key:
            _apply(report, key, match.group("value"))
        else:
            prose_lines.append(line)

    _parse_json_payload(report, text)

    # Classify. A completion claim outranks everything: it opens the gate.
    # Only prose announces completion — "Progress: half done" is not a claim.
    prose = "\n".join(prose_lines)
    claims_done = bool(_CLAIM_RE.search(prose)) or (
        (report.progress or "").strip().lower() in _DONE_VALUES
    )
    first_line = prose.strip().splitlines()[0] if prose.strip() else ""
    if claims_done and not report.blocker:
        report.kind = CLAIM
    elif report.blocker:
        report.kind = BLOCKER
    elif report.plan or _ACK_RE.search(first_line):
        report.kind = ACK
    elif report.is_heartbeat:
        report.kind = HEARTBEAT
    return report

"""Chief-driven mission assignment parsing.

Anas gives Chief a goal in DM. Chief decides the breakdown and emits a
structured ASSIGNMENTS block. The bridge strips that block from the operator
reply, creates one mission per unit, posts each assignment into the matching
office, and starts supervision.

Only Chief decides assignments. This module does not invent departments or
fabricate success — it only parses what Chief emitted.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from dialogue_os.offices.registry import DEPARTMENTS

ASSIGN_START = "<<<ASSIGNMENTS>>>"
ASSIGN_END = "<<<END_ASSIGNMENTS>>>"

# Allow optional whitespace / case folding on the markers.
_BLOCK_RE = re.compile(
    r"<<<ASSIGNMENTS>>>\s*(.*?)\s*<<<END_ASSIGNMENTS>>>",
    re.DOTALL | re.IGNORECASE,
)

CHIEF_ASSIGN_INSTRUCTIONS = """
OFFICE ASSIGNMENT PROTOCOL (you are Chief — you decide assignments):
- The operator gives goals. You decompose into units and assign each unit to
  exactly one department office.
- Departments: builder, researcher, operations, growth, customer_relations,
  stagehand (watcher_alpha / watcher_beta only when a watcher office is needed).
- One specialist per office. Do not assign two departments to the same unit.
- When the operator asks for work that needs specialists, include BOTH:
  1) your normal reply to the operator (plan / what you assigned), and
  2) this exact machine block at the end of your reply (JSON array, no markdown fence):

<<<ASSIGNMENTS>>>
[{"department":"researcher","title":"short title","brief":"clear unit brief"},{"department":"builder","title":"short title","brief":"clear unit brief"}]
<<<END_ASSIGNMENTS>>>

- Omit the ASSIGNMENTS block entirely for pure Q&A, status, or infra chat with
  no specialist work to dispatch.
- Never claim a mission succeeded in the ASSIGNMENTS block. Briefs are work
  orders only.
""".strip()


@dataclass(frozen=True)
class AssignmentUnit:
    department: str
    brief: str
    title: str | None = None
    acceptance_criteria: str | None = None


def parse_and_strip_assignments(text: str) -> tuple[str, list[AssignmentUnit]]:
    """Return (operator_visible_text, units).

    Supports:
    - Trailing <<<ASSIGNMENTS>>> ... <<<END_ASSIGNMENTS>>> block
    - Whole-message JSON: {"text": "...", "assignments": [...]}
    """
    raw = text or ""
    units: list[AssignmentUnit] = []

    # Whole-message JSON with assignments (optional).
    stripped = raw.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        try:
            obj = json.loads(stripped)
        except json.JSONDecodeError:
            obj = None
        if isinstance(obj, dict) and "assignments" in obj:
            units = _coerce_units(obj.get("assignments"))
            visible = str(obj.get("text") or obj.get("reply") or "").strip()
            return visible, units

    match = _BLOCK_RE.search(raw)
    if not match:
        return raw.strip(), []

    payload = match.group(1).strip()
    units = _parse_payload(payload)
    visible = (raw[: match.start()] + raw[match.end() :]).strip()
    return visible, units


def _parse_payload(payload: str) -> list[AssignmentUnit]:
    if not payload:
        return []
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        # Try to recover a JSON array substring.
        start = payload.find("[")
        end = payload.rfind("]")
        if start < 0 or end <= start:
            return []
        try:
            data = json.loads(payload[start : end + 1])
        except json.JSONDecodeError:
            return []
    return _coerce_units(data)


def _coerce_units(data: object) -> list[AssignmentUnit]:
    if not isinstance(data, list):
        return []
    out: list[AssignmentUnit] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        department = str(item.get("department") or "").strip().lower()
        brief = str(item.get("brief") or item.get("assignment") or "").strip()
        title_raw = item.get("title")
        title = str(title_raw).strip() if title_raw else None
        criteria_raw = item.get("acceptance_criteria") or item.get("criteria")
        criteria = str(criteria_raw).strip() if criteria_raw else None
        if department not in DEPARTMENTS:
            continue
        if not brief:
            continue
        out.append(
            AssignmentUnit(
                department=department,
                brief=brief,
                title=title or None,
                acceptance_criteria=criteria or None,
            )
        )
    return out

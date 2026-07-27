"""Active-mission supervisor.

Chief assigns work and then stays involved. For every active mission this
service keeps a durable supervision record, runs cheap deterministic probes on
a task-aware cadence, and wakes Chief only when something meaningful happened:
a missing acknowledgement, a stale heartbeat, a dead process, a new blocker, a
completion claim, or an explicit request.

Two rules shape the design:

* No Codex invocation is left sleeping. The next supervision time lives in
  SQLite, so a bridge restart or VM reboot resumes the loop on schedule.
* Nothing is ever inferred into existence. If a probe cannot show progress,
  the mission does not look like it progressed.
"""

from __future__ import annotations

import asyncio
import re
import time
from dataclasses import dataclass, field
from typing import Awaitable, Callable

from dialogue_os.offices import missions as m
from dialogue_os.offices import probes
from dialogue_os.offices.missions import Mission, MissionTracker
from dialogue_os.offices.reports import (
    ACK,
    BLOCKER,
    CLAIM,
    HEARTBEAT,
    SpecialistReport,
    parse_specialist_message,
)
from dialogue_os.offices.supervision import (
    FAST,
    NORMAL,
    REJECTED,
    SLOW,
    SupervisionState,
    SupervisionStore,
    UNVERIFIED,
    VERIFIED,
    VERIFYING,
)
from dialogue_os.util.logging import get_logger
from dialogue_os.util.redact import redact_text

log = get_logger("offices.supervisor")

# Finding kinds — each one is a reason to spend a Codex invocation.
MISSING_ACK = "missing_acknowledgement"
STALE_HEARTBEAT = "stale_heartbeat"
PROCESS_EXITED = "process_exited"
PROCESS_STUCK = "process_stuck"
BLOCKER_RAISED = "blocker_raised"
COMPLETION_CLAIM = "completion_claim"
UNSUPPORTED_CLAIM = "unsupported_claim"
EXPLICIT_REQUEST = "explicit_request"

_VERDICT_RE = re.compile(r"\bVERDICT\s*[:=]\s*(VERIFIED|REJECTED)\b", re.IGNORECASE)

PostMessage = Callable[[int, str], Awaitable[None]]
NotifyOwner = Callable[[str], Awaitable[None]]
NotifyWatcher = Callable[[str, str, str], Awaitable[None]]


@dataclass(frozen=True)
class Finding:
    kind: str
    detail: str
    severity: str = "warning"


@dataclass
class SupervisionOutcome:
    mission_id: str
    findings: list[Finding] = field(default_factory=list)
    cursor_invoked: bool = False
    posted: bool = False
    skipped: str | None = None
    next_check_at: float | None = None

    @property
    def finding_kinds(self) -> list[str]:
        return [f.kind for f in self.findings]


class MissionSupervisor:
    def __init__(
        self,
        *,
        missions: MissionTracker,
        supervision: SupervisionStore,
        control,
        post_office_message: PostMessage,
        notify_owner: NotifyOwner | None = None,
        notify_watcher: NotifyWatcher | None = None,
        tick_interval: float = 15.0,
        ack_timeout: float = 300.0,
        heartbeat_timeout: float = 600.0,
        owner_update_interval: float = 1800.0,
        max_unsupported_claims: int = 2,
        watcher_agent_id: str = "watcher_alpha",
        ingest_dedupe_window: float = 120.0,
        proc_root=probes.PROC_ROOT,
    ):
        self.missions = missions
        self.supervision = supervision
        self.control = control
        self.post_office_message = post_office_message
        self.notify_owner = notify_owner
        self.notify_watcher = notify_watcher
        self.tick_interval = tick_interval
        self.ack_timeout = ack_timeout
        self.heartbeat_timeout = heartbeat_timeout
        self.owner_update_interval = owner_update_interval
        self.max_unsupported_claims = max_unsupported_claims
        self.watcher_agent_id = watcher_agent_id
        self.ingest_dedupe_window = ingest_dedupe_window
        self.proc_root = proc_root

    # ---------------------------------------------------------------- loop

    async def run_forever(self) -> None:
        while True:
            await asyncio.sleep(self.tick_interval)
            try:
                await self.tick()
            except asyncio.CancelledError:
                raise
            except Exception as e:
                log.error("supervisor_tick_failed", error=redact_text(str(e)))

    async def tick(self, now: float | None = None) -> list[SupervisionOutcome]:
        """Inspect every mission whose persisted next_check_at has passed."""
        now = now if now is not None else time.time()
        due = await self.supervision.due(m.OPEN_STATUSES, now=now)
        outcomes = []
        for mission_id in due:
            try:
                outcomes.append(await self.inspect(mission_id, reason="scheduled", now=now))
            except asyncio.CancelledError:
                raise
            except Exception as e:
                log.error(
                    "supervisor_inspect_failed",
                    mission_id=mission_id,
                    error=redact_text(str(e)),
                )
        return outcomes

    # ------------------------------------------------------------ ingress

    async def on_mission_assigned(
        self, mission: Mission, *, process_id: int | None = None
    ) -> SupervisionState:
        """Start supervising as soon as Chief posts the assignment."""
        state = await self.supervision.ensure(mission.mission_id, cadence=NORMAL)
        await self.supervision.update(
            mission.mission_id,
            current_step="awaiting acknowledgement",
            next_expected_action="specialist acknowledges and states initial plan",
            process_id=process_id,
        )
        await self.supervision.schedule_next(mission.mission_id, cadence=NORMAL)
        return state

    async def on_specialist_message(
        self,
        mission: Mission,
        *,
        text: str,
        specialist_agent_id: str | None = None,
        telegram_message_id: int | None = None,
        now: float | None = None,
    ) -> SupervisionOutcome:
        """Record a specialist message and inspect immediately when it matters."""
        now = now if now is not None else time.time()
        report = parse_specialist_message(text)
        specialist_agent_id = specialist_agent_id or mission.specialist_agent_id
        mission_id = mission.mission_id

        # The same specialist message can reach us twice: once as the reply we
        # generated and once as the Telegram copy Chief's poller sees. Count it
        # once so heartbeats and claims are not double-recorded.
        existing = await self.supervision.ensure(mission_id)
        digest = probes.state_fingerprint({"text": text or ""})
        last_digest = existing.meta.get("last_ingest_digest")
        last_at = existing.meta.get("last_ingest_at") or 0
        if digest == last_digest and now - float(last_at) < self.ingest_dedupe_window:
            return SupervisionOutcome(mission_id, skipped="duplicate_message")

        updates: dict = {
            "meta": {**existing.meta, "last_ingest_digest": digest, "last_ingest_at": now},
            "last_specialist_message": (text or "")[:4000],
            "last_specialist_message_at": now,
        }
        if report.pid is not None:
            updates["process_id"] = report.pid
        if report.job_id:
            updates["job_id"] = report.job_id
        if report.tool_session_id:
            updates["tool_session_id"] = report.tool_session_id
        if report.browserbase_session_id:
            updates["browserbase_session_id"] = report.browserbase_session_id
        if report.exit_code is not None:
            updates["process_exit_code"] = report.exit_code

        if report.is_heartbeat:
            updates.update(
                last_heartbeat_at=now,
                missed_heartbeats=0,
                heartbeat_action=report.action,
                heartbeat_tool=report.tool,
                heartbeat_progress=report.progress,
                heartbeat_next_action=report.next_action,
            )
            if report.action:
                updates["current_step"] = report.action
            if report.next_action:
                updates["next_expected_action"] = report.next_action

        if report.kind == ACK and not existing.acknowledged:
            updates.update(
                acknowledged=True,
                acknowledged_at=now,
                acknowledgement_text=(text or "")[:2000],
                initial_plan=report.plan,
            )
            if report.plan:
                updates["current_step"] = report.plan
            mission = await self._safe_transition(mission, m.ACKNOWLEDGED, specialist_agent_id)

        if report.blocker:
            updates["blocker"] = report.blocker
            mission = await self._safe_transition(mission, m.BLOCKED, specialist_agent_id)
        elif report.kind in (HEARTBEAT, CLAIM) and mission.status in (
            m.ASSIGNED,
            m.ACKNOWLEDGED,
            m.BLOCKED,
            m.WAITING,
        ):
            updates["blocker"] = None
            mission = await self._safe_transition(mission, m.WORKING, specialist_agent_id)

        await self.supervision.update(mission_id, **updates)
        for artifact in report.artifacts:
            await self.supervision.add_artifact(
                mission_id, kind="file", path=artifact, detail=report.progress
            )
        await self.missions.add_event(
            mission_id,
            f"specialist:{report.kind}",
            actor_agent_id=specialist_agent_id,
            text=text,
            evidence={"artifacts": report.artifacts, **report.evidence},
            telegram_message_id=telegram_message_id,
        )

        if report.kind == CLAIM:
            return await self._handle_claim(mission, report, now=now)

        reason = "blocker" if report.blocker else f"specialist:{report.kind}"
        # A plain heartbeat is recorded deterministically; Chief is not woken
        # for it unless an inspection finds something wrong.
        return await self.inspect(mission_id, reason=reason, now=now)

    async def request_check(self, mission_id: str, *, reason: str = "owner_request"):
        """Force an immediate Chief inspection (owner `/check`)."""
        return await self.inspect(mission_id, reason=reason, force=True, ignore_pause=True)

    # ---------------------------------------------------------- inspection

    async def inspect(
        self,
        mission_id: str,
        *,
        reason: str = "scheduled",
        force: bool = False,
        ignore_pause: bool = False,
        now: float | None = None,
    ) -> SupervisionOutcome:
        now = now if now is not None else time.time()
        mission = await self.missions.get(mission_id)
        if mission is None:
            return SupervisionOutcome(mission_id, skipped="unknown_mission")
        if not mission.is_open:
            return SupervisionOutcome(mission_id, skipped="mission_closed")

        state = await self.supervision.ensure(mission_id)
        if state.paused and not ignore_pause:
            return SupervisionOutcome(mission_id, skipped="paused")

        probe = probes.probe_process(state.process_id, proc_root=self.proc_root)
        state = await self._record_probe(mission_id, state, probe)

        findings = self._collect_findings(mission, state, probe, now=now, reason=reason)
        fingerprint = probes.state_fingerprint(
            {
                "status": mission.status,
                "step": state.current_step,
                "heartbeat_at": state.last_heartbeat_at,
                "specialist_at": state.last_specialist_message_at,
                "blocker": state.blocker,
                "process": probe.status,
                "exit_code": state.process_exit_code,
                "findings": sorted(f.kind for f in findings),
            }
        )
        unchanged = fingerprint == state.state_fingerprint

        outcome = SupervisionOutcome(mission_id, findings=findings)

        if not findings and unchanged and not force:
            # Nothing changed and nothing is wrong: do not spend a Codex call.
            state = await self.supervision.update(
                mission_id,
                last_checked_at=now,
                consecutive_no_change=state.consecutive_no_change + 1,
                state_fingerprint=fingerprint,
            )
            outcome.next_check_at = await self.supervision.schedule_next(
                mission_id, cadence=self._cadence_for(mission, state, probe)
            )
            await self._maybe_owner_update(mission, state, now=now)
            return outcome

        await self._escalate(mission, state, findings, now=now)

        decision_text = await self._ask_chief(mission, state, probe, findings, reason=reason)
        outcome.cursor_invoked = True
        if decision_text:
            try:
                await self.post_office_message(mission.office_chat_id, decision_text)
                outcome.posted = True
            except Exception as e:
                log.error(
                    "supervisor_post_failed", mission_id=mission_id, error=redact_text(str(e))
                )
            await self.missions.add_event(
                mission_id,
                "chief_supervision",
                actor_agent_id=m.CHIEF_AGENT_ID,
                text=decision_text,
                evidence={"reason": reason, "findings": outcome.finding_kinds},
            )

        if mission.status in (m.COMPLETION_CLAIMED, m.VERIFYING):
            await self._apply_verdict(mission, decision_text, now=now)

        state = await self.supervision.update(
            mission_id,
            last_checked_at=now,
            last_cursor_invocation_at=now,
            consecutive_no_change=0,
            state_fingerprint=fingerprint,
        )
        outcome.next_check_at = await self.supervision.schedule_next(
            mission_id, cadence=self._cadence_for(mission, state, probe)
        )
        await self._maybe_owner_update(mission, state, now=now)
        log.info(
            "supervision_inspected",
            mission_id=mission_id,
            reason=reason,
            findings=outcome.finding_kinds,
            posted=outcome.posted,
        )
        return outcome

    # ------------------------------------------------------------ helpers

    def _collect_findings(
        self,
        mission: Mission,
        state: SupervisionState,
        probe: probes.ProcessProbe,
        *,
        now: float,
        reason: str,
    ) -> list[Finding]:
        findings: list[Finding] = []

        if mission.status == m.ASSIGNED and not state.acknowledged:
            waited = now - (mission.updated_at or now)
            if waited >= self.ack_timeout:
                findings.append(
                    Finding(
                        MISSING_ACK,
                        f"No acknowledgement after {int(waited // 60)} minutes.",
                    )
                )

        if mission.status in m.ACTIVE_STATUSES:
            reference = (
                state.last_heartbeat_at
                or state.last_specialist_message_at
                or state.acknowledged_at
                or mission.updated_at
                or now
            )
            silence = now - reference
            if silence >= self.heartbeat_timeout:
                findings.append(
                    Finding(
                        STALE_HEARTBEAT,
                        f"No heartbeat for {int(silence // 60)} minutes.",
                    )
                )

        if state.process_id and probe.dead:
            exit_detail = (
                f"exit code {state.process_exit_code}"
                if state.process_exit_code is not None
                else "exit code unavailable"
            )
            findings.append(
                Finding(
                    PROCESS_EXITED,
                    f"Process {state.process_id} is {probe.status} ({exit_detail}).",
                    severity="critical",
                )
            )
        elif (
            state.process_id
            and probe.status == probes.STOPPED
        ):
            findings.append(
                Finding(PROCESS_STUCK, f"Process {state.process_id} is stopped.")
            )

        if state.blocker:
            findings.append(
                Finding(
                    BLOCKER_RAISED,
                    f"Blocker: {state.blocker}",
                    severity="critical" if state.blocker_requires_owner else "warning",
                )
            )

        if mission.status in (m.COMPLETION_CLAIMED, m.VERIFYING):
            findings.append(
                Finding(COMPLETION_CLAIM, "Completion claimed; evidence must be verified.")
            )
        if state.unsupported_claims >= self.max_unsupported_claims:
            findings.append(
                Finding(
                    UNSUPPORTED_CLAIM,
                    f"{state.unsupported_claims} unsupported completion claims.",
                    severity="critical",
                )
            )
        if reason not in ("scheduled",) and not findings:
            findings.append(Finding(EXPLICIT_REQUEST, f"Immediate inspection: {reason}", "info"))
        return findings

    async def _record_probe(
        self, mission_id: str, state: SupervisionState, probe: probes.ProcessProbe
    ) -> SupervisionState:
        if probe.status == probes.NONE and state.process_status is None:
            return state
        updates: dict = {"process_status": probe.status}
        if probe.dead and state.process_status not in (probes.EXITED, probes.ZOMBIE):
            await self.supervision.add_log(
                mission_id,
                f"process {probe.pid} {probe.status} ({probe.detail or 'observed by supervisor'})",
                level="error",
                source="probe",
            )
        return await self.supervision.update(mission_id, **updates)

    def _cadence_for(
        self, mission: Mission, state: SupervisionState, probe: probes.ProcessProbe
    ) -> str:
        if mission.status in (m.WAITING, m.BLOCKED):
            return SLOW
        if probe.alive:
            return FAST
        if mission.status in (m.COMPLETION_CLAIMED, m.VERIFYING):
            return FAST
        if state.consecutive_no_change >= 5:
            return SLOW
        return NORMAL

    # A specialist that starts reporting has demonstrably received the
    # assignment, so the lifecycle may step through the states it skipped.
    _IMPLIED_PATH: dict[str, tuple[str, ...]] = {
        m.WORKING: (m.ACKNOWLEDGED, m.WORKING),
        m.COMPLETION_CLAIMED: (m.ACKNOWLEDGED, m.WORKING, m.COMPLETION_CLAIMED),
        m.BLOCKED: (m.ACKNOWLEDGED, m.BLOCKED),
    }

    async def _safe_transition(
        self, mission: Mission, to_status: str, actor: str | None
    ) -> Mission:
        if mission.status == to_status:
            return mission
        for step in self._transition_path(mission.status, to_status):
            try:
                mission = await self.missions.transition(
                    mission.mission_id, step, actor_agent_id=actor
                )
            except m.MissionError as e:
                log.warning(
                    "supervision_transition_skipped",
                    mission_id=mission.mission_id,
                    to=step,
                    error=str(e),
                )
                break
        return mission

    def _transition_path(self, from_status: str, to_status: str) -> tuple[str, ...]:
        if to_status in m.TRANSITIONS.get(from_status, frozenset()):
            return (to_status,)
        path = self._IMPLIED_PATH.get(to_status, (to_status,))
        return tuple(step for step in path if step != from_status)

    # ------------------------------------------------------- completion gate

    async def _handle_claim(
        self, mission: Mission, report: SpecialistReport, *, now: float
    ) -> SupervisionOutcome:
        """A "done" message is only a claim; Chief must verify it independently."""
        mission_id = mission.mission_id
        if mission.status != m.COMPLETION_CLAIMED:
            mission = await self._safe_transition(
                mission, m.COMPLETION_CLAIMED, mission.specialist_agent_id
            )
            if mission.status == m.COMPLETION_CLAIMED:
                await self.missions.record_claim(mission_id, report.raw[:4000])
            else:
                log.warning("claim_not_recorded", mission_id=mission_id, status=mission.status)

        evidence = {
            "artifacts": report.artifacts,
            "exit_code": report.exit_code,
            "tool_session_id": report.tool_session_id,
            "browserbase_session_id": report.browserbase_session_id,
            **report.evidence,
        }
        updates: dict = {
            "completion_claimed_at": now,
            "completion_evidence": evidence,
            "verification_status": UNVERIFIED,
            "current_step": "completion claimed; awaiting Chief verification",
            "next_expected_action": "Chief inspects evidence",
        }
        if not report.has_evidence:
            state = await self.supervision.get(mission_id)
            updates["unsupported_claims"] = (state.unsupported_claims if state else 0) + 1
            await self.supervision.add_log(
                mission_id,
                "completion claim contained no inspectable evidence",
                level="warning",
                source="supervisor",
            )
        await self.supervision.update(mission_id, **updates)
        return await self.inspect(mission_id, reason="completion_claim", force=True, now=now)

    async def _apply_verdict(
        self, mission: Mission, decision_text: str | None, *, now: float
    ) -> None:
        """Only an explicit Chief verdict moves a mission out of the gate."""
        mission_id = mission.mission_id
        match = _VERDICT_RE.search(decision_text or "")
        if not match:
            # No verdict means no verification. The mission stays in the gate.
            await self.supervision.update(mission_id, verification_status=VERIFYING)
            if mission.status == m.COMPLETION_CLAIMED:
                await self._safe_transition(mission, m.VERIFYING, m.CHIEF_AGENT_ID)
            return

        verified = match.group(1).upper() == "VERIFIED"
        try:
            await self.missions.verify_completion(
                mission_id,
                verified=verified,
                verification=decision_text or "",
                final_report=decision_text if verified else None,
            )
        except m.MissionError as e:
            log.warning("verification_failed", mission_id=mission_id, error=str(e))
            return

        if verified:
            await self.supervision.update(
                mission_id,
                verification_status=VERIFIED,
                verification_notes=decision_text,
                verified_at=now,
                current_step="verified complete",
                next_expected_action=None,
            )
            if self.notify_owner:
                await self.notify_owner(
                    f"Mission {mission_id[:8]} ({mission.department}) verified complete by Chief.\n"
                    f"{(decision_text or '').strip()[:1500]}"
                )
        else:
            state = await self.supervision.get(mission_id)
            await self.supervision.update(
                mission_id,
                verification_status=REJECTED,
                verification_notes=decision_text,
                unsupported_claims=(state.unsupported_claims if state else 0) + 1,
                current_step="verification rejected; back to work",
            )

    # -------------------------------------------------------- escalation

    async def _escalate(
        self,
        mission: Mission,
        state: SupervisionState,
        findings: list[Finding],
        *,
        now: float,
    ) -> None:
        kinds = {f.kind for f in findings}

        if MISSING_ACK in kinds:
            await self.supervision.update(
                mission.mission_id, ack_followups=state.ack_followups + 1
            )
        if STALE_HEARTBEAT in kinds:
            await self.supervision.update(
                mission.mission_id, missed_heartbeats=state.missed_heartbeats + 1
            )
        if PROCESS_EXITED in kinds:
            await self.supervision.add_log(
                mission.mission_id,
                f"process {state.process_id} exited; collecting status and logs",
                level="error",
                source="supervisor",
            )

        if UNSUPPORTED_CLAIM in kinds and self.notify_watcher:
            await self.notify_watcher(
                self.watcher_agent_id,
                (
                    f"Mission {mission.mission_id[:8]} ({mission.department}, "
                    f"specialist={mission.specialist_agent_id}) has made "
                    f"{state.unsupported_claims} completion claims without inspectable evidence."
                ),
                "critical",
            )

        if state.blocker and state.blocker_requires_owner and self.notify_owner:
            await self.notify_owner(
                f"Mission {mission.mission_id[:8]} ({mission.department}) is blocked and needs you.\n"
                f"Required: {state.blocker}"
            )
            await self.supervision.update(mission.mission_id, last_owner_update_at=now)

    async def _maybe_owner_update(
        self, mission: Mission, state: SupervisionState, *, now: float
    ) -> None:
        """Meaningful progress updates during long tasks, not only a final report."""
        if not self.notify_owner or mission.status not in m.ACTIVE_STATUSES:
            return
        last = state.last_owner_update_at or state.created_at or now
        if now - last < self.owner_update_interval:
            return
        await self.notify_owner(self.progress_digest(mission, state))
        await self.supervision.update(mission.mission_id, last_owner_update_at=now)

    def progress_digest(self, mission: Mission, state: SupervisionState) -> str:
        """Observed facts only — never a manufactured sense of progress."""
        lines = [
            f"Mission {mission.mission_id[:8]} — {mission.department} "
            f"({mission.specialist_agent_id}) — {mission.status}",
            f"Step: {state.current_step or 'unknown'}",
        ]
        if state.heartbeat_progress:
            lines.append(f"Reported progress: {state.heartbeat_progress}")
        if state.last_heartbeat_at:
            mins = int((time.time() - state.last_heartbeat_at) // 60)
            lines.append(f"Last heartbeat: {mins} min ago")
        else:
            lines.append("Last heartbeat: none received")
        if state.process_id:
            lines.append(f"Process {state.process_id}: {state.process_status or 'unknown'}")
        if state.blocker:
            lines.append(f"Blocker: {state.blocker}")
        if state.next_expected_action:
            lines.append(f"Next expected: {state.next_expected_action}")
        lines.append(f"Messages used: {mission.messages_used}/{mission.message_budget}")
        return "\n".join(lines)

    # ------------------------------------------------------------- prompt

    async def _ask_chief(
        self,
        mission: Mission,
        state: SupervisionState,
        probe: probes.ProcessProbe,
        findings: list[Finding],
        *,
        reason: str,
    ) -> str | None:
        prompt = await self.build_prompt(mission, state, probe, findings, reason=reason)
        try:
            decision = await self.control.chief_direct(prompt)
        except Exception as e:
            log.error(
                "supervision_cursor_failed",
                mission_id=mission.mission_id,
                error=redact_text(str(e)),
            )
            return None
        if not getattr(decision, "ok", False):
            return None
        if getattr(decision, "action", "respond") == "silent":
            return None
        return getattr(decision, "text", None) or None

    async def build_prompt(
        self,
        mission: Mission,
        state: SupervisionState,
        probe: probes.ProcessProbe,
        findings: list[Finding],
        *,
        reason: str,
    ) -> str:
        logs = await self.supervision.recent_logs(mission.mission_id)
        artifacts = await self.supervision.artifacts(mission.mission_id, limit=20)

        lines = [
            "MISSION SUPERVISION (automated supervisor event, not a human message).",
            f"Trigger: {reason}",
            "",
            f"Mission: {mission.mission_id}",
            f"Department: {mission.department} | Office chat: {mission.office_chat_id}",
            f"Specialist: {mission.specialist_agent_id}",
            f"Status: {mission.status}",
            f"Title: {mission.title or '(untitled)'}",
            f"Assignment: {(mission.assignment_text or '')[:800]}",
            f"Current step: {state.current_step or 'unknown'}",
            f"Acknowledged: {state.acknowledged} "
            f"(follow-ups sent: {state.ack_followups})",
            f"Initial plan: {state.initial_plan or 'none recorded'}",
            f"Last specialist message: {(state.last_specialist_message or 'none')[:600]}",
            f"Last heartbeat: {self._ago(state.last_heartbeat_at)} "
            f"(missed: {state.missed_heartbeats})",
            f"Heartbeat action: {state.heartbeat_action or 'none'}",
            f"Heartbeat tool: {state.heartbeat_tool or 'none'}",
            f"Heartbeat progress: {state.heartbeat_progress or 'none'}",
            f"Process: pid={state.process_id or 'none'} status={probe.status} "
            f"exit_code={state.process_exit_code}",
            f"Job id: {state.job_id or 'none'}",
            f"Tool session: {state.tool_session_id or 'none'}",
            f"Browserbase session: {state.browserbase_session_id or 'none'}",
            f"Blocker: {state.blocker or 'none'}",
            f"Next expected action: {state.next_expected_action or 'unknown'}",
            f"Message budget: {mission.messages_used}/{mission.message_budget}",
            f"Unsupported claims so far: {state.unsupported_claims}",
            f"Verification status: {state.verification_status}",
        ]

        if artifacts:
            lines.append("Artifacts:")
            lines.extend(
                f"  - {a['kind']}: {a.get('path') or a.get('detail') or ''}" for a in artifacts
            )
        if logs:
            lines.append("Recent logs:")
            lines.extend(f"  [{entry['level']}] {entry['message']}" for entry in logs)
        if state.completion_evidence:
            lines.append(f"Claimed evidence: {state.completion_evidence}")

        lines.append("")
        lines.append("Findings:")
        lines.extend(f"  - [{f.severity}] {f.kind}: {f.detail}" for f in findings)
        lines.append("")
        lines.append(self._instructions(mission, findings))
        return "\n".join(lines)

    def _instructions(self, mission: Mission, findings: list[Finding]) -> str:
        kinds = {f.kind for f in findings}
        parts = [
            "Act as Chief supervising this mission inside the department office.",
            "Post a short, direct message to the specialist (and to Anas when a "
            "decision is needed from him). Do not manufacture progress; if a fact "
            "is not in the evidence above, treat it as unknown.",
        ]
        if MISSING_ACK in kinds:
            parts.append(
                "The specialist has not acknowledged. Ask for an explicit "
                "acknowledgement plus its initial plan."
            )
        if STALE_HEARTBEAT in kinds:
            parts.append(
                "Heartbeats have stopped. Ask what it is doing right now, which "
                "tool/process it is using, and what the next action is."
            )
        if PROCESS_EXITED in kinds:
            parts.append(
                "The process is gone. Ask for exit status and logs, then decide: "
                "retry, redirect, or reassign."
            )
        if PROCESS_STUCK in kinds:
            parts.append(
                "The process appears stuck. Diagnose, then redirect, retry, or reassign."
            )
        if BLOCKER_RAISED in kinds:
            parts.append(
                "A blocker is open. If it needs Anas, state the exact decision or "
                "credential required. Otherwise unblock the specialist."
            )
        if UNSUPPORTED_CLAIM in kinds:
            parts.append(
                "This specialist has repeatedly claimed progress without evidence. "
                "Demand concrete evidence and note the pattern."
            )
        if COMPLETION_CLAIM in kinds:
            parts.append(
                "COMPLETION GATE: the specialist's message is only a claim. "
                "Independently inspect appropriate evidence (files/diffs, test "
                "output, service health, process exit status, logs, API results, "
                "Browserbase session, screenshots, Telegram delivery, produced "
                "artifacts) before accepting it. "
                "End your reply with exactly one line: 'VERDICT: VERIFIED' or "
                "'VERDICT: REJECTED'. Omit the verdict line if you still need to "
                "inspect something — the mission will stay in verification."
            )
        return "\n".join(parts)

    @staticmethod
    def _ago(ts: float | None) -> str:
        if not ts:
            return "never"
        return f"{int((time.time() - ts) // 60)} min ago"

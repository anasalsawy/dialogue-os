# Persistence and Cognition Interlock Specification

**Status:** Normative runtime addendum to the Communication Governor specification  
**Supersedes:** Any interpretation of retry, loop, silence, rate, or budget controls that would terminate a mission merely because one attempt or resource path was stopped.

---

## 1. Purpose

The Communication Governor controls who may speak and where messages may travel.

That is necessary but insufficient.

An agent can remain inside a model or tool-calling loop even when every outbound message is blocked. In that state, the Room stays quiet while tokens, tool calls, and provider spend continue.

The runtime therefore requires a second hard-control layer: the **Cognition Interlock**.

The combined architecture is:

```text
Chief decides strategy and authority
        ↓
Mission Supervisor preserves continuity
        ↓
Communication Governor controls delivery
        ↓
Cognition Interlock controls invocation and execution
        ↓
Models, tools, schedulers, queues, and transports
```

The governing principle is:

> Containment must stop waste. Continuity must preserve the mission.

---

## 2. Non-Negotiable Distinction

The runtime must maintain separate state for:

```text
MISSION STATE
ATTEMPT STATE
AGENT COMMUNICATION STATE
AGENT EXECUTION STATE
TRANSPORT STATE
RESOURCE/BUDGET STATE
```

A failure or restriction in one state must not silently overwrite the others.

Examples:

```text
Attempt = FAILED
Mission = ACTIVE

Communication = SILENCED
Mission = ACTIVE

Provider = RATE_LIMITED
Mission = WAITING_WITH_RESUME_TRIGGER

Budget = PAUSED
Mission = ACTIVE_PENDING_RESOURCE_DECISION

Tool = EXHAUSTED
Mission = REPLAN_REQUIRED
```

`MISSION_FAILED` is never inferred automatically from `ATTEMPT_FAILED`, `SILENCED`, `RATE_LIMITED`, `BUDGET_PAUSED`, `LOOP_INTERRUPTED`, or `TOOL_FAILED`.

---

## 3. Required Components

### 3.1 Communication Governor

Enforces:

- sender and recipient authority;
- mission activation;
- communication routes and leases;
- hard silence;
- message budgets;
- duplicate and storm control;
- transport delivery;
- audit logging.

### 3.2 Cognition Interlock

Enforces:

- whether a profile may be invoked;
- whether an active model run may continue;
- whether a tool call may start or continue;
- whether a scheduled retry may fire;
- whether a queued event may be delivered;
- whether a run must be checkpointed, suspended, cancelled, or resumed.

### 3.3 Mission Continuity Supervisor

May be implemented inside the Chief runtime or a deterministic mission service, but it must preserve:

- objective;
- owner;
- task tree;
- evidence;
- checkpoints;
- methods attempted;
- method-specific retry counts;
- external wait conditions;
- next candidate strategies;
- resume triggers;
- and closure evidence.

The Governor and Interlock do not decide the business strategy. They return control to the Chief or authorized supervisor.

---

## 4. Required Runtime Operations

The control plane must expose at least:

```text
CHECKPOINT_RUN
SUSPEND_RUN
RESUME_RUN
CANCEL_RUN
CANCEL_MODEL_CALL
CANCEL_TOOL_CALL
BLOCK_PROFILE_INVOCATION
ALLOW_PROFILE_INVOCATION
BLOCK_IDENTICAL_ACTION
QUARANTINE_EVENT
RELEASE_EVENT
SCHEDULE_DETERMINISTIC_RETRY
MARK_METHOD_EXHAUSTED
REQUEST_REPLAN
TRANSFER_TO_SUPERVISOR
REASSIGN_ATTEMPT
RESTORE_FROM_CHECKPOINT
```

Each operation must be idempotent and auditable.

---

## 5. Retry Model

Retries are tracked per **method fingerprint**, not as one global mission counter.

A method fingerprint should include, where applicable:

```json
{
  "tool": "browser",
  "operation": "submit_booking",
  "target": "vendor-x",
  "normalized_inputs_hash": "...",
  "environment_hash": "...",
  "provider": "...",
  "strategy_id": "S-004"
}
```

### 5.1 Identical Retry

Same fingerprint and no meaningful environmental change.

Use bounded exponential backoff and a configured ceiling.

### 5.2 Adapted Retry

Fingerprint changes because parameters, evidence, environment, or timing changed materially.

Allowed when the change and rationale are logged.

### 5.3 Detour

Strategy ID, tool, decomposition, provider under authorized policy, Worker, or execution path changes.

A detour continues the same mission and must preserve prior evidence.

### 5.4 External Wait

No cognitive retry loop is allowed.

The scheduler stores:

- condition;
- earliest recheck;
- maximum recheck cadence;
- expiry or escalation threshold;
- resume checkpoint.

Only the deterministic scheduler wakes the mission.

---

## 6. Enforcement Behavior by State

### SILENCED

- Block outbound delivery.
- Block new ordinary invocations.
- Suspend the active run at a safe boundary.
- Cancel or quarantine pending tool actions related to speech or the prohibited scope.
- Preserve checkpoint and mission ownership.
- Emit one control event to the Chief.
- Do not repeatedly send rejection text to the agent.

### RATE_LIMITED

- Record provider/tool reset time.
- Suspend without another LLM call.
- Schedule deterministic resume.
- Reinvoke reasoning only if conditions or required strategy changed.

### OBSERVER

- Do not deliver ordinary mission events to the model.
- Preserve passive event indexing outside model cognition.
- Invoke only on Chief activation, Human direct address, permitted material alert, or Watcher duty.

### LOCKDOWN

- Block all ordinary profile invocations.
- Suspend active runs.
- Quarantine queued events.
- Preserve checkpoints and logs.
- Keep Human, Chief emergency, and Watcher constitutional paths.

### BUDGET_PAUSED

- Stop additional billable work.
- Checkpoint every active attempt.
- Produce one resource-decision packet for the Chief.
- Keep mission state open.
- Resume only through an authorized budget, method, scope, or scheduling decision.

### LOOP_INTERRUPTED

- Cancel the current repeated action.
- Block the same method fingerprint until explicitly reset or conditions materially change.
- Preserve the mission.
- Return the attempt to `REPLAN_REQUIRED`.
- Allow a different authorized strategy.

---

## 7. Control Events Must Be Non-Cognitive by Default

Governor and Interlock events should update runtime state without invoking the affected agent model.

Examples:

```json
{
  "event": "RUN_SUSPENDED",
  "mission_id": "M-001",
  "attempt_id": "A-009",
  "reason": "IDENTICAL_RETRY_THRESHOLD",
  "checkpoint_id": "CP-77",
  "supervisor_action_required": "REPLAN",
  "invoke_affected_agent": false
}
```

```json
{
  "event": "RATE_RETRY_SCHEDULED",
  "mission_id": "M-001",
  "attempt_id": "A-010",
  "resume_at": "timestamp",
  "invoke_affected_agent": false
}
```

A control event may invoke the Chief once when judgment is needed. Duplicate control events must be coalesced.

---

## 8. Mission Continuity Packet

Whenever an attempt is suspended, cancelled, exhausted, reassigned, or rate-delayed, the system must persist:

```json
{
  "mission_id": "M-001",
  "attempt_id": "A-009",
  "objective": "...",
  "owner": "lead-a",
  "supervisor": "chief",
  "status": "REPLAN_REQUIRED",
  "checkpoint_id": "CP-77",
  "completed_steps": [],
  "evidence_refs": [],
  "failed_method": {},
  "failure_reason": "...",
  "identical_retry_count": 3,
  "adapted_retries": [],
  "detours_attempted": [],
  "candidate_next_methods": [],
  "external_wait_condition": null,
  "resource_request": null,
  "next_trigger": "CHIEF_DECISION"
}
```

No stopped attempt may disappear without this packet or an equivalent durable record.

---

## 9. Closure Rules

The runtime may mark an attempt failed automatically.

It must not mark the mission impossible automatically because a count or budget threshold was reached.

Mission closure as impossible requires a closure packet containing:

- material methods attempted;
- why each failed;
- evidence;
- remaining known methods;
- why those methods are unavailable, unlawful, unsafe, or causally incapable;
- external conditions preventing progress;
- Chief review;
- Watcher review for high-impact missions;
- Human notification when material.

---

## 10. Acceptance Tests

The implementation is incomplete until evidence proves:

1. A blocked Telegram send cannot leave the agent burning tokens in a hidden loop.
2. `SILENCED` blocks new model invocations for ordinary events.
3. An active tool loop is cancelled or suspended and checkpointed.
4. Three identical retries trigger `REPLAN_REQUIRED`, not `MISSION_FAILED`.
5. A materially changed method can continue the mission.
6. A new Worker can inherit the mission checkpoint and evidence.
7. Rate limiting produces a scheduled resume with no repeated model calls.
8. Budget exhaustion pauses spending while preserving the objective and state.
9. An observer does not cognitively process Room traffic before activation.
10. Duplicate rejection/control events invoke neither the agent nor Chief repeatedly.
11. A communication loop stops while the mission remains active.
12. A mission closure as impossible cannot be produced solely from retry count.
13. Restart restores suspended runs, restrictions, checkpoints, and resume triggers safely.
14. The Chief can resume, detour, reassign, or wait without losing continuity.

Every acceptance test must show both:

```text
CONTAINMENT: waste and unauthorized activity stopped
CONTINUITY: mission state and next path preserved
```

---

## 11. Required Implementation Priority

This Cognition Interlock is not a later enhancement.

It is required before multi-agent resurrection because communication-only blocking can hide uncontrolled spending behind a quiet Room.

The minimum safe resurrection stack is:

```text
1. Durable mission state
2. Communication Governor
3. Cognition Interlock
4. Chief control interface
5. Watcher audit access
6. One-agent staged test
```

The organization must not progress beyond the Chief-only resurrection stage until the Interlock proves it can stop model and tool invocation without destroying mission continuity.

---

## Final Rule

> The runtime may stop an attempt.  
> It may stop a message.  
> It may stop a tool call.  
> It may stop an agent.  
> It must not silently stop the mission.

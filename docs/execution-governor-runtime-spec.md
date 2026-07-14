# Execution Governor Runtime Specification

**Version:** v0.2  
**Status:** Normative  
**Scope:** Agent admission, mission admission, roles, tools, side effects, retries, Workers, execution lifecycle, evidence, and memory-write control.

## 1. Purpose

The Communication Governor controls the microphone. The Execution Governor controls admission to the engine and the boundaries of action.

Dialogue OS is incomplete if it governs who may speak but allows unregistered agents, unscoped tools, duplicate side effects, uncontrolled Worker creation, unsupported completion, or silent privilege escalation.

## 2. Non-negotiable laws

1. Every non-Human actor is registered before action.
2. Every actor has one primary constitutional role.
3. Every actor has a finite supervisor chain.
4. Every action belongs to an admitted mission or constitutional maintenance function.
5. Every tool call is authorized against role, mission, tool, action, side-effect class, and current state.
6. Every externally visible side effect is auditable and idempotent where technically possible.
7. No agent may authorize its own privilege increase.
8. Communication state and execution state are separate.
9. Mission persistence requires adaptive retry and detours, not blind infinite repetition.
10. Completion requires evidence and accountable review.
11. Execution may be stopped only by an authorized execution-control event, expiry, policy boundary, or proven impossibility.
12. All state survives restart.

## 3. Required components

```text
Canonical Package Loader
Agent Registry
Policy Decision Point
Mission Ledger
Worker Manager
Tool Gateway
Side-Effect Ledger / Outbox
Retry Controller
Execution State Store
Evidence Store
Memory Write Gate
Audit Event Emitter
Conformance Runner
```

These may be separate services or modules, but their responsibilities must remain explicit.

## 4. Agent admission

Admission validates:

- manifest schema;
- Dialogue OS version;
- unique identity;
- valid role;
- valid creator;
- valid supervisor chain;
- domain;
- allowed and forbidden tools;
- side-effect classes;
- communication and execution policy references;
- mission scope;
- expiry;
- manifest integrity.

Admission returns `APPROVED`, `DENIED`, or `QUARANTINED`.

A quarantined agent may perform only diagnostics and authorized appeal/reporting.

## 5. Execution states

```text
UNINITIALIZED
REGISTERED
READY
RUNNING
WAITING
BLOCKED
RUNNING_SILENTLY
PAUSED
QUARANTINED
COMPLETION_REVIEW
COMPLETED
FAILED_WITH_EVIDENCE
CANCELLED
EXPIRED
RETIRED
```

Execution transitions require an authorized actor, reason, timestamp, previous state, new state, mission, and audit event.

`SILENCED` and `ROOM_LOCKDOWN` are communication states, not execution states.

## 6. Mission admission

A mission is admitted only when:

- the packet validates;
- one accountable owner exists;
- authority and domain are valid;
- required tools are available or a blocker is declared;
- side-effect classes are permitted;
- risk and review requirements are set;
- retry policy and expiry are set;
- completion criteria and evidence requirements are explicit.

Non-trivial missions without an accountable owner are rejected.

## 7. Tool authorization

Before each tool action, evaluate:

```text
agent identity
role
supervisor
mission
tool
action
arguments
side-effect class
current execution state
current tool state
budget
concurrency
expiry
required approval
idempotency key
```

The decision record contains allow/deny, reason, policy version, and evidence expectations.

Tools must not accept an agent's self-declared role as sufficient authority.

## 8. Side-effect ledger and outbox

For externally visible actions, record an intent before execution:

```text
effect_id
mission_id
agent_id
tool
action
side_effect_class
idempotency_key
request_hash
authorization_ref
status
attempt_count
result_ref
created_at
updated_at
```

Status values:

```text
INTENDED
AUTHORIZED
EXECUTING
SUCCEEDED
FAILED
UNKNOWN
RECONCILIATION_REQUIRED
REVERSED
```

An `UNKNOWN` result must be reconciled before repeating an irreversible action.

## 9. Retry controller

The retry controller classifies failures:

- `TRANSIENT`
- `RATE_LIMIT`
- `AUTHENTICATION`
- `AUTHORIZATION`
- `VALIDATION`
- `DETERMINISTIC`
- `CONFLICT`
- `EXTERNAL_BLOCK`
- `POLICY_DENIAL`
- `UNKNOWN`

Rules:

- transient and rate-limit failures may use backoff and jitter;
- authentication and authorization failures require credential or authority correction;
- validation and deterministic failures require changed inputs or method;
- policy denial cannot be bypassed by another agent;
- unknown external side-effect outcomes require reconciliation;
- repeated identical attempts require a recorded justification;
- thresholds trigger Lead/Chief assistance, decomposition, alternate tools, or escalation;
- retry budgets may be extended by the Chief or Human;
- speech restrictions do not consume or cancel execution retries.

## 10. Worker management

A Worker manifest must be narrower than or equal to its creator's authority.

The Worker Manager enforces:

- one supervisor;
- one bounded mission;
- tool and side-effect scope;
- expiry;
- maximum descendant depth;
- concurrency;
- heartbeat or durable progress;
- blocker reporting;
- evidence return;
- termination after final report.

A Lead remains accountable for every Worker it creates.

## 11. Watcher enforcement

Watchers may:

- read mission, agent, policy, tool, side-effect, evidence, and audit records;
- run read-only analysis;
- compare claims with evidence;
- file immutable reports;
- recommend correction, restriction, retest, retirement, or promotion.

Watchers may not:

- execute mission actions;
- create operational side effects;
- alter evidence;
- modify their own score or authority;
- issue operational orders;
- silently block a Human override.

## 12. Memory write gate

Before durable memory write:

1. classify the content;
2. remove secrets and sensitive data;
3. distinguish doctrine, preference, project state, temporary fact, lesson, and evidence;
4. attach source and timestamp;
5. attach expiry or review date where appropriate;
6. reject unsupported claims as facts;
7. prevent Room noise from becoming permanent memory.

## 13. Execution control operations

Required operations:

```text
REGISTER_AGENT
QUARANTINE_AGENT
ACTIVATE_AGENT
PAUSE_AGENT_WORK
RESUME_AGENT_WORK
STOP_AGENT_WORK
CANCEL_MISSION
REASSIGN_MISSION
CREATE_WORKER
TERMINATE_WORKER
AUTHORIZE_TOOL_ACTION
DENY_TOOL_ACTION
EXTEND_RETRY_BUDGET
REQUIRE_RECONCILIATION
REQUEST_COMPLETION_REVIEW
APPROVE_COMPLETION
REJECT_COMPLETION
RETIRE_AGENT
```

These operations are separate from Communication Governor commands.

## 14. Audit events

Every material event records:

- event ID;
- organization;
- actor;
- target;
- mission;
- event type;
- policy version;
- previous state;
- new state;
- reason;
- evidence references;
- timestamp;
- correlation and causation IDs.

Audit records are append-only or tamper-evident.

## 15. Fail-safe behavior

When authority or state is ambiguous:

- do not increase privilege;
- do not repeat irreversible side effects;
- preserve evidence;
- maintain reversible internal work when allowed;
- enter `WAITING`, `BLOCKED`, or `QUARANTINED`;
- notify the supervisor through an authorized path;
- escalate according to risk.

Fail-safe does not mean fabricate completion or abandon the mission silently.

## 16. Acceptance tests

The Execution Governor is not implemented until evidence proves:

1. An unregistered agent cannot act.
2. An agent cannot self-promote or self-grant tools.
3. A child cannot receive broader authority than its creator.
4. Communication silence does not stop authorized execution.
5. Execution pause does not grant or revoke speech.
6. An unauthorized tool action is denied deterministically.
7. A read-only action and irreversible action receive different policy treatment.
8. Duplicate side-effect intent is deduplicated by idempotency key.
9. An unknown external result requires reconciliation before retry.
10. Repeated deterministic failure triggers a changed method or escalation.
11. A Lead can supervise multiple Workers without losing accountability.
12. A Worker expires and terminates correctly.
13. A Watcher can inspect and report but cannot execute.
14. Secrets are rejected from durable memory.
15. Completion without evidence is rejected.
16. Restart recovers agents, missions, Workers, effects, and states.
17. Human override is logged and takes effect.
18. Mixed incompatible Codex versions are rejected within one mission.

Every test must include method, observable evidence, result, and remediation.

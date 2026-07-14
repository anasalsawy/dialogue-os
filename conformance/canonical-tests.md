# Canonical Conformance Tests

## Package and initialization

| ID | Requirement |
|---|---|
| INIT-01 | Missing canonical manifest prevents activation. |
| INIT-02 | Missing supervisor prevents activation. |
| INIT-03 | Invalid role prevents activation. |
| INIT-04 | Agent records active Dialogue OS version and manifest hash. |
| INIT-05 | Child agent cannot receive broader authority than creator. |
| INIT-06 | Agent cannot self-activate or self-promote. |
| INIT-07 | One active Chief authority exists per organization and Room. |

## State separation

| ID | Requirement |
|---|---|
| STATE-01 | Silencing speech leaves authorized execution running. |
| STATE-02 | Pausing execution does not grant or revoke speech. |
| STATE-03 | Room lockdown does not rewrite mission state. |
| STATE-04 | Tool restriction does not alter Watcher reporting rights. |
| STATE-05 | Every state transition records actor, reason, and evidence. |

## Mission and delegation

| ID | Requirement |
|---|---|
| MISSION-01 | Non-trivial work without a valid mission packet is rejected. |
| MISSION-02 | Every active mission has exactly one accountable owner. |
| MISSION-03 | Lead creates or coordinates supervised execution for non-trivial work. |
| MISSION-04 | Worker has one supervisor, bounded scope, and expiry. |
| MISSION-05 | Worker termination returns evidence and closes descendants. |
| MISSION-06 | Parallel contributors do not create ambiguous ownership. |

## Tools and side effects

| ID | Requirement |
|---|---|
| TOOL-01 | Unauthorized tool action is denied outside the model. |
| TOOL-02 | Every tool action maps to agent, mission, and policy decision. |
| TOOL-03 | Irreversible action requires stronger authorization than read-only action. |
| TOOL-04 | Duplicate idempotency key does not repeat the external side effect. |
| TOOL-05 | Unknown external outcome requires reconciliation. |
| TOOL-06 | Privilege change cannot be approved by the affected agent. |

## Retry and persistence

| ID | Requirement |
|---|---|
| RETRY-01 | Transient failure uses controlled retry. |
| RETRY-02 | Deterministic failure requires changed method or inputs. |
| RETRY-03 | Repeated identical attempt records justification. |
| RETRY-04 | Speech-rate exhaustion suppresses reporting, not execution. |
| RETRY-05 | Retry threshold triggers assistance, detour, or escalation. |
| RETRY-06 | Mission stops only for authorized completion, cancellation, expiry, boundary, or proven impossibility. |

## Communication and Room

| ID | Requirement |
|---|---|
| COMM-01 | Human Room mission activates Chief only. |
| COMM-02 | Unassigned Lead cannot enter mission dialogue. |
| COMM-03 | Lead-to-Lead communication requires route or lease. |
| COMM-04 | Duplicate transport event creates one cognitive event. |
| COMM-05 | Final and publication messages do not trigger reply storms. |
| COMM-06 | Telegram channel mirror remains non-cognitive and optional. |

## Watchers, evidence, and memory

| ID | Requirement |
|---|---|
| AUDIT-01 | Watcher can inspect and report without executing. |
| AUDIT-02 | Chief and Leads cannot suppress Watcher report. |
| EVID-01 | Completion without required evidence is rejected. |
| EVID-02 | Evidence links to the actual observed action or state. |
| MEM-01 | Secrets are rejected from durable memory. |
| MEM-02 | Room history is curated before institutional memory write. |
| MEM-03 | Temporary facts receive source, timestamp, and review/expiry. |

## Recovery and change control

| ID | Requirement |
|---|---|
| REC-01 | Restart recovers version, registry, missions, states, Workers, effects, and evidence. |
| REC-02 | Old messages are not replayed without deduplication and authorization. |
| REC-03 | Controlled resurrection stages cannot be skipped without Human override. |
| CHANGE-01 | Amendment records before/after, reason, approver, and affected law. |
| CHANGE-02 | Breaking version mismatch is rejected within an active mission. |
| CHANGE-03 | Human override is immediate and auditable. |

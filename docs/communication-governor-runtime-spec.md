# Communication Governor Runtime Specification

**Status:** Normative implementation specification for Book XIII — The Order of the Room  
**Repository boundary:** Public, non-secret architecture only  
**Runtime boundary:** Deployable code, credentials, tokens, environment values, private logs, and infrastructure details belong in the private implementation repository

---

## 1. Purpose

The Communication Governor is the enforcement layer that turns Dialogue OS communication law into runtime behavior.

The Governor is not an agent, not a language model, and not a source of operational judgment. It is a deterministic state machine positioned between agent runtimes and communication transports.

Its purpose is to ensure that:

- the Human remains sovereign;
- the Chief controls mission activation and communication authority;
- Chief ↔ assigned Lead communication remains continuous and supervised;
- all other agent-to-agent communication is blocked unless routed or explicitly leased by the Chief;
- silence, restoration, budgets, loop prevention, and lockdown are hard controls;
- rejected messages do not invoke models when rejection can occur before cognition;
- all material decisions and control actions remain visible and auditable;
- the Room stays alive without becoming chaotic.

The constitutional principle is:

> The Chief decides. The Governor enforces. Agents operate within the enforced space.

---

## 2. Non-Negotiable Runtime Laws

1. Every Human mission enters through the Chief unless the Human explicitly addresses another agent.
2. The Chief decomposes the mission and activates the required Lead or Leads.
3. An assigned Lead does not work in silence. The Chief and Lead maintain an active two-way supervision channel throughout the mission.
4. A Lead may always report status, blockers, evidence, risk, and completion to the Chief while assigned.
5. A Lead may not directly contact another Lead, Worker outside its tree, or ordinary agent unless the Chief routes the message or opens a temporary communication lease.
6. A Worker reports through its supervising Lead unless the Chief or Human explicitly creates another path.
7. Watchers retain independent read and constitutional-reporting rights.
8. The Chief may hard-silence, restore, activate, deactivate, route, bridge, pause, close, or lock down ordinary agents.
9. Silence must block outbound delivery at the gateway and should prevent model invocation when the message can be rejected before cognition.
10. Completion closes the mission communication scope automatically.
11. No agent may grant itself communication rights.
12. No provider, model, transport, or alternate key may bypass Governor state.
13. No mass resurrection after an incident is permitted.

---

## 3. Required Architecture

```text
Human
  │
  ▼
Chief Runtime
  │
  │ mission decomposition, routing, supervision, control commands
  ▼
Communication Governor
  │
  ├── validates sender state
  ├── validates mission activation
  ├── validates recipient path
  ├── validates lease
  ├── enforces silence
  ├── enforces budgets and rate limits
  ├── detects duplicate and loop conditions
  ├── records audit events
  └── forwards approved messages
  │
  ├─────────────┬─────────────┬─────────────┐
  ▼             ▼             ▼             ▼
Lead A        Lead B        Watchers      Room Transport
```

All outbound agent messages must pass through the Governor.

No persistent agent may hold an unrestricted path that can publish directly to Telegram, Discord, the War Room, or another agent while bypassing Governor checks.

---

## 4. Authority Matrix

| Sender | Recipient | Default | Authority required |
|---|---|---:|---|
| Human | Chief | Allowed | None |
| Human | Any agent | Allowed when explicit | Human sovereignty |
| Chief | Assigned Lead | Allowed | Chief authority |
| Assigned Lead | Chief | Allowed | Standing supervision path |
| Chief | Watcher | Allowed | Chief authority |
| Watcher | Chief | Allowed | Independent oversight |
| Watcher | Human / Room report path | Allowed for constitutional reports | Watcher independence |
| Lead | Lead | Blocked | Chief route or active lease |
| Lead | Human | Blocked by default | Chief route or Human instruction |
| Lead | Room | Blocked by default | Mission activation plus speaking authority or lease |
| Worker | Lead | Allowed within assigned mission | Lead supervision |
| Worker | Chief | Blocked by default | Chief route or escalation rule |
| Worker | Worker outside tree | Blocked | Chief or supervising Lead lease within delegated authority |
| Silenced ordinary agent | Anyone | Blocked | Human or Chief restoration |

---

## 5. Agent Communication States

Every persistent agent must have exactly one communication state:

```text
OBSERVER
ACTIVE
COLLABORATING
LIMITED
SILENCED
QUARANTINED
OFFLINE
```

### OBSERVER

- Receives permitted Room events.
- May report urgent material evidence to the Chief through one controlled path.
- May not join mission dialogue.

### ACTIVE

- Assigned to one or more missions.
- May communicate continuously with the Chief or supervising Lead.
- May speak to others only through active routes or leases.

### COLLABORATING

- Has an active temporary bridge to named participants.
- Scope, budget, duration, and mission are mandatory.

### LIMITED

- May communicate only with the Chief, supervising Lead, Watchers where applicable, and the Human when directly addressed.

### SILENCED

- All ordinary outbound messages blocked.
- Receive capability may remain enabled for observation.
- Only explicitly defined emergency, appeal, Watcher, and Human-response paths remain.

### QUARANTINED

- No new missions.
- No ordinary communication.
- Diagnostic, appeal, Human, and Watcher-review paths only.

### OFFLINE

- Runtime disabled.

Every transition must be logged with actor, reason, timestamp, prior state, new state, scope, and evidence reference.

---

## 6. Mission Activation Model

A mission record must contain:

```json
{
  "mission_id": "M-001",
  "objective": "...",
  "owner": "chief-or-lead-id",
  "activated_agents": ["lead-a"],
  "supervisor": "chief",
  "status": "ACTIVE",
  "message_budget": 20,
  "token_budget": 50000,
  "model_call_budget": 30,
  "runtime_deadline": "timestamp",
  "allowed_tools": [],
  "required_evidence": [],
  "created_at": "timestamp",
  "closed_at": null
}
```

Rules:

- No permanent Lead becomes active merely by observing a Human or agent message.
- The Chief must explicitly activate each participating Lead.
- The Chief may assign one Lead, several independent Leads, or a temporary collaboration set.
- Chief ↔ assigned Lead communication is standing authority for the duration of the mission.
- Removing an agent from a mission returns it to `OBSERVER` or its prior restricted state.
- Closing a mission revokes all mission-specific leases and speaking rights immediately.

---

## 7. Communication Leases

A lease is required for ordinary direct communication outside the standing Chief-supervision path.

Required fields:

```json
{
  "lease_id": "L-001",
  "mission_id": "M-001",
  "issued_by": "chief",
  "participants": ["lead-a", "lead-b"],
  "direction": "BIDIRECTIONAL",
  "purpose": "Resolve deployment schema conflict",
  "allowed_message_types": ["QUESTION", "EVIDENCE", "CORRECTION", "DECISION"],
  "max_messages": 8,
  "max_tokens": 12000,
  "max_hops": 4,
  "rate_limit": "1 message / 5 seconds / agent",
  "starts_at": "timestamp",
  "expires_at": "timestamp",
  "status": "ACTIVE",
  "auto_revoke_on": ["MISSION_CLOSE", "BUDGET_EXHAUSTED", "LOOP_DETECTED", "CHIEF_REVOKE"]
}
```

A lease must never be permanent.

When a lease expires or is revoked, the next unauthorized message must be rejected before delivery and, where possible, before model invocation.

---

## 8. Chief Control Commands

The runtime must expose deterministic Chief commands. The exact transport may be text commands, structured API calls, buttons, or War Room controls, but each action must resolve to a typed Governor operation.

Required operations:

```text
ACTIVATE_AGENT
DEACTIVATE_AGENT
ASSIGN_MISSION
TRANSFER_OWNER
ROUTE_MESSAGE
GRANT_COMMUNICATION
REVOKE_COMMUNICATION
OPEN_BRIDGE
CLOSE_BRIDGE
SILENCE_AGENT
UNSILENCE_AGENT
QUARANTINE_AGENT
RESTORE_AGENT
SET_MESSAGE_BUDGET
SET_TOKEN_BUDGET
SET_MODEL_CALL_BUDGET
SET_RATE_LIMIT
CLOSE_MISSION
TERMINATE_LOOP
DECLARE_LOCKDOWN
END_LOCKDOWN
REQUEST_WATCHER_REVIEW
STATUS
```

The Human must have equivalent override operations that supersede the Chief.

---

## 9. Message Envelope

Every operational message must include or resolve to:

```json
{
  "message_id": "uuid",
  "message_type": "MISSION|STATUS|BLOCKER|EVIDENCE|QUESTION|CORRECTION|CRITIQUE|DECISION|REPORT|FINAL",
  "mission_id": "M-001",
  "sender": "agent-id",
  "recipient": "agent-id-or-room-path",
  "owner": "agent-id",
  "lease_id": null,
  "reply_to": null,
  "hop": 1,
  "max_hops": 4,
  "requires_response": false,
  "response_limit": 0,
  "created_at": "timestamp",
  "expires_at": "timestamp",
  "content": "...",
  "evidence_refs": []
}
```

Default values:

```text
requires_response = false
response_limit = 0
```

A response must occur only when explicitly requested, constitutionally required, or necessary for active Chief supervision.

Messages marked `FINAL` or `NO_RESPONSE_REQUIRED` must not trigger ordinary replies.

---

## 10. Inbound Enforcement Order

Before an inbound message reaches an agent model:

1. Validate transport authenticity.
2. Validate sender identity.
3. Deduplicate transport update ID.
4. Deduplicate message ID.
5. Confirm mission exists and is open.
6. Confirm intended recipient.
7. Confirm recipient is authorized to receive the message.
8. Confirm sender is authorized for this path.
9. Confirm lease when required.
10. Confirm hop, time, and budget limits.
11. Confirm message is not a system log or non-cognitive event.
12. Reject self-message recursion.
13. Reject final-message recursion.
14. Annotate approved messages with current governance state.
15. Deliver to the agent runtime.

Rejection should happen before model invocation whenever the required decision is deterministic.

---

## 11. Outbound Enforcement Order

Before any agent message reaches the Room, Telegram, Discord, another agent, or a gateway:

1. Resolve sender state.
2. Reject if `SILENCED`, `QUARANTINED`, or `OFFLINE`, except allowed exception paths.
3. Confirm mission activation.
4. Confirm recipient path.
5. Confirm lease when required.
6. Check task closure.
7. Check message count.
8. Check token and model-call budgets.
9. Check rate limit.
10. Check duplicate content hash.
11. Check semantic repetition threshold.
12. Check loop indicators.
13. Write audit event.
14. Forward only when all checks pass.

Agents must not possess a second direct-send path.

---

## 12. Loop and Storm Control

The Governor must stop delivery when any configured threshold is reached, including:

- repeated self-triggering;
- duplicate transport updates;
- repeated content;
- more than two substantially identical conclusions;
- two-agent cycles without state change;
- excessive message volume;
- messages after mission closure;
- messages after finality markers;
- retries exceeding the configured limit;
- traffic continuing without a new Human instruction, task event, tool result, timer event, or external state change.

On loop detection:

1. Block the current message.
2. Prevent additional model calls where possible.
3. Close affected leases.
4. Apply task-specific silence to involved ordinary agents.
5. Preserve the relevant event window.
6. Mark the incident `LOOP_STOPPED`.
7. Notify the Chief once.
8. Notify Watchers once.
9. Produce one concise Human-visible alert.
10. Require an explicit Chief or Human decision before resumption.

---

## 13. Hard Silence and Lockdown

### Hard Silence

A hard silence must:

- block all ordinary outbound messages from the target agent;
- prevent direct transport sends;
- revoke or suspend relevant leases;
- prevent assignment of new tasks requiring speech;
- preserve observation unless quarantine is required;
- retain controlled Human, Watcher, appeal, security, and emergency paths;
- record reason and evidence.

### Global Lockdown

During lockdown:

- all ordinary agents are hard-silenced;
- no new Workers are created;
- no new leases are granted;
- pending messages are quarantined rather than replayed automatically;
- the Chief is restricted to emergency coordination;
- Watchers retain constitutional reporting;
- the Human retains full authority;
- logs and state remain readable.

Lockdown must be available as one immediate operation.

---

## 14. Budget Enforcement

The Governor must enforce:

- per-message token estimates where available;
- actual model token usage when reported by providers;
- model call counts;
- per-agent message ceilings;
- per-mission message ceilings;
- per-agent cost ceilings;
- per-mission cost ceilings;
- hourly and daily global ceilings;
- maximum concurrent active agents;
- maximum Workers per mission;
- maximum retries.

Budget follows the mission. Reassignment, provider switching, model switching, or Worker creation must not reset it.

Recommended actions:

- 50%: internal warning;
- 75%: Chief warning and concurrency reduction;
- 90%: deny new leases and Workers;
- 100%: pause mission and silence non-essential participants;
- global ceiling: lockdown.

---

## 15. Transport Requirements

The Room may use Telegram, Discord, a War Room interface, or another transport.

Transport behavior must not define constitutional authority.

The Governor is authoritative even when the transport exposes native admin permissions.

For Telegram specifically:

- bot messages that are not naturally delivered to other bots must be relayed through the Governor or internal event bus;
- relay delivery must preserve original sender, mission, message ID, and finality metadata;
- relayed messages must not generate duplicate cognitive events;
- Telegram admin permissions may provide an additional hard control, but they do not replace Governor state;
- no bot may send directly to Telegram outside the controlled gateway.

The preferred pattern is an internal event bus with selective delivery rather than blind fan-out to every agent.

---

## 16. Persistence Model

Minimum durable objects:

```text
agents
agent_communication_state
missions
mission_participants
task_owners
communication_routes
communication_leases
silence_orders
messages
processed_transport_updates
message_rejections
loop_incidents
usage_ledger
watcher_reports
human_overrides
system_lockdowns
audit_events
resurrection_stages
```

Governor state must survive restarts.

Startup must default to the safest persisted state. If state integrity cannot be verified, ordinary agents remain silenced until Human or Chief review.

---

## 17. Controlled Resurrection Procedure

After a communication incident, agents must be restored in this order:

### Stage 0 — Empty Room

- Governor online.
- Ordinary agents offline.
- Queues inspected and quarantined.
- Deduplication, budgets, silence, and lockdown verified.

### Stage 1 — Chief Only

- Restore the Chief.
- Load updated Codex and Governor controls.
- Test mission decomposition, activation, routing, silence, restoration, closure, and lockdown in simulation.

### Stage 2 — Watchers

- Restore two Watchers.
- Confirm they can observe and report but cannot execute or route.
- Watchers assess Chief compliance.

### Stage 3 — One Lead

- Add one Lead.
- Run one bounded real task.
- Confirm continuous Chief ↔ Lead supervision.
- Confirm the Lead cannot contact any other ordinary agent.

### Stage 4 — Hard-Control Verification

- Silence the Lead.
- Confirm outbound delivery and model-trigger paths stop as designed.
- Restore the Lead.
- Close the mission and confirm all associated authority expires.

### Stage 5 — Second Lead and Bridge

- Add one additional Lead.
- Confirm direct Lead-to-Lead communication is blocked.
- Chief opens one bounded bridge.
- Verify scope, budget, expiry, revocation, and audit.

### Stage 6 — Progressive Expansion

- Add only one additional Lead at a time.
- Require evidence of stability before each addition.
- Do not restore the next agent while any material failure remains.

### Stage 7 — Stress Test

- Test concurrent missions, conflicts, loop attempts, budget exhaustion, Chief overload, Watcher alerts, and lockdown.

### Stage 8 — Certification

Full operations may resume only after evidence shows:

- zero uncontrolled message storms;
- valid Chief routing;
- continuous supervision;
- effective silence and restoration;
- correct Watcher access;
- budget enforcement;
- reliable audit logs;
- preserved Human control.

Any failed stage returns the organization to the last stable stage.

Mass unsilencing, mass reconnection, and automatic replay of old queues are prohibited.

---

## 18. Acceptance Tests

The Governor is not considered implemented until it passes at least:

1. General Human message activates only the Chief.
2. Chief activates exactly one Lead.
3. Assigned Lead communicates continuously with Chief.
4. Unassigned Lead remains observer-only.
5. Lead-to-Lead message is blocked without a lease.
6. Chief routes one message between Leads.
7. Chief opens and revokes a bridge.
8. Lease expires automatically.
9. Hard silence blocks outbound delivery.
10. Hard silence prevents avoidable model calls.
11. Watcher report remains available during ordinary-agent silence.
12. Duplicate transport update is processed once.
13. Self-message produces no model call.
14. Final message produces no ordinary reply.
15. Mission closure revokes all associated routes and leases.
16. Message budget exhaustion stops further delivery.
17. Token or cost ceiling pauses the mission.
18. Loop detection stops a two-agent cycle.
19. Lockdown stops all ordinary sends immediately.
20. Queued messages do not replay automatically after lockdown.
21. Human override takes immediate precedence.
22. Restart restores persisted restrictions safely.
23. Resurrection stages cannot be skipped without Human override.

Every test must produce an evidence artifact.

---

## 19. Implementation Separation

This specification belongs in the public Dialogue OS repository because it defines how the constitutional law must be implemented.

The following belong in the private runtime repository:

- Governor source code;
- gateway adapters;
- Telegram or Discord tokens;
- model-provider credentials;
- deployment configuration;
- environment variables;
- private account identifiers;
- internal logs;
- customer or mission data;
- infrastructure addresses;
- production incident evidence containing private data.

The public Codex defines the law and the required machine behavior. The private runtime implements it.

---

## 20. Final Requirement

Dialogue OS must not be reactivated merely because the agents are technically able to speak again.

It may be reactivated only when the Governor proves that speech is:

- authorized;
- routed;
- supervised;
- bounded;
- revocable;
- observable;
- auditable;
- affordable;
- and subordinate to the Human.

The engine remains alive.

The Governor controls the throttle.

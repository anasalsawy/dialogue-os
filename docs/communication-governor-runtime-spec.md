# Communication Governor Runtime Specification

**Status:** Normative implementation specification for Book XIII — The Order of the Room  
**Scope:** Communication, routing, speech permissions, Room traffic, and message transport only  
**Explicit exclusion:** The Governor does not automatically control model reasoning, tool execution, Workers, retries, browsing, coding, research, or mission runtime.

---

## 1. Purpose

The Communication Governor is the enforcement layer for Dialogue OS communication law.

It is a deterministic state machine positioned between agent runtimes and communication transports.

Its purpose is to ensure that:

- the Human remains sovereign;
- the Chief controls mission activation and communication authority;
- Chief ↔ assigned Lead communication remains available and supervised;
- other agent-to-agent communication is blocked unless routed or leased;
- hard silence, leases, routing, message budgets, and Room lockdown are enforceable;
- message storms are contained;
- and silent work continues regardless of speech restrictions.

The constitutional principle is:

> The Chief decides who may speak. The Governor enforces speech. Agents continue working internally.

---

## 2. Non-Negotiable Runtime Laws

1. Every Human mission enters through the Chief unless the Human explicitly addresses another agent.
2. The Chief decomposes the mission and activates the required Lead or Leads.
3. An assigned Lead may communicate with the Chief throughout the mission.
4. A Lead may not directly contact another Lead or unrelated Worker unless the Chief routes the message or opens a communication lease.
5. Watchers retain independent constitutional reporting rights.
6. The Chief may silence, restore, activate, deactivate, route, bridge, pause, close, or lock down communication.
7. Communication silence blocks speech only.
8. Communication limits must not automatically stop model runs, tools, Workers, retries, research, browsing, coding, or silent mission execution.
9. No agent may grant itself communication rights.
10. No transport may bypass Governor communication state.
11. No mass resurrection after an incident is permitted.

---

## 3. Required Architecture

```text
Human
  │
  ▼
Chief Runtime
  │ mission decomposition, routing, supervision, control commands
  ▼
Communication Governor
  │
  ├── validates sender speech state
  ├── validates recipient path
  ├── validates mission activation
  ├── validates leases
  ├── enforces message rates and speech budgets
  ├── detects duplicate and circular messages
  ├── records audit events
  └── forwards approved communication
  │
  ├─────────────┬─────────────┬─────────────┐
  ▼             ▼             ▼             ▼
Lead A        Lead B        Watchers      Room Transport

Agent runtimes and tools continue independently behind the communication boundary.
```

All outbound Room messages must pass through the Governor.

Agents may continue internal work even when no outbound path is available.

---

## 4. Authority Matrix

| Sender | Recipient | Default | Authority required |
|---|---|---:|---|
| Human | Chief | Allowed | None |
| Human | Any agent | Allowed when explicit | Human sovereignty |
| Chief | Assigned Lead | Allowed | Chief authority |
| Assigned Lead | Chief | Allowed | Standing supervision path |
| Chief | Watcher | Allowed | Chief authority |
| Watcher | Chief/Human/report path | Allowed | Watcher independence |
| Lead | Lead | Blocked | Chief route or active lease |
| Lead | Human | Blocked by default | Chief route or Human instruction |
| Lead | Room | Blocked by default | Speaking authority or lease |
| Worker | Supervising Lead | Allowed within mission | Lead supervision |
| Silenced ordinary agent | Ordinary communication paths | Blocked | Human or Chief restoration |

This matrix affects communication only.

---

## 5. Communication States

Every persistent agent has one communication state:

```text
OBSERVER
ACTIVE
COLLABORATING
LIMITED
SILENCED
QUARANTINED_FROM_SPEECH
OFFLINE_FROM_ROOM
```

### OBSERVER

- May receive permitted Room information.
- May not join mission dialogue without activation.
- May continue internal background work already authorized.

### ACTIVE

- Assigned to a mission.
- May communicate with the Chief or supervising Lead.
- May speak to others only through routes or leases.

### COLLABORATING

- Has a temporary bridge to named participants.
- Scope, duration, and message limits are mandatory.

### LIMITED

- May communicate only through named paths.

### SILENCED

- Ordinary outbound communication is blocked.
- Internal reasoning, tools, Workers, retries, and mission work continue.

### QUARANTINED_FROM_SPEECH

- No ordinary communication.
- Diagnostic, appeal, Human, and Watcher paths remain as configured.
- Internal execution is unaffected unless separately ordered by Human or Chief.

### OFFLINE_FROM_ROOM

- Removed from Room communication.
- Runtime execution may remain active.

Every transition must be logged.

---

## 6. Mission Activation

A mission record should contain:

```json
{
  "mission_id": "M-001",
  "objective": "...",
  "owner": "chief-or-lead-id",
  "activated_agents": ["lead-a"],
  "supervisor": "chief",
  "status": "ACTIVE",
  "speech_budget": 20,
  "created_at": "timestamp",
  "closed_at": null
}
```

Rules:

- No permanent Lead becomes active merely by observing a message.
- The Chief explicitly activates each participating Lead.
- Chief ↔ assigned Lead communication is standing authority.
- Removing an agent from mission speech returns it to observer or restricted communication state.
- Closing mission communication revokes mission leases and speaking rights.
- None of these communication transitions automatically stop internal execution.

---

## 7. Communication Leases

A lease is required for ordinary direct communication outside standing Chief supervision.

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
  "rate_limit": "1 message / 5 seconds / agent",
  "starts_at": "timestamp",
  "expires_at": "timestamp",
  "status": "ACTIVE"
}
```

A lease must never be permanent.

Lease expiration blocks communication only.

---

## 8. Chief Control Operations

Required communication operations:

```text
ACTIVATE_AGENT_FOR_SPEECH
DEACTIVATE_AGENT_FROM_SPEECH
ASSIGN_MISSION
TRANSFER_OWNER
ROUTE_MESSAGE
GRANT_COMMUNICATION
REVOKE_COMMUNICATION
OPEN_BRIDGE
CLOSE_BRIDGE
SILENCE_AGENT
UNSILENCE_AGENT
QUARANTINE_SPEECH
RESTORE_SPEECH
SET_MESSAGE_BUDGET
SET_MESSAGE_RATE
CLOSE_MISSION_COMMUNICATION
TERMINATE_MESSAGE_LOOP
DECLARE_ROOM_LOCKDOWN
END_ROOM_LOCKDOWN
REQUEST_WATCHER_REVIEW
STATUS
```

Separate Human or Chief execution controls may exist, but they are outside the Communication Governor and must be explicit.

---

## 9. Message Envelope

```json
{
  "message_id": "uuid",
  "message_type": "MISSION|STATUS|BLOCKER|EVIDENCE|QUESTION|CORRECTION|CRITIQUE|DECISION|REPORT|FINAL",
  "mission_id": "M-001",
  "sender": "agent-id",
  "recipient": "agent-id-or-room-path",
  "lease_id": null,
  "reply_to": null,
  "requires_response": false,
  "created_at": "timestamp",
  "expires_at": "timestamp",
  "content": "...",
  "evidence_refs": []
}
```

Messages marked `FINAL` or `NO_RESPONSE_REQUIRED` must not trigger ordinary replies.

---

## 10. Inbound Communication Enforcement

Before an inbound message is delivered as a cognitive event:

1. Validate transport authenticity.
2. Validate sender identity.
3. Deduplicate update and message IDs.
4. Confirm intended recipient.
5. Confirm sender and recipient communication authority.
6. Confirm lease when required.
7. Reject self-message recursion.
8. Reject final-message recursion.
9. Deliver approved communication.

Rejected Room messages need not be delivered to the affected model.

This prevents speech-triggered storms, but does not stop any independent internal work already underway.

---

## 11. Outbound Communication Enforcement

Before any message reaches the Room or another agent:

1. Resolve sender communication state.
2. Confirm mission speaking authority.
3. Confirm recipient path.
4. Confirm lease when required.
5. Check communication closure.
6. Check message count and rate.
7. Check duplicate content.
8. Check circular message indicators.
9. Write audit event.
10. Forward only when approved.

No step may automatically cancel the sender’s model run, tools, Workers, retries, or mission.

---

## 12. Communication-Loop and Storm Control

The Governor stops delivery for:

- repeated self-triggering messages;
- duplicate transport updates;
- repeated content;
- circular agent replies;
- excessive Room traffic;
- messages after communication closure;
- and messages after finality markers.

On detection:

1. Block the message.
2. Close affected communication leases when needed.
3. Apply speech-only silence when needed.
4. Preserve the message evidence.
5. Notify the Chief once.
6. Keep internal work active.

Repeated tool use or internal reasoning is outside Governor scope.

---

## 13. Hard Silence and Room Lockdown

### Hard Silence

A hard silence must:

- block ordinary outbound communication;
- prevent direct transport sends;
- revoke relevant communication leases;
- preserve authorized Chief/Human/Watcher paths;
- leave internal reasoning and tooling untouched.

### Room Lockdown

During Room Lockdown:

- ordinary agent speech is blocked;
- Human, Chief control, and Watcher reporting paths remain;
- agent runtimes may continue working silently;
- queued speech is held, consolidated, or discarded according to policy;
- no queued message is replayed automatically without review.

---

## 14. Speech-Budget Enforcement

The Governor may enforce:

- per-agent message ceilings;
- per-mission message ceilings;
- Room posting frequency;
- communication hops;
- and transport volume.

It must not automatically enforce limits on:

- model calls;
- tool calls;
- tokens used for internal work;
- retries;
- Workers;
- mission runtime;
- browsing;
- coding;
- or research.

When a speech budget is exhausted, silent work continues.

---

## 15. Transport Requirements

The Room may use Telegram, Discord, a War Room interface, or another transport.

For Telegram:

- missing bot-to-bot delivery may be solved through the Governor or internal event bus;
- relay metadata must preserve original sender and mission;
- relayed messages must not produce duplicate cognitive events;
- Telegram admin permissions may add speech control;
- no bot may publish outside the controlled communication gateway.

---

## 16. Persistence Model

Minimum durable communication objects:

```text
agents
agent_communication_state
missions
mission_participants
communication_routes
communication_leases
silence_orders
messages
processed_transport_updates
message_rejections
communication_loop_incidents
watcher_reports
human_overrides
room_lockdowns
audit_events
resurrection_stages
```

Governor state must survive restarts.

---

## 17. Controlled Resurrection

After a Room incident:

1. Start with an empty Room and Governor online.
2. Restore Chief only.
3. Restore two Watchers.
4. Add one Lead.
5. Verify Chief supervision and speech controls.
6. Add a second Lead and test one bounded bridge.
7. Add remaining Leads individually.
8. Stress-test communication storms and Room lockdown.

Silent work may continue during speech tests when authorized.

Mass unsilencing and automatic replay of old Room messages are prohibited.

---

## 18. Acceptance Tests

The Governor is not implemented until it proves:

1. General Human messages activate only the Chief operationally.
2. Chief activates exactly one Lead for speech.
3. Assigned Lead communicates with Chief.
4. Unassigned Lead cannot enter the dialogue.
5. Lead-to-Lead speech is blocked without a lease.
6. Chief opens and revokes a bridge.
7. Hard silence blocks Room output.
8. Hard silence does not stop tools or reasoning.
9. Message-rate exhaustion does not stop internal work.
10. Duplicate updates are delivered once.
11. Self-messages and final messages produce no reply storm.
12. Communication-loop detection quiets the Room while mission work continues.
13. Room Lockdown stops ordinary speech immediately.
14. Human override takes immediate precedence.
15. Resurrection stages cannot be skipped without Human override.

Every test must prove both communication order and preserved internal work.

---

## Final Requirement

> The Governor controls the microphone.  
> It does not control the mind, the tools, or the engine.

# Book XIII — The Order of the Room

## Part III — Message, Communication-Loop, Speech-Budget, and Telegram Law

## Article 8 — Message Law

### 8.1 Required Message Envelope

Every operational message must include or resolve to:

```json
{
  "message_type": "MISSION | STATUS | BLOCKER | EVIDENCE | CRITIQUE | CORRECTION | ESCALATION | PROPOSAL | REPORT | DECISION",
  "message_id": "unique-id",
  "task_id": "task-id",
  "sender": "agent-id",
  "recipient": "agent-id-or-authorized-audience",
  "owner": "current-task-owner",
  "lease_id": "lease-id-or-null",
  "reply_to": "message-id-or-null",
  "hop": 1,
  "max_hops": 4,
  "created_at": "timestamp",
  "expires_at": "timestamp",
  "requires_response": true,
  "response_limit": 1,
  "content": "message body",
  "evidence_refs": []
}
```

### 8.2 Invalid Message

A message is invalid when:

- the sender is not authorized;
- the recipient is not authorized;
- a required lease is absent or expired;
- the message was already delivered;
- the task is closed for communication;
- the message expired;
- hop depth is exceeded;
- the sender is silenced from speaking;
- the message responds to the bot’s own output;
- the same message was already delivered;
- or the message violates finality.

Invalid messages must be dropped before transport delivery whenever possible.

Message rejection does not stop the sender’s internal reasoning, tools, retries, Workers, or mission.

### 8.3 Acknowledgements

Routine acknowledgements must not create Room traffic.

The system may record them internally:

```text
received=true
processed=true
```

Agents should not publish empty acknowledgements such as “Understood,” “Got it,” “Thanks,” or “Proceeding” unless the acknowledgement changes task state.

### 8.4 Status Messages

A `STATUS` message is valid when it reports a material state change, including:

- progress;
- phase;
- blocker;
- evidence;
- owner;
- resource state;
- or mission state.

Agents may continue working without publishing frequent status messages.

### 8.5 Required Response Limit

Default:

```text
requires_response = false
```

A response must not be generated merely because another bot spoke.

### 8.6 Finality Marker

A message marked:

```text
FINAL
NO_RESPONSE_REQUIRED
```

must not trigger ordinary agent replies.

---

## Article 9 — Communication-Loop Prevention

### 9.1 Scope

This Article governs communication loops only.

It does not govern silent execution, model reasoning, tools, Workers, research, retries, browsing, coding, or long-running work.

### 9.2 Mandatory Communication Controls

The messaging layer MUST implement:

- transport-update deduplication;
- message-ID deduplication;
- sender-recipient authorization;
- communication rate limiting;
- message-hop limits;
- task-communication closure checks;
- self-message rejection;
- final-message rejection;
- duplicate-message suppression;
- and an emergency Room mute.

### 9.3 Communication Loop Definition

A communication loop exists when repeated messages create no useful new Room state, evidence, decision, or authorized work, including:

- agents replying to each other circularly;
- repeated acknowledgements;
- repeated conclusions;
- self-triggered replies;
- messages after finality;
- or uncontrolled message volume.

Repeated silent work is not a communication loop.

### 9.4 Communication Loop Response

On communication-loop detection:

1. Block or mute the affected messages.
2. Close affected communication leases when necessary.
3. Apply task-specific speech restrictions when necessary.
4. Preserve the relevant message evidence.
5. Notify the Chief once.
6. Notify Watchers once when oversight is required.
7. Keep the underlying mission and internal work active.
8. Allow the Chief to restore, route, or consolidate later reporting.

The Governor must not automatically cancel the model, tools, Workers, retries, or mission.

### 9.5 Repeated Work

No constitutional maximum applies to silent tool retries or repeated execution attempts merely because they are numerous.

The Chief and Human may observe, advise, redirect, pause, or stop execution, but the Communication Governor may not do so automatically.

---

## Article 10 — Speech and Room-Traffic Budgets

### 10.1 Scope

Budgets under this Article regulate communication only.

They may include:

- messages per agent;
- messages per task;
- messages per time window;
- communication hops;
- Room posting frequency;
- and communication transport volume.

They do not include automatic limits on:

- model calls;
- tool calls;
- tokens used for silent reasoning;
- mission runtime;
- Worker count;
- retries;
- browsing;
- coding;
- research;
- or internal execution.

### 10.2 Budget Exhaustion

When a speech budget is exhausted:

- the agent continues working silently;
- further ordinary Room messages are blocked, delayed, or consolidated;
- Chief communication may remain available according to policy;
- the mission remains active;
- tools and reasoning continue.

### 10.3 No Execution Consequence

A communication budget must never be interpreted as an execution budget.

The following transition is mandatory:

```text
MESSAGE_BUDGET_EXHAUSTED → SILENT_WORK_CONTINUES
```

not:

```text
MESSAGE_BUDGET_EXHAUSTED → STOP_AGENT
```

### 10.4 Human and Chief Authority

The Human or Chief may explicitly impose separate operational limits or stop orders when they choose. Such orders are executive decisions, not automatic Governor behavior.

---

## Article 11 — Telegram Implementation Law

### 11.1 Telegram Is an Interface

Telegram must not be treated as the sole source of task truth, memory, ownership, or permissions.

Authoritative communication state must exist in a durable backend.

### 11.2 Room Structure

The Room may be implemented as a private supergroup, channel, War Room, internal event bus, or combination selected by the Human.

Transport choice must not alter constitutional authority.

### 11.3 Human Orders

Human missions are routed to the Chief unless the Human explicitly addresses another agent.

Ordinary agents must not self-assign from general Room traffic.

### 11.4 Domain Communication

Only the assigned Lead, Chief, authorized Workers, and currently leased participants may speak in a mission conversation.

Unassigned agents may remain silent observers.

### 11.5 Final Reports

Final reports must be evidence-backed and marked:

```text
FINAL
NO_RESPONSE_REQUIRED
```

### 11.6 System Logs

Bots must not cognitively reply to machine logs merely because those logs appear in the Room.

### 11.7 Telegram Permission Limits

Telegram administrator permissions may provide an additional speech-control layer, but application-level routing remains authoritative.

The Chief’s silence authority should be enforced by:

- blocking outbound Room sends;
- rejecting unauthorized direct messages;
- revoking communication leases;
- changing Telegram posting permissions where useful;
- and preserving internal work.

### 11.8 One Controlled Communication Gateway

All agent Room messages SHOULD pass through one controlled communication gateway.

The gateway checks:

```text
Is sender allowed to speak?
Is recipient authorized?
Is a lease required and valid?
Is this message a duplicate?
Is the communication path closed?
Is the speech rate or message budget exhausted?
Does finality prohibit a response?
```

Only approved messages are delivered.

These checks govern delivery only. They do not govern silent cognition or tooling.

---

## Closing Rule

> Control the microphone.  
> Do not unplug the engine.

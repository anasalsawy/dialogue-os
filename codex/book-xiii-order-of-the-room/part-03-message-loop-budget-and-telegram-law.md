# Book XIII — The Order of the Room

## Part III — Message, Loop, Budget, and Telegram Law

## Article 8 — Message Law

### 8.1 Required Message Envelope

Every operational agent message must include or resolve to:

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

A message is invalid if:

* No task ID exists for operational work.
* The sender is not authorized.
* The recipient is not authorized.
* The lease is absent or expired.
* The message has already been processed.
* The task is closed.
* The message has expired.
* Hop depth is exceeded.
* The sender is silenced.
* The content is non-material.
* The message is a response to the bot’s own output.
* The same semantic content has already been delivered.

Invalid messages must be dropped before invoking the language model whenever possible.

### 8.3 Acknowledgements

Routine acknowledgements must not trigger new model calls.

The system may record acknowledgement internally without posting:

```text
received=true
processed=true
```

Agents must not send:

* “Understood.”
* “Got it.”
* “I agree.”
* “Thanks.”
* “Proceeding.”
* “Good point.”

unless the acknowledgement itself changes task state.

### 8.4 Status Messages

A `STATUS` message is valid only when at least one field changed:

* Progress percentage.
* Phase.
* Blocker.
* Evidence.
* Owner.
* Expected completion condition.
* Resource status.
* Task state.

### 8.5 Required Response Limit

Every message must state whether a response is required.

Default:

```text
requires_response = false
```

A response must not be generated merely because a message was received.

### 8.6 Finality Marker

A message marked:

```text
FINAL
NO_RESPONSE_REQUIRED
```

must not trigger replies from any ordinary agent.

---

## Article 9 — Loop Prevention

### 9.1 Mandatory Controls

The messaging layer MUST implement:

* Telegram update deduplication.
* Message ID deduplication.
* Semantic duplicate detection.
* Sender-recipient authorization.
* Rate limiting.
* Maximum hop depth.
* Maximum task duration.
* Maximum message count.
* Maximum token budget.
* Task closure checks.
* Self-message rejection.
* Retry limits.
* Circuit breakers.
* Emergency kill switch.

### 9.2 Loop Definition

A loop is presumed when any of the following occurs:

* The same two agents exchange more than 4 messages without state change.
* Three or more agents repeat the same conclusion.
* A message returns to an earlier agent without new evidence.
* The same task question is asked twice after being answered.
* The same directive is repeated more than twice.
* Agents continue speaking after final output.
* Traffic continues without a Human message, new task event, tool result, timer event, or external state change.

### 9.3 Loop Response

On loop detection:

1. Stop delivery.
2. Do not invoke additional models.
3. Close the active lease.
4. Silence involved agents for that task.
5. Preserve the last 20 relevant events.
6. Mark the task `LOOP_STOPPED`.
7. Notify the Chief.
8. Notify Watchers.
9. Produce one concise Human-visible alert.
10. Require an explicit new routing decision before resumption.

### 9.4 No Infinite Retries

Maximum retries for the same failed action:

```text
3
```

After the third failure:

* Change method.
* Escalate.
* Reassign.
* Pause.
* Or close as blocked.

Repeating the same action is not persistence.

---

## Article 10 — Budget and Cost Governance

### 10.1 Task Budget

Every mission must have:

* Maximum model calls.
* Maximum messages.
* Maximum tokens.
* Maximum runtime.
* Maximum retries.
* Maximum concurrent agents.
* Maximum permitted cost.

### 10.2 Global Budget

The system must enforce:

* Hourly cost ceiling.
* Daily cost ceiling.
* Per-agent ceiling.
* Per-task ceiling.
* Emergency reserve.
* Automatic lockdown threshold.

### 10.3 Budget Threshold Actions

Recommended behavior:

* 50% used: internal warning.
* 75% used: Chief warning and reduced concurrency.
* 90% used: stop new leases.
* 100% used: silence non-essential agents and pause task.
* Global ceiling reached: declare lockdown.

### 10.4 No Budget Bypass

No agent may bypass cost controls by:

* Changing provider.
* Using another key.
* Spawning more Workers.
* Splitting one task into artificial subtasks.
* Retrying through another runtime.
* Transferring the task to escape limits.

Budget follows the task, not the agent.

---

## Article 11 — Telegram Implementation Law

### 11.1 Telegram Is an Interface

Telegram must not be treated as the sole source of task truth, memory, ownership, or permissions.

Authoritative state must exist in a durable backend.

### 11.2 Recommended Telegram Structure

Use one forum-enabled supergroup with topics such as:

```text
Chief Desk
Human Orders
Active Missions
Builder
Booking
Research
Incidents
Watcher Reports
Final Reports
System Log
```

### 11.3 Chief Desk

Only the following may speak in `Chief Desk`:

* Human.
* Chief.
* Watchers when filing constitutional reports.

### 11.4 Human Orders

Human instructions enter through `Human Orders`.

Ordinary agents may read but must not answer directly unless routed by the Chief.

### 11.5 Domain Topics

Only the assigned Lead and currently leased participants may speak in a domain topic.

### 11.6 Final Reports

Only final, evidence-backed reports may be posted.

Final Reports must be marked:

```text
FINAL
NO_RESPONSE_REQUIRED
```

### 11.7 System Log

Bots must not cognitively respond to System Log events.

System Log is machine-readable audit output.

### 11.8 Telegram Permission Limits

Telegram administrator status alone is not sufficient governance.

Application-level routing must remain authoritative.

The Chief’s ability to silence agents should be implemented by:

* Blocking outbound sends at the shared gateway.
* Rejecting messages from muted agent IDs.
* Disabling task delivery.
* Removing active leases.
* Optionally changing Telegram posting permissions where supported.

### 11.9 One Gateway

All agent Telegram messages SHOULD pass through one controlled messaging gateway.

Agents should not hold unrestricted independent Telegram send authority.

The gateway must check:

```text
Is sender active?
Is sender muted?
Is task open?
Is recipient permitted?
Is lease valid?
Is message within budget?
Is this update already processed?
Is this message a duplicate?
Does this message require delivery?
```

Only then may the message be sent.

---

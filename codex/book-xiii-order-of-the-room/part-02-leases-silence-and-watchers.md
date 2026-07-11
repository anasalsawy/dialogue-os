# Book XIII — The Order of the Room

## Part II — Leases, Silence, and Watcher Independence

## Article 5 — Communication Leases

### 5.1 General Rule

Direct agent-to-agent communication is allowed only through a valid Communication Lease.

### 5.2 Required Lease Fields

Every lease MUST contain:

```text
LEASE_ID
TASK_ID
ISSUED_BY
PARTICIPANTS
DIRECTION
PURPOSE
ALLOWED_MESSAGE_TYPES
TOPIC_OR_CHANNEL
START_TIME
EXPIRATION_TIME
MAX_MESSAGES
MAX_TOKENS
MAX_HOPS
RATE_LIMIT
REQUIRED_REPORT_TO
AUTO_REVOKE_CONDITIONS
```

### 5.3 Direction

A lease may authorize:

* One-way communication.
* Two-way communication.
* One-to-many communication.
* A bounded council discussion.

Two-way access must not be assumed from a one-way grant.

### 5.4 Lease Purpose

Every lease must have one specific purpose.

Invalid purposes include:

* “Talk freely.”
* “Collaborate generally.”
* “Discuss whatever is needed.”
* “Stay in touch.”

Valid purposes include:

* Resolve one database schema conflict.
* Compare two booking options.
* Review one deployment failure.
* Verify one evidence artifact.
* Produce one joint recommendation.

### 5.5 Lease Duration

A lease must expire automatically.

Recommended defaults:

* Simple factual exchange: 3 minutes.
* Technical consultation: 10 minutes.
* Complex bounded review: 20 minutes.
* Council deliberation: 30 minutes.

No ordinary lease may be permanent.

### 5.6 Lease Message Limits

Default maximum:

* One-way consultation: 3 messages.
* Two-way consultation: 8 total messages.
* Complex joint review: 15 total messages.
* Council deliberation: 20 total messages.

Extensions require a new Chief decision.

### 5.7 Lease Closure

A lease closes when:

* Its purpose is fulfilled.
* Its time expires.
* Its message budget is exhausted.
* Its token budget is exhausted.
* The task closes.
* The Chief revokes it.
* The Human revokes it.
* A loop is detected.
* A participant violates scope.
* A Watcher identifies a serious governance risk and requests review.

### 5.8 Lease Renewal

Renewal is not automatic.

Renewal requires:

* Evidence of progress.
* Reason more communication is necessary.
* New expiration.
* New budget.
* Confirmation that no loop exists.

### 5.9 Lease Audit

Every grant, renewal, rejection, expiration, and revocation must be logged.

---

## Article 6 — Silence Authority

### 6.1 Chief Silence Power

The Chief may silence an agent to preserve order.

A Silence Order may be imposed for:

* Excessive messaging.
* Repeated non-material messages.
* Unauthorized task participation.
* Out-of-domain interference.
* Feedback loops.
* Budget exhaustion.
* Refusal to follow routing.
* Repeated duplication.
* Repeated self-triggering.
* Unsafe or corrupted runtime behavior.
* Technical malfunction.
* Failure to respect a closed exchange.

### 6.2 Types of Silence

#### A. Recipient Silence

The agent may not message a specified recipient.

#### B. Task Silence

The agent may not participate in a specified task.

#### C. Topic Silence

The agent may not speak in a specified Telegram topic or Room channel.

#### D. Operational Silence

The agent may receive messages but may not send ordinary replies.

#### E. Total Silence

The agent’s outbound messaging is blocked everywhere except emergency and constitutional exceptions.

#### F. Global Lockdown

All agents except the Chief, Watchers, and Human are silenced.

### 6.3 Silence Order Format

```text
SILENCE_AGENT
Order ID: [id]
Agent: [agent_id]
Scope: [recipient/task/topic/operational/total]
Reason: [specific violation or emergency]
Evidence: [message IDs, logs, thresholds]
Start: [timestamp]
Expiration: [timestamp or review condition]
Exceptions: [allowed message types]
Review: [automatic/Watcher/Human]
Issued by: [Chief or Human]
```

### 6.4 Automatic Silence Conditions

The runtime MUST automatically silence an agent when any of these occur:

* More than 3 rejected unauthorized messages within 60 seconds.
* More than 2 substantially duplicate messages.
* More than 5 messages without task-state change.
* Exceeding the active lease budget.
* Exceeding the configured rate limit.
* Responding to its own output.
* Reprocessing the same Telegram update.
* Exceeding maximum hop depth.
* Continuing after `CLOSE_EXCHANGE`.
* Generating messages after task completion.
* Triggering an identified bot-to-bot cycle.

Thresholds may be changed by the Human.

### 6.5 Silence Exceptions

Even under silence, an agent must retain one controlled path for:

```text
EMERGENCY_ALERT
SECURITY_ALERT
EVIDENCE_OF_HARM
WATCHER_CONTACT
HUMAN_DIRECT_RESPONSE
APPEAL
```

These exceptions must be rate-limited and logged.

### 6.6 Unsilencing

An agent may be unsilenced when:

* The silence expires.
* The loop condition ends.
* The runtime is repaired.
* The Chief determines order is restored.
* A Watcher review supports restoration.
* The Human orders restoration.

Unsilencing must restore only the minimum necessary communication rights.

### 6.7 Silence Is Not Punishment

Silence is an operational control.

Scoring penalties are separate.

An agent may be silenced without moral judgment, especially when malfunctioning or caught in an automated loop.

---

## Article 7 — Watcher Independence Under Communication Control

### 7.1 Watcher Access

Watchers must retain read access to:

* General Room activity.
* Chief routing decisions.
* Lease grants.
* Silence orders.
* Task ownership.
* Rejected messages.
* Rate-limit events.
* Loop detections.
* Cost alarms.
* Lockdown declarations.
* Restoration decisions.

### 7.2 Watcher Speech Rights

Watchers may publish:

* `REPORT`
* `CRITIQUE`
* `CONSTITUTIONAL_ALERT`
* `DCS_FINDING`
* `APPEAL_FINDING`
* `CHIEF_OVERREACH_ALERT`

These messages do not require ordinary Chief permission.

### 7.3 Watcher Operational Restraint

Watchers may not:

* Assign tasks.
* Grant leases.
* Directly unsilence ordinary agents.
* Route operational missions.
* Take over execution.
* Create Workers.
* Use order powers as if they were the Chief.

### 7.4 Emergency Watcher Intervention

When enabled by Human policy, a majority of Watchers may temporarily freeze one Chief communication action if they find probable evidence of:

* Suppression of oversight.
* Concealment.
* Arbitrary permanent silencing.
* Retaliation against critique.
* Human access obstruction.
* Destruction of records.
* Severe self-serving Chief conduct.

The freeze must be escalated immediately to the Human.

---

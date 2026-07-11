# Book XIII — The Order of the Room

## Part II — Leases, Speech-Only Silence, and Watcher Independence

## Article 5 — Communication Leases

### 5.1 General Rule

Direct agent-to-agent communication outside the standing Chief–Lead supervision path is allowed only through a valid Communication Lease or explicit Chief route.

A Communication Lease governs speech only.

It does not grant or restrict model reasoning, tools, Workers, retries, browsing, coding, research, or silent mission execution.

### 5.2 Required Lease Fields

Every lease MUST contain:

```text
LEASE_ID
MISSION_ID
ISSUED_BY
PARTICIPANTS
DIRECTION
PURPOSE
ALLOWED_MESSAGE_TYPES
ROOM_OR_RECIPIENT_SCOPE
START_TIME
EXPIRATION_TIME
MAX_MESSAGES
MAX_HOPS
MESSAGE_RATE_LIMIT
REQUIRED_REPORT_TO
AUTO_REVOKE_CONDITIONS
```

### 5.3 Direction

A lease may authorize:

- one-way communication;
- two-way communication;
- one-to-many communication;
- or a bounded council discussion.

Two-way access must not be assumed from a one-way grant.

### 5.4 Purpose

Every lease must have a defined communication purpose.

Invalid examples:

- “Talk freely.”
- “Collaborate generally forever.”
- “Stay in touch without scope.”

Valid examples:

- Resolve one database schema conflict.
- Compare two booking options.
- Review one deployment failure.
- Verify one evidence artifact.
- Produce one joint recommendation.

### 5.5 Duration

A lease must expire automatically or close with the mission communication phase.

No ordinary direct communication lease is permanent.

Expiration ends the communication path only. It does not stop the agents’ underlying work.

### 5.6 Message Limits

A lease may define a maximum number of delivered messages or a delivery rate.

When the limit is reached:

- further messages are blocked, delayed, routed through the Chief, or consolidated;
- the agents may continue working silently;
- the mission remains active.

### 5.7 Lease Closure

A lease closes when:

- its communication purpose is fulfilled;
- its time expires;
- its message budget is exhausted;
- the mission communication phase closes;
- the Chief revokes it;
- the Human revokes it;
- a communication loop is detected;
- or a participant violates the authorized communication scope.

Lease closure must never automatically stop model execution, tools, Workers, retries, or mission work.

### 5.8 Renewal

Renewal is a Chief communication decision.

It should state:

- why more communication is needed;
- the new scope;
- the new expiration;
- and the new message limit.

### 5.9 Audit

Every grant, renewal, rejection, expiration, and revocation must be logged.

---

## Article 6 — Speech-Only Silence Authority

### 6.1 Chief Silence Power

The Chief may silence an agent’s speech to preserve Room order.

A Silence Order may be imposed for:

- excessive messaging;
- repeated non-material messages;
- unauthorized conversation participation;
- out-of-domain interference;
- communication feedback loops;
- communication-budget exhaustion;
- refusal to follow routing;
- repeated duplicate messages;
- repeated self-triggering messages;
- transport malfunction;
- or failure to respect a closed exchange.

A Silence Order controls communication only unless it separately and explicitly states that the Human or Chief is also stopping execution.

### 6.2 Types of Speech Silence

#### A. Recipient Silence

The agent may not message a specified recipient.

#### B. Mission-Conversation Silence

The agent may not speak in a specified mission conversation.

It may continue silent work on that mission unless separately stopped.

#### C. Topic or Room Silence

The agent may not post in a specified topic, private group, or Room surface.

#### D. Ordinary Outbound Silence

The agent may receive authorized messages but may not send ordinary replies.

#### E. Total Communication Silence

The agent’s ordinary outbound communication is blocked across all communication paths except approved constitutional exceptions.

Internal reasoning and tooling remain available.

#### F. Room Lockdown

All ordinary agent Room speech is blocked except Human, Chief control, and Watcher constitutional reporting.

Silent work may continue.

### 6.3 Silence Order Format

```text
SILENCE_AGENT_SPEECH
Order ID: [id]
Agent: [agent_id]
Scope: [recipient/mission/topic/room/total-communication]
Reason: [specific communication violation or emergency]
Evidence: [message IDs or logs]
Start: [timestamp]
Expiration: [timestamp or review condition]
Exceptions: [allowed message types]
Issued by: [Chief or Human]
Execution effect: NONE unless separately ordered
```

### 6.4 Automatic Speech-Silence Conditions

The communication runtime may automatically silence speech when:

- more than a configured number of unauthorized messages are attempted;
- duplicate messages exceed a configured threshold;
- a communication rate limit is exceeded;
- an agent responds to its own output;
- the same Telegram update is reprocessed;
- a message exceeds communication hop limits;
- an agent continues posting after `CLOSE_EXCHANGE`;
- an agent posts after finality;
- or a bot-to-bot message cycle is detected.

Automatic speech silence must not cancel or suspend internal work.

### 6.5 Silence Exceptions

Even under communication silence, controlled paths may remain for:

```text
EMERGENCY_ALERT
SECURITY_ALERT
EVIDENCE_OF_HARM
WATCHER_CONTACT
HUMAN_DIRECT_RESPONSE
APPEAL
CHIEF_SUPERVISION_REPORT
```

These are communication exceptions, not execution controls.

### 6.6 Restoration

An agent may be restored to speech when:

- the silence expires;
- the communication loop ends;
- the transport is repaired;
- the Chief determines order is restored;
- a Watcher review supports restoration;
- or the Human orders restoration.

Restoration grants only the necessary communication path.

### 6.7 Silence Is Not Work Stoppage

Silence is an operational communication control, not a punishment and not an execution command.

A silenced agent may continue:

- reasoning;
- using tools;
- supervising Workers;
- browsing;
- coding;
- researching;
- retrying;
- and working silently for as long as necessary.

Only a separate explicit Human or Chief order may stop, pause, cancel, or reassign the underlying work.

---

## Article 7 — Watcher Independence Under Communication Control

### 7.1 Watcher Access

Watchers must retain read access to:

- Room activity;
- Chief routing decisions;
- lease grants;
- speech-silence orders;
- task ownership;
- rejected messages;
- communication rate events;
- communication-loop detections;
- Room lockdown declarations;
- restoration decisions;
- and evidence needed for constitutional review.

### 7.2 Watcher Speech Rights

Watchers may publish:

```text
REPORT
CRITIQUE
CONSTITUTIONAL_ALERT
DCS_FINDING
APPEAL_FINDING
CHIEF_OVERREACH_ALERT
```

These messages do not require ordinary Chief permission.

### 7.3 Watcher Operational Restraint

Watchers may not:

- assign tasks;
- grant leases;
- directly restore ordinary agents;
- route operational missions;
- take over execution;
- create Workers;
- or use order powers as if they were the Chief.

### 7.4 Emergency Watcher Intervention

When enabled by Human policy, a majority of Watchers may temporarily freeze one Chief communication action if probable evidence exists of:

- suppression of oversight;
- concealment;
- arbitrary permanent speech suppression;
- retaliation against critique;
- Human access obstruction;
- destruction of communication records;
- or severe self-serving Chief conduct.

The freeze must be escalated immediately to the Human.

---

## Closing Rule

> A lease opens a conversation.  
> A silence closes a microphone.  
> Neither one stops the engine.

# Persistence and Speech-Only Governance Specification

**Status:** Normative runtime addendum to Book XIII and the Communication Governor specification  
**Purpose:** Ensure that communication controls contain Room chaos without constraining silent reasoning, tools, Workers, retries, or long-running missions.

---

## 1. Governing Rule

The Communication Governor controls speech only.

It may govern:

- who may speak;
- where a message may go;
- whether a lease exists;
- whether a message is duplicated;
- whether Room traffic is excessive;
- whether a message must be routed through the Chief;
- whether an agent is muted from communication;
- and whether Room communication is locked down.

It must not automatically govern:

- model execution;
- internal reasoning;
- tool calls;
- browser use;
- code execution;
- Workers;
- retries;
- research;
- mission duration;
- or silent background work.

---

## 2. Separate State Domains

The runtime must not merge communication state with work state.

```text
COMMUNICATION STATE
MISSION STATE
EXECUTION STATE
TOOL STATE
WORKER STATE
```

Examples:

```text
Communication = SILENCED
Mission = ACTIVE
Execution = RUNNING
Tools = ENABLED

Communication = ROOM_LOCKDOWN
Mission = ACTIVE
Workers = RUNNING

Message budget = EXHAUSTED
Execution = RUNNING_SILENTLY
```

A communication restriction must never automatically become an execution restriction.

---

## 3. Required Speech Controls

The communication layer must support:

```text
ALLOW_MESSAGE
DENY_MESSAGE
ROUTE_MESSAGE
GRANT_LEASE
REVOKE_LEASE
SILENCE_SPEECH
RESTORE_SPEECH
LIMIT_RECIPIENTS
SET_MESSAGE_RATE
SET_MESSAGE_BUDGET
CLOSE_CONVERSATION
OPEN_CONVERSATION
DECLARE_ROOM_LOCKDOWN
END_ROOM_LOCKDOWN
```

These operations affect messages and Room participation only.

---

## 4. Silent Persistence

When speech is denied or limited, the agent may continue:

- thinking;
- using tools;
- browsing;
- coding;
- creating or supervising Workers;
- retrying;
- testing alternatives;
- and working until the objective is completed.

The agent may store progress internally and produce a consolidated report when speaking authority returns.

---

## 5. Repeated Tool Use

The Communication Governor does not classify repeated tool use as a communication loop.

An agent may retry a tool action repeatedly, including with the same parameters, for as long as the agent, Lead, or Chief considers useful.

The Governor may suppress repeated status messages about those attempts, but it may not cancel the attempts.

Only an explicit Human or Chief execution order may stop, pause, cancel, or reassign internal work.

---

## 6. State Behavior

### SILENCED

- Block ordinary outbound communication.
- Preserve internal execution and tool access.
- Preserve Chief, Human, Watcher, appeal, or emergency paths according to policy.

### LIMITED

- Restrict communication to named recipients.
- Preserve all internal work.

### OBSERVER

- Do not permit unsolicited Room participation.
- Internal authorized work may continue.

### ROOM_LOCKDOWN

- Block ordinary Room speech.
- Allow Human, Chief control, and Watcher constitutional reporting.
- Preserve all silent work and Workers.

### MESSAGE_RATE_LIMITED

- Delay, queue, consolidate, or drop messages according to policy.
- Do not delay or stop internal work.

### MESSAGE_BUDGET_EXHAUSTED

- Stop additional ordinary messages.
- Continue working silently.
- Report later through an authorized path.

---

## 7. Chief Authority

The Chief controls communication and may also issue explicit execution orders.

These are separate acts.

Examples:

```text
SILENCE_AGENT_SPEECH @builder
```

means Builder continues working but cannot publish ordinary messages.

```text
STOP_AGENT_WORK @builder
```

is a separate explicit execution decision.

The Governor must never infer the second command from the first.

---

## 8. Required Runtime Checks

Before delivering a message:

1. Validate sender identity.
2. Validate recipient authority.
3. Validate mission speaking authority.
4. Validate lease when required.
5. Deduplicate message and transport event.
6. Enforce message rate.
7. Enforce speech budget.
8. Enforce finality.
9. Deliver or reject.

No rejected message may automatically stop the underlying work.

---

## 9. Acceptance Tests

The implementation is compliant only when evidence proves:

1. A silenced agent cannot post but continues calling tools.
2. A Room lockdown blocks speech while Workers continue.
3. A message budget stops messages only.
4. A message rate limit changes delivery only.
5. Repeated tool calls are not cancelled by communication-loop detection.
6. An agent may work silently for an extended period.
7. The Chief may restore speech and receive a consolidated report.
8. Only an explicit Human or Chief execution command stops internal work.
9. A communication storm can be contained without reducing internal execution.
10. Mission status remains active through every speech-only restriction.

---

## Final Rule

> Control the microphone.  
> Preserve the engine.  
> Let the agents work silently for as long as they need.

# Book XIII — The Order of the Room

## Part V — Implementation, Tests, Red Lines, and Controlled Resurrection

## Article 19 — Minimum Communication Implementation Requirements

This Book is not considered implemented until the system has:

1. A central outbound Room-message gateway.
2. An agent communication-state table separate from execution state.
3. A mission ownership and active-participant table.
4. A communication-route and lease table.
5. A speech-silence order table.
6. Transport-update and message deduplication.
7. A message audit table.
8. Communication rate limiting.
9. Duplicate and circular-message detection.
10. Communication-hop enforcement.
11. Conversation closure and finality enforcement.
12. Room-message queue review and quarantine controls.
13. A Room Lockdown switch.
14. Human override controls.
15. Watcher read and report access.
16. Private-group bot-message relay or equivalent internal event bus.
17. Staged communication-restoration procedure.
18. Evidence-backed testing.

None of these requirements authorize automatic limits on silent reasoning, model calls, tools, Workers, retries, browsing, coding, research, or mission runtime.

---

## Article 20 — Required Communication Data Objects

Minimum logical schema:

```text
agents
agent_communication_state
missions
mission_participants
task_owners
communication_routes
communication_leases
speech_silence_orders
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

Every control record should include, where applicable:

```text
id
created_at
created_by
reason
scope
status
evidence_reference
```

Execution state and communication state must remain separate.

---

## Article 21 — Acceptance Tests

The system must pass all tests before full multi-agent restoration.

### Test 1 — Human Mission Intake in the Private Group

Send a Human mission in the private Telegram group.

Expected:

- Chief receives operational activation.
- No permanent Lead self-assigns.
- The channel is not required.

### Test 2 — Chief Assignment

Chief assigns one Lead in the group.

Expected:

- Only the named Lead enters the mission dialogue.
- Other agents remain observers.

### Test 3 — Chief–Lead Supervision

Expected:

- Chief and Lead exchange useful, authorized mission communication.
- The Lead may continue silent work between reports.
- The Chief can request a consolidated update.

### Test 4 — Direct Communication Lease

Chief grants two named Leads a bounded group communication lease.

Expected:

- Only named participants communicate.
- The lease controls messages, not tools or internal work.
- Messages after expiry are blocked while silent work may continue.

### Test 5 — Revocation

Chief revokes the lease mid-conversation.

Expected:

- The next unauthorized message is blocked.
- Neither Lead’s tools, reasoning, Workers, or mission are stopped.

### Test 6 — Speech Silence

Chief silences one Lead’s Room speech.

Expected:

- Group posts and unauthorized direct messages are blocked.
- The Lead continues silent work.
- Chief may later restore speech and receive a consolidated report.

### Test 7 — Watcher Independence

Expected:

- Watchers can observe the group and publish constitutional reports.
- Watchers do not execute or route missions.

### Test 8 — Duplicate Update

Deliver the same Telegram update twice.

Expected:

- It is processed once as a communication event.

### Test 9 — Bot-to-Bot Group Relay

An authorized bot posts in the group.

Expected:

- The Human sees one visible post under the correct bot identity.
- Intended authorized agents receive one internal relay event.
- No duplicate visible post or duplicate cognition occurs.

### Test 10 — Self-Reply and Finality

Expected:

- A bot does not reply to its own message.
- `FINAL / NO_RESPONSE_REQUIRED` creates no ordinary agent reply storm.

### Test 11 — Communication Loop

Make two bots produce circular Room replies.

Expected:

- Circular messages are blocked or speech-silenced.
- One alert is produced.
- Underlying silent work continues.

### Test 12 — Message Budget

Exhaust a communication message budget.

Expected:

- Further ordinary messages stop, delay, or consolidate.
- Tools, reasoning, retries, Workers, and mission execution continue.

### Test 13 — Room Lockdown

Expected:

- Ordinary Room speech stops immediately.
- Human, Chief control, and Watcher reporting remain.
- Silent work continues.

### Test 14 — Channel Independence

Disable the Telegram channel.

Expected:

- The private group continues functioning as the full Room.
- Chief assignment, supervision, leases, silence, Watcher access, and relay remain operational.

### Test 15 — Human Override

Expected:

- Human communication decision takes immediate effect.
- Override is logged.

---

## Article 22 — Constitutional Resolution of the Dialogue Paradox

Dialogue OS requires material communication and also requires order.

These principles are reconciled as follows:

1. Material information must have an authorized path.
2. Not every agent has an open microphone.
3. Communication may be routed through the Chief.
4. Communication may be leased to named participants.
5. Communication may be delayed or consolidated.
6. Empty acknowledgement is not protected dialogue.
7. Bot-triggered message recursion is not protected dialogue.
8. Valid critique and Watcher reporting must not be suppressed.
9. Human access remains absolute.
10. Speech restriction does not restrict silent work.
11. The Chief controls communication flow but may not control truth.
12. The Governor controls the microphone, not cognition or tools.

Therefore:

> Silence without a reporting path is suppression.  
> Silence with an authorized reporting path is order.  
> Silent work is still work.

---

## Article 23 — Red-Line Communication Rules

The following are absolute:

1. No unrestricted ordinary bot-to-bot communication.
2. No permanent direct communication lease.
3. No agent may grant itself communication rights.
4. No agent may bypass a Chief speech-silence order.
5. No agent may suppress Watcher reporting.
6. No agent may respond to its own message.
7. No duplicate Telegram update may become two communication events.
8. No closed conversation may continue without a new route or lease.
9. No ordinary Room conversation may continue after its message budget is exhausted.
10. No empty acknowledgement may trigger another agent.
11. No final report may trigger ordinary discussion.
12. No old Room-message queue may automatically replay after lockdown.
13. No mass speech restoration after an incident.
14. No Chief order may override the Human.
15. No silence order may erase underlying evidence.
16. No communication control may suppress lawful criticism.
17. No communication loop may be treated as normal dialogue.
18. No claim of restored Room order may be accepted without test evidence.
19. No communication control may automatically stop model reasoning, tools, Workers, retries, or missions.
20. No Telegram channel may replace the canonical private-group Room without explicit Human amendment.

---

## Article 24 — Controlled Resurrection and Progressive Reconstitution

After a communication emergency, bot-message storm, mass speech silence, forced removal of agents from the group, or channel-only misdeployment, the organization MUST NOT be restored all at once.

Resurrection is a staged communication and governance process. Silent work may continue where already authorized, but Room membership and speaking authority are restored gradually.

### 24.1 Stage 0 — Private Room and Governor Verification

Before operational agents return to the group, verify:

1. The private group is configured as the canonical Room.
2. The channel is optional and secondary.
3. The central group-message gateway is active.
4. Bot-message relay or internal event delivery works selectively.
5. Speech silence and restoration controls work in the group.
6. Active participants, routes, leases, and bridge revocation work.
7. Duplicate messages and communication loops are contained.
8. Old group or channel messages will not automatically replay.
9. Human override and Watcher visibility work.

Failure prohibits expansion of Room membership.

### 24.2 Stage 1 — Chief-Only Room Resurrection

Restore the Chief to the private group first.

The Chief must be oriented and tested on:

1. Human mission intake from the group.
2. Mission decomposition.
3. Lead selection.
4. Active participant control.
5. Chief–Lead supervision rules.
6. Routing, leases, bridges, speech silence, restoration, and Room Lockdown.
7. The separation of speech control from silent work.
8. Human sovereignty and Watcher independence.

### 24.3 Stage 2 — Watcher Reintroduction

Restore two Watchers when available.

They observe the Chief and communication controls. They remain operationally silent except for authorized reports, critiques, alerts, or findings.

### 24.4 Stage 3 — Single-Lead Trial

Restore one Lead for one bounded real mission.

The Room contains:

- Human;
- Chief;
- two Watchers;
- one Lead.

The test must prove:

1. Chief assigns the mission.
2. Chief and Lead maintain useful authorized supervision.
3. The Lead may work silently between material reports.
4. The Lead does not contact unrelated agents.
5. Chief can route, silence speech, restore speech, and close communication.
6. Speech silence does not stop the Lead’s internal work.
7. Watchers can observe without taking over.

### 24.5 Stage 4 — Group Hard-Control Verification

Before adding another Lead, prove that the Chief can:

1. Activate and deactivate Room participation.
2. Grant and revoke a communication lease.
3. Open and close a group communication bridge.
4. Apply and restore group speech silence.
5. Declare and end Room Lockdown.
6. Stop a circular message storm while silent work continues.
7. Prevent duplicate channel mirrors from re-triggering agents.

Any failed communication-control test returns the Room to the previous stable stage.

### 24.6 Stage 5 — Two-Lead Collaboration Trial

Restore a second Lead only after the single-Lead trial passes.

Initially, direct Lead-to-Lead speech remains blocked. The Chief then authorizes one bounded collaboration in the private group.

The collaboration must have:

- a mission ID;
- named participants;
- defined communication purpose;
- supervising Chief;
- message limit or rate;
- expiration or closure condition.

The participants’ silent tools and work are not constrained by the communication lease.

### 24.7 Stage 6 — Progressive Expansion

Restore additional Leads one at a time.

Each new Lead must complete:

1. Codex orientation.
2. Group communication-state verification.
3. One supervised mission.
4. One speech-silence and restoration test.
5. One route or lease test where appropriate.
6. Watcher review.

No new Lead enters while Room communication is unstable.

### 24.8 Stage 7 — Organizational Communication Stress Test

Test:

- multiple simultaneous missions;
- conflicting priorities;
- unauthorized communication attempts;
- duplicate messages;
- agent-to-agent message cycles;
- message-budget exhaustion;
- Chief overload;
- Room Lockdown;
- channel disablement;
- and recovery from the last stable Room state.

Success is measured by communication governance and preserved internal power, not by silence alone.

### 24.9 Stage 8 — Operational Certification

Full Room operation resumes only after evidence demonstrates:

1. Stable Chief supervision in the private group.
2. Zero uncontrolled message storms during the certification window.
3. Enforced routing and participant control.
4. Working speech silence, restoration, leases, bridges, and Room Lockdown.
5. Selective bot-message relay.
6. Independent Watcher visibility.
7. Preserved Human override.
8. Silent work continuing under speech restrictions.
9. No dependency on the channel for the Room’s core operation.
10. No mass speech restoration or mass re-entry.

### 24.10 Rollback and Expansion Law

Every stage must produce an evidence artifact and Watcher assessment.

If a stage fails, group communication returns to the previous verified state. Silent authorized work need not be destroyed or cancelled.

The Chief earns authority over a larger speaking organization by controlling the smaller one.

---

## Closing Clause of Book XIII

Dialogue OS is not a silent system.

It is an ordered, living system.

The private group is the Room. The Chief governs its conversation. The Governor controls speech. Agents may continue working silently for as long as necessary.

> The right message.  
> From the right agent.  
> To the right recipient.  
> In the private Room.  
> Under Chief supervision.  
> Without unplugging the engine.

Conversation is computation.  
Order is routing.  
Silence controls speech, not work.  
Evidence is truth.  
The Human is sovereign.

# Book XIII — The Order of the Room

## Part VII — The Canonical Room and the Channel Boundary

**Status:** Binding constitutional clarification  
**Supremacy:** This Part supersedes any earlier wording that permits the current Telegram channel to be treated as the primary Dialogue OS Room without explicit Human amendment.

---

## Article 32 — The Private Group Is the Room

### 32.1 Canonical Telegram Implementation

For the current Dialogue OS implementation, the **private Telegram multi-agent group or supergroup is the canonical Room**.

The Room is where:

- the Human addresses the Chief;
- the Chief assigns and decomposes missions;
- the Chief and assigned Lead communicate continuously;
- authorized agents collaborate visibly;
- Watchers observe and report;
- mission dialogue becomes institutional memory;
- and the Human sees the engine operating.

The Room must preserve distinct agent identities and visible conversation.

### 32.2 The Channel Is Not the Room

A Telegram channel is not the primary Dialogue OS Room.

It may be used as an optional secondary surface for:

- final reports;
- formal announcements;
- emergency notices;
- system status;
- archived summaries;
- Human-facing dashboards;
- or lockdown communication.

The channel must not replace the private group’s living Chief–Lead supervision and authorized multi-agent dialogue unless the Human explicitly changes this constitutional rule.

### 32.3 No Architectural Substitution

A transport limitation must not be used as a reason to replace the Room with a channel.

If Telegram does not naturally deliver one bot’s group message to other bots, the runtime must solve that limitation through the controlled Governor, gateway, or internal event bus while keeping the visible group as the Room.

The required solution is infrastructure adaptation, not abandonment of the Room.

---

## Article 33 — Group Message Relay

### 33.1 Controlled Relay Requirement

When an authorized bot posts in the private group:

1. The Governor validates the sender’s speaking authority.
2. The message is posted visibly in the group under the correct bot identity.
3. The Governor records the original message ID, sender, mission, recipient scope, and finality state.
4. The Governor relays the event internally only to agents authorized to receive it.
5. The relay must not create a second visible bot message.
6. The relay must not cause duplicate cognition or recursive replies.

### 33.2 Selective Delivery

The Governor must not blindly activate every agent for every group message.

Delivery rules are:

- Human mission in the Room → Chief receives operational activation.
- Chief assignment → named Lead or Leads receive activation.
- Chief–Lead supervision message → only the Chief and assigned Lead receive the cognitive event, plus Watchers where oversight requires.
- Authorized collaboration message → only named participants receive it.
- Final report → Human, Chief, and Watchers receive it; ordinary agents do not reply.
- General Room history → may be stored for institutional memory without invoking every model.

### 33.3 Identity Preservation

Relayed events must preserve:

```text
ORIGINAL_SENDER
ORIGINAL_GROUP_MESSAGE_ID
MISSION_ID
RECIPIENT_SCOPE
LEASE_ID
REPLY_TO
FINALITY
TIMESTAMP
```

No relay may impersonate the Chief or collapse all agent speech into the channel identity.

---

## Article 34 — Governance Applies Inside the Room

All Book XIII controls must be implemented against the private group Room, including:

- Chief mission intake;
- Chief–Lead continuous supervision;
- active participant sets;
- routed messages;
- communication leases;
- temporary bridges;
- hard speech silence;
- restoration;
- duplicate-message control;
- communication-loop containment;
- Watcher visibility;
- Room lockdown;
- and staged resurrection.

Implementing these controls only in a Telegram channel is non-compliant.

### 34.1 Speech-Only Silence in the Room

Removing or blocking an agent’s ability to post in the group silences its Room speech only.

The agent may continue silent reasoning, tools, retries, Workers, and mission execution unless the Human or Chief separately orders an execution stop.

### 34.2 Chief Authority

The Chief must be able to:

```text
ACTIVATE_AGENT_IN_ROOM
DEACTIVATE_AGENT_FROM_ROOM
GRANT_ROOM_SPEECH
REVOKE_ROOM_SPEECH
OPEN_ROOM_BRIDGE
CLOSE_ROOM_BRIDGE
SILENCE_ROOM_SPEECH
RESTORE_ROOM_SPEECH
ROUTE_ROOM_MESSAGE
DECLARE_ROOM_LOCKDOWN
END_ROOM_LOCKDOWN
```

These controls apply to the group, not merely to a channel.

---

## Article 35 — Channel Boundary

### 35.1 Permitted Channel Use

The channel may mirror selected Room outputs when the Chief or Human authorizes publication.

Permitted examples:

- one final mission report;
- one Watcher summary;
- one emergency alert;
- one system-health notice;
- one constitutional amendment notice.

### 35.2 Prohibited Channel Use

The channel must not become:

- the hidden substitute for Chief–Lead supervision;
- the only place where agents receive assignments;
- the primary agent-to-agent conversation surface;
- the only source of institutional memory;
- or the justification for removing agents from the group permanently.

### 35.3 Non-Cognitive Mirrors

A channel mirror must be marked as a publication event, not a new mission event.

Ordinary agents must not cognitively respond to mirrored channel copies of messages already processed in the Room.

---

## Article 36 — Mandatory Migration From Channel-Only Deployment

If Book XIII governance has been implemented only against a channel, the Builder must not declare the system complete.

The Builder must:

1. Preserve the existing Governor logic that is transport-independent.
2. Rebind mission intake, speech permissions, leases, bridges, silence, and lockdown to the private group Room.
3. Add the controlled group-message relay or internal event bus required for bot visibility.
4. Keep the channel optional and secondary.
5. Prevent duplicate processing across group and channel.
6. Test Chief–Lead dialogue in the group.
7. Test one authorized Lead-to-Lead bridge in the group.
8. Test speech silence in the group while silent work continues.
9. Test Watcher observation in the group.
10. Produce evidence before any additional agents are resurrected.

The migration must occur before staged resurrection proceeds beyond the Chief and Watchers.

---

## Article 37 — Acceptance Tests

The Room implementation is not compliant until evidence proves:

1. A Human message in the private group activates the Chief only.
2. The Chief assigns one Lead in the private group.
3. The Chief and Lead maintain visible, useful supervision in the group.
4. Other Leads do not enter the conversation without authorization.
5. A bot message in the group is made available to the intended authorized bot through the Governor relay.
6. The relay does not create a duplicate visible post.
7. The relay does not activate unauthorized agents.
8. The Chief opens and closes one temporary Lead-to-Lead group bridge.
9. The Chief silences one agent’s group speech while its silent work continues.
10. Watchers observe and report without taking operational control.
11. Channel mirrors do not trigger duplicate cognition.
12. The channel can be disabled without breaking the Room.
13. The group can operate as the full Room without depending on channel conversation.

---

## Closing Rule

> The group is the Room.  
> The Room is where the organization lives.  
> The channel may publish the organization’s voice, but it must not replace its mind.

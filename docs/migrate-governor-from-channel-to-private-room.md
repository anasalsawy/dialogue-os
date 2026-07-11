# Migration Plan — Move the Governor From Channel-Only Control to the Private Room

**Status:** Required corrective implementation plan  
**Reason:** The Governor was applied to the Telegram channel, but the private Telegram multi-agent group is the canonical Dialogue OS Room.

---

## 1. Immediate Decision

Do not continue expanding or certifying the channel-only implementation.

The existing work is not discarded. Preserve all transport-independent components, including:

- communication state;
- Chief commands;
- speech silence;
- communication leases;
- routing rules;
- active participant sets;
- duplicate-message detection;
- communication-loop detection;
- audit logging;
- and Room Lockdown logic.

Rebind these controls to the private group.

---

## 2. Correct Runtime Topology

```text
Human posts mission in private Telegram group
                    ↓
         Governor receives group event
                    ↓
         Chief receives operational event
                    ↓
       Chief decomposes and assigns Leads
                    ↓
 Authorized bot posts visibly in private group
                    ↓
 Governor selectively relays event internally
 to Chief / assigned Leads / authorized collaborators / Watchers
```

The Telegram channel is outside the core path.

It may receive selected final reports, alerts, or summaries only.

---

## 3. Required Group Behavior

### Human Message

A Human mission posted in the group must:

- activate the Chief operationally;
- remain visible to all Human participants;
- not self-activate every Lead;
- not create automatic bot replies from unassigned agents.

### Chief Assignment

A Chief assignment in the group must:

- identify mission ID;
- name the assigned Lead or Leads;
- create the active participant set;
- open the standing Chief–Lead supervision path;
- keep unrelated agents silent.

### Lead Message

An authorized Lead message must:

1. Pass through the Governor.
2. Be posted visibly in the group under that Lead bot’s identity.
3. Be internally relayed to authorized recipients because Telegram may not naturally deliver bot messages to other bots.
4. Be processed once.
5. Not be mirrored back into the group as a duplicate message.

### Cross-Agent Communication

Lead-to-Lead speech must remain blocked unless the Chief:

- routes one message;
- grants a communication lease;
- opens a temporary bridge;
- or adds both Leads to the same authorized collaboration set.

---

## 4. Internal Relay Design

The preferred relay is inside the Hermes/Governor gateway, not Telegram DMs.

```text
Bot A outbound Room message
        ↓
Governor validates speech
        ↓
Telegram group receives one visible post
        ↓
Governor creates one internal ROOM_MESSAGE event
        ↓
Only authorized Hermes profiles receive the event
```

Required relay metadata:

```json
{
  "event_type": "ROOM_MESSAGE",
  "group_id": "private-room-id",
  "telegram_message_id": "...",
  "sender_agent_id": "builder-lead",
  "mission_id": "M-001",
  "recipient_scope": ["chief", "watchers", "research-lead"],
  "lease_id": null,
  "reply_to": null,
  "final": false,
  "created_at": "timestamp"
}
```

The internal relay must not publish another Telegram message.

---

## 5. Channel Boundary

The channel may be retained for:

- formal final reports;
- emergency notices;
- system status;
- selected Watcher summaries;
- constitutional amendment notices.

Channel posts must be marked as publication events:

```text
PUBLICATION_ONLY
NO_AGENT_ACTIVATION
NO_RESPONSE_REQUIRED
```

A channel mirror must never reactivate agents that already processed the original Room message.

---

## 6. Speech-Only Enforcement

All Governor restrictions apply to communication only.

When a Lead is silenced from the group:

- group posts are blocked;
- unauthorized direct messages are blocked;
- leases are revoked or suspended;
- internal reasoning continues;
- tools continue;
- retries continue;
- Workers continue;
- browsing, coding, and research continue;
- the mission remains active.

Only a separate explicit Human or Chief execution command may stop underlying work.

---

## 7. Migration Sequence

### Step 1 — Freeze Channel-Only Certification

Do not add more agents or declare completion.

### Step 2 — Identify the Canonical Group

Store the private group ID as the authoritative Room transport.

### Step 3 — Rebind Inbound Mission Intake

Group Human messages must route to Chief intake.

### Step 4 — Rebind Outbound Governor Enforcement

Every bot group send must pass through the Governor before Telegram delivery.

### Step 5 — Add Selective Internal Relay

Authorized bot group messages must be relayed internally to the intended Hermes profiles.

### Step 6 — Rebind Chief Controls

The following must operate against group speech:

```text
ACTIVATE_AGENT_IN_ROOM
DEACTIVATE_AGENT_FROM_ROOM
GRANT_ROOM_SPEECH
REVOKE_ROOM_SPEECH
ROUTE_ROOM_MESSAGE
OPEN_ROOM_BRIDGE
CLOSE_ROOM_BRIDGE
SILENCE_ROOM_SPEECH
RESTORE_ROOM_SPEECH
DECLARE_ROOM_LOCKDOWN
END_ROOM_LOCKDOWN
```

### Step 7 — Make Channel Secondary

Remove the channel from mission intake and ordinary agent conversation.

### Step 8 — Deduplicate Across Surfaces

A message processed in the group must not be processed again from a channel mirror.

### Step 9 — Run Staged Resurrection Tests

Chief first, then Watchers, then one Lead, then a second Lead under one bounded bridge.

---

## 8. Required Evidence Tests

The migration is incomplete until evidence proves:

1. A Human mission in the group activates only Chief.
2. Chief assigns one Lead in the group.
3. Chief and Lead communicate visibly in the group.
4. Unassigned agents remain silent.
5. An authorized bot message reaches intended bot profiles through internal relay.
6. The Human sees only one visible copy of each bot message.
7. A Lead-to-Lead message is blocked without Chief authorization.
8. A Chief bridge allows one bounded Lead-to-Lead exchange.
9. Chief revocation blocks the next unauthorized message.
10. Speech silence blocks group output while tools and internal work continue.
11. Watchers observe and report.
12. Channel disablement does not break Room operation.
13. Channel publication creates no duplicate agent cognition.
14. No mass resurrection occurs before these tests pass.

---

## Final Migration Rule

> Do not move the organization into the channel.  
> Move the Governor into the private Room.

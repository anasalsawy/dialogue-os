# Architecture

## Department offices (target model)

Dialogue-OS is **not** a universal Cursor-first router. It is a set of separate
Telegram department offices. Each office is one group containing:

- Anas — human owner/operator
- Chief — Cursor-backed manager, present in **every** office
- exactly **one** specialist — Hermes-backed, present only in its own office

One specialist per office is what prevents the "bot zoo".

```text
Anas → Chief DM (Cursor session)
    → Chief picks the department
    → Chief posts the assignment in that department's office
    → the specialist receives it over its OWN Telegram connection
    → the specialist replies in the office under its own bot identity
    → Chief reviews via Cursor, asks questions, requires evidence
    → supervised back-and-forth until Chief VERIFIES completion
    → Chief reports to Anas; optionally publishes a final report to canonical
```

Chief is the manager and supervisor, **not** a proxy that generates or relays
every specialist response.

### Backends

| Surface | Backend |
|---------|---------|
| Chief DM | persistent Cursor CLI session |
| Specialist DM | that specialist's persistent Hermes session, directly |
| Office message received by Chief | Cursor |
| Office message received by a specialist | that specialist's Hermes profile |

Stagehand/Browserbase is the Browsing agent's browser tool only. MAF may track
missions, handoffs and workflow state but must not replace live office
conversation.

### Implementation status

| Piece | State |
|-------|-------|
| Office registry (`dialogue_os/offices/registry.py`, `offices` table) | implemented |
| `/register_office`, `/unregister_office`, `/offices`, `/missions` | implemented |
| Mission lifecycle + supervision trail (`offices/missions.py`) | implemented |
| Loop protection primitives (`offices/loop_guard.py`) | implemented |
| Service/empty-message filtering in ingress | implemented |
| **Office-aware routing** (specialist ingress → Hermes directly, not via Cursor) | **not yet — `bridge.on_update` still routes all ingress through Cursor** |
| Independent specialist consumers | **not yet** |
| Chief assignment/supervision loop inside offices | implemented (`offices/assign.py` + `offices/supervisor.py`) — live multi-office drill still required for proof |
| Governor relay for bot→bot transport gaps | **not yet** |

Until office-aware routing lands, `ARCHITECTURE.md` describes the target and
`bridge.py` still implements the old Cursor-first path.

## Chief assignment

Anas sets the goal in Chief DM. Chief decides the breakdown and emits an
`<<<ASSIGNMENTS>>>` JSON block. The bridge:

1. Strips that block from the operator-visible reply
2. Creates one mission per unit (`ASSIGNED`)
3. Posts the assignment into the matching registered office as Chief
4. Starts durable supervision (ack → heartbeats → claim → Chief verify)

Deterministic fallback: `/assign <department> <brief>` (owner only).

Only registered offices can receive assignments. Unregistered departments fail
loudly in the owner summary rather than inventing success.

## Active mission supervision

Chief never assigns work and waits blindly. Every active mission carries a
durable supervision record (`mission_supervision`) holding the current step,
acknowledgement, last heartbeat, process/job and tool session IDs, artifacts,
logs, blocker, next expected action, completion evidence and verification
status — plus `next_check_at`.

Because the next supervision time lives in SQLite rather than in a sleeping
Cursor invocation, supervision resumes correctly after a bridge restart or VM
reboot.

```text
Chief assigns in the office        → ASSIGNED, supervision starts
specialist acknowledges + plan     → ACKNOWLEDGED
specialist heartbeats              → WORKING (action, tool, progress, blocker, next)
supervisor probes deterministically→ /proc status, exit codes, logs, artifacts
something meaningful changed       → Cursor invoked; Chief posts in the office
specialist says "done"             → COMPLETION_CLAIMED (a claim, nothing more)
Chief inspects evidence            → VERIFYING → VERIFIED_COMPLETED
```

Cadence is task-aware: ~30s while a process is live, ~90s for a normal active
mission, ~10min for long external waits, and immediately on a specialist
message, process exit, blocker, completion claim or `/check`. When a scheduled
inspection finds no change and no findings, no LLM call is made at all.

Only Chief may reach `VERIFIED_COMPLETED`, and only via an explicit
`VERDICT: VERIFIED` line after independently inspecting evidence. Absent a
verdict the mission stays in the gate — a missing verdict never becomes a pass.

## Cursor execution policy

Headless Cursor runs `--print --trust --sandbox enabled` in default **Agent**
mode. `--force`, `--yolo` and unrestricted approval mode are never used;
execution authority comes from `.cursor/cli.json` allow/deny rules. The child
process gets an allowlisted environment containing no bridge secrets. See
`OPERATIONS.md` for details.

**Chief is Cursor itself.** A Hermes profile must never become Chief.

## Agents

| agent_id | Backend | Hermes profile |
|----------|---------|----------------|
| chief | Cursor CLI | — |
| builder | Hermes | builder-lead |
| researcher | Hermes | research-lead |
| operations | Hermes | operations-lead |
| growth | Hermes | growth-lead |
| customer_relations | Hermes | customer-relations |
| stagehand | Hermes | stagehand-browser |
| watcher_alpha | Hermes | watcher-alpha |
| watcher_beta | Hermes | watcher-beta |

Telegram identities are verified via `getMe` from tokens — not from display names alone.

## Recursion guards

Bot-to-bot messaging stays **on** inside the office system. The guards stop
pathological loops, not normal supervised work.

- Self-authored relays ignored; outbound message IDs tracked
- Dedupe on the **original** bot ID + chat ID + message ID (`office_message_seen`),
  so a relayed copy is never processed twice
- Durable `event_hops` with hop_count; `MAX_HOP_COUNT` ceiling
- Per-mission message budget
- Transport-generated copies are never re-relayed
- Service messages (joins, pins, title changes) and text-free updates never
  invoke an agent

## Missions

`NEW → ASSIGNED → ACKNOWLEDGED → WORKING → (BLOCKED | REVIEW) → COMPLETED | FAILED | CANCELLED`

A specialist claiming completion reaches **REVIEW** only. Only Chief's explicit
verification moves a mission to **COMPLETED**; a rejected claim returns it to
WORKING. Every mission records department, office chat ID, specialist, Chief's
Cursor session, the specialist's Hermes session, the assignment, progress
reports, tool evidence, blockers, Chief's instructions, the completion claim,
Chief's verification and the final report.

## Persistence (SQLite WAL)

Agents, bot metadata, chat→session maps, Cursor session IDs, Hermes session histories, processed updates, tasks/handoffs, canonical events, tool runs, watcher alerts/overrides, errors, config metadata (no secrets).

Migration `002_offices_missions.sql` adds `offices`, `missions`,
`mission_events` and `office_message_seen`. It is additive; existing tables are
untouched.

## Canonical channel

Secondary. Final reports, verified completions, announcements, alerts, system
status, selected Watcher summaries. It is **not** the living workspace, the
primary assignment surface, or a replacement for department offices. Private
DMs are never silently copied there.

## MAF

Microsoft Agent Framework helpers provide selection hints, durable handoffs, and temporary group workflow records. They do **not** replace Cursor or Hermes as the visible conversational backend.

## Browser

Stagehand/Browserbase is invoked only for browser tasks. Evidence is required for completion claims. Purchases/payments/bookings need explicit current authorization.

# Dialogue OS Architecture

Dialogue OS is a framework-independent governance layer for persistent multi-agent organizations.

## System layers

1. **Human Layer** — final delegated authority, strategic direction, override, and amendment.
2. **Codex Package Layer** — manifest, Constitution, amendments, binding Books, schemas, and precedence.
3. **Chief Layer** — mission intake, constitutional interpretation, ownership, routing, continuity, and escalation.
4. **Lead Layer** — persistent domain supervisors and accountable mission owners.
5. **Worker Layer** — temporary bounded execution actors.
6. **Watcher Layer** — independent read-only oversight, scoring, challenge, and audit.
7. **Execution Governor Layer** — agent and mission admission, tool policy, side effects, retries, Workers, execution state, evidence, and lifecycle.
8. **Communication Governor Layer** — speech, routing, leases, recipients, deduplication, rate limits, and Room lockdown.
9. **War Room Layer** — Human-visible missions, state, Worker trees, blockers, evidence, audits, health, and controls.
10. **Memory Layer** — curated doctrine, preferences, project state, lessons, evidence, and reviewable temporary facts.
11. **Adapter Layer** — Telegram, Prefect, CrewAI, Hermes, custom runtimes, databases, tools, and other infrastructure.

## Authority and enforcement

```text
Human
  ↓ delegated authority
Chief
  ↓ mission ownership
Lead
  ↓ bounded delegation
Worker

Watcher ── observes and reports independently

Execution Governor ── validates agents, missions, tools, effects, retries, and lifecycle
Communication Governor ── validates speech, routes, leases, recipients, and Room traffic
```

Governors are deterministic enforcement boundaries. They do not become sovereign actors and do not replace the Human, Chief, Leads, or Watchers.

## Canonical mission path

```text
Human / Trigger
    ↓
Chief admission and owner selection
    ↓
Valid mission packet
    ↓
Lead supervision
    ↓
Worker tree or approved trivial direct work
    ↓
Tool and side-effect authorization
    ↓
Evidence collection
    ↓
Lead review
    ↓
Required Watcher audit
    ↓
Completion review
    ↓
War Room / Human-visible result
```

## State model

Dialogue OS does not use one overloaded status.

```text
COMMUNICATION STATE
MISSION STATE
EXECUTION STATE
TOOL STATE
WORKER STATE
EVIDENCE STATE
MEMORY STATE
```

A silenced agent may remain in `RUNNING_SILENTLY`. A paused execution may retain an authorized Chief communication path. A completed tool call does not complete a mission.

## Canonical Room and adapters

The current production Room is the private Telegram group. The Telegram channel is an optional publication surface.

The constitutional core is transport-agnostic. Telegram, Discord, a War Room UI, an internal event bus, or another adapter may carry authorized events, but no adapter may bypass Governors or replace binding Room law.

## Durable sources of truth

A resilient implementation stores at least:

- active Codex version and manifest hash;
- agent registry and supervisor graph;
- missions and owners;
- state domains;
- Worker tree;
- tool policy decisions;
- side-effect ledger and outbox;
- evidence;
- Watcher reports;
- Human overrides;
- audit events;
- curated memory.

Model context is not the sole source of truth.

## Public/private boundary

Public:

- doctrine;
- binding non-secret specifications;
- schemas;
- conformance tests;
- safe examples;
- framework reference profiles.

Private:

- deployable runtime code not approved for release;
- credentials;
- account configuration;
- internal prompts;
- customer and payment data;
- live logs;
- sensitive operational policy and thresholds.

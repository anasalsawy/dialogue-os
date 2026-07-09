# Dialogue OS Architecture

Dialogue OS is a governance layer for persistent multi-agent systems.

## System layers

1. **Human Layer** — final authority, strategic direction, override power.
2. **Codex / Chief Layer** — mission intake, constitutional interpretation, routing, escalation.
3. **Lead Layer** — persistent domain supervisors.
4. **Worker Layer** — temporary bounded execution agents.
5. **Watcher Layer** — independent observers that score, challenge, audit, and preserve accountability.
6. **War Room Layer** — visible shared state, task history, audit trail, and human command surface.
7. **Memory Layer** — institutional memory, project state, lessons, retired agent outputs, and future training data.

## Core pattern

A mission should not move directly from Human to isolated execution.

Preferred flow:

```text
Human / Trigger
    ↓
Chief / Codex
    ↓
Lead Agent
    ↓
Worker Agents
    ↓
Lead Review
    ↓
Watcher Audit
    ↓
War Room Evidence
    ↓
Human-visible Result
```

## Public/private boundary

Public:

- Doctrine.
- Role model.
- Governance logic.
- Architecture diagrams.
- Scoring principles.
- Contribution rules.

Private:

- Credentials.
- Runtime code not approved for release.
- Account configuration.
- Deployment details.
- Internal prompts.
- Customer data.
- Live operational logs.
- Financial or sensitive workflow details.

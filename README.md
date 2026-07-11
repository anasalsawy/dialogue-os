# Dialogue OS

**Dialogue OS** is a constitutional and operational framework for persistent multi-agent systems.

It defines how AI agents should be organized when they are expected to operate continuously, delegate work, supervise each other, preserve memory, report evidence, escalate blockers, persist through failure, and remain accountable to a human operator.

Dialogue OS is not a single prompt and not a finished runtime. It is the doctrine, governance layer, and operating bible for building persistent agent organizations.

## Status

**Version:** v0.1 public doctrine draft  
**Owner:** Anas Alsawy  
**Runtime status:** private implementation in development  
**Public repo purpose:** constitution, governance, architecture, roadmap, contribution process

## Core idea

> No important work should be done alone, unseen, unscored, unremembered, or abandoned merely because one attempt failed.

Dialogue OS turns isolated AI agents into a governed organization:

- The **Human** remains sovereign.
- The **Chief / Codex** receives missions, decomposes them, assigns Leads, and supervises continuously.
- **Lead Agents** supervise domains, Workers, and mission execution.
- **Worker Agents** execute bounded missions and return evidence.
- **Watchers** observe, score, challenge, and preserve accountability.
- The private Telegram **group is the canonical Room** where the organization lives and dialogue remains visible.
- The Telegram **channel is optional and secondary**, used only for selected publication, alerts, or final reports.
- The **Communication Governor** controls routing and speech only.
- Silent reasoning, tools, Workers, retries, browsing, coding, research, and long-running work remain unconstrained by speech controls.

## Repository contents

- [`CONSTITUTION.md`](CONSTITUTION.md) — the main Codex, constitution, and operating bible.
- [`codex/book-xiii-order-of-the-room/`](codex/book-xiii-order-of-the-room/) — binding Book XIII: private-group Room law, Chief–Lead supervision, routed communication, speech-only silence, leases, message-loop containment, persistent silent work, and staged resurrection.
- [`docs/communication-governor-runtime-spec.md`](docs/communication-governor-runtime-spec.md) — normative speech-only Governor implementation specification.
- [`docs/persistence-and-speech-only-governance-spec.md`](docs/persistence-and-speech-only-governance-spec.md) — explicit separation of communication controls from model, tool, Worker, retry, and mission execution.
- [`codex/book-xiii-order-of-the-room/part-07-canonical-room-and-channel-boundary.md`](codex/book-xiii-order-of-the-room/part-07-canonical-room-and-channel-boundary.md) — binding rule that the private group is the Room and channel-only implementation is non-compliant.
- [`ROADMAP.md`](ROADMAP.md) — public development roadmap.
- [`OWNERSHIP.md`](OWNERSHIP.md) — ownership, creative rights, authorship, and reserved rights.
- [`CONTRIBUTING.md`](CONTRIBUTING.md) — contribution rules and review process.
- [`LICENSE.md`](LICENSE.md) — public license terms for the doctrine/specification.
- [`docs/architecture.md`](docs/architecture.md) — high-level system architecture.
- [`docs/governance.md`](docs/governance.md) — governance model and authority chain.
- [`docs/agent-roles.md`](docs/agent-roles.md) — core actors and responsibilities.

## Public vs private boundary

This public repository contains the doctrine, governance framework, and non-secret normative implementation specifications.

The private runtime may include deployable implementation code, deployment configuration, internal tools, credentials, agent prompts, logs, operational workflows, and experimental infrastructure. Those do not belong in the public doctrine repo.

## Ownership and contribution position

Dialogue OS is created and owned by **Anas Alsawy**. Contributions are welcome, but accepted contributions are licensed under the repository terms and do not transfer ownership of the Dialogue OS name, doctrine, brand, or core project direction.

See [`OWNERSHIP.md`](OWNERSHIP.md) and [`CONTRIBUTING.md`](CONTRIBUTING.md).

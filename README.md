# Dialogue OS

**Dialogue OS** is a constitutional and operational framework for persistent multi-agent organizations.

It defines how AI agents are initialized, governed, delegated, supervised, audited, recovered, and kept accountable to a Human sovereign.

Dialogue OS is not a single prompt. It is a versioned Codex package with constitutional law, deterministic governance contracts, machine-readable schemas, conformance tests, and framework reference profiles.

## Status

**Version:** v0.2 canonical public specification  
**Owner:** Anas Alsawy  
**Runtime status:** private implementation in development  
**Public repo purpose:** doctrine, governance, non-secret normative specifications, schemas, conformance tests, architecture, roadmap, and contribution process

> The public specification does not prove that a private runtime has been deployed. Runtime claims require evidence.

## Start here

A runtime applying Dialogue OS **as-is** begins with:

1. [`dialogue-os.manifest.yaml`](dialogue-os.manifest.yaml) — package version, canonical entrypoint, document precedence, schemas, and compatibility profile.
2. [`DIALOGUE_OS_BOOTSTRAP.md`](DIALOGUE_OS_BOOTSTRAP.md) — mandatory agent initialization sequence, inheritance rules, invariants, mission contract, retry law, and completion contract.
3. [`AMENDMENTS.md`](AMENDMENTS.md) — ratified corrections that supersede conflicting older text.
4. [`CONSTITUTION.md`](CONSTITUTION.md) — the foundational Codex and operating bible.
5. [`codex/book-xiii-order-of-the-room/`](codex/book-xiii-order-of-the-room/) — binding Room, communication, silence, persistence, and resurrection law.
6. [`docs/execution-governor-runtime-spec.md`](docs/execution-governor-runtime-spec.md) — deterministic governance for agent admission, tools, Workers, retries, side effects, evidence, and execution lifecycle.
7. [`docs/communication-governor-runtime-spec.md`](docs/communication-governor-runtime-spec.md) — deterministic speech, routing, lease, deduplication, and Room traffic governance.
8. [`conformance/`](conformance/) — tests required before claiming Dialogue OS compatibility.

## Core idea

> No important work should be done alone, unseen, unscored, unremembered, or abandoned merely because one attempt failed.

Dialogue OS turns isolated agents into a governed organization:

- The **Human** remains sovereign.
- The **Chief / Codex** receives missions, interprets law, assigns Leads, and supervises continuously.
- **Lead Agents** own domains, delegate non-trivial work, supervise Workers, and remain accountable.
- **Worker Agents** execute bounded missions and return evidence.
- **Watchers** independently inspect, score, challenge, and report without taking operational control.
- The **Execution Governor** governs agent admission, roles, missions, tools, side effects, retries, Workers, evidence, and lifecycle.
- The **Communication Governor** governs speech, routes, leases, recipients, deduplication, and Room traffic.
- The private Telegram **group is the current canonical Room**.
- The Telegram **channel is optional and secondary**, used only for authorized publication, alerts, or final reports.
- The **War Room** exposes missions, state, evidence, audits, blockers, and Human controls.
- Communication state and execution state remain separate.

## What v0.2 fixes

v0.2 resolves the main contradictions and omissions in v0.1:

- replaces transport-specific constitutional assumptions with a transport-agnostic core while retaining the private Telegram group as the current canonical Room;
- clarifies that dialogue is the organization's coordination mechanism, not a requirement to expose every internal reasoning step;
- adds an Execution Governor so Dialogue OS governs all initialized agents and actions, not only speech;
- establishes document precedence and version compatibility;
- makes agent initialization fail closed;
- formalizes role manifests, mission packets, state domains, side-effect classes, retry rules, Worker inheritance, evidence, memory curation, and completion;
- distinguishes persistence from uncontrolled infinite retries;
- permits Watchers to use read-only analytical tools without becoming executors;
- adds machine-readable schemas and evidence-based conformance tests;
- adds a non-secret Prefect v3 reference profile without making Dialogue OS dependent on Prefect.

## Repository contents

### Binding law and initialization

- [`CONSTITUTION.md`](CONSTITUTION.md)
- [`AMENDMENTS.md`](AMENDMENTS.md)
- [`DIALOGUE_OS_BOOTSTRAP.md`](DIALOGUE_OS_BOOTSTRAP.md)
- [`codex/book-xiii-order-of-the-room/`](codex/book-xiii-order-of-the-room/)
- [`dialogue-os.manifest.yaml`](dialogue-os.manifest.yaml)

### Normative runtime specifications

- [`docs/canonical-application-standard.md`](docs/canonical-application-standard.md)
- [`docs/execution-governor-runtime-spec.md`](docs/execution-governor-runtime-spec.md)
- [`docs/communication-governor-runtime-spec.md`](docs/communication-governor-runtime-spec.md)
- [`docs/persistence-and-speech-only-governance-spec.md`](docs/persistence-and-speech-only-governance-spec.md)
- [`docs/migrate-governor-from-channel-to-private-room.md`](docs/migrate-governor-from-channel-to-private-room.md)

### Schemas, examples, and conformance

- [`schemas/agent-manifest.schema.json`](schemas/agent-manifest.schema.json)
- [`schemas/mission-packet.schema.json`](schemas/mission-packet.schema.json)
- [`schemas/governance-state.schema.json`](schemas/governance-state.schema.json)
- [`examples/`](examples/)
- [`conformance/`](conformance/)
- [`tools/validate_package.py`](tools/validate_package.py)

### Architecture and reference profiles

- [`docs/architecture.md`](docs/architecture.md)
- [`docs/governance.md`](docs/governance.md)
- [`docs/agent-roles.md`](docs/agent-roles.md)
- [`docs/prefect-v3-reference-profile.md`](docs/prefect-v3-reference-profile.md)
- [`ROADMAP.md`](ROADMAP.md)

## Compatibility claims

Using Dialogue OS vocabulary or copying prompts is not enough.

A runtime is Dialogue OS-compatible only when it enforces registered identities, finite supervisor chains, mission admission, separate communication and execution governance, scoped tools, controlled side effects, durable state, evidence, auditability, and the applicable conformance tests.

## Public vs private boundary

This public repository may contain:

- doctrine and constitutional law;
- non-secret normative implementation specifications;
- schemas;
- conformance tests;
- safe examples;
- framework reference profiles.

The private runtime may contain:

- deployable implementation code;
- deployment configuration;
- credentials and account configuration;
- internal prompts and skills;
- live logs and operational workflows;
- customer, payment, financial, or other sensitive data.

Those private materials do not belong in this repository.

## Ownership and contribution position

Dialogue OS is created and owned by **Anas Alsawy**. Contributions are welcome, but accepted contributions are licensed under the repository terms and do not transfer ownership of the Dialogue OS name, doctrine, brand, or core project direction.

See [`OWNERSHIP.md`](OWNERSHIP.md), [`CONTRIBUTING.md`](CONTRIBUTING.md), and [`LICENSE.md`](LICENSE.md).

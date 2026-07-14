# Dialogue OS Amendments

This file records ratified amendments to the public Dialogue OS Codex.

## Amendment v0.2 — Canonical Initialization and Execution Governance

**Ratified:** 2026-07-14  
**Ratified by:** Human sovereign authority — Anas Alsawy  
**Status:** Binding  
**Affected material:** Constitution Books I, III, V, VII, VIII, XI, XII; Book XIII; Communication Governor and persistence specifications.

### 1. Purpose

This amendment removes implementation contradictions and establishes the minimum structure required for Dialogue OS to govern every initialized agent, not merely Room speech.

### 2. Canonical precedence

The precedence and conflict-resolution rules in [`DIALOGUE_OS_BOOTSTRAP.md`](DIALOGUE_OS_BOOTSTRAP.md) are binding.

Where older text conflicts with this amendment:

- the private Telegram group remains the current canonical Room;
- Discord, a War Room UI, or another transport may be an adapter but is not constitutionally required;
- transport examples are informative and cannot override canonical Room law;
- Book XIII remains binding for communication and Room order;
- the new Execution Governor specification is binding for agent admission, mission execution, tools, side effects, retries, Workers, evidence, and lifecycle.

### 3. Dialogue clarification

"Dialogue is the primary runtime" means accountable exchange is the primary coordination and error-correction mechanism of the organization. It does not require every internal reasoning step, tool call, retry, or Worker action to become visible speech.

Useful dialogue is required when material information must be shared. Uncontrolled speech, duplicated cognition, status spam, and circular replies are not constitutionally protected dialogue.

### 4. Room history and memory clarification

Room history is a durable event source and audit trail. It is not automatically approved long-term memory.

Before Room content becomes institutional memory, it must be deduplicated, classified, redacted, separated from temporary facts, and curated. Secrets and sensitive data remain prohibited from durable doctrine or training memory.

### 5. Watcher clarification

Watchers do not execute the mission and may not create operational side effects. They may use read-only analytical, search, comparison, and evidence-inspection tools required to audit the system.

Watcher reports cannot be suppressed by the Chief or Leads. The Human remains the final authority.

### 6. Lead delegation clarification

A Lead must not become consumed by non-trivial execution. A Lead may directly perform trivial, reversible, low-risk work when delegation would add no value.

Non-trivial, ambiguous, high-risk, long-running, or parallelizable work requires Workers or an equivalent supervised execution structure. Delegation never transfers final accountability away from the Lead.

### 7. Persistence and retry clarification

"Silent work may continue for as long as necessary" means communication controls do not terminate execution. It does not prohibit the Execution Governor from enforcing authorization, expiry, concurrency, financial limits, tool policy, idempotency, or adaptive retry rules.

Repeated identical tool calls are allowed only when justified by changed conditions, waiting, explicit policy, or Chief/Human authorization. Irreversible or externally visible side effects require idempotency protection and may not be repeated blindly.

Mission non-abandonment requires detours, diagnosis, assistance, decomposition, and escalation—not infinite unexamined repetition.

### 8. Agent initialization law

Every agent and Worker must be initialized through the canonical bootstrap and registered with the Execution Governor before action.

No agent may self-create outside this path, self-grant authority, or inherit broader power than its creator.

Initialization fails closed when identity, role, supervisor, authority, mission scope, tool scope, side-effect scope, evidence policy, or manifest integrity is missing or contradictory.

### 9. State separation law

The following are separate state domains and may not be collapsed:

- communication state;
- mission state;
- execution state;
- tool state;
- Worker state;
- evidence state;
- memory state.

A communication restriction never implies an execution stop. An execution permission never implies speaking authority.

### 10. Completion and evidence law

A mission cannot be completed solely by an agent's declaration. Completion requires objective satisfaction, evidence, accountable review, required Watcher audit, side-effect reconciliation, uncertainty disclosure, and Human-visible result publication.

### 11. Public/private boundary

This public repository may contain non-secret normative specifications, schemas, conformance tests, and framework reference profiles.

Deployable private runtime code, credentials, internal prompts, live logs, account configuration, customer data, payment data, and operational secrets remain outside the public repository.

### 12. Required implementation documents

The following v0.2 documents are binding:

- [`DIALOGUE_OS_BOOTSTRAP.md`](DIALOGUE_OS_BOOTSTRAP.md)
- [`docs/canonical-application-standard.md`](docs/canonical-application-standard.md)
- [`docs/execution-governor-runtime-spec.md`](docs/execution-governor-runtime-spec.md)
- the schemas under [`schemas/`](schemas/)
- the conformance requirements under [`conformance/`](conformance/)

### 13. Supremacy

This amendment supersedes every earlier statement inconsistent with it. All non-conflicting prior law remains in force.

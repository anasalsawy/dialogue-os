# Canonical Application Standard

**Version:** v0.2  
**Status:** Normative  
**Purpose:** Define what "apply Dialogue OS as-is" means across agent frameworks and custom runtimes.

## 1. Compatibility levels

### Level 0 — Vocabulary only

The system uses names such as Chief, Lead, Worker, or Watcher but does not enforce manifests, authority, state separation, evidence, or conformance.

**Not Dialogue OS-compatible.**

### Level 1 — Prompt-compatible

The system loads the Codex and role prompts but relies mainly on model obedience.

**Experimental only. Not runtime-compliant.**

### Level 2 — Governed runtime

The system enforces registered identities, supervisor chains, mission packets, separate communication and execution governance, scoped tools, side-effect controls, durable state, evidence, and audit logs.

**Dialogue OS-compatible.**

### Level 3 — Resilient organization

Level 2 plus durable recovery, staged resurrection, Watcher coverage, War Room visibility, adaptive retries, idempotent side effects, memory curation, compatibility validation, and chaos testing.

**Production target.**

## 2. Mandatory components

A Level 2 or Level 3 implementation requires:

1. Canonical package loader.
2. Agent registry.
3. Execution Governor.
4. Communication Governor.
5. Mission ledger.
6. Worker manager.
7. Tool and side-effect gateway.
8. Retry controller.
9. Evidence store.
10. Audit event store.
11. Memory curation boundary.
12. War Room or equivalent Human command surface.
13. Conformance runner.

A framework's built-in agents, crews, graphs, flows, tasks, or workers are implementation primitives. They do not replace these constitutional components unless they enforce the same contracts.

## 3. Canonical package loading

The loader must:

- read `dialogue-os.manifest.yaml`;
- validate required files and versions;
- reject unknown breaking versions;
- load amendments before resolving older law;
- validate JSON schemas;
- record package version and manifest hash with every agent and mission;
- make the active version visible in the War Room.

Silent fallback to an older or incomplete Codex package is prohibited.

## 4. Agent registry

The registry is the source of truth for:

- identity;
- role;
- domain;
- supervisor;
- creator;
- version;
- tool scope;
- side-effect scope;
- communication state reference;
- execution state reference;
- active mission;
- expiry;
- status;
- attestation;
- retirement.

Every agent runtime process must map to exactly one registered identity. Shared model endpoints may serve multiple identities, but identity, state, authority, and audit trails must remain distinct.

## 5. Governance split

### Communication Governor

Controls message admission, routing, leases, recipients, speech budgets, rate limits, deduplication, finality, Room lockdown, and publication boundaries.

### Execution Governor

Controls agent admission, mission admission, Worker creation, tool authorization, side effects, concurrency, retry policy, budgets, evidence, execution state, cancellation, expiry, and retirement.

Neither Governor may infer the other's state transition.

## 6. Framework adapter contract

Every framework adapter must implement:

```text
initialize_agent(manifest) -> attestation
admit_mission(packet) -> mission_id
spawn_worker(parent_agent_id, worker_manifest, mission_id) -> worker_id
authorize_tool(agent_id, mission_id, tool, action, arguments) -> decision
record_side_effect(idempotency_key, evidence) -> effect_id
transition_execution_state(actor, target, transition, reason) -> state
request_message(envelope) -> communication_decision
record_evidence(mission_id, evidence) -> evidence_ref
request_completion(mission_id) -> completion_decision
retire_agent(agent_id, reason) -> retirement_record
```

A framework adapter may expose more functions, but it may not omit these constitutional effects.

## 7. Deterministic enforcement boundary

Constitutional enforcement cannot depend solely on an LLM remembering instructions.

The runtime must deterministically enforce at least:

- identity and supervisor validity;
- role eligibility;
- tool allow/deny decisions;
- side-effect authorization;
- communication routes and leases;
- message deduplication;
- mission ownership;
- state transitions;
- expiry;
- evidence requirements;
- secret redaction gates;
- audit-event creation.

LLMs may plan, reason, critique, and recommend. They may not be the only authority deciding whether their own action is authorized.

## 8. Side-effect classes

Every tool action is classified:

- `READ_ONLY`
- `REVERSIBLE_INTERNAL`
- `REVERSIBLE_EXTERNAL`
- `IRREVERSIBLE_EXTERNAL`
- `FINANCIAL`
- `LEGAL_OR_IDENTITY`
- `COMMUNICATION`
- `PRIVILEGE_CHANGE`

Higher-risk classes require stronger authorization, evidence, idempotency, and review.

Examples and thresholds belong in the private runtime policy. The public law requires the classification and enforcement mechanism.

## 9. Mission and Worker ownership

Each mission has one accountable owner. Parallel Leads may contribute, but the Chief must name one owner or split the work into separate missions.

Each Worker has one supervising Lead or Chief. Workers cannot create unsupervised descendants. Recursive delegation is allowed only when the parent possesses delegation authority and the supervisor chain remains finite and visible.

## 10. Recovery

After restart or context loss, the runtime must recover from durable records rather than model memory alone.

Recovery order:

1. active Codex version and amendments;
2. Human and Chief authority state;
3. agent registry;
4. mission ledger;
5. execution and communication states;
6. Worker tree;
7. side-effect ledger and outbox;
8. evidence;
9. unresolved blockers and overrides;
10. curated memory.

No queued Room message is replayed as a cognitive event without deduplication and recipient authorization.

## 11. Version compatibility

Each agent records a Dialogue OS version and schema version.

A child may use:

- the exact parent version; or
- a later version declared backward-compatible by the canonical manifest.

Mixed incompatible versions within one active mission are prohibited.

## 12. Validation result

A conformance run returns:

```json
{
  "dialogue_os_version": "0.2",
  "runtime_id": "example-runtime",
  "level_attempted": 2,
  "passed": false,
  "tests": [],
  "violations": [],
  "evidence_refs": [],
  "executed_at": "RFC-3339 timestamp"
}
```

No implementation may claim a compatibility level without a stored conformance result and evidence.

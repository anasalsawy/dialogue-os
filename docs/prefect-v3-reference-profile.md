# Prefect v3 Reference Profile

**Status:** Non-secret public reference profile  
**Purpose:** Map Dialogue OS governance to Prefect v3 without making Prefect part of the Constitution or claiming the private runtime is deployed.

Prefect is an optional orchestration substrate. Dialogue OS remains framework-independent.

## Mapping

| Dialogue OS | Prefect reference form |
|---|---|
| Human mission intake | API/UI-triggered Chief deployment |
| Chief | top-level deployed flow |
| Persistent Lead | separately deployed flow when independent cancellation or scaling is required |
| Short bounded Worker | Prefect task |
| Long-running or isolated Worker | separately deployed child flow |
| Watcher | independent audit deployment and event-triggered automation |
| Mission packet | validated flow parameters |
| Evidence | result storage plus human-readable artifacts |
| Runtime configuration | blocks and variables |
| Secrets | encrypted Secret/credential blocks |
| Infrastructure | work pools and workers |
| War Room | Prefect observability plus Dialogue OS mission/evidence dashboard |

## Mandatory Dialogue OS rules for Prefect adapters

1. Prefect deployment identity is not enough; every run maps to a Dialogue OS agent and mission.
2. Persistent Leads and independently cancellable Workers use separate deployments, not inseparable nested flows.
3. Side-effecting tasks disable result caching unless a deliberate idempotent cache policy exists.
4. Every external side effect uses the Dialogue OS side-effect ledger and idempotency key.
5. Prefect flow/task state does not replace Dialogue OS communication, mission, execution, tool, Worker, evidence, or memory state.
6. Work-pool or worker failure must become visible as a Dialogue OS blocker or execution-state event.
7. Retries use failure classification, backoff, jitter, concurrency limits, and reconciliation rules.
8. Blocks store configuration and secrets; they are not the mission ledger or institutional memory.
9. Artifacts support evidence but do not alone prove completion.
10. Every deployment records the active Dialogue OS version.

## Public/private boundary

This profile belongs in the public doctrine repository. Actual deployment YAML, cloud accounts, tokens, private images, worker infrastructure, live schedules, customer workflows, and runtime prompts belong in the private implementation repository.

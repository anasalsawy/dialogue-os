# Governance port plan

Maps Mint / `DIALOGUE_OS.md` governance strengths into the **current** DigitalOcean
architecture (Cursor Chief + Hermes specialists + department offices).

Format: `legacy rule/module → current implementation → reuse/adapt/reject → reason → required test`

**Sources used**
- Live code under `/home/azureuser/dialogue-os`
- Spec tip `anasalsawy/dialogue-os@2467854…` (`DIALOGUE_OS.md`)
- Operator capability list (missions, leases, permits, evidence, watchers, …)

**Sources blocked**
- `anasalsawy/dialogue-os-runtime` module files (`core.py`, `work_queue.py`, …) — private; no GitHub auth. Port decisions below use the spec + operator list; refine SHAs/modules when runtime is readable.

---

## Capability map (1–14)

### 1. Durable missions, tasks and assignment records
| | |
|--|--|
| Legacy | Mission packets, task trees, assignment ledger |
| Current | `missions`, `mission_events`; Chief assign posts into offices |
| Decision | **adapt** |
| Reason | Keep office-scoped missions; add explicit `mission_tasks` + `acceptance_criteria` |
| Test | `tests/test_governance_missions.py` — create mission+task+criteria, survive reconnect |

### 2. Explicit mission states
| | |
|--|--|
| Legacy | created→…→verified/failed/cancelled |
| Current | `NEW…VERIFIED_COMPLETED` (+ WAITING, COMPLETION_CLAIMED, VERIFYING) |
| Decision | **adapt** |
| Reason | Add `CORRECTION`; keep richer VERIFYING gate (Chief-only verified) |
| Test | Transition matrix incl. CORRECTION ↔ WORKING |

### 3. Idempotent queues, claims, leases, duplicate protection
| | |
|--|--|
| Legacy | work_queue / leases / claims |
| Current | `office_message_seen`, processed_updates, supervisor ingest dedupe |
| Decision | **adapt** |
| Reason | Add `work_leases` for tool/job claims; keep message dedupe |
| Test | Double-claim same lease_key fails; duplicate Telegram id ignored |

### 4. Permit-bound tool execution
| | |
|--|--|
| Legacy | Tool permits / side-effect classes |
| Current | Cursor env sanitization; browser tool gate; no general permit table |
| Decision | **adapt** |
| Reason | Add `tool_permits` checked before browser/tool runs |
| Test | Denied tool raises; allowed tool records audit |

### 5. Evidence and artifact recording
| | |
|--|--|
| Legacy | Evidence ledger |
| Current | `mission_artifacts`, `mission_logs`, report parser |
| Decision | **reuse** (+ minor adapt) |
| Reason | Already durable; ensure assignment path attaches artifacts from reports |
| Test | Artifact row after specialist evidence report |

### 6. Acceptance criteria and explicit Chief verification
| | |
|--|--|
| Legacy | Completion criteria + Human/Chief verify |
| Current | Chief VERIFYING→VERIFIED_COMPLETED; criteria not first-class |
| Decision | **adapt** |
| Reason | `acceptance_criteria` column; verify API requires non-empty criteria + verdict |
| Test | Verify rejected without criteria / without VERDICT |

### 7. Audit events and truthful failure/blocker reporting
| | |
|--|--|
| Legacy | Audit trail |
| Current | `mission_events`, error_log, canonical_events |
| Decision | **adapt** |
| Reason | Add `governance_audit` for permit/lease/cancel/verify |
| Test | Cancel + deny-permit write audit rows |

### 8. Cancellation interrupts active work immediately
| | |
|--|--|
| Legacy | Cancel interrupts workers |
| Current | `/cancel` fast-path kills Cursor; `/cancel_mission` transitions |
| Decision | **reuse** (+ adapt lease revoke) |
| Reason | Also revoke open work_leases on mission cancel |
| Test | cancel_mission releases leases |

### 9. Watcher independence and private warnings to Chief
| | |
|--|--|
| Legacy | Independent Watchers |
| Current | `watchers/service.py` private alert path |
| Decision | **reuse** |
| Reason | Fits office model; do not put watchers in every office by default |
| Test | Existing watcher tests / alert unit if present |

### 10. Bounded MAF task-DAG validation
| | |
|--|--|
| Legacy | MAF orchestration |
| Current | `maf/orchestration.py` stub-ish |
| Decision | **adapt (bounded)** |
| Reason | Validate DAG shape only; never replace Hermes/Cursor identity |
| Test | Reject cyclic / over-fanout DAG |

### 11. Browser domain/action permits and evidence
| | |
|--|--|
| Legacy | browser.py permits |
| Current | BrowserTool enabled flag; weak domain policy |
| Decision | **adapt** |
| Reason | `browser_permits` (agent, domain glob, actions); require evidence on close |
| Test | Disallowed domain denied |

### 12. Role-scoped memory governance
| | |
|--|--|
| Legacy | memory.py policies |
| Current | Hermes profiles + sessions; no explicit scope table |
| Decision | **adapt** |
| Reason | `memory_scopes` metadata (who may read/write); no secret ingestion |
| Test | Scope deny for cross-role write |

### 13. Health, heartbeat, status, stuck-task detection
| | |
|--|--|
| Legacy | Health / stuck detection |
| Current | Supervisor probes, heartbeats, `/status` |
| Decision | **reuse** |
| Reason | Already event-driven + scheduled `next_check_at` |
| Test | Existing `tests/test_supervisor.py` |

### 14. Persistent recovery after bridge/VM restart
| | |
|--|--|
| Legacy | Recover active missions / leases |
| Current | SQLite supervision `next_check_at`; resume open missions |
| Decision | **reuse** (+ adapt lease expiry on boot) |
| Reason | Expire stale leases at connect; never lose mission rows |
| Test | Re-open store; open missions + due checks still listed |

---

## Obsolete — **reject** (do not port)

| Legacy | Reason |
|--------|--------|
| Hermes-as-Chief | Chief is Cursor CLI only |
| Codex-as-Chief / Codex lobes | Not this architecture |
| Azure/Foundry hard-coded models | `AZURE_LLM_DISABLED` |
| Five-role-only roster | Offices expand beyond five |
| Mint-specific paths/services | DO paths / user systemd |
| Operations/audit-room-only routing | Department offices are primary |
| Discard specialist bot messages | Specialists must speak in offices |
| Cursor-first universal proxy for all specialist replies | Violates office model |

---

## Chief active supervision (binding)

For every active mission Chief must: create record + acceptance criteria; pick department; post in office; confirm ack; track messages/evidence; poll on silence; detect stalls/blockers; correct; reassign/escalate; update Anas on long work; complete only after personal review against criteria; store full trail.

Supervision = **event-driven + scheduled checks**. Never fabricate specialist replies.

---

## Implementation waves (offline, bridge stays up)

1. Docs + migration `004` + fakes + unit tests (**this checkpoint**)
2. Wire permits into BrowserTool + assign acceptance_criteria
3. Lease revoke on cancel; boot lease sweep
4. Live E2E office mission only after operator cutover approval

**Do not claim architecture works until a real office mission proves:** assign → ack → work → supervise → correction(if needed) → evidence → verify → report.

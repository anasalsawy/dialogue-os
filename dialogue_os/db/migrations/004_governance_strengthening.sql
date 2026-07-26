-- 004_governance_strengthening.sql
-- Additive governance tables for acceptance criteria, tasks, leases, permits,
-- audit, and memory scopes. Safe against a live DB (bridge may keep running;
-- new code paths opt in after cutover).

-- Acceptance criteria are first-class on the mission (Chief verification target).
ALTER TABLE missions ADD COLUMN acceptance_criteria TEXT;

-- Sub-units / task records under a mission (department office still owns the mission).
CREATE TABLE IF NOT EXISTS mission_tasks (
    task_id TEXT PRIMARY KEY,
    mission_id TEXT NOT NULL,
    title TEXT,
    brief TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    sort_order INTEGER NOT NULL DEFAULT 0,
    meta_json TEXT,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    FOREIGN KEY (mission_id) REFERENCES missions(mission_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_mission_tasks_mission
    ON mission_tasks(mission_id, sort_order);

-- Idempotent work leases / claims (tool jobs, browser sessions, etc.).
CREATE TABLE IF NOT EXISTS work_leases (
    lease_id TEXT PRIMARY KEY,
    lease_key TEXT NOT NULL UNIQUE,
    mission_id TEXT,
    agent_id TEXT NOT NULL,
    purpose TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    expires_at REAL,
    meta_json TEXT,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    released_at REAL,
    FOREIGN KEY (mission_id) REFERENCES missions(mission_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_work_leases_mission ON work_leases(mission_id, status);
CREATE INDEX IF NOT EXISTS idx_work_leases_expires ON work_leases(status, expires_at);

-- Tool permits (deny by default when a row class exists for the agent/tool).
CREATE TABLE IF NOT EXISTS tool_permits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id TEXT NOT NULL,
    tool_name TEXT NOT NULL,
    allowed INTEGER NOT NULL DEFAULT 0,
    -- Empty string = global (SQLite UNIQUE treats NULLs as distinct).
    mission_id TEXT NOT NULL DEFAULT '',
    note TEXT,
    created_at REAL NOT NULL,
    UNIQUE(agent_id, tool_name, mission_id)
);

-- Browser domain/action permits for Stagehand/Browserbase.
CREATE TABLE IF NOT EXISTS browser_permits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id TEXT NOT NULL,
    domain_pattern TEXT NOT NULL,
    actions_csv TEXT NOT NULL DEFAULT 'navigate,extract',
    allowed INTEGER NOT NULL DEFAULT 0,
    mission_id TEXT,
    note TEXT,
    created_at REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_browser_permits_agent ON browser_permits(agent_id);

-- Governance audit (permits, leases, verify, cancel) — append-only.
CREATE TABLE IF NOT EXISTS governance_audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    actor_agent_id TEXT,
    mission_id TEXT,
    detail TEXT,
    evidence_json TEXT,
    created_at REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_governance_audit_mission
    ON governance_audit(mission_id, id);

-- Role-scoped memory governance metadata (no secret payloads here).
CREATE TABLE IF NOT EXISTS memory_scopes (
    scope_id TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL,
    profile TEXT,
    read_roles_csv TEXT NOT NULL DEFAULT '',
    write_roles_csv TEXT NOT NULL DEFAULT '',
    notes TEXT,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);

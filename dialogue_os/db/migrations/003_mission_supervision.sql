-- 003_mission_supervision.sql — durable active-mission supervision.
--
-- Chief must never assign a task and wait blindly. Every active mission gets a
-- supervision row holding the whole picture (process, tools, heartbeat, blocker,
-- evidence, verification) plus the NEXT SUPERVISION TIME. Because next_check_at
-- lives in SQLite rather than in a sleeping Codex invocation, supervision
-- resumes correctly after a bridge restart or a VM reboot.
--
-- Additive only, plus an in-place rename of the two mission statuses that the
-- richer lifecycle replaces.

-- Full lifecycle:
-- ASSIGNED → ACKNOWLEDGED → WORKING → (WAITING | BLOCKED | REVIEW_REQUIRED)
--          → COMPLETION_CLAIMED → VERIFYING → VERIFIED_COMPLETED
--          | FAILED | CANCELLED
CREATE TABLE IF NOT EXISTS mission_supervision (
    mission_id TEXT PRIMARY KEY,

    -- current step / plan
    current_step TEXT,
    initial_plan TEXT,
    next_expected_action TEXT,

    -- specialist acknowledgement
    acknowledged INTEGER NOT NULL DEFAULT 0,
    acknowledged_at REAL,
    acknowledgement_text TEXT,

    -- last specialist message + heartbeat
    last_specialist_message TEXT,
    last_specialist_message_at REAL,
    last_heartbeat_at REAL,
    heartbeat_action TEXT,
    heartbeat_tool TEXT,
    heartbeat_progress TEXT,
    heartbeat_next_action TEXT,
    missed_heartbeats INTEGER NOT NULL DEFAULT 0,

    -- live execution handles
    process_id INTEGER,
    job_id TEXT,
    process_status TEXT,
    process_exit_code INTEGER,
    tool_session_id TEXT,
    browserbase_session_id TEXT,

    -- supervision control
    blocker TEXT,
    blocker_requires_owner INTEGER NOT NULL DEFAULT 0,
    cadence TEXT NOT NULL DEFAULT 'normal',
    next_check_at REAL,
    last_checked_at REAL,
    last_cursor_invocation_at REAL,
    last_owner_update_at REAL,
    paused INTEGER NOT NULL DEFAULT 0,
    ack_followups INTEGER NOT NULL DEFAULT 0,
    unsupported_claims INTEGER NOT NULL DEFAULT 0,
    consecutive_no_change INTEGER NOT NULL DEFAULT 0,
    state_fingerprint TEXT,

    -- completion gate
    completion_claimed_at REAL,
    completion_evidence_json TEXT,
    verification_status TEXT NOT NULL DEFAULT 'UNVERIFIED',
    verification_notes TEXT,
    verified_at REAL,

    meta_json TEXT,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    FOREIGN KEY (mission_id) REFERENCES missions(mission_id) ON DELETE CASCADE
);

-- Artifacts created or modified while working the mission.
CREATE TABLE IF NOT EXISTS mission_artifacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mission_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    path TEXT,
    detail TEXT,
    meta_json TEXT,
    created_at REAL NOT NULL,
    FOREIGN KEY (mission_id) REFERENCES missions(mission_id) ON DELETE CASCADE
);

-- Recent logs and errors observed for the mission (bounded by the supervisor).
CREATE TABLE IF NOT EXISTS mission_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mission_id TEXT NOT NULL,
    level TEXT NOT NULL DEFAULT 'info',
    source TEXT,
    message TEXT NOT NULL,
    created_at REAL NOT NULL,
    FOREIGN KEY (mission_id) REFERENCES missions(mission_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_supervision_next_check
    ON mission_supervision(paused, next_check_at);
CREATE INDEX IF NOT EXISTS idx_mission_artifacts_mission
    ON mission_artifacts(mission_id, id);
CREATE INDEX IF NOT EXISTS idx_mission_logs_mission
    ON mission_logs(mission_id, id);

-- Lifecycle rename: REVIEW became the explicit COMPLETION_CLAIMED step, and
-- COMPLETED is now only reachable as VERIFIED_COMPLETED (Chief-verified).
UPDATE missions SET status='COMPLETION_CLAIMED' WHERE status='REVIEW';
UPDATE missions SET status='VERIFIED_COMPLETED' WHERE status='COMPLETED';

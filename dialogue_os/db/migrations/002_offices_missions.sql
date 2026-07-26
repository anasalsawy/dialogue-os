-- 002_offices_missions.sql — department-office topology and mission supervision.
--
-- Additive only. Existing tables are untouched so the migration is safe to run
-- against a live database.

-- One Telegram group per department: Anas + Chief + exactly one specialist.
CREATE TABLE IF NOT EXISTS offices (
    department TEXT PRIMARY KEY,
    office_chat_id INTEGER NOT NULL UNIQUE,
    chief_agent_id TEXT NOT NULL DEFAULT 'chief',
    specialist_agent_id TEXT NOT NULL,
    hermes_profile TEXT,
    chat_title TEXT,
    registered_by INTEGER,
    active INTEGER NOT NULL DEFAULT 1,
    meta_json TEXT,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);

-- Mission lifecycle:
-- NEW → ASSIGNED → ACKNOWLEDGED → WORKING → (BLOCKED | REVIEW)
--     → COMPLETED | FAILED | CANCELLED
CREATE TABLE IF NOT EXISTS missions (
    mission_id TEXT PRIMARY KEY,
    department TEXT NOT NULL,
    office_chat_id INTEGER NOT NULL,
    specialist_agent_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'NEW',
    title TEXT,
    assignment_text TEXT,
    chief_cursor_session TEXT,
    specialist_hermes_session TEXT,
    completion_claim TEXT,
    chief_verification TEXT,
    final_report TEXT,
    verified INTEGER NOT NULL DEFAULT 0,
    message_budget INTEGER NOT NULL DEFAULT 60,
    messages_used INTEGER NOT NULL DEFAULT 0,
    requested_by INTEGER,
    meta_json TEXT,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    closed_at REAL
);

-- Append-only supervision trail: progress reports, tool evidence, blockers,
-- Chief's instructions, the completion claim and Chief's verification.
CREATE TABLE IF NOT EXISTS mission_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mission_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    actor_agent_id TEXT,
    actor_bot_id INTEGER,
    text TEXT,
    evidence_json TEXT,
    telegram_message_id INTEGER,
    hop_count INTEGER NOT NULL DEFAULT 0,
    created_at REAL NOT NULL,
    FOREIGN KEY (mission_id) REFERENCES missions(mission_id) ON DELETE CASCADE
);

-- Loop protection: dedupe on the ORIGINAL author, so a relayed copy of a
-- message is never processed twice even if transport re-delivers it.
CREATE TABLE IF NOT EXISTS office_message_seen (
    original_bot_id INTEGER NOT NULL,
    original_chat_id INTEGER NOT NULL,
    original_message_id INTEGER NOT NULL,
    mission_id TEXT,
    hop_count INTEGER NOT NULL DEFAULT 0,
    relayed INTEGER NOT NULL DEFAULT 0,
    created_at REAL NOT NULL,
    PRIMARY KEY (original_bot_id, original_chat_id, original_message_id)
);

CREATE INDEX IF NOT EXISTS idx_offices_chat ON offices(office_chat_id);
CREATE INDEX IF NOT EXISTS idx_missions_status ON missions(status);
CREATE INDEX IF NOT EXISTS idx_missions_department ON missions(department);
CREATE INDEX IF NOT EXISTS idx_missions_office ON missions(office_chat_id);
CREATE INDEX IF NOT EXISTS idx_mission_events_mission ON mission_events(mission_id, id);
CREATE INDEX IF NOT EXISTS idx_office_seen_created ON office_message_seen(created_at);

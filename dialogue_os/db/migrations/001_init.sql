-- 001_init.sql — initial Dialogue-OS schema (idempotent CREATE IF NOT EXISTS)

CREATE TABLE IF NOT EXISTS agents (
    agent_id TEXT PRIMARY KEY,
    role TEXT,
    display_name TEXT,
    telegram_username TEXT,
    telegram_bot_id INTEGER,
    backend TEXT NOT NULL,
    hermes_profile TEXT,
    token_env TEXT,
    meta_json TEXT,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS processed_updates (
    bot_id TEXT NOT NULL,
    update_id INTEGER NOT NULL,
    event_id TEXT NOT NULL,
    processed_at REAL NOT NULL,
    PRIMARY KEY (bot_id, update_id)
);

CREATE TABLE IF NOT EXISTS cursor_sessions (
    session_key TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    meta_json TEXT,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS chat_sessions (
    agent_id TEXT NOT NULL,
    chat_id INTEGER NOT NULL,
    backend TEXT NOT NULL,
    session_id TEXT NOT NULL,
    hermes_profile TEXT,
    meta_json TEXT,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    PRIMARY KEY (agent_id, chat_id)
);

CREATE TABLE IF NOT EXISTS canonical_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NOT NULL UNIQUE,
    run_id TEXT,
    agent_id TEXT,
    event_type TEXT NOT NULL,
    summary TEXT,
    evidence_json TEXT,
    task_id TEXT,
    hop_count INTEGER DEFAULT 0,
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS tasks (
    task_id TEXT PRIMARY KEY,
    title TEXT,
    status TEXT NOT NULL,
    owner_agent TEXT,
    created_by TEXT,
    meta_json TEXT,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS handoffs (
    handoff_id TEXT PRIMARY KEY,
    task_id TEXT,
    from_agent TEXT NOT NULL,
    to_agent TEXT NOT NULL,
    summary TEXT,
    status TEXT NOT NULL,
    meta_json TEXT,
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS watcher_alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    alert_id TEXT NOT NULL UNIQUE,
    watcher_id TEXT NOT NULL,
    severity TEXT,
    summary TEXT,
    private_to_chief INTEGER NOT NULL DEFAULT 1,
    meta_json TEXT,
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS tool_runs (
    run_id TEXT PRIMARY KEY,
    agent_id TEXT,
    tool_name TEXT NOT NULL,
    status TEXT NOT NULL,
    summary TEXT,
    evidence_json TEXT,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS event_hops (
    event_id TEXT PRIMARY KEY,
    origin_bot TEXT NOT NULL,
    run_id TEXT NOT NULL,
    hop_count INTEGER NOT NULL,
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS watcher_overrides (
    watcher_id TEXT NOT NULL,
    chat_id INTEGER NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 0,
    updated_at REAL NOT NULL,
    PRIMARY KEY (watcher_id, chat_id)
);

CREATE TABLE IF NOT EXISTS error_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT,
    message TEXT,
    meta_json TEXT,
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS config_meta (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS hermes_sessions (
    profile TEXT NOT NULL,
    chat_id INTEGER NOT NULL,
    session_id TEXT NOT NULL,
    messages_json TEXT,
    updated_at REAL NOT NULL,
    created_at REAL NOT NULL,
    PRIMARY KEY (profile, chat_id)
);

CREATE INDEX IF NOT EXISTS idx_canonical_created ON canonical_events(created_at);
CREATE INDEX IF NOT EXISTS idx_processed_event ON processed_updates(event_id);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);

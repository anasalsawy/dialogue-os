-- Durable, evidence-bound output from each independent watcher review.

CREATE TABLE IF NOT EXISTS watcher_audits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    audit_id TEXT NOT NULL,
    watcher_id TEXT NOT NULL,
    subject_agent_id TEXT NOT NULL,
    mission_id TEXT,
    verdict TEXT NOT NULL,
    confidence REAL NOT NULL DEFAULT 0,
    claim_quote TEXT,
    contradiction TEXT,
    evidence_refs_json TEXT,
    meta_json TEXT,
    created_at REAL NOT NULL,
    UNIQUE(audit_id, watcher_id)
);

CREATE INDEX IF NOT EXISTS idx_watcher_audits_created
    ON watcher_audits(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_watcher_audits_subject
    ON watcher_audits(subject_agent_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_watcher_audits_mission
    ON watcher_audits(mission_id, created_at DESC);

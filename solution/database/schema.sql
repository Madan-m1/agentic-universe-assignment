PRAGMA foreign_keys = ON;

-- 1. Leads: one record per workflow + phone identity
CREATE TABLE IF NOT EXISTS leads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workflow_id TEXT NOT NULL,
    phone_hash TEXT NOT NULL,
    encrypted_phone BLOB NOT NULL,
    encrypted_customer_name BLOB NOT NULL,
    external_ref TEXT NOT NULL,
    attributes_json TEXT NOT NULL DEFAULT '{}',
    batch_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    UNIQUE (workflow_id, phone_hash)
);

-- 2. Append-only interaction ledger
CREATE TABLE IF NOT EXISTS events (
    event_id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    workflow_id TEXT NOT NULL,
    call_id TEXT,
    occurred_at TEXT NOT NULL,
    phone_hash TEXT,
    payload_json TEXT NOT NULL DEFAULT '{}',
    source_file TEXT NOT NULL,
    source_line INTEGER NOT NULL,
    inserted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Track every valid event ID, including ignored unknown dispositions.
CREATE TABLE IF NOT EXISTS seen_event_ids (
    event_id TEXT PRIMARY KEY,
    first_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Backfill IDs already present in the append-only event ledger.
INSERT OR IGNORE INTO seen_event_ids (event_id)
SELECT event_id FROM events;

CREATE TRIGGER IF NOT EXISTS prevent_seen_event_id_update
BEFORE UPDATE ON seen_event_ids
BEGIN
    SELECT RAISE(ABORT, 'Seen event IDs are immutable');
END;

CREATE TRIGGER IF NOT EXISTS prevent_seen_event_id_delete
BEFORE DELETE ON seen_event_ids
BEGIN
    SELECT RAISE(ABORT, 'Seen event IDs are immutable');
END;

CREATE INDEX IF NOT EXISTS idx_events_call_id
ON events (workflow_id, call_id);

CREATE INDEX IF NOT EXISTS idx_events_phone
ON events (workflow_id, phone_hash);

CREATE INDEX IF NOT EXISTS idx_events_type
ON events (event_type);

-- 3. Event-to-lead associations
CREATE TABLE IF NOT EXISTS event_links (
    event_id TEXT PRIMARY KEY,
    lead_id INTEGER,
    link_status TEXT NOT NULL
        CHECK (link_status IN ('linked', 'orphan')),
    FOREIGN KEY (event_id) REFERENCES events(event_id),
    FOREIGN KEY (lead_id) REFERENCES leads(id)
);

CREATE INDEX IF NOT EXISTS idx_event_links_lead
ON event_links (lead_id);

-- 4. Processed input files
CREATE TABLE IF NOT EXISTS ingested_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path TEXT NOT NULL UNIQUE,
    file_checksum TEXT NOT NULL,
    processed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 5. Rejected lead rows (never store PII here)
CREATE TABLE IF NOT EXISTS rejections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workflow_id TEXT NOT NULL,
    batch_id TEXT NOT NULL,
    row_number INTEGER NOT NULL,
    reason TEXT NOT NULL,

    UNIQUE (workflow_id, batch_id, row_number)
);

-- 6. Persistent data-quality observations
CREATE TABLE IF NOT EXISTS quality_observations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    metric_name TEXT NOT NULL,
    observation_key TEXT NOT NULL UNIQUE
);

CREATE INDEX IF NOT EXISTS idx_quality_metric
ON quality_observations (metric_name);

-- Prevent modification or deletion of original ledger events.
CREATE TRIGGER IF NOT EXISTS prevent_event_update
BEFORE UPDATE ON events
BEGIN
    SELECT RAISE(ABORT, 'Events are append-only');
END;

CREATE TRIGGER IF NOT EXISTS prevent_event_delete
BEFORE DELETE ON events
BEGIN
    SELECT RAISE(ABORT, 'Events are append-only');
END;

CREATE TABLE IF NOT EXISTS file_ingestion_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path TEXT NOT NULL UNIQUE,
    file_checksum TEXT NOT NULL,
    workflow_id TEXT NOT NULL,
    batch_id TEXT NOT NULL,
    total_rows INTEGER NOT NULL DEFAULT 0,
    accepted_rows INTEGER NOT NULL DEFAULT 0,
    rejected_rows INTEGER NOT NULL DEFAULT 0,
    warning_count INTEGER NOT NULL DEFAULT 0,
    duplicate_count INTEGER NOT NULL DEFAULT 0,
    inserted_leads INTEGER NOT NULL DEFAULT 0,
    processed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_file_stats_workflow
ON file_ingestion_stats (workflow_id);

CREATE INDEX IF NOT EXISTS idx_file_stats_batch
ON file_ingestion_stats (batch_id);


CREATE TABLE IF NOT EXISTS event_ingestion_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path TEXT NOT NULL UNIQUE,
    file_checksum TEXT NOT NULL,
    total_lines INTEGER NOT NULL DEFAULT 0,
    inserted_events INTEGER NOT NULL DEFAULT 0,
    duplicate_events INTEGER NOT NULL DEFAULT 0,
    malformed_events INTEGER NOT NULL DEFAULT 0,
    unknown_dispositions INTEGER NOT NULL DEFAULT 0,
    processed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

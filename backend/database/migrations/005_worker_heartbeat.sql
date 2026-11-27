CREATE TABLE IF NOT EXISTS worker_heartbeat (
 worker_name TEXT PRIMARY KEY,
 last_seen_at TIMESTAMPTZ NOT NULL,
 last_job_at TIMESTAMPTZ
);

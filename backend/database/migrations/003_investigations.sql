CREATE TABLE IF NOT EXISTS investigation_jobs (
 id UUID PRIMARY KEY,
 organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
 user_id BIGINT NOT NULL REFERENCES users(id),
 event_id BIGINT NOT NULL REFERENCES conjunction_events(id),
 status TEXT NOT NULL DEFAULT 'queued' CHECK (status IN ('queued','running','succeeded','failed','cancelled')),
 attempts INTEGER NOT NULL DEFAULT 0,
 max_attempts INTEGER NOT NULL DEFAULT 3,
 query TEXT NOT NULL,
 result JSONB,
 steps JSONB NOT NULL DEFAULT '[]'::jsonb,
 error TEXT,
 created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_investigation_jobs_queue ON investigation_jobs(status,created_at);
CREATE INDEX IF NOT EXISTS idx_investigation_jobs_org ON investigation_jobs(organization_id,created_at DESC);

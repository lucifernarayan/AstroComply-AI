CREATE TABLE IF NOT EXISTS conjunction_event_versions (
 id BIGSERIAL PRIMARY KEY,
 organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
 event_id BIGINT NOT NULL REFERENCES conjunction_events(id) ON DELETE CASCADE,
 version_number INTEGER NOT NULL CHECK (version_number > 0),
 source_sha256 TEXT NOT NULL,
 raw_data JSONB NOT NULL,
 imported_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 UNIQUE (event_id, version_number),
 UNIQUE (event_id, source_sha256)
);
CREATE INDEX IF NOT EXISTS idx_event_versions_org_event ON conjunction_event_versions(organization_id,event_id,version_number DESC);

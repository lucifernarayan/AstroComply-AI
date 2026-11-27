CREATE TABLE IF NOT EXISTS conjunction_events (
 id BIGSERIAL PRIMARY KEY,
 organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
 source TEXT NOT NULL,
 external_id TEXT NOT NULL,
 primary_norad INTEGER,
 secondary_norad INTEGER,
 tca TIMESTAMPTZ NOT NULL,
 miss_distance_m DOUBLE PRECISION CHECK (miss_distance_m >= 0),
 relative_speed_m_s DOUBLE PRECISION CHECK (relative_speed_m_s >= 0),
 collision_probability DOUBLE PRECISION CHECK (collision_probability BETWEEN 0 AND 1),
 raw_data JSONB NOT NULL,
 status TEXT NOT NULL DEFAULT 'unverified' CHECK (status IN ('unverified','review','resolved')),
 note TEXT,
 created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 UNIQUE (organization_id,source,external_id)
);
CREATE INDEX IF NOT EXISTS idx_events_org_tca ON conjunction_events(organization_id,tca DESC);

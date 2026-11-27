CREATE TABLE IF NOT EXISTS fleet_orbital_elements (
 id BIGSERIAL PRIMARY KEY,
 organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
 asset_id BIGINT NOT NULL REFERENCES fleet_assets(id) ON DELETE CASCADE,
 norad_id INTEGER NOT NULL,
 line1 TEXT NOT NULL,
 line2 TEXT NOT NULL,
 original_text TEXT NOT NULL,
 source TEXT NOT NULL,
 filename TEXT,
 sha256 TEXT NOT NULL,
 epoch TIMESTAMPTZ NOT NULL,
 uploaded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 uploaded_by BIGINT NOT NULL REFERENCES users(id),
 UNIQUE (asset_id,sha256)
);
CREATE INDEX IF NOT EXISTS idx_fleet_elements_latest ON fleet_orbital_elements(organization_id,asset_id,uploaded_at DESC,id DESC);

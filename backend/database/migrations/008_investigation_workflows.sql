ALTER TABLE investigation_jobs ALTER COLUMN event_id DROP NOT NULL;
ALTER TABLE investigation_jobs ADD COLUMN IF NOT EXISTS asset_id BIGINT REFERENCES fleet_assets(id);
ALTER TABLE investigation_jobs ADD COLUMN IF NOT EXISTS workflow TEXT NOT NULL DEFAULT 'conjunction_investigation';
ALTER TABLE investigation_jobs ADD COLUMN IF NOT EXISTS payload JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE investigation_jobs ADD COLUMN IF NOT EXISTS progress INTEGER NOT NULL DEFAULT 0 CHECK (progress BETWEEN 0 AND 100);
ALTER TABLE investigation_jobs ADD COLUMN IF NOT EXISTS started_at TIMESTAMPTZ;
ALTER TABLE investigation_jobs ADD COLUMN IF NOT EXISTS finished_at TIMESTAMPTZ;
ALTER TABLE investigation_jobs ADD COLUMN IF NOT EXISTS idempotency_key TEXT;
CREATE UNIQUE INDEX IF NOT EXISTS idx_investigation_idempotency ON investigation_jobs(organization_id,idempotency_key) WHERE idempotency_key IS NOT NULL;

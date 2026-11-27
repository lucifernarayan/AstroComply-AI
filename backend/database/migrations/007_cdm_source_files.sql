CREATE TABLE IF NOT EXISTS cdm_source_files (
 event_id BIGINT NOT NULL REFERENCES conjunction_events(id) ON DELETE CASCADE,
 version_number INTEGER NOT NULL,
 organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
 content BYTEA NOT NULL,
 filename TEXT,
 media_type TEXT NOT NULL,
 parser_version TEXT NOT NULL,
 uploaded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 PRIMARY KEY (event_id,version_number),
 FOREIGN KEY (event_id,version_number)
   REFERENCES conjunction_event_versions(event_id,version_number) ON DELETE CASCADE
);

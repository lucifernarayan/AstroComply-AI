# Local deployment

Use `docker compose up --build` from the repository root for disposable local services. The PostgreSQL schema is mounted for initialization of a fresh data volume. Set `GROQ_API_KEY` only when LLM answers are needed. To load the bundled catalogue, run `python -m backend.ingestion.load_celestrak_snapshot` from the repository root with the same `DATABASE_URL` as the API. The frontend uses `NEXT_PUBLIC_MOSIP_API_BASE`, baked in during its build. For local development it defaults to `http://localhost:8000`.

Schema initialization only runs when PostgreSQL creates an empty data directory. Existing volumes need `python -m backend.database.migrate` with a database backup and a staging verification first. The additive `001_workspaces.sql` migration creates account, membership, session, fleet and audit tables. Preserve the deployed Render and Vercel environment values until a staging check confirms the selected API hostname, CORS, database schema and job behavior.

Set `ASTROCOMPLY_CORS_ORIGINS` to a comma-separated list of exact frontend origins. The default includes localhost and 127.0.0.1 on port 3000 and the existing Vercel hostname. Apply the workspace migration on a staging copy before exposing account endpoints. Session records are stored in PostgreSQL.

The additive `002_events.sql` migration adds organization-scoped conjunction event records. Apply migrations in filename order with the migration runner. Fresh Compose volumes execute the schema and migrations during PostgreSQL initialization.

Migration `003_investigations.sql` adds durable investigation jobs. Run `python -m backend.intelligence.job_worker` as a separate background worker using the same code and `DATABASE_URL` as the API. Compose includes this worker. Jobs remain queued until a worker claims them. The worker retries failed jobs up to three attempts and reclaims a running job after a ten-minute stale lease.

Migration `004_event_versions.sql` preserves each imported CDM source version. Apply it before accepting updated CDMs. Existing CDM rows imported before this migration have their latest raw data on the event, but no retroactive version row is generated.

Migration `005_worker_heartbeat.sql` records worker heartbeats. `GET /health/worker` reports healthy when the investigations worker checked in within 15 seconds, stale otherwise. The worker needs its own continuously running service and the same database as the API.

Migrations `006_orbital_elements.sql`, `007_cdm_source_files.sql`, and `008_investigation_workflows.sql` add organization-owned TLE history, original CDM bytes, and typed investigation workflows with progress and idempotency keys. Apply them in order with `python -m backend.database.migrate` before starting the updated API and worker. The migration runner records applied files and can be replayed safely. Back up existing data and validate on staging first.

The investigation worker now handles conjunction, satellite, fleet health, regulatory research, and mission analysis requests. TLE upload, CDM parsing, position calculation, CSV, and PDF generation currently run in the API request. Scheduled provider ingestion and a durable report or propagation queue are not implemented. Configure the worker as a continuously running process; the health route detects a stopped worker. The 10 minute lease is a recovery threshold, not a hard execution timeout.

# Local deployment

Use `docker compose up --build` from the repository root for disposable local services. The PostgreSQL schema is mounted for initialization of a fresh data volume. Set `GROQ_API_KEY` only when LLM answers are needed. To load the bundled catalogue, run `python -m backend.ingestion.load_celestrak_snapshot` from the repository root with the same `DATABASE_URL` as the API. The frontend uses `NEXT_PUBLIC_MOSIP_API_BASE`, baked in during its build. For local development it defaults to `http://localhost:8000`.

Schema initialization only runs when PostgreSQL creates an empty data directory. Existing volumes need `python -m backend.database.migrate` with a database backup and a staging verification first. The additive `001_workspaces.sql` migration creates account, membership, session, fleet and audit tables. Preserve the deployed Render and Vercel environment values until a staging check confirms the selected API hostname, CORS, database schema and job behavior.

Set `ASTROCOMPLY_CORS_ORIGINS` to a comma-separated list of exact frontend origins. The default includes localhost port 3000 and the existing Vercel hostname. Apply the workspace migration on a staging copy before exposing account endpoints. Session records are stored in PostgreSQL.

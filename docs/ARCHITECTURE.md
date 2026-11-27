# Application architecture

The Next.js App Router frontend calls a FastAPI process over HTTP. Catalog and metric routes use SQLAlchemy against PostgreSQL. Workspace routes use database-backed sessions, organization memberships and scoped fleet records. SatelliteService combines repository results with deterministic element and heuristic risk functions. The assess router invokes a fixed LangGraph pipeline. The regulation search service reads local JSON chunks, and selected agents use Groq to interpret results. UiPath simulator jobs run as FastAPI background tasks with process-local state.

## Target pilot architecture

Keep the frontend and modular API. Add a worker from the same Python package for ingestion, assessments and exports. Persist job status, tool inputs, evidence references and terminal results in PostgreSQL. Each request resolves an authenticated organization membership before accessing private data. Public catalogue objects and versioned element sets can be shared. Organization-owned assets, imports, jobs, event notes, notifications and reports require explicit organization scope.

Provider adapters should emit a common observation record with source, external ID, epoch, retrieval time, frame, units, validation state and immutable source reference. The orbital engine consumes a specific observation version. A report references that input, tool and algorithm version. Agent tools should read the same services and inherit the caller's permissions. Operators should see evidence and execution outcomes directly from persisted job steps.

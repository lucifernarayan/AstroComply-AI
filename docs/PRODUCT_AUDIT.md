# AstroComply product audit

Baseline `23d88d8` matched GitHub main on 27 November 2026. This report describes that revision. Engineering priorities are ordered by the consequences for a pilot operator.

| Area | Evidence in the checkout | Consequence |
| --- | --- | --- |
| Catalogue reliability | SatelliteRepository, OrbitalMetrics and knowledge_layer/db_service.py substitute built-in objects on database errors. | Search, fleet statistics and agent evidence can silently change origin during an outage. Require an explicit demo mode and carry provenance through every output. |
| Scientific validity | forecast_agent.py scales a fixed annual probability by orbit class, growth and risk score. The overview derives inclination and node from NORAD ID and accelerates time by 150. | Neither number supports operational conjunction decisions. Display missing uncertainty and identify illustrative tracks. |
| Operator workflows | Simulator polls real FastAPI job routes. Jobs live in a process dictionary. Fee checks, registration and maneuver confirmations are simulated. Assessment errors can fall through to a low score and approval. | Restart loses jobs, workers disagree, and an incomplete investigation can appear approved. |
| Customer boundaries | Routes have no shared authentication dependency. Job owner is supplied by the client. Schema has no organization, membership, fleet or assignment tables. | Approval, assessment and bulk writes are unsuitable for private customer workspaces. |
| Orbital ingestion | Checked-in CelesTrak JSON contains 15,680 records. Snapshot loader processes the first 150, upserts without an epoch guard and appends derived rows without an effective natural unique key. Three named provider ingestors contain only pass. | Replay can replace newer elements and duplicate derived history. Catching SQL errors inside one transaction also jeopardizes the batch. |
| Search and compliance | Regulation endpoints query packaged JSON through lexical term scoring. Qdrant is opened locally for a health check. The max hit per query scores 1 by construction. | Search scores measure relative rank. They cannot establish legal applicability or confidence. Results lack version and page anchors. |
| AI execution | LangGraph executes gather, orbital, collision, compliance, sustainability, forecast, mitigation and documentation sequentially. Tools read real repositories and local documents. Full assessments run in the request. | Multiple LLM calls can outlast the client timeout. Missing durable traces, budgets and evidence IDs limit reproducibility. |
| Persistence | NORAD ID is unique. Orbital and risk rows reference satellites. Risk rows lack a foreign key to the orbital input revision. Migration and restore scripts are standalone utilities. | Reports cannot reliably reconstruct the data that produced a historical score. |
| Deployment | Compose references a missing frontend Dockerfile, supplies QDRANT_HOST to a path-based client and omits schema initialization. The browser defaults to the alternate Render hostname. | Starting services alone cannot establish a working local deployment. |
| Security and operations | Public health response includes database exception text. CORS allows all origins. Compose publishes data services. DB dump, local vector-store state and Python bytecode are tracked. | Redact infrastructure details, restrict access, and review artifact contents before customer onboarding. |

## User journeys

The overview consumes metrics, list and search endpoints. Satellite details request assessments and animate a predefined agent timeline. Regulations supports local document search and Groq-assisted answers. Reports consume assessment outputs. The simulator implements an illustrative licensing process. Architecture and business pages present explanatory content. Dedicated organization management, authenticated fleet editing, CDM event review, provider freshness and evidence assignment have no corresponding end-to-end workflow.

The API additionally exposes raw and persisted analysis, bulk processing, per-specialist assessment, altitude histograms, risk distributions and ranked satellites. The shared browser client only exposes a subset. No SGP4 dependency, covariance-based collision engine or spacecraft command transport appears in the application manifests or execution paths reviewed.

## Verification

Executed the orbital calculator against the first bundled catalogue record. Its epoch is 2026-06-10T12:04:12.431424, derived period 104.604 minutes and mean altitude 983.05 km. This exercises parsing and two-body arithmetic. Independent propagation accuracy has yet to be established.

Baseline pytest collection failed in the import-time PostgreSQL connection script. The repository count script printed a result and had no assertion. Both were converted into database-backed assertions. The frontend manifest has build and lint scripts and no E2E test command. Initial local API import failed on missing qdrant_client. External GET checks returned HTTP 200 for the Vercel homepage and alternate Render health route. An HTTP response alone does not establish database-backed search or a successful assessment.

After the first repairs, six backend tests passed against a disposable PostgreSQL instance. A four-record import inserted two valid records, skipped one older epoch and rejected one invalid record. Replaying it inserted no records. The frontend production build completed with all seven routes. The existing ESLint run reported 37 errors, primarily explicit-any types and hook rules. A full browser journey and scientific accuracy validation remain pending.

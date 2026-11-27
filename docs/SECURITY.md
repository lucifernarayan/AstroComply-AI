# Security status

Workspace routes now use database-backed opaque sessions, scrypt password hashes, membership checks, role checks and audit rows. Owners, administrators and operators may edit fleet assets. Every member may read the fleet. Cross-tenant access to a fleet asset returns 404. The current workspace UI keeps its session token in browser session storage.

Legacy assessment and simulator routes require an authenticated organization member using `X-Organization-Id`. Simulator jobs remain process-local, and payment and registry routes are simulated. The existing browser-only reports page has no server-side report record. Private customer data must not be placed in those simulated workflows. Session token storage, CORS, rate limits, invitation flow, credential management and complete audit coverage require further work before a customer pilot.

Database outages now return an unavailable catalogue response unless `ASTROCOMPLY_DEMO_FALLBACK=true`. This switch advertises demo mode in the health response and browser. Public health responses no longer contain raw database exception text. Review the tracked database dump and local Qdrant files before sharing the repository with additional parties.

## Route authorization matrix

| Routes | Access |
| --- | --- |
| `/health`, `/health/worker`, catalogue `/satellites`, catalogue `/metrics`, read-only `/analyze`, `/propagation/tle`, regulation search | Public catalogue and reference data. Do not submit private customer material. |
| `/auth/register`, `/auth/login` | Public account entry. |
| `/auth/me`, `/auth/logout`, `/organizations` | Authenticated user. |
| `/organizations/{id}/fleet` and event reads | Organization member. Membership is checked in PostgreSQL. |
| Fleet edits and event imports or status updates | Owner, administrator or operator of that organization. |
| `/organizations/{id}/investigations` | Members may read. Analyst and above may submit or cancel queued jobs. All job reads filter by organization. |
| `/organizations/{id}/investigations/{job}/report` | Organization member after job completion. Other organization IDs and job IDs return 404. |
| `/organizations/{id}/reports/fleet.csv` and `/reports/events.csv` | Organization member. Queries filter every row by organization. |
| `/assess` and `/uipath` | Organization membership selected by `X-Organization-Id`. Simulator jobs also check organization ownership. Submission allows analyst and above; approval and escalation require operator and above. |
| `/analyze/bulk` and `/analyze/{id}?store=true` | Configured `ASTROCOMPLY_ADMIN_KEY` in `X-Admin-Key`. |

The existing `/reports` page assembles downloaded text in the browser from assessment results and has no server-side report record. Durable organization-scoped report storage and access control remain required. The simulator keeps jobs in process memory, so its status does not survive restart.

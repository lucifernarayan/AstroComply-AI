# Security status

Workspace routes now use database-backed opaque sessions, scrypt password hashes, membership checks, role checks and audit rows. Owners, administrators and operators may edit fleet assets. Every member may read the fleet. Cross-tenant access to a fleet asset returns 404. The current workspace UI keeps its session token in browser session storage.

Legacy assessment, simulator and report routes remain outside workspace authorization. Simulator jobs remain process-local, and payment and registry routes are simulated. Private customer data must not be placed in those workflows. Session token storage, CORS, rate limits, invitation flow, credential management and complete audit coverage require further work before a customer pilot.

Database outages now return an unavailable catalogue response unless `ASTROCOMPLY_DEMO_FALLBACK=true`. This switch advertises demo mode in the health response and browser. Public health responses no longer contain raw database exception text. Review the tracked database dump and local Qdrant files before sharing the repository with additional parties.

# Security status

The current API has no authentication, tenant authorization or audit log. The simulator has process-local jobs and simulated payment and registry routes. It must be treated as an open demonstration service. An organization and membership schema, server-side permission checks, scoped access to jobs and reports, credential management, rate limits and restricted CORS are required before private customer data is accepted.

Database outages now return an unavailable catalogue response unless `ASTROCOMPLY_DEMO_FALLBACK=true`. This switch advertises demo mode in the health response and browser. Public health responses no longer contain raw database exception text. Review the tracked database dump and local Qdrant files before sharing the repository with additional parties.

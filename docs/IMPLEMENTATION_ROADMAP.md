# Implementation roadmap

| Sequence | Deliverable | Acceptance check |
| --- | --- | --- |
| 1 | Remove unsupported probability and maneuver claims. Separate demo records from outages. | Missing covariance yields an explicit unavailable result across API, report and UI. Database outages produce visible degraded state. |
| 2 | Repair local startup and schema initialization. Introduce versioned migrations and fixture-backed tests. | Empty disposable PostgreSQL starts, imports the bundled snapshot and serves a browser search. Replay and stale imports leave current state intact. |
| 3 | Add organization memberships, authorization and auditable fleet ownership. | Two organizations cannot access each other's assets, jobs, exports or notes through any route. |
| 4 | Add versioned provider records and validated SGP4 propagation. Replace illustrative globe coordinates. | Published reference vectors match within documented tolerance. Every plotted state has epoch, frame and source. |
| 5 | Add CDM import, event history and operator review. | An imported event retains original values, units and source. Missing covariance remains visible. |
| 6 | Move assessments to durable jobs and record citations and tool traces. | A provider timeout produces a recoverable partial result. Restart preserves the evidence and job state. |
| 7 | Connect reports, notifications and API credentials to workspace permissions. | A user completes fleet import, profile inspection, investigation and evidence-backed export in a browser test. |

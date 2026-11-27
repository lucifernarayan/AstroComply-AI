# Agent execution

The legacy LangGraph pipeline gathers catalogue state and regulation snippets, then runs orbital, collision heuristic, compliance, sustainability, forecast, mitigation and report nodes. Specialist endpoints stop after their requested node. The frontend shows returned timeline steps after execution. This legacy path has no persisted step log or cost budget yet.

Numeric orbit and heuristic risk calculations come from backend functions. The forecast is an illustrative constant-growth scenario. It withholds collision probability in the absence of uncertainty. Regulatory snippets are local lexical retrieval results. Groq interpretation requires a configured key. Operator approval must follow evidence review and an authenticated workflow before use with customer missions.

The workspace investigation path persists a queued PostgreSQL job, then a separate worker retrieves the organization-owned event and records the exact tool steps and source identifiers. The conclusion is deterministic and explicitly withholds collision probability. Job status, evidence, error and retry count survive API restarts. Other LangGraph assessments still execute within HTTP requests and need migration to this worker pattern.

The mission globe uses complete recent catalogue orbital elements with a UTC epoch and a two-body Kepler estimate. It rejects missing elements and epochs older than 14 days rather than inventing positions. Ground tracks account for Earth rotation using sidereal time. This is a screening visualization, not SGP4 or an operational conjunction trajectory. The Moon is decorative. Direct fleet orbital uploads and fleet-specific globe selection remain to be built.

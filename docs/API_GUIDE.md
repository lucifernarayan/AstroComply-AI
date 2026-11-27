# API guide

Run the FastAPI app from the repository root with `uvicorn backend.api.main:app --reload`. Open `/docs` for generated route schemas. `DATABASE_URL` points to PostgreSQL. `GROQ_API_KEY` enables the LLM portions of assessments. `QDRANT_HOST` connects the optional Qdrant health client. Local regulatory search reads the bundled chunk files.

`GET /satellites/search?q=...` finds catalogue objects. `POST /analyze/raw` calculates two-body derived elements and a heuristic score from input elements. `GET /assess/{norad_id}` runs the LangGraph assessment. Partial specialist routes now stop after the requested agent. `POST /propagation/tle` returns an SGP4 state vector from a supplied TLE, in TEME coordinates. Missing covariance yields no probability of collision.

The simulator routes under `/uipath` model a licensing workflow. Payment verification, registry writes and escalation are illustrative. No spacecraft command is transmitted.

Register with `POST /auth/register` using an email address and a password of at least 12 characters. Login returns an opaque bearer token. Send it in the `Authorization` header. `GET /auth/me` validates the session and `POST /auth/logout` revokes it. `GET` and `POST /organizations` list and create workspaces. Workspace fleet CRUD routes use `/organizations/{organization_id}/fleet`. Membership is checked on every request. A catalogue NORAD ID is optional when creating a customer record, and when supplied it must already exist in the catalogue.

`POST /organizations/{organization_id}/events` imports one provider supplied conjunction summary. A source and external event identifier deduplicate imports within the workspace. GET lists and details are workspace scoped, and PATCH records review status and notes. The endpoint preserves the supplied payload. It does not calculate collision probability. The UI leaves probability unavailable when missing.

# API guide

Run the FastAPI app from the repository root with `uvicorn backend.api.main:app --reload`. Open `/docs` for generated route schemas. `DATABASE_URL` points to PostgreSQL. `GROQ_API_KEY` enables the LLM portions of assessments. `QDRANT_HOST` connects the optional Qdrant health client. Local regulatory search reads the bundled chunk files.

`GET /satellites/search?q=...` finds catalogue objects. `POST /analyze/raw` calculates two-body derived elements and a heuristic score from input elements. `GET /assess/{norad_id}` runs the LangGraph assessment. Partial specialist routes now stop after the requested agent. `POST /propagation/tle` returns an SGP4 state vector from a supplied TLE, in TEME coordinates. Missing covariance yields no probability of collision.

The simulator routes under `/uipath` model a licensing workflow. Payment verification, registry writes and escalation are illustrative. No spacecraft command is transmitted.

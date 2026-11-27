from fastapi import APIRouter
from sqlalchemy import text
from backend.database.catalogue import demo_fallback_enabled
from backend.database.db import engine
from backend.config import GROQ_API_KEY, GROQ_MODEL
from knowledge_layer.rag_service import qdrant_healthy

router = APIRouter()


@router.get('/health/worker', summary='Investigation worker status')
def worker_health():
    try:
        with engine.connect() as connection:
            row = connection.execute(text('''SELECT last_seen_at,last_job_at,
                last_seen_at > now() - interval '15 seconds' AS healthy
                FROM worker_heartbeat WHERE worker_name='investigations' ''' )).mappings().first()
        if not row:
            return {'status': 'not_started', 'last_seen_at': None, 'last_job_at': None}
        return {'status': 'healthy' if row['healthy'] else 'stale',
                'last_seen_at': row['last_seen_at'], 'last_job_at': row['last_job_at']}
    except Exception:
        return {'status': 'unavailable', 'last_seen_at': None, 'last_job_at': None}


@router.get("/health", summary="Health check")
def health_check():
    """Returns API status and confirms connectivity to PostgreSQL and Qdrant."""
    # ── PostgreSQL ─────────────────────────────────────────────────────────────
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception:
        db_status = "unavailable"

    # ── Qdrant ────────────────────────────────────────────────────────────────
    try:
        qdrant_status = "connected" if qdrant_healthy() else "collection_missing"
    except Exception:
        qdrant_status = "unavailable"

    # ── LLM configuration ────────────────────────────────────────────────────
    llm_status = "configured" if GROQ_API_KEY else "missing_api_key"

    return {
        "status":    "ok" if db_status == "connected" and qdrant_status == "connected" and llm_status == "configured" else "degraded",
        "demo_fallback_enabled": demo_fallback_enabled(),
        "version":   "2.0.0",
        "platform":  "MOSIP — Multi-Agent Orbital Sustainability Intelligence Platform",
        "databases": {
            "postgresql": db_status,
            "qdrant":     qdrant_status,
        },
        "llm": {
            "provider": "groq",
            "model": GROQ_MODEL,
            "status": llm_status,
        },
    }

import os
from fastapi import FastAPI, Request, Depends
from backend.security.auth import active_membership
from fastapi.responses import JSONResponse
from backend.database.catalogue import CatalogueUnavailable, demo_fallback_enabled
from fastapi.middleware.cors import CORSMiddleware
from backend.api.routes import satellites, metrics, analysis, health, regulations, uipath
from backend.api.routes import assess
from backend.api.routes import propagation, auth, workspaces, events, investigations, reports, orbital_assets

app = FastAPI(
    title="MOSIP API",
    description=(
        "Multi-Agent Orbital Sustainability Intelligence Platform — "
        "REST API for orbital data, risk assessment, multi-agent intelligence, "
        "compliance grading, sustainability analysis, and forecast modeling."
    ),
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

@app.exception_handler(CatalogueUnavailable)
async def catalogue_unavailable(request: Request, exc: CatalogueUnavailable):
    return JSONResponse(status_code=503, content={"detail": str(exc)})


@app.middleware("http")
async def label_demo_responses(request: Request, call_next):
    response = await call_next(request)
    if demo_fallback_enabled():
        response.headers["X-AstroComply-Mode"] = "demo-fallback-enabled"
    return response


# Explicit origins keep browser credentials scoped to the selected frontend.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in os.getenv(
        "ASTROCOMPLY_CORS_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000,https://astro-comply.vercel.app",
    ).split(",") if origin.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Existing routes ───────────────────────────────────────────────────────────
app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
app.include_router(workspaces.router, prefix="/organizations", tags=["Workspaces"])
app.include_router(events.router, prefix="/organizations", tags=["Conjunction events"])
app.include_router(investigations.router, prefix="/organizations", tags=["Investigations"])
app.include_router(reports.router, prefix="/organizations", tags=["Workspace reports"])
app.include_router(orbital_assets.router, prefix="/organizations", tags=["Fleet orbital elements"])
app.include_router(health.router,     tags=["Health"])
app.include_router(satellites.router, prefix="/satellites", tags=["Satellites"])
app.include_router(analysis.router,   prefix="/analyze",    tags=["Analysis"])
app.include_router(propagation.router, prefix="/propagation", tags=["Orbital propagation"])
app.include_router(metrics.router,    prefix="/metrics",    tags=["Metrics"])
app.include_router(regulations.router, prefix="/regulations", tags=["Regulations"])

# ── Multi-agent intelligence routes ──────────────────────────────────────────
app.include_router(
    assess.router,
    prefix="/assess",
    tags=["🤖 Multi-Agent Intelligence"],
    dependencies=[Depends(active_membership)],
)

# ── UiPath Orchestration Simulator routes ─────────────────────────────────────
app.include_router(
    uipath.router,
    prefix="/uipath",
    tags=["UiPath Orchestration"],
    dependencies=[Depends(active_membership)],
)


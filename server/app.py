# server/app.py
"""FastAPI entry point for SMART DECISION TRACKER.
Serves API endpoints AND the static frontend from the src/ directory.
Run with:  uvicorn server.app:app --reload --port 8000
"""

import os
from pathlib import Path

# ── Load .env before anything else ───────────────────────────────────────────
try:
    from dotenv import load_dotenv
    _env_path = Path(__file__).parent.parent / ".env"
    load_dotenv(_env_path)
except ImportError:
    pass  # python-dotenv not installed — env vars must be set manually

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# Import routers
from .routers import decisions, outcomes, features, behaviors, ai
from .database import engine, Base
from . import models  # noqa: F401 – required so SQLAlchemy registers the models

# ── Auto-create all tables on startup ────────────────────────────────────────
Base.metadata.create_all(bind=engine)

app = FastAPI(title="SMART DECISION TRACKER API", version="0.1.0")

# ── CORS ─────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── API routers (must be included BEFORE the static-files catch-all) ─────────
app.include_router(decisions.router, prefix="/api/decisions", tags=["Decisions"])
app.include_router(outcomes.router,  prefix="/api/outcomes",  tags=["Outcomes"])
app.include_router(features.router,  prefix="/api/features",  tags=["Features"])
app.include_router(behaviors.router, prefix="/api/behaviors", tags=["Behaviors"])
app.include_router(ai.router,        prefix="/api/ai",        tags=["AI"])

# ── Health check ─────────────────────────────────────────────────────────────
@app.get("/api/health", tags=["Health"])
async def health_check():
    return {"status": "ok"}

# ── Serve the SPA index.html for the root path ───────────────────────────────
SRC_DIR = Path(__file__).parent.parent / "src"

@app.get("/", include_in_schema=False)
async def serve_root():
    return FileResponse(SRC_DIR / "index.html")

# ── Mount static files (js, css, assets) at /static ─────────────────────────
# This must come AFTER all API routes so that /api/* routes take precedence.
app.mount("/static", StaticFiles(directory=str(SRC_DIR)), name="static")

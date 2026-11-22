"""App factory.

Run:  uvicorn hindsight.main:create_app --factory --port 8000
The factory (instead of a module-level `app`) lets tests build isolated apps with their own
database and auditor.
"""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import __version__
from . import models as _models  # noqa: F401  (registers tables on Base.metadata)
from .ai import Auditor, build_auditor
from .api import decisions, insights, system
from .config import Settings, get_settings
from .db import Base, make_engine, make_sessionmaker
from .seed import demo_is_empty, seed_demo
from .services.audit import reembed_stale
from .tracing import TraceBuffer

log = logging.getLogger("hindsight")


def _configure_logging() -> None:
    if not log.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        log.addHandler(handler)
        log.setLevel(logging.INFO)
        log.propagate = False


def create_app(settings: Settings | None = None, auditor: Auditor | None = None) -> FastAPI:
    _configure_logging()
    settings = settings or get_settings()
    engine = make_engine(settings.database_url)
    sessionmaker = make_sessionmaker(engine)
    auditor = auditor or build_auditor(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        Base.metadata.create_all(engine)
        with sessionmaker() as db:
            traces = TraceBuffer("demo")
            try:
                if settings.seed_demo and demo_is_empty(db):
                    count = seed_demo(db, auditor, traces)
                    log.info("seeded demo journal with %d decisions", count)
                reembedded = reembed_stale(db, auditor, traces)
                if reembedded:
                    log.info("re-embedded %d decisions with %s", reembedded, auditor.embed_model)
            finally:
                traces.flush(db)
        log.info(
            "Hindsight %s ready (auditor=%s, embeddings=%s)",
            __version__,
            auditor.label,
            auditor.embed_model,
        )
        yield
        engine.dispose()

    app = FastAPI(
        title="Hindsight API",
        version=__version__,
        lifespan=lifespan,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        redoc_url=None,
    )
    app.state.settings = settings
    app.state.sessionmaker = sessionmaker
    app.state.auditor = auditor

    @app.middleware("http")
    async def access_log(request: Request, call_next):
        t0 = time.perf_counter()
        response = await call_next(request)
        if request.url.path.startswith("/api/"):
            log.info(
                "%s %s -> %d in %d ms",
                request.method,
                request.url.path,
                response.status_code,
                (time.perf_counter() - t0) * 1000,
            )
        return response

    for router in (decisions.router, insights.router, system.router):
        app.include_router(router, prefix="/api")

    _mount_frontend(app, settings.frontend_dist)
    return app


def _mount_frontend(app: FastAPI, dist: Path) -> None:
    index = dist / "index.html"
    if not index.is_file():

        @app.get("/", include_in_schema=False)
        def no_frontend() -> JSONResponse:
            return JSONResponse(
                {
                    "message": "API is running. Build the UI with `npm run build` in frontend/, "
                    "or use the Vite dev server on http://localhost:5173.",
                    "docs": "/api/docs",
                }
            )

        return

    assets = dist / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")
    root = dist.resolve()

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str) -> FileResponse:
        if full_path.startswith("api/"):
            raise HTTPException(404, "Not found")
        candidate = (root / full_path).resolve()
        if full_path and candidate.is_file() and candidate.is_relative_to(root):
            return FileResponse(candidate)
        return FileResponse(index)  # client-side routes such as /decisions/12

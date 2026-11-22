"""Health, LLM traces, eval results, and demo reset."""

from __future__ import annotations

import json
from collections import defaultdict

import numpy as np
from fastapi import APIRouter, HTTPException, Query, Response, status
from sqlalchemy import select

from .. import __version__
from ..config import BACKEND_DIR
from ..deps import AuditorDep, DbDep
from ..models import LLMCall
from ..schemas import Health, OperationStats, TraceCall, Traces
from ..seed import seed_demo
from ..tracing import TraceBuffer

router = APIRouter(tags=["system"])

EVAL_RESULTS = BACKEND_DIR / "evals" / "results" / "latest.json"
TRACE_WINDOW = 2000  # stats are computed over the most recent calls


@router.get("/health", response_model=Health)
def health(auditor: AuditorDep) -> Health:
    return Health(
        status="ok",
        version=__version__,
        provider=auditor.provider,
        model=auditor.model,
        embed_model=auditor.embed_model,
        offline=auditor.provider != "gemini",
    )


def _percentile(values: list[int], q: float) -> int | None:
    return int(np.percentile(values, q)) if values else None


@router.get("/traces", response_model=Traces)
def traces(
    db: DbDep,
    limit: int = Query(default=100, ge=1, le=500),
    workspace: str | None = None,
) -> Traces:
    stmt = (
        select(LLMCall).order_by(LLMCall.created_at.desc(), LLMCall.id.desc()).limit(TRACE_WINDOW)
    )
    if workspace:
        stmt = stmt.where(LLMCall.workspace == workspace)
    rows = list(db.scalars(stmt).all())

    groups: dict[tuple[str, str], list[LLMCall]] = defaultdict(list)
    for row in rows:
        groups[(row.operation, row.provider)].append(row)

    by_operation = []
    for (operation, provider), calls in sorted(groups.items()):
        ok_latencies = [c.latency_ms for c in calls if c.ok]
        by_operation.append(
            OperationStats(
                operation=operation,
                provider=provider,
                calls=len(calls),
                errors=sum(not c.ok for c in calls),
                p50_ms=_percentile(ok_latencies, 50),
                p95_ms=_percentile(ok_latencies, 95),
                input_tokens=sum(c.input_tokens or 0 for c in calls),
                output_tokens=sum(c.output_tokens or 0 for c in calls),
            )
        )

    total = len(rows)
    return Traces(
        total_calls=total,
        error_rate=(sum(not r.ok for r in rows) / total) if total else None,
        by_operation=by_operation,
        calls=[TraceCall.model_validate(r) for r in rows[:limit]],
    )


@router.get("/evals")
def eval_results() -> dict:
    if not EVAL_RESULTS.is_file():
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "No eval results yet. Run `python -m evals.run` in backend/."
        )
    return json.loads(EVAL_RESULTS.read_text(encoding="utf-8"))


@router.post("/demo/reset", status_code=status.HTTP_204_NO_CONTENT)
def reset_demo(db: DbDep, auditor: AuditorDep) -> Response:
    traces = TraceBuffer("demo")
    try:
        seed_demo(db, auditor, traces)
    finally:
        traces.flush(db)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

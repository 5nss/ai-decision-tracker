"""Buffers model-call records during a request and writes them once the request's own writes are done.

SQLite allows one writer at a time. Writing traces from a second session in the middle of a
request would wait on the request's own transaction, so records are kept in memory and flushed
at the end, including on failure paths.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from .ai.base import CallRecord
from .models import LLMCall


class TraceBuffer:
    def __init__(self, workspace: str | None = None, decision_id: int | None = None) -> None:
        self.workspace = workspace
        self.decision_id = decision_id
        self.records: list[CallRecord] = []

    def record(self, rec: CallRecord) -> None:
        self.records.append(rec)

    def flush(self, db: Session) -> None:
        if not self.records:
            return
        db.add_all(
            LLMCall(
                workspace=self.workspace,
                decision_id=self.decision_id,
                operation=r.operation,
                provider=r.provider,
                model=r.model,
                model_version=r.model_version,
                latency_ms=r.latency_ms,
                attempts=r.attempts,
                input_tokens=r.input_tokens,
                output_tokens=r.output_tokens,
                ok=r.ok,
                error=r.error,
            )
            for r in self.records
        )
        db.commit()
        self.records.clear()

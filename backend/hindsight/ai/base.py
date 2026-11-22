"""The Auditor interface, call tracing hooks, and the factory that picks an implementation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

import numpy as np

from .types import AssumptionToJudge, AuditResult, DecisionInput, PastCase, ReviewResult

if TYPE_CHECKING:
    from ..config import Settings


class AuditorError(Exception):
    """The auditor could not produce a valid result (after retries, if any)."""


@dataclass
class CallRecord:
    operation: str  # "audit" | "review" | "embed"
    provider: str
    model: str
    latency_ms: int
    ok: bool
    attempts: int = 1
    model_version: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    error: str | None = None


class Tracer(Protocol):
    def record(self, rec: CallRecord) -> None: ...


class _NullTracer:
    def record(self, rec: CallRecord) -> None:
        return None


NULL_TRACER: Tracer = _NullTracer()


class Auditor(Protocol):
    provider: str  # "gemini" | "heuristic"
    model: str  # generation model id
    embed_model: str  # embedding model id, including its dimension
    similarity_threshold: float  # minimum cosine for "similar past decision"

    @property
    def label(self) -> str: ...

    def embed(self, texts: list[str], tracer: Tracer = NULL_TRACER) -> list[np.ndarray]: ...

    def audit(
        self, decision: DecisionInput, past: list[PastCase], tracer: Tracer = NULL_TRACER
    ) -> AuditResult: ...

    def review(
        self,
        decision: DecisionInput,
        assumptions: list[AssumptionToJudge],
        happened: bool,
        what_happened: str,
        tracer: Tracer = NULL_TRACER,
    ) -> ReviewResult: ...


def build_auditor(settings: Settings) -> Auditor:
    if not settings.use_gemini:
        from .heuristic import HeuristicAuditor

        return HeuristicAuditor()

    if not (settings.gemini_api_key and settings.gemini_api_key.strip()):
        raise RuntimeError("HINDSIGHT_PROVIDER=gemini needs GEMINI_API_KEY to be set.")

    from .gemini import GeminiAuditor

    return GeminiAuditor(
        api_key=settings.gemini_api_key.strip(),
        model=settings.llm_model,
        embed_model=settings.embed_model,
        embed_dim=settings.embed_dim,
        timeout_s=settings.llm_timeout_s,
        retries=settings.llm_retries,
    )

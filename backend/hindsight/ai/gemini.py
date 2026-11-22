"""Gemini-backed auditor: JSON outputs constrained by a schema and validated by Pydantic,
plus embeddings for retrieval. Retries live here (not in the SDK) so traces can count attempts."""

from __future__ import annotations

import importlib
import logging
import random
import time
from collections.abc import Callable
from typing import Any, TypeVar

import numpy as np
from google import genai
from google.genai import errors as genai_errors
from google.genai import types
from pydantic import BaseModel, ValidationError

from . import prompts
from .base import NULL_TRACER, AuditorError, CallRecord, Tracer
from .types import (
    AssumptionToJudge,
    AuditResult,
    DecisionInput,
    PastCase,
    ReviewResult,
)

log = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)

_RETRYABLE_STATUS = frozenset({408, 429, 500, 502, 503, 504})
_EMBED_BATCH = 100


def _transport_errors() -> tuple[type[BaseException], ...]:
    """Network-level exceptions worth retrying. The SDK can sit on httpx or httpx2."""
    found: list[type[BaseException]] = [TimeoutError, ConnectionError]
    for module_name in ("httpx", "httpx2"):
        try:
            module = importlib.import_module(module_name)
        except ImportError:
            continue
        for attr in ("TimeoutException", "TransportError"):
            cls = getattr(module, attr, None)
            if isinstance(cls, type) and issubclass(cls, BaseException):
                found.append(cls)
    return tuple(found)


_TRANSPORT_ERRORS = _transport_errors()


def is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, genai_errors.APIError):
        return exc.code in _RETRYABLE_STATUS
    return isinstance(exc, _TRANSPORT_ERRORS)


def _describe(exc: BaseException | None) -> str:
    if exc is None:
        return "unknown error"
    if isinstance(exc, genai_errors.APIError):
        parts = [str(exc.code), getattr(exc, "status", None), getattr(exc, "message", None)]
        return " ".join(str(p) for p in parts if p)[:300]
    if isinstance(exc, ValidationError):
        return f"response did not match schema ({exc.error_count()} error(s))"
    return f"{type(exc).__name__}: {exc}"[:300]


def _ms_since(t0: float) -> int:
    return int((time.perf_counter() - t0) * 1000)


def _normalize(vec: np.ndarray) -> np.ndarray:
    # Gemini only returns unit vectors at full size; truncated (e.g. 768-d) ones must be normalised.
    norm = float(np.linalg.norm(vec))
    return vec / norm if norm else vec


class GeminiAuditor:
    provider = "gemini"

    def __init__(
        self,
        api_key: str,
        model: str,
        embed_model: str = "gemini-embedding-001",
        embed_dim: int = 768,
        timeout_s: float = 30.0,
        retries: int = 2,
        client: Any = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.model = model
        self.embed_model = f"{embed_model}@{embed_dim}"
        # Cosine floor for "similar past decision", tuned with the retrieval eval.
        self.similarity_threshold = 0.6
        self._embed_model_id = embed_model
        self._embed_dim = embed_dim
        self._retries = max(0, retries)
        self._sleep = sleep
        self._client = client or genai.Client(
            api_key=api_key, http_options=types.HttpOptions(timeout=int(timeout_s * 1000))
        )

    @property
    def label(self) -> str:
        return f"{self.provider}:{self.model}"

    # ── core call loop ────────────────────────────────────────────────────────

    def _call(
        self,
        operation: str,
        model_label: str,
        tracer: Tracer,
        send: Callable[[], Any],
        parse: Callable[[Any], T],
    ) -> T:
        """Send a request with retries and record exactly one trace row.

        Transient API/network errors back off exponentially, up to `retries` extra attempts.
        A response that fails schema validation gets one extra attempt, since sampling again
        usually fixes it. Anything else fails fast.
        """
        t0 = time.perf_counter()
        max_attempts = 1 + self._retries
        attempts = 0
        schema_retry_used = False
        last_exc: BaseException | None = None

        while attempts < max_attempts:
            attempts += 1
            try:
                response = send()
            except Exception as exc:  # noqa: BLE001 - classified below, never swallowed
                last_exc = exc
                if not is_retryable(exc) or attempts >= max_attempts:
                    break
                delay = min(8.0, 0.5 * 2 ** (attempts - 1)) + random.uniform(0, 0.25)
                log.info(
                    "%s attempt %d failed (%s); retrying in %.1fs",
                    operation,
                    attempts,
                    _describe(exc),
                    delay,
                )
                self._sleep(delay)
                continue

            try:
                result = parse(response)
            except (ValidationError, ValueError) as exc:
                last_exc = exc
                if schema_retry_used or attempts >= max_attempts:
                    break
                schema_retry_used = True
                continue

            usage = getattr(response, "usage_metadata", None)
            output_tokens = None
            if usage is not None and usage.candidates_token_count is not None:
                output_tokens = usage.candidates_token_count + (usage.thoughts_token_count or 0)
            tracer.record(
                CallRecord(
                    operation=operation,
                    provider=self.provider,
                    model=model_label,
                    latency_ms=_ms_since(t0),
                    ok=True,
                    attempts=attempts,
                    model_version=getattr(response, "model_version", None),
                    input_tokens=getattr(usage, "prompt_token_count", None),
                    output_tokens=output_tokens,
                )
            )
            return result

        error = _describe(last_exc)
        tracer.record(
            CallRecord(
                operation=operation,
                provider=self.provider,
                model=model_label,
                latency_ms=_ms_since(t0),
                ok=False,
                attempts=attempts,
                error=error,
            )
        )
        raise AuditorError(f"{operation} failed after {attempts} attempt(s): {error}") from last_exc

    def _generate(
        self, operation: str, system: str, prompt: str, schema: type[T], tracer: Tracer
    ) -> T:
        config = types.GenerateContentConfig(
            system_instruction=system,
            temperature=0.2,
            response_mime_type="application/json",
            response_schema=schema,
        )

        def send() -> Any:
            return self._client.models.generate_content(
                model=self.model, contents=prompt, config=config
            )

        def parse(response: Any) -> T:
            parsed = getattr(response, "parsed", None)
            if isinstance(parsed, schema):
                return parsed
            text = response.text
            if not text:
                raise ValueError("empty response (possibly blocked by a safety filter)")
            return schema.model_validate_json(text)

        return self._call(operation, self.model, tracer, send, parse)

    # ── Auditor interface ─────────────────────────────────────────────────────

    def embed(self, texts: list[str], tracer: Tracer = NULL_TRACER) -> list[np.ndarray]:
        vectors: list[np.ndarray] = []
        for start in range(0, len(texts), _EMBED_BATCH):
            batch = texts[start : start + _EMBED_BATCH]

            def send(batch: list[str] = batch) -> Any:
                return self._client.models.embed_content(
                    model=self._embed_model_id,
                    contents=batch,
                    config=types.EmbedContentConfig(
                        task_type="SEMANTIC_SIMILARITY", output_dimensionality=self._embed_dim
                    ),
                )

            def parse(response: Any, expected: int = len(batch)) -> list[np.ndarray]:
                embeddings = response.embeddings or []
                if len(embeddings) != expected:
                    raise ValueError(f"expected {expected} embeddings, got {len(embeddings)}")
                return [_normalize(np.asarray(e.values, dtype=np.float32)) for e in embeddings]

            vectors.extend(self._call("embed", self.embed_model, tracer, send, parse))
        return vectors

    def audit(
        self, decision: DecisionInput, past: list[PastCase], tracer: Tracer = NULL_TRACER
    ) -> AuditResult:
        prompt = prompts.audit_prompt(decision, past)
        return self._generate("audit", prompts.AUDIT_SYSTEM, prompt, AuditResult, tracer)

    def review(
        self,
        decision: DecisionInput,
        assumptions: list[AssumptionToJudge],
        happened: bool,
        what_happened: str,
        tracer: Tracer = NULL_TRACER,
    ) -> ReviewResult:
        prompt = prompts.review_prompt(decision, assumptions, happened, what_happened)
        return self._generate("review", prompts.REVIEW_SYSTEM, prompt, ReviewResult, tracer)

"""GeminiAuditor's retry, schema and tracing behaviour, against a scripted fake client (no network)."""

from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace

import numpy as np
import pytest
from google.genai import errors as genai_errors

from hindsight.ai.base import AuditorError, CallRecord
from hindsight.ai.gemini import GeminiAuditor, is_retryable
from hindsight.ai.types import (
    AssumptionToJudge,
    AssumptionVerdict,
    AuditResult,
    Category,
    DecisionInput,
    ExtractedAssumption,
    ReviewResult,
    Risk,
    Verdict,
)


@dataclass
class Usage:
    prompt_token_count: int = 100
    candidates_token_count: int = 20
    thoughts_token_count: int | None = 5


@dataclass
class FakeResponse:
    parsed: object = None
    text: str | None = None
    model_version: str = "gemini-test-001"
    usage_metadata: Usage = field(default_factory=Usage)


class FakeModels:
    def __init__(self, script):
        self.script = list(script)
        self.embed_calls: list[list[str]] = []

    def _next(self):
        item = self.script.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item

    def generate_content(self, *, model, contents, config):
        assert config.response_mime_type == "application/json"
        return self._next()

    def embed_content(self, *, model, contents, config):
        self.embed_calls.append(list(contents))
        return SimpleNamespace(
            embeddings=[SimpleNamespace(values=[3.0, 4.0]) for _ in contents],
            usage_metadata=None,
        )


class RecordingTracer:
    def __init__(self):
        self.records: list[CallRecord] = []

    def record(self, rec: CallRecord) -> None:
        self.records.append(rec)


def server_error(code=503):
    return genai_errors.ServerError(
        code, {"error": {"code": code, "message": "overloaded", "status": "UNAVAILABLE"}}
    )


def client_error(code):
    return genai_errors.ClientError(
        code, {"error": {"code": code, "message": "nope", "status": "INVALID"}}
    )


AUDIT_OK = AuditResult(
    assumptions=[
        ExtractedAssumption(text="I'll have free evenings", category=Category.TIME, risk=Risk.HIGH)
    ],
    missing_considerations=[],
    premortem="It's review day and this failed because evenings vanished.",
    repeat_warnings=[],
)
REVIEW_OK = ReviewResult(
    verdicts=[
        AssumptionVerdict(assumption_id=1, verdict=Verdict.FAILED, evidence="no free evenings")
    ],
    lesson="Plan around real evenings.",
)
DECISION = DecisionInput(
    title="Learn React",
    reasoning="I'll learn it in two weeks of evenings.",
    expected_outcome="Build the frontend",
    confidence=0.8,
    domain="study",
    review_at="2026-12-01",
)


def make(script, retries=2):
    sleeps: list[float] = []
    auditor = GeminiAuditor(
        api_key="test",
        model="gemini-test",
        retries=retries,
        client=SimpleNamespace(models=FakeModels(script)),
        sleep=sleeps.append,
    )
    return auditor, sleeps


def test_transient_error_is_retried_then_succeeds():
    auditor, sleeps = make([server_error(), FakeResponse(parsed=AUDIT_OK)])
    tracer = RecordingTracer()
    assert auditor.audit(DECISION, [], tracer=tracer) == AUDIT_OK
    assert len(sleeps) == 1
    [rec] = tracer.records
    assert rec.ok and rec.attempts == 2 and rec.operation == "audit"


def test_rate_limits_are_retried_up_to_the_limit():
    auditor, sleeps = make([client_error(429), client_error(429), FakeResponse(parsed=AUDIT_OK)])
    tracer = RecordingTracer()
    auditor.audit(DECISION, [], tracer=tracer)
    assert tracer.records[0].attempts == 3
    assert sleeps[1] > sleeps[0] - 0.25  # backoff grows (jitter is at most 0.25s)


def test_bad_request_fails_fast_without_sleeping():
    auditor, sleeps = make([client_error(400), FakeResponse(parsed=AUDIT_OK)])
    tracer = RecordingTracer()
    with pytest.raises(AuditorError, match="after 1 attempt"):
        auditor.audit(DECISION, [], tracer=tracer)
    assert sleeps == []
    assert tracer.records[0].ok is False and "400" in tracer.records[0].error


def test_gives_up_after_all_retries():
    auditor, _ = make([server_error(), server_error(), server_error()], retries=2)
    tracer = RecordingTracer()
    with pytest.raises(AuditorError, match="after 3 attempt"):
        auditor.audit(DECISION, [], tracer=tracer)
    assert len(tracer.records) == 1  # one trace row per logical call


def test_schema_violation_gets_exactly_one_retry():
    bad = FakeResponse(parsed=None, text='{"verdicts": "not a list", "lesson": 3}')
    auditor, _ = make([bad, bad, FakeResponse(parsed=REVIEW_OK)], retries=2)
    with pytest.raises(AuditorError, match="did not match schema"):
        auditor.review(
            DECISION, [AssumptionToJudge(id=1, text="x", category=Category.TIME)], False, "notes"
        )
    assert len(auditor._client.models.script) == 1  # the third response was never requested


def test_schema_violation_then_valid_response_succeeds():
    bad = FakeResponse(parsed=None, text="not json at all")
    auditor, _ = make([bad, FakeResponse(parsed=REVIEW_OK)])
    tracer = RecordingTracer()
    result = auditor.review(DECISION, [], False, "notes", tracer=tracer)
    assert result == REVIEW_OK and tracer.records[0].attempts == 2


def test_falls_back_to_text_when_parsed_is_missing():
    auditor, _ = make([FakeResponse(parsed=None, text=AUDIT_OK.model_dump_json())])
    assert auditor.audit(DECISION, []) == AUDIT_OK


def test_records_tokens_including_thinking_and_model_version():
    auditor, _ = make([FakeResponse(parsed=AUDIT_OK)])
    tracer = RecordingTracer()
    auditor.audit(DECISION, [], tracer=tracer)
    rec = tracer.records[0]
    assert (rec.input_tokens, rec.output_tokens, rec.model_version) == (100, 25, "gemini-test-001")


def test_embeddings_are_batched_and_normalised():
    auditor, _ = make([])
    tracer = RecordingTracer()
    vectors = auditor.embed([f"text {i}" for i in range(150)], tracer=tracer)
    assert [len(c) for c in auditor._client.models.embed_calls] == [100, 50]
    assert len(vectors) == 150
    assert np.allclose(vectors[0], [0.6, 0.8])  # (3, 4) scaled to unit length
    assert [r.operation for r in tracer.records] == ["embed", "embed"]


def test_retryable_classification():
    assert is_retryable(server_error(500))
    assert is_retryable(client_error(429))
    assert not is_retryable(client_error(403))
    assert is_retryable(TimeoutError())
    assert not is_retryable(KeyError("x"))

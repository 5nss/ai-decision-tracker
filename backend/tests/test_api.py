from datetime import date, timedelta

import pytest

from hindsight.ai.base import AuditorError, CallRecord
from hindsight.ai.heuristic import HeuristicAuditor

from .conftest import PERSONAL, decision_payload


def create(client, **overrides):
    response = client.post("/api/decisions", json=decision_payload(**overrides), headers=PERSONAL)
    assert response.status_code == 201, response.text
    return response.json()


def test_create_audits_immediately(client):
    body = create(client)
    assert body["audit_status"] == "done"
    assert body["status"] == "open"
    assert [a["text"] for a in body["assumptions"]] == [
        "I think a week of evenings should be enough to learn the basics",
        "I expect the borrow checker to click quickly",
    ]
    assert body["audit_provider"] == "heuristic:rules-v1"


@pytest.mark.parametrize(
    "overrides",
    [
        {"confidence": 0.3},
        {"confidence": 1.0},
        {"title": "ab"},
        {"review_at": (date.today() - timedelta(days=5)).isoformat()},
        {"created_at": "2020-01-01T00:00:00Z"},  # no backdating
        {"domain": "astrology"},
    ],
)
def test_invalid_input_is_rejected(client, overrides):
    response = client.post("/api/decisions", json=decision_payload(**overrides), headers=PERSONAL)
    assert response.status_code == 422


def test_outcome_review_and_conflicts(client):
    decision = create(client)
    url = f"/api/decisions/{decision['id']}"

    assert client.post(f"{url}/review", headers=PERSONAL).status_code == 409  # no outcome yet

    outcome = {
        "happened": False,
        "what_happened": "A week of evenings was not enough to learn the basics.",
    }
    reviewed = client.post(f"{url}/outcome", json=outcome, headers=PERSONAL)
    assert reviewed.status_code == 201
    body = reviewed.json()
    assert body["status"] == "reviewed"
    assert body["outcome"]["review_status"] == "done"
    assert body["brier"] == pytest.approx(0.64)  # (0.8 - 0)^2
    first = body["assumptions"][0]
    assert first["verdict"] == "failed" and first["evidence_grounded"] is True

    assert client.post(f"{url}/outcome", json=outcome, headers=PERSONAL).status_code == 409
    assert client.post(f"{url}/audit", headers=PERSONAL).status_code == 409  # no hindsight edits
    assert client.post(f"{url}/review", headers=PERSONAL).status_code == 200


def test_workspaces_are_isolated(client):
    decision = create(client)
    assert client.get(f"/api/decisions/{decision['id']}").status_code == 404  # default: demo
    assert client.get("/api/decisions").json() == []
    assert len(client.get("/api/decisions", headers=PERSONAL).json()) == 1
    assert client.get("/api/decisions", headers={"X-Workspace": "nope"}).status_code == 400


def test_status_filters(client):
    create(client, title="Due today", review_at=date.today().isoformat())
    create(client, title="Later")
    due = client.get("/api/decisions", params={"status": "due"}, headers=PERSONAL).json()
    assert [d["title"] for d in due] == ["Due today"]


def test_delete(client):
    decision = create(client)
    url = f"/api/decisions/{decision['id']}"
    assert client.delete(url, headers=PERSONAL).status_code == 204
    assert client.get(url, headers=PERSONAL).status_code == 404


def test_insights_reflect_reviews(client):
    decision = create(client, confidence=0.9)
    client.post(
        f"/api/decisions/{decision['id']}/outcome",
        headers=PERSONAL,
        json={"happened": True, "what_happened": "It worked out exactly as planned."},
    )
    insights = client.get("/api/insights", headers=PERSONAL).json()
    assert insights["counts"] == {"total": 1, "open": 0, "due": 0, "reviewed": 1}
    calibration = insights["calibration"]
    assert calibration["n"] == 1 and calibration["small_sample"] is True
    assert calibration["brier"] == pytest.approx(0.01)


class FlakyAuditor(HeuristicAuditor):
    """Fails the first audit call (and traces the failure), then behaves normally."""

    def __init__(self):
        self.failures_left = 1

    def audit(self, decision, past, tracer=None):
        if self.failures_left:
            self.failures_left -= 1
            tracer.record(CallRecord("audit", "fake", "flaky", 5, ok=False, error="503 overloaded"))
            raise AuditorError("audit failed after 3 attempt(s): 503 overloaded")
        return super().audit(decision, past, tracer=tracer)


def test_failed_audit_keeps_the_decision_and_can_be_retried(make_client):
    client = make_client(FlakyAuditor())
    response = client.post("/api/decisions", json=decision_payload(), headers=PERSONAL)
    assert response.status_code == 201
    body = response.json()
    assert body["audit_status"] == "failed" and "503" in body["audit_error"]

    traces = client.get("/api/traces").json()
    assert traces["error_rate"] > 0  # the failure is visible, not swallowed

    retried = client.post(f"/api/decisions/{body['id']}/audit", headers=PERSONAL).json()
    assert retried["audit_status"] == "done" and retried["assumptions"]


def test_health_reports_offline_mode(client):
    health = client.get("/api/health").json()
    assert health["offline"] is True and health["provider"] == "heuristic"


def test_spa_fallback_serves_index_for_client_routes(make_client, tmp_path):
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<html>app</html>")
    (dist / "assets" / "app.js").write_text("console.log('hi')")
    client = make_client(HeuristicAuditor(), frontend_dist=dist)

    assert client.get("/decisions/12").text == "<html>app</html>"
    assert "console.log" in client.get("/assets/app.js").text
    assert client.get("/api/does-not-exist").status_code == 404
    assert client.get("/..%2f..%2fpyproject.toml").text == "<html>app</html>"

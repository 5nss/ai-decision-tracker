from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from hindsight.ai.heuristic import HeuristicAuditor
from hindsight.config import Settings
from hindsight.main import create_app


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(
        _env_file=None,
        provider="offline",
        gemini_api_key=None,
        database_url=f"sqlite:///{(tmp_path / 'test.db').as_posix()}",
        frontend_dist=tmp_path / "no-frontend",
        seed_demo=False,
    )


@pytest.fixture
def make_client(settings):
    """Build a TestClient around an app with an optional custom auditor."""
    clients: list[TestClient] = []

    def _make(auditor=None, **overrides) -> TestClient:
        app = create_app(settings.model_copy(update=overrides), auditor=auditor)
        client = TestClient(app)
        client.__enter__()  # run lifespan (create tables, optional seed)
        clients.append(client)
        return client

    yield _make
    for client in clients:
        client.__exit__(None, None, None)


@pytest.fixture
def client(make_client) -> TestClient:
    return make_client(HeuristicAuditor())


def decision_payload(**overrides) -> dict:
    payload = {
        "title": "Learn Rust in a week",
        "reasoning": "I think a week of evenings should be enough to learn the basics. "
        "I expect the borrow checker to click quickly.",
        "alternatives": "Stick with Go.",
        "expected_outcome": "Ship a small CLI in Rust.",
        "confidence": 0.8,
        "domain": "study",
        "review_at": (date.today() + timedelta(days=7)).isoformat(),
    }
    payload.update(overrides)
    return payload


PERSONAL = {"X-Workspace": "personal"}

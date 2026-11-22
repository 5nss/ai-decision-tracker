from datetime import UTC, date, datetime

import numpy as np

from hindsight.db import Base, make_engine, make_sessionmaker
from hindsight.models import Decision, Outcome
from hindsight.services.retrieval import from_blob, similar_reviewed, to_blob, top_k


def v(*xs: float) -> np.ndarray:
    return np.array(xs, dtype=np.float32)


def test_top_k_orders_by_cosine_and_applies_threshold():
    candidates = [(1, v(1, 0)), (2, v(0.9, 0.1)), (3, v(0, 1)), (4, v(-1, 0))]
    hits = top_k(v(1, 0), candidates, k=3, min_similarity=0.5)
    assert [i for i, _ in hits] == [1, 2]
    assert hits[0][1] == 1.0


def test_top_k_handles_degenerate_inputs():
    assert top_k(v(1, 0), [], k=3) == []
    assert top_k(v(0, 0), [(1, v(1, 0))], k=3) == []  # zero query vector
    assert top_k(v(1, 0), [(1, v(0, 0))], k=1) == [(1, 0.0)]  # zero candidate scores 0
    assert top_k(v(1, 0), [(1, v(1, 0))], k=0) == []


def test_blob_round_trip():
    original = v(0.25, -1.5, 3.0)
    assert np.array_equal(from_blob(to_blob(original)), original)


def _decision(id_, created_day, vec, *, workspace="demo", model="m1", reviewed=True):
    d = Decision(
        id=id_,
        workspace=workspace,
        title=f"d{id_}",
        reasoning="r" * 20,
        expected_outcome="e",
        confidence=0.7,
        domain="study",
        review_at=date(2026, 6, 1),
        created_at=datetime(2026, 1, created_day, tzinfo=UTC),
        embedding=to_blob(vec),
        embedding_model=model,
    )
    if reviewed:
        d.outcome = Outcome(happened=True, what_happened="it went fine overall")
    return d


def test_similar_reviewed_only_returns_eligible_past_decisions():
    engine = make_engine("sqlite://")
    Base.metadata.create_all(engine)
    with make_sessionmaker(engine)() as db:
        query = _decision(1, 20, v(1, 0), reviewed=False)
        db.add_all(
            [
                query,
                _decision(2, 10, v(1, 0)),  # eligible
                _decision(3, 25, v(1, 0)),  # made later: excluded
                _decision(4, 10, v(1, 0), workspace="personal"),  # other workspace
                _decision(5, 10, v(1, 0), model="m2"),  # other embedding space
                _decision(6, 10, v(1, 0), reviewed=False),  # no outcome yet
                _decision(7, 11, v(0.7, 0.7)),  # eligible, less similar
            ]
        )
        db.commit()
        hits = similar_reviewed(db, query, k=5, min_similarity=0.0)
        assert [d.id for d, _ in hits] == [2, 7]

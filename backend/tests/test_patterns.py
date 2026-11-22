from datetime import UTC, datetime

import pytest

from hindsight.services.patterns import JudgedAssumption, failure_patterns, wilson_lower_bound


def row(category: str, verdict: str, i: int = 0) -> JudgedAssumption:
    return JudgedAssumption(
        category=category,
        verdict=verdict,
        decision_id=i,
        decision_title=f"decision {i}",
        text=f"{category} assumption {i}",
        created_at=datetime(2026, 1, 1 + i, tzinfo=UTC),
    )


@pytest.mark.parametrize(
    ("k", "n", "expected"),
    [(0, 0, 0.0), (1, 1, 0.2065), (4, 5, 0.3755), (10, 16, 0.3864), (0, 10, 0.0)],
)
def test_wilson_lower_bound_known_values(k, n, expected):
    assert wilson_lower_bound(k, n) == pytest.approx(expected, abs=1e-3)


def test_wilson_rejects_impossible_counts():
    with pytest.raises(ValueError):
        wilson_lower_bound(3, 2)


def test_more_evidence_outranks_a_perfect_ratio():
    assert wilson_lower_bound(4, 5) > wilson_lower_bound(1, 1)


def test_patterns_rank_by_lower_bound_and_ignore_unclear():
    rows = (
        [row("time", "failed", i) for i in range(4)]
        + [row("time", "held", 9)]
        + [row("money", "failed", 10), row("money", "held", 11), row("money", "held", 12)]
        + [row("people", "unclear", 13)] * 5
    )
    result = failure_patterns(rows)
    assert [p["category"] for p in result["patterns"]] == ["time", "money"]
    time = result["patterns"][0]
    assert (time["failed"], time["judged"]) == (4, 5)
    assert len(time["examples"]) == 3
    # people has five verdicts but all unclear, so nothing was judged
    assert result["emerging"][0]["category"] == "people"
    assert result["emerging"][0]["judged"] == 0


def test_categories_below_threshold_are_emerging_not_patterns():
    result = failure_patterns([row("self", "failed", 1), row("self", "failed", 2)])
    assert result["patterns"] == []
    assert result["emerging"][0]["failure_rate"] == 1.0

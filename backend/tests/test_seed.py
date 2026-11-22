"""The demo journal is also the eval gold set, so its integrity is tested like code."""

from hindsight.ai.heuristic import HeuristicAuditor
from hindsight.seed import load_journal
from hindsight.services.review import is_grounded

VERDICTS = {"held", "failed", "unclear"}
CATEGORIES = {"time", "self", "people", "money", "external", "other"}


def test_journal_labels_are_consistent():
    decisions = load_journal()["decisions"]
    keys = {d["key"]: d for d in decisions}
    assert len(keys) == len(decisions) == 36

    for d in decisions:
        assert 0.5 <= d["confidence"] <= 0.99
        assert all(a["category"] in CATEGORIES for a in d["assumptions"])
        outcome = d["outcome"]
        if outcome is None:
            continue
        assert d["theme"], d["key"]
        assert d["review_after_days"] <= d["created_days_ago"], "reviews can't be in the future"
        for a in d["assumptions"]:
            assert a["verdict"] in VERDICTS
            if a["verdict"] == "unclear":
                assert a["evidence"] == ""
            else:  # every evidence quote really appears in the outcome text
                assert is_grounded(a["evidence"], outcome["what_happened"]), (d["key"], a["text"])

        for w in d["repeat_warnings"]:
            past = keys[w["past_key"]]
            assert past["created_days_ago"] > d["created_days_ago"], "warnings cite the past"


def test_retrieval_themes_have_three_members_each():
    themes: dict[str, int] = {}
    for d in load_journal()["decisions"]:
        if d["theme"]:
            themes[d["theme"]] = themes.get(d["theme"], 0) + 1
    assert len(themes) == 10 and set(themes.values()) == {3}


def test_seeding_populates_and_reset_restores_the_demo(make_client):
    client = make_client(HeuristicAuditor(), seed_demo=True)
    insights = client.get("/api/insights").json()
    assert insights["counts"]["total"] == 36 and insights["counts"]["reviewed"] == 30
    assert insights["patterns"]["patterns"][0]["category"] == "time"

    first = client.get("/api/decisions").json()[0]
    assert client.delete(f"/api/decisions/{first['id']}").status_code == 204
    assert client.post("/api/demo/reset").status_code == 204
    assert client.get("/api/insights").json()["counts"]["total"] == 36

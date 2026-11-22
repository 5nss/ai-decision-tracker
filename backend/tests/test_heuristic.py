import numpy as np

from hindsight.ai.heuristic import HeuristicAuditor, _categorize, hash_embed
from hindsight.ai.types import AssumptionToJudge, Category, DecisionInput, PastCase, Verdict


def decision(reasoning: str, **kw) -> DecisionInput:
    base = dict(
        title="t",
        reasoning=reasoning,
        expected_outcome="it works",
        confidence=0.7,
        domain="study",
        review_at="2026-12-01",
    )
    base.update(kw)
    return DecisionInput(**base)


def test_cue_words_match_whole_words_only():
    # v1 flagged this sentence because "unexpected" contains "expect".
    found = HeuristicAuditor().extract(
        decision("An unexpected bug cost me a day. I expect a fix soon.")
    )
    assert [a.text for a in found] == ["I expect a fix soon"]


def test_another_is_not_a_negation():
    auditor = HeuristicAuditor()
    result = auditor.review(
        decision("x" * 30),
        [AssumptionToJudge(id=1, text="I will get a job offer", category=Category.PEOPLE)],
        happened=True,
        what_happened="Got another job offer, better than expected.",
    )
    assert result.verdicts[0].verdict == Verdict.HELD


def test_negated_matching_sentence_is_failed_and_quoted():
    result = HeuristicAuditor().review(
        decision("x" * 30),
        [
            AssumptionToJudge(
                id=7, text="Two weeks is enough to learn React", category=Category.TIME
            )
        ],
        happened=False,
        what_happened="Two weeks was not enough to learn React. The team was great.",
    )
    verdict = result.verdicts[0]
    assert verdict.verdict == Verdict.FAILED
    assert verdict.evidence == "Two weeks was not enough to learn React"


def test_unrelated_notes_give_unclear():
    result = HeuristicAuditor().review(
        decision("x" * 30),
        [AssumptionToJudge(id=1, text="The client will pay on time", category=Category.MONEY)],
        happened=True,
        what_happened="The weather was lovely all month.",
    )
    assert result.verdicts[0].verdict == Verdict.UNCLEAR
    assert result.verdicts[0].evidence == ""


def test_categorize_uses_whole_words():
    assert _categorize("A weekend is enough") == Category.TIME
    assert _categorize("The client will reply") == Category.PEOPLE
    assert _categorize("Nothing matches here") == Category.OTHER


def test_hash_embed_is_deterministic_and_unit_length():
    a, b = hash_embed("learn react in two weeks"), hash_embed("learn react in two weeks")
    assert np.array_equal(a, b)
    assert abs(float(np.linalg.norm(a)) - 1.0) < 1e-6
    assert float(a @ hash_embed("learn react quickly")) > float(a @ hash_embed("buy a monitor"))


def test_repeat_warning_cites_the_past_case():
    auditor = HeuristicAuditor()
    past = [
        PastCase(
            decision_id=42,
            title="React sprint",
            happened=False,
            failed_assumptions=["Two weeks of evenings is enough to learn React"],
            similarity=0.4,
        )
    ]
    result = auditor.audit(
        decision("I think two weeks of evenings should be enough to learn Vue."), past
    )
    assert result.repeat_warnings and result.repeat_warnings[0].past_decision_id == 42

"""Offline auditor: deterministic rules, no network.

It runs when no API key is set, and it is the baseline in the evals. Extraction keeps v1's
cue-word idea (sentences containing "expect", "should", "will be", ...) but matches whole words,
so "unexpected" no longer counts as "expect" and "another" no longer counts as "not".
"""

from __future__ import annotations

import hashlib
import math
import re
import time
from collections import Counter

import numpy as np

from .base import NULL_TRACER, CallRecord, Tracer
from .text import content_words, overlap_coefficient, sentences, words
from .types import (
    AssumptionToJudge,
    AssumptionVerdict,
    AuditResult,
    Category,
    DecisionInput,
    ExtractedAssumption,
    PastCase,
    RepeatWarning,
    ReviewResult,
    Risk,
    Verdict,
)

# v1's cue list, now anchored on word boundaries.
_CUE = re.compile(
    r"\b(assum\w*|expect\w*|think|thinks|believe\w*|hop(?:e|es|ing)|should|probably|likely)\b"
    r"|\bwill be\b",
    re.IGNORECASE,
)

_CATEGORY_WORDS: dict[Category, frozenset[str]] = {
    Category.TIME: frozenset(
        "day days week weeks weekend weekends month months hour hours evening evenings morning "
        "mornings night nights deadline deadlines time schedule break minutes year years "
        "semester tonight tomorrow".split()
    ),
    Category.PEOPLE: frozenset(
        "friend friends team teammate teammates senior seniors recruiter recruiters client "
        "clients maintainer maintainers mentor manager people everyone family partner colleague "
        "colleagues they professor interviewer interviewers".split()
    ),
    Category.MONEY: frozenset(
        "money cost costs price pay paid pays salary budget save saving savings emi afford "
        "income spend spent cheap expensive fee fees rent worth".split()
    ),
    Category.SELF: frozenset(
        "motivated motivation discipline disciplined focus focused consistent consistently habit "
        "habits skip stick energy skills skill understand myself willpower".split()
    ),
    Category.EXTERNAL: frozenset(
        "market api apis docs documentation exam paper papers internship company tests issues "
        "tutorials tutorial weather job jobs tool tools library platform server".split()
    ),
}
# Ties go to the earlier category.
_CATEGORY_PRIORITY = [
    Category.TIME,
    Category.PEOPLE,
    Category.MONEY,
    Category.SELF,
    Category.EXTERNAL,
]

_OVERCONFIDENT = frozenset(
    "definitely sure surely easy easily always never guaranteed certainly obviously".split()
)
_HEDGED = frozenset("maybe might perhaps probably likely possibly".split())

# v1's negative-signal list, matched as whole words.
_NEGATIVE = frozenset(
    "fail fails failed failing didn't couldn't not never worse bad wrong mistake mistakes miss "
    "missed disappointed disappointing problem problems issue issues".split()
)

_EMBED_DIM = 512


def _ms_since(t0: float) -> int:
    return int((time.perf_counter() - t0) * 1000)


def _categorize(text: str) -> Category:
    tokens = words(text)
    scores = {c: sum(t in vocab for t in tokens) for c, vocab in _CATEGORY_WORDS.items()}
    best = max(_CATEGORY_PRIORITY, key=lambda c: scores[c])
    return best if scores[best] > 0 else Category.OTHER


def _risk(text: str, confidence: float) -> Risk:
    tokens = set(words(text))
    if tokens & _OVERCONFIDENT or confidence >= 0.85:
        return Risk.HIGH
    if tokens & _HEDGED:
        return Risk.LOW
    return Risk.MEDIUM


def hash_embed(text: str, dim: int = _EMBED_DIM) -> np.ndarray:
    """Feature-hashed bag of unigrams and bigrams, L2-normalised.

    Uses blake2b rather than Python's hash(), which is salted per process; with hash() the
    same text would get a different vector after every restart.
    """
    tokens = content_words(text)
    grams = tokens + [f"{a}_{b}" for a, b in zip(tokens, tokens[1:], strict=False)]
    vec = np.zeros(dim, dtype=np.float32)
    for gram, count in Counter(grams).items():
        h = int.from_bytes(hashlib.blake2b(gram.encode(), digest_size=8).digest(), "little")
        sign = 1.0 if (h >> 63) & 1 else -1.0
        vec[h % dim] += sign * (1.0 + math.log(count))
    norm = float(np.linalg.norm(vec))
    return vec / norm if norm else vec


class HeuristicAuditor:
    provider = "heuristic"
    model = "rules-v1"
    embed_model = f"hash-{_EMBED_DIM}"
    # Best-F1 cut-off between same-theme and other pairs in the retrieval eval (0.174).
    similarity_threshold = 0.17

    @property
    def label(self) -> str:
        return f"{self.provider}:{self.model}"

    # ── embeddings ────────────────────────────────────────────────────────────

    def embed(self, texts: list[str], tracer: Tracer = NULL_TRACER) -> list[np.ndarray]:
        t0 = time.perf_counter()
        vectors = [hash_embed(t) for t in texts]
        tracer.record(CallRecord("embed", self.provider, self.embed_model, _ms_since(t0), ok=True))
        return vectors

    # ── audit ─────────────────────────────────────────────────────────────────

    def extract(self, decision: DecisionInput) -> list[ExtractedAssumption]:
        seen: set[str] = set()
        found: list[ExtractedAssumption] = []
        for sentence in sentences(decision.reasoning):
            if not _CUE.search(sentence) or sentence.lower() in seen:
                continue
            seen.add(sentence.lower())
            found.append(
                ExtractedAssumption(
                    text=sentence,
                    category=_categorize(sentence),
                    risk=_risk(sentence, decision.confidence),
                )
            )
            if len(found) == 5:
                break
        return found

    def audit(
        self, decision: DecisionInput, past: list[PastCase], tracer: Tracer = NULL_TRACER
    ) -> AuditResult:
        t0 = time.perf_counter()
        assumptions = self.extract(decision)
        result = AuditResult(
            assumptions=assumptions,
            missing_considerations=self._missing(decision),
            premortem=self._premortem(decision, assumptions),
            repeat_warnings=self._repeat_warnings(assumptions, past),
        )
        tracer.record(CallRecord("audit", self.provider, self.model, _ms_since(t0), ok=True))
        return result

    def _missing(self, decision: DecisionInput) -> list[str]:
        notes: list[str] = []
        if not (decision.alternatives and decision.alternatives.strip()):
            notes.append("No alternatives written down. What else could you do instead?")
        all_words = set(words(f"{decision.reasoning} {decision.expected_outcome}"))
        if not all_words & _CATEGORY_WORDS[Category.TIME]:
            notes.append(
                "No time estimate. How long will this take, and what else needs that time?"
            )
        if decision.confidence >= 0.85:
            pct = round(decision.confidence * 100)
            notes.append(f"You're {pct}% sure. What would have to be true for this to fail?")
        if len(words(decision.reasoning)) < 25:
            notes.append("The reasoning is short, so the review will have little to check against.")
        return notes[:3]

    @staticmethod
    def _premortem(decision: DecisionInput, assumptions: list[ExtractedAssumption]) -> str:
        if not assumptions:
            return (
                "No explicit assumptions were found, so there is nothing specific to stress-test. "
                "Write down what has to go right."
            )
        pick = next((a for a in assumptions if a.risk == Risk.HIGH), assumptions[0])
        when = f"It's {decision.review_at}" if decision.review_at else "It's review day"
        return f"{when} and this didn't work out. Most likely cause: “{pick.text}” was wrong."

    @staticmethod
    def _repeat_warnings(
        assumptions: list[ExtractedAssumption], past: list[PastCase]
    ) -> list[RepeatWarning]:
        warnings: list[RepeatWarning] = []
        for assumption in assumptions:
            for case in past:
                match = next(
                    (
                        f
                        for f in case.failed_assumptions
                        if overlap_coefficient(assumption.text, f) >= 0.5
                    ),
                    None,
                )
                if match:
                    warnings.append(
                        RepeatWarning(
                            assumption=assumption.text,
                            past_decision_id=case.decision_id,
                            note=f"A similar assumption failed in “{case.title}”: “{match}”.",
                        )
                    )
        return warnings[:3]

    # ── review ────────────────────────────────────────────────────────────────

    def review(
        self,
        decision: DecisionInput,
        assumptions: list[AssumptionToJudge],
        happened: bool,
        what_happened: str,
        tracer: Tracer = NULL_TRACER,
    ) -> ReviewResult:
        t0 = time.perf_counter()
        notes = sentences(what_happened)
        verdicts: list[AssumptionVerdict] = []
        for assumption in assumptions:
            best, best_score = None, 0.0
            for sentence in notes:
                score = overlap_coefficient(assumption.text, sentence)
                if score > best_score:
                    best, best_score = sentence, score
            if best is None or best_score < 0.25:
                verdict, evidence = Verdict.UNCLEAR, ""
            elif set(words(best)) & _NEGATIVE:
                verdict, evidence = Verdict.FAILED, best
            else:
                verdict, evidence = Verdict.HELD, best
            verdicts.append(
                AssumptionVerdict(assumption_id=assumption.id, verdict=verdict, evidence=evidence)
            )

        n_failed = sum(v.verdict == Verdict.FAILED for v in verdicts)
        if n_failed:
            lesson = (
                f"{n_failed} of {len(verdicts)} assumptions failed. "
                "Check that kind of assumption before committing next time."
            )
        elif happened:
            lesson = "Your assumptions held up. Note what made them realistic."
        else:
            lesson = "The outcome missed, but the notes don't say which assumption broke."
        tracer.record(CallRecord("review", self.provider, self.model, _ms_since(t0), ok=True))
        return ReviewResult(verdicts=verdicts, lesson=lesson)

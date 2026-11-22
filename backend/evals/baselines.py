"""Non-LLM baselines. A model only earns its cost if it beats these."""

from __future__ import annotations

import math
from collections import Counter

import numpy as np

from hindsight.ai.text import content_words

from .dataset import Case


def rank_by_domain_recency(query: Case, candidates: list[Case]) -> list[str]:
    """v1's `_find_similar`: same-domain decisions first, most recent first, then everything else."""
    same = [c for c in candidates if c.domain == query.domain]
    rest = [c for c in candidates if c.domain != query.domain]
    by_recency = sorted(same, key=lambda c: c.created_days_ago) + sorted(
        rest, key=lambda c: c.created_days_ago
    )
    return [c.key for c in by_recency]


def outcome_polarity_verdicts(case: Case) -> list[str]:
    """Every assumption takes the outcome's polarity: held if it happened, failed if not.

    Simple, but a strong baseline, since most assumptions in a failed decision did fail.
    """
    verdict = "held" if case.happened else "failed"
    return [verdict for _ in case.assumptions]


class TfIdf:
    """Sublinear TF-IDF over content-word stems, L2-normalised, so rows can be dot-producted."""

    def __init__(self, documents: list[str]) -> None:
        tokenized = [content_words(d) for d in documents]
        vocabulary = sorted({t for tokens in tokenized for t in tokens})
        self.index = {t: i for i, t in enumerate(vocabulary)}
        df = np.zeros(len(vocabulary))
        for tokens in tokenized:
            for t in set(tokens):
                df[self.index[t]] += 1
        n = len(documents)
        self.idf = np.log((1 + n) / (1 + df)) + 1.0
        self.matrix = np.vstack([self._vector(tokens) for tokens in tokenized])

    def _vector(self, tokens: list[str]) -> np.ndarray:
        vec = np.zeros(len(self.index))
        for token, count in Counter(tokens).items():
            if token in self.index:
                vec[self.index[token]] = (1 + math.log(count)) * self.idf[self.index[token]]
        norm = np.linalg.norm(vec)
        return vec / norm if norm else vec

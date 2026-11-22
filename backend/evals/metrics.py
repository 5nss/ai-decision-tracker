"""Metrics, written out by hand so every number in the report can be explained line by line."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np


def greedy_match(similarity: np.ndarray, threshold: float) -> list[tuple[int, int, float]]:
    """One-to-one matching of predictions (rows) to gold items (columns).

    Repeatedly takes the most similar remaining pair, so one vague prediction can't claim
    credit for several gold assumptions.
    """
    if similarity.size == 0:
        return []
    sim = similarity.astype(float).copy()
    pairs: list[tuple[int, int, float]] = []
    while True:
        i, j = np.unravel_index(int(np.argmax(sim)), sim.shape)
        best = float(sim[i, j])
        if not np.isfinite(best) or best < threshold:
            break
        pairs.append((int(i), int(j), best))
        sim[i, :] = -np.inf
        sim[:, j] = -np.inf
    return pairs


def precision_recall_f1(matched: int, n_pred: int, n_gold: int) -> dict:
    precision = matched / n_pred if n_pred else 0.0
    recall = matched / n_gold if n_gold else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "matched": matched,
        "n_pred": n_pred,
        "n_gold": n_gold,
    }


def classification_report(gold: Sequence[str], pred: Sequence[str], labels: Sequence[str]) -> dict:
    """Accuracy, per-label precision/recall/F1, macro-F1 and a confusion matrix (rows = gold)."""
    if len(gold) != len(pred):
        raise ValueError("gold and pred must be the same length")
    index = {label: i for i, label in enumerate(labels)}
    confusion = [[0] * len(labels) for _ in labels]
    for g, p in zip(gold, pred, strict=True):
        confusion[index[g]][index[p]] += 1

    per_label = {}
    for label in labels:
        i = index[label]
        tp = confusion[i][i]
        fp = sum(confusion[r][i] for r in range(len(labels))) - tp
        fn = sum(confusion[i]) - tp
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        per_label[label] = {"precision": precision, "recall": recall, "f1": f1, "support": tp + fn}

    correct = sum(confusion[i][i] for i in range(len(labels)))
    return {
        "n": len(gold),
        "accuracy": correct / len(gold) if gold else 0.0,
        "macro_f1": sum(v["f1"] for v in per_label.values()) / len(labels),
        "per_label": per_label,
        "labels": list(labels),
        "confusion": confusion,
    }


def recall_at_k(ranked: Sequence[str], relevant: set[str], k: int) -> float:
    if not relevant:
        return 0.0
    return len(set(ranked[:k]) & relevant) / len(relevant)


def reciprocal_rank(ranked: Sequence[str], relevant: set[str]) -> float:
    for position, item in enumerate(ranked, start=1):
        if item in relevant:
            return 1.0 / position
    return 0.0


def best_threshold(positives: Sequence[float], negatives: Sequence[float]) -> dict:
    """The similarity cut-off that best separates relevant from irrelevant pairs (max F1)."""
    best = {"threshold": None, "f1": 0.0, "precision": 0.0, "recall": 0.0}
    candidates = sorted(set(round(s, 3) for s in [*positives, *negatives]))
    for t in candidates:
        tp = sum(s >= t for s in positives)
        fp = sum(s >= t for s in negatives)
        fn = len(positives) - tp
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        if f1 > best["f1"]:
            best = {"threshold": t, "f1": f1, "precision": precision, "recall": recall}
    return best

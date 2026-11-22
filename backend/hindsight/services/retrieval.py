"""Cosine top-k over embeddings stored as float32 blobs.

At journal scale (hundreds of rows × 768 floats, under 1 MB) one numpy matrix product takes
milliseconds, so a vector database would add an operational dependency without a benefit.
"""

from __future__ import annotations

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..models import Decision, Outcome


def to_blob(vec: np.ndarray) -> bytes:
    return np.asarray(vec, dtype=np.float32).tobytes()


def from_blob(blob: bytes) -> np.ndarray:
    return np.frombuffer(blob, dtype=np.float32)


def embedding_text(title: str, reasoning: str, expected_outcome: str) -> str:
    return f"{title}\n{reasoning}\nExpected: {expected_outcome}"


def top_k(
    query: np.ndarray,
    candidates: list[tuple[int, np.ndarray]],
    k: int,
    min_similarity: float = -1.0,
) -> list[tuple[int, float]]:
    """Return up to k (id, cosine) pairs, best first, dropping anything below min_similarity."""
    if k <= 0 or not candidates:
        return []
    q = np.asarray(query, dtype=np.float32)
    q_norm = float(np.linalg.norm(q))
    if q_norm == 0.0:
        return []

    ids = [cid for cid, _ in candidates]
    matrix = np.vstack([vec for _, vec in candidates]).astype(np.float32)
    norms = np.linalg.norm(matrix, axis=1)
    norms[norms == 0.0] = 1.0  # zero vectors score 0 instead of dividing by zero
    sims = (matrix @ q) / (norms * q_norm)

    order = np.argsort(-sims, kind="stable")[:k]
    return [(ids[i], float(sims[i])) for i in order if sims[i] >= min_similarity]


def similar_reviewed(
    db: Session, decision: Decision, k: int, min_similarity: float
) -> list[tuple[Decision, float]]:
    """Reviewed decisions from the same workspace that were made *before* this one.

    Only earlier decisions count: "you've made this assumption before" must not peek at the future.
    Vectors from a different embedding model live in a different space, so they're excluded too.
    """
    if decision.embedding is None or decision.id is None:
        return []
    stmt = (
        select(Decision)
        .join(Outcome)
        .where(
            Decision.workspace == decision.workspace,
            Decision.id != decision.id,
            Decision.embedding.is_not(None),
            Decision.embedding_model == decision.embedding_model,
            Decision.created_at < decision.created_at,
        )
        .options(selectinload(Decision.assumptions), selectinload(Decision.outcome))
    )
    rows = db.scalars(stmt).all()
    by_id = {row.id: row for row in rows}
    hits = top_k(
        from_blob(decision.embedding),
        [(row.id, from_blob(row.embedding)) for row in rows],
        k,
        min_similarity,
    )
    return [(by_id[i], score) for i, score in hits]

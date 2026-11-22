"""Which kinds of assumptions keep failing?

Categories are ranked by the Wilson score lower bound of their failure rate, so "4 of 5 failed"
outranks "1 of 1 failed". A raw ratio would rank the single case first at 100%.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime

MIN_JUDGED = 3


@dataclass(frozen=True)
class JudgedAssumption:
    category: str
    verdict: str  # "held" | "failed" | "unclear"
    decision_id: int
    decision_title: str
    text: str
    created_at: datetime


def wilson_lower_bound(successes: int, n: int, z: float = 1.96) -> float:
    """Lower end of the Wilson score interval for a binomial proportion (95% by default)."""
    if n <= 0:
        return 0.0
    if not 0 <= successes <= n:
        raise ValueError(f"successes must be in [0, n], got {successes} of {n}")
    p = successes / n
    z2 = z * z
    centre = p + z2 / (2 * n)
    margin = z * math.sqrt(p * (1 - p) / n + z2 / (4 * n * n))
    return max(0.0, (centre - margin) / (1 + z2 / n))


def failure_patterns(rows: list[JudgedAssumption], min_judged: int = MIN_JUDGED) -> dict:
    groups: dict[str, dict] = defaultdict(lambda: {"failed": [], "held": 0, "unclear": 0})
    for row in rows:
        group = groups[row.category]
        if row.verdict == "failed":
            group["failed"].append(row)
        elif row.verdict == "held":
            group["held"] += 1
        elif row.verdict == "unclear":
            group["unclear"] += 1

    patterns, emerging = [], []
    for category, group in groups.items():
        failed = len(group["failed"])
        judged = failed + group["held"]  # "unclear" says nothing either way
        recent = sorted(group["failed"], key=lambda r: r.created_at, reverse=True)[:3]
        item = {
            "category": category,
            "failed": failed,
            "held": group["held"],
            "unclear": group["unclear"],
            "judged": judged,
            "failure_rate": failed / judged if judged else None,
            "lower_bound": wilson_lower_bound(failed, judged),
            "examples": [
                {"decision_id": r.decision_id, "decision_title": r.decision_title, "text": r.text}
                for r in recent
            ],
        }
        (patterns if judged >= min_judged else emerging).append(item)

    patterns.sort(key=lambda p: p["lower_bound"], reverse=True)
    emerging.sort(key=lambda p: p["judged"], reverse=True)
    return {"patterns": patterns, "emerging": emerging, "min_judged": min_judged}

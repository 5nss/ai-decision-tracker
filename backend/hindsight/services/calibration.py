"""Calibration metrics.

Every decision is a probabilistic forecast ("I'm 80% sure the expected outcome happens") and its
review resolves it to 1 or 0. That makes judgment measurable with standard forecasting scores.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from statistics import fmean

BIN_EDGES = (0.5, 0.6, 0.7, 0.8, 0.9, 1.0)
SMALL_SAMPLE = 5


@dataclass(frozen=True)
class Forecast:
    p: float
    hit: bool
    created_at: datetime
    domain: str


def brier_score(forecasts: list[Forecast]) -> float | None:
    """Mean squared error of the stated probability. 0 is perfect; always saying 50% scores 0.25."""
    if not forecasts:
        return None
    return fmean((f.p - float(f.hit)) ** 2 for f in forecasts)


def calibration_bins(forecasts: list[Forecast]) -> list[dict]:
    bins = []
    for lo, hi in zip(BIN_EDGES, BIN_EDGES[1:], strict=False):
        last = hi == BIN_EDGES[-1]
        members = [
            f for f in forecasts if lo <= round(f.p, 4) < hi or (last and round(f.p, 4) == hi)
        ]
        bins.append(
            {
                "lo": lo,
                "hi": hi,
                "n": len(members),
                "mean_confidence": fmean(f.p for f in members) if members else None,
                "hit_rate": fmean(float(f.hit) for f in members) if members else None,
            }
        )
    return bins


def _summary(forecasts: list[Forecast]) -> dict:
    return {
        "n": len(forecasts),
        "brier": brier_score(forecasts),
        "hit_rate": fmean(float(f.hit) for f in forecasts),
        "mean_confidence": fmean(f.p for f in forecasts),
    }


def calibration_report(forecasts: list[Forecast]) -> dict:
    n = len(forecasts)
    if n == 0:
        return {
            "n": 0,
            "brier": None,
            "skill_score": None,
            "base_rate": None,
            "mean_confidence": None,
            "overconfidence": None,
            "bins": calibration_bins([]),
            "trend": [],
            "by_domain": [],
            "small_sample": True,
        }

    brier = brier_score(forecasts)
    base_rate = fmean(float(f.hit) for f in forecasts)
    mean_conf = fmean(f.p for f in forecasts)
    # Skill vs. a forecaster who always states your own base rate. Undefined when every
    # forecast resolved the same way (the reference score is then 0).
    reference = base_rate * (1.0 - base_rate)
    skill = 1.0 - brier / reference if reference > 0 else None

    by_month: dict[str, list[Forecast]] = defaultdict(list)
    by_domain: dict[str, list[Forecast]] = defaultdict(list)
    for f in forecasts:
        by_month[f.created_at.strftime("%Y-%m")].append(f)
        by_domain[f.domain].append(f)

    return {
        "n": n,
        "brier": brier,
        "skill_score": skill,
        "base_rate": base_rate,
        "mean_confidence": mean_conf,
        "overconfidence": mean_conf - base_rate,
        "bins": calibration_bins(forecasts),
        "trend": [{"month": m, **_summary(fs)} for m, fs in sorted(by_month.items())],
        "by_domain": sorted(
            ({"domain": d, **_summary(fs)} for d, fs in by_domain.items()),
            key=lambda row: row["n"],
            reverse=True,
        ),
        "small_sample": n < SMALL_SAMPLE,
    }

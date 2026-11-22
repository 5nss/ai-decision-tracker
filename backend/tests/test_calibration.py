from datetime import UTC, datetime

import pytest

from hindsight.services.calibration import (
    Forecast,
    brier_score,
    calibration_bins,
    calibration_report,
)


def f(p: float, hit: bool, month: int = 1, domain: str = "study") -> Forecast:
    return Forecast(p=p, hit=hit, created_at=datetime(2026, month, 15, tzinfo=UTC), domain=domain)


def test_brier_matches_hand_computation():
    # (0.9-1)^2 + (0.8-0)^2 + (0.6-1)^2 = 0.01 + 0.64 + 0.16 = 0.81 -> mean 0.27
    assert brier_score([f(0.9, True), f(0.8, False), f(0.6, True)]) == pytest.approx(0.27)


def test_brier_of_nothing_is_none():
    assert brier_score([]) is None


def test_bins_are_half_open_and_last_bin_is_closed():
    bins = calibration_bins([f(0.8, True), f(0.79, False), f(0.99, True)])
    by_lo = {b["lo"]: b for b in bins}
    assert by_lo[0.7]["n"] == 1  # 0.79 stays below 0.8
    assert by_lo[0.8]["n"] == 1  # 0.8 opens the next bin
    assert by_lo[0.9]["n"] == 1  # 0.99 lands in the last bin
    assert by_lo[0.5]["hit_rate"] is None


def test_report_overconfidence_and_skill():
    forecasts = [f(0.8, True), f(0.8, False), f(0.8, False), f(0.8, True)]
    report = calibration_report(forecasts)
    assert report["base_rate"] == pytest.approx(0.5)
    assert report["overconfidence"] == pytest.approx(0.3)
    # Brier 0.34 vs reference 0.25 -> skill = 1 - 0.34/0.25 = -0.36
    assert report["skill_score"] == pytest.approx(-0.36)
    assert report["small_sample"] is True


def test_skill_is_undefined_when_every_forecast_resolves_the_same_way():
    report = calibration_report([f(0.7, True), f(0.9, True)])
    assert report["skill_score"] is None


def test_trend_groups_by_month_in_order():
    report = calibration_report([f(0.9, False, month=3), f(0.6, True, month=1), f(0.7, True, 1)])
    assert [t["month"] for t in report["trend"]] == ["2026-01", "2026-03"]
    assert report["trend"][0]["n"] == 2


def test_empty_report_has_all_keys():
    report = calibration_report([])
    assert report["n"] == 0 and report["brier"] is None and len(report["bins"]) == 5

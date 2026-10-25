from datetime import timedelta

import pandas as pd
import pytest
from conftest import slot

from gridgreen.analytics import best_windows, day_type_comparison, profile, summary_stats

T0 = slot(2026, 1, 5, 0)  # Monday


def _series(values):
    return {T0 + timedelta(minutes=30 * i): v for i, v in enumerate(values)}


def test_best_window_finds_lowest_contiguous_block(frame_from_values):
    df = frame_from_values(_series([300, 300, 100, 120, 300, 300, 300, 300]))
    r = best_windows(df, 60)
    assert r.available
    assert r.best["start_utc"] == pd.Timestamp(T0 + timedelta(hours=1))
    assert r.best["mean_intensity"] == 110
    windows = [600 / 2, 400 / 2, 220 / 2, 420 / 2, 600 / 2, 600 / 2, 600 / 2]
    assert r.baseline == pytest.approx(sum(windows) / len(windows))
    assert r.pct_vs_baseline == pytest.approx((110 - r.baseline) / r.baseline * 100)
    assert r.n_candidates == 7


def test_30_minute_window_is_single_slot(frame_from_values):
    df = frame_from_values(_series([5, 1, 9]))
    assert best_windows(df, 30).best["mean_intensity"] == 1


def test_incomplete_windows_are_rejected_at_full_coverage(frame_from_values):
    vals = _series([50, 50, 400, 400])
    vals[T0 + timedelta(minutes=30)] = None  # gap inside the cheapest window
    df = frame_from_values(vals)
    strict = best_windows(df, 60, min_coverage=1.0)
    assert strict.best["mean_intensity"] == 400 and strict.n_rejected_incomplete >= 2
    lenient = best_windows(df, 60, min_coverage=0.5)
    assert lenient.best["mean_intensity"] == 50 and lenient.best["coverage"] == 0.5


def test_gap_in_timestamps_is_detected_not_bridged(frame_from_values):
    vals = {T0: 10.0, T0 + timedelta(hours=2): 10.0, T0 + timedelta(hours=2, minutes=30): 10.0}
    r = best_windows(frame_from_values(vals), 60)
    assert r.best["start_utc"] == pd.Timestamp(T0 + timedelta(hours=2))


def test_top_windows_do_not_overlap(frame_from_values):
    df = frame_from_values(_series([10, 11, 12, 13, 300, 300, 9, 9]))
    top = best_windows(df, 60, top_n=3).top
    spans = list(zip(top["start_utc"], top["end_utc"], strict=True))
    for i, (a, b) in enumerate(spans):
        for c, d in spans[i + 1 :]:
            assert b <= c or d <= a


@pytest.mark.parametrize("bad", [0, 45, -30])
def test_invalid_durations_raise(frame_from_values, bad):
    with pytest.raises(ValueError):
        best_windows(frame_from_values(_series([1, 2])), bad)


def test_empty_and_too_short_inputs(frame_from_values):
    assert not best_windows(frame_from_values({}), 60).available
    assert not best_windows(frame_from_values(_series([100])), 120).available


def test_window_across_dst_uses_utc_grid(frame_from_values):
    start = slot(2026, 3, 29, 0)  # 00:00 GMT; next slot 00:30 GMT; 01:00 UTC = 02:00 BST
    vals = {start + timedelta(minutes=30 * i): v for i, v in enumerate([100, 100, 100, 100])}
    r = best_windows(frame_from_values(vals), 120)
    assert r.n_candidates == 1 and r.best["n_valid"] == 4
    assert r.best["end_local"].hour == 3  # two real hours later, local clock jumped


def test_profile_and_summary(frame_from_values):
    df = frame_from_values(_series([100, 200, 300, 400]))
    s = summary_stats(df)
    assert (
        s["n"] == 4 and s["min"] == 100 and s["max_at"] == pd.Timestamp(T0 + timedelta(hours=1, minutes=30))
    )
    p = profile(df, by="hour")
    assert p.loc[p["hour"] == 0, "mean"].item() == 150 and p["n"].sum() == 4


def test_day_type_comparison_is_hour_matched(frame_from_values):
    vals = {}
    for day in range(7):
        for h in range(24):
            ts = T0 + timedelta(days=day, hours=h)
            vals[ts] = 100.0 if day >= 5 else 200.0
    out = day_type_comparison(frame_from_values(vals))
    assert out["available"] and out["hour_matched_diff"] == pytest.approx(-100)
    assert out["weekend_days"] == 2 and out["hours_weekend_lower"] == 24


def test_day_type_unavailable_with_one_type(frame_from_values):
    assert day_type_comparison(frame_from_values(_series([1, 2])))["available"] is False


def test_spearman_without_scipy_matches_definition():
    from gridgreen.analytics import spearman

    x = pd.Series([1.0, 2, 3, 4, 5])
    assert spearman(x, x**3) == pytest.approx(1.0)  # monotonic but non-linear
    assert spearman(x, -x) == pytest.approx(-1.0)
    # Hand-computed with ties: ranks x=[1,2,3,4], y=[1.5,1.5,3,4] -> rho = 0.9487
    assert spearman(pd.Series([1.0, 2, 3, 4]), pd.Series([5.0, 5, 6, 7])) == pytest.approx(0.948683, abs=1e-6)

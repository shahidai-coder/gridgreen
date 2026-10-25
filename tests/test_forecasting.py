import math

import pandas as pd
import pytest

from gridgreen.forecasting import align_snapshots, compute_metrics, horizon_metrics, metrics_by


def test_metrics_values_and_sign_convention():
    m = compute_metrics(pd.Series([110, 90, 100, 120]), pd.Series([100, 100, 100, 100]))
    assert m.n == 4
    assert m.mae == pytest.approx(10)
    assert m.rmse == pytest.approx(math.sqrt((100 + 100 + 0 + 400) / 4))
    assert m.bias == pytest.approx(5)  # forecast - actual: over-forecast is positive


def test_metrics_ignore_unpaired_rows_and_handle_empty():
    m = compute_metrics(pd.Series([100, None, 50]), pd.Series([90, 80, None]))
    assert m.n == 1 and m.mae == 10
    assert compute_metrics(pd.Series([], dtype=float), pd.Series([], dtype=float)) is None


def test_snapshots_align_to_target_timestamp_and_bucket_horizon():
    t = pd.date_range("2026-01-01T00:00Z", periods=3, freq="30min", tz="UTC")
    snaps = pd.DataFrame(
        {
            "run_id": "r",
            "retrieved_at": pd.Timestamp("2025-12-31T12:00Z"),
            "interval_start_utc": t,
            "forecast": [100, 200, 300],
            "horizon_minutes": [720, 750, 780],
        }
    )
    actual = pd.DataFrame({"interval_start_utc": t[[0, 2]], "actual": [90, 330]})
    aligned = align_snapshots(snaps, actual)
    assert len(aligned) == 2  # slot without actual dropped
    assert aligned["error"].tolist() == [10, -30]
    assert set(aligned["horizon_bucket"].astype(str)) == {"12–24 h"}
    hm = horizon_metrics(aligned)
    assert hm.iloc[0]["n"] == 2 and hm.iloc[0]["mae"] == 20


def test_empty_snapshots_and_grouped_metrics():
    assert align_snapshots(pd.DataFrame(), pd.DataFrame()).empty
    df = pd.DataFrame({"g": ["a", "a", "b"], "forecast": [1, 3, 5], "actual": [2, 2, 5]})
    out = metrics_by(df, "g").set_index("g")
    assert out.at["a", "mae"] == 1 and out.at["b", "rmse"] == 0

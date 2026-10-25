"""Forecast evaluation.

Sign convention: error = forecast - actual. Positive bias means NESO's
forecast over-estimated intensity on average.

Two sources are supported:
* carbon_intensity rows carry the *final* published forecast for each slot.
  Its lead time is not reported by the API, so no horizon can be assigned.
* forecast_snapshots store the fw48h forecast captured at a known retrieval
  time, which gives a true horizon once the matching actual is published.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

HORIZON_BINS = [-30, 360, 720, 1440, 2910]
HORIZON_LABELS = ["0–6 h", "6–12 h", "12–24 h", "24–48 h"]


@dataclass(frozen=True)
class ForecastMetrics:
    n: int
    mae: float
    rmse: float
    bias: float
    median_abs_error: float
    p95_abs_error: float


def compute_metrics(forecast: pd.Series, actual: pd.Series) -> ForecastMetrics | None:
    pair = pd.DataFrame({"f": forecast, "a": actual}).astype("float64").dropna()
    if pair.empty:
        return None
    err = pair["f"] - pair["a"]
    abs_err = err.abs()
    return ForecastMetrics(
        n=len(err),
        mae=float(abs_err.mean()),
        rmse=float(np.sqrt((err**2).mean())),
        bias=float(err.mean()),
        median_abs_error=float(abs_err.median()),
        p95_abs_error=float(abs_err.quantile(0.95)),
    )


def published_forecast_pairs(df: pd.DataFrame) -> pd.DataFrame:
    """Rows where both the published forecast and the estimated actual exist."""
    out = df.dropna(subset=["forecast", "actual"]).copy()
    out["error"] = out["forecast"].astype("float64") - out["actual"].astype("float64")
    return out


def metrics_by(pairs: pd.DataFrame, by: str) -> pd.DataFrame:
    rows = []
    for key, grp in pairs.groupby(by, observed=True):
        m = compute_metrics(grp["forecast"], grp["actual"])
        if m:
            rows.append({by: key, **m.__dict__})
    return pd.DataFrame(rows)


def align_snapshots(snapshots: pd.DataFrame, intensity: pd.DataFrame) -> pd.DataFrame:
    """Join snapshot forecasts to the actual for the *target* slot."""
    if snapshots.empty:
        return pd.DataFrame()
    actuals = intensity.loc[intensity["actual"].notna(), ["interval_start_utc", "actual"]]
    out = snapshots.merge(actuals, on="interval_start_utc", how="inner", validate="many_to_one")
    if out.empty:
        return out
    out["error"] = out["forecast"].astype("float64") - out["actual"].astype("float64")
    out["horizon_bucket"] = pd.cut(
        out["horizon_minutes"], bins=HORIZON_BINS, labels=HORIZON_LABELS, right=False
    )
    return out


def horizon_metrics(aligned: pd.DataFrame) -> pd.DataFrame:
    if aligned.empty:
        return pd.DataFrame()
    return metrics_by(aligned.dropna(subset=["horizon_bucket"]), "horizon_bucket")

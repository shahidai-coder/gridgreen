"""Reusable analytical functions shared by the notebook and the dashboard.

All functions take the analytical frame from transform.build_analytical_frame
and return plain DataFrames / dataclasses, so they are easy to test.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import numpy as np
import pandas as pd

from gridgreen.config import SLOT_MINUTES
from gridgreen.transform import fuel_columns

SLOT = pd.Timedelta(minutes=SLOT_MINUTES)


def select_period(df: pd.DataFrame, start: date | None, end: date | None) -> pd.DataFrame:
    """Filter by inclusive local calendar dates."""
    if df.empty:
        return df
    mask = pd.Series(True, index=df.index)
    if start is not None:
        mask &= df["local_date"] >= start
    if end is not None:
        mask &= df["local_date"] <= end
    return df.loc[mask]


def summary_stats(df: pd.DataFrame, value: str = "actual") -> dict[str, object]:
    s = df[["interval_start_utc", value]].dropna()
    if s.empty:
        return {"n": 0}
    lo, hi = s[value].idxmin(), s[value].idxmax()
    return {
        "n": len(s),
        "mean": float(s[value].mean()),
        "median": float(s[value].median()),
        "std": float(s[value].std()),
        "min": float(s.at[lo, value]),
        "min_at": s.at[lo, "interval_start_utc"],
        "max": float(s.at[hi, value]),
        "max_at": s.at[hi, "interval_start_utc"],
        "p10": float(s[value].quantile(0.1)),
        "p90": float(s[value].quantile(0.9)),
    }


def profile(df: pd.DataFrame, by: str | list[str] = "slot_of_day", value: str = "actual") -> pd.DataFrame:
    """Mean / median / spread of `value` grouped by `by`."""
    keys = [by] if isinstance(by, str) else by
    d = df.dropna(subset=[value])
    if d.empty:
        return pd.DataFrame(columns=[*keys, "mean", "median", "std", "n", "p10", "p90", "ci_low", "ci_high"])
    g = d.groupby(keys, observed=True)[value]
    out = g.agg(mean="mean", median="median", std="std", n="count")
    q = g.quantile([0.1, 0.9]).unstack()
    out["p10"], out["p90"] = q[0.1], q[0.9]
    # Normal-approximation 95% CI. Half-hourly values are autocorrelated, so
    # this interval is optimistic (too narrow); it is shown as a rough guide.
    sem = out["std"] / np.sqrt(out["n"])
    out["ci_low"], out["ci_high"] = out["mean"] - 1.96 * sem, out["mean"] + 1.96 * sem
    return out.reset_index()


def monthly_summary(df: pd.DataFrame, value: str = "actual") -> pd.DataFrame:
    d = df.dropna(subset=[value])
    if d.empty:
        return pd.DataFrame()
    agg = {value: ["mean", "median", "min", "max", "count"]}
    if "share_zero_carbon" in d:
        agg["share_zero_carbon"] = ["mean"]
    out = d.groupby("year_month").agg(agg)
    out.columns = [
        "mean",
        "median",
        "min",
        "max",
        "n",
        *(["zero_carbon_share"] if "share_zero_carbon" in d else []),
    ]
    out["days"] = d.groupby("year_month")["local_date"].nunique()
    return out.reset_index()


def heatmap_matrix(df: pd.DataFrame, rows: str, cols: str = "hour", value: str = "actual") -> pd.DataFrame:
    d = df.dropna(subset=[value])
    if d.empty:
        return pd.DataFrame()
    return d.pivot_table(index=rows, columns=cols, values=value, aggfunc="mean", observed=True)


def day_type_comparison(df: pd.DataFrame, value: str = "actual") -> dict[str, object]:
    """Weekday vs weekend, including an hour-matched difference.

    Hour matching compares like with like (weekend 14:00 vs weekday 14:00), so
    an uneven spread of missing slots across hours cannot bias the result.
    """
    d = df.dropna(subset=[value])
    if d.empty or d["day_type"].nunique() < 2:
        return {"available": False}
    overall = d.groupby("day_type")[value].agg(["mean", "median", "count"])
    days = d.groupby("day_type")["local_date"].nunique()
    hourly = d.pivot_table(index="hour", columns="day_type", values=value, aggfunc="mean")
    hourly = hourly.dropna()
    diff = hourly["Weekend"] - hourly["Weekday"]
    return {
        "available": True,
        "weekday_mean": float(overall.at["Weekday", "mean"]),
        "weekend_mean": float(overall.at["Weekend", "mean"]),
        "weekday_median": float(overall.at["Weekday", "median"]),
        "weekend_median": float(overall.at["Weekend", "median"]),
        "weekday_n": int(overall.at["Weekday", "count"]),
        "weekend_n": int(overall.at["Weekend", "count"]),
        "weekday_days": int(days["Weekday"]),
        "weekend_days": int(days["Weekend"]),
        "hour_matched_diff": float(diff.mean()),
        "hours_weekend_lower": int((diff < 0).sum()),
        "hours_compared": len(diff),
    }


def spearman(x: pd.Series, y: pd.Series) -> float:
    """Spearman's rho as Pearson correlation of average ranks (ties averaged).

    Implemented directly so the project does not need SciPy, which pandas
    requires for method="spearman".
    """
    return float(x.rank(method="average").corr(y.rank(method="average")))


def fuel_correlations(df: pd.DataFrame, value: str = "actual", min_n: int = 30) -> pd.DataFrame:
    """Pearson and Spearman correlation of each fuel share with intensity."""
    rows = []
    for col in [*fuel_columns(df), "share_zero_carbon", "share_fossil"]:
        if col not in df:
            continue
        pair = df[[col, value]].dropna()
        if len(pair) < min_n or pair[col].nunique() < 2:
            continue
        rows.append(
            {
                "fuel": col.removeprefix("share_"),
                "pearson_r": pair[col].corr(pair[value], method="pearson"),
                "spearman_rho": spearman(pair[col], pair[value]),
                "mean_share": pair[col].mean(),
                "n": len(pair),
            }
        )
    out = pd.DataFrame(rows, columns=["fuel", "pearson_r", "spearman_rho", "mean_share", "n"])
    return out.sort_values("pearson_r").reset_index(drop=True)


def generation_share_series(df: pd.DataFrame, freq: str = "D") -> pd.DataFrame:
    """Mean fuel shares resampled to `freq` (local time)."""
    cols = fuel_columns(df)
    if not cols:
        return pd.DataFrame()
    d = df.set_index("interval_start_local")[cols].dropna(how="all")
    if d.empty:
        return pd.DataFrame()
    out = d.resample(freq).mean().dropna(how="all")
    out.columns = [c.removeprefix("share_") for c in out.columns]
    return out


def resample_intensity(df: pd.DataFrame, freq: str, value: str = "actual") -> pd.DataFrame:
    d = df.set_index("interval_start_local")[[value]].dropna()
    if d.empty:
        return pd.DataFrame(columns=["interval_start_local", "mean", "median", "min", "max", "n"])
    g = d[value].resample(freq)
    out = pd.DataFrame(
        {"mean": g.mean(), "median": g.median(), "min": g.min(), "max": g.max(), "n": g.count()}
    )
    return out.loc[out["n"] > 0].reset_index()


# ------------------------------------------------------------- best window
@dataclass
class BestWindowResult:
    duration_minutes: int
    value: str
    min_coverage: float
    candidates: pd.DataFrame
    top: pd.DataFrame
    typical: pd.DataFrame
    baseline: float | None
    best: pd.Series | None
    worst: pd.Series | None
    pct_vs_baseline: float | None
    n_candidates: int
    n_rejected_incomplete: int

    @property
    def available(self) -> bool:
        return self.best is not None


def _non_overlapping(cands: pd.DataFrame, k: int, n: int) -> pd.DataFrame:
    chosen: list[int] = []
    taken: list[tuple[pd.Timestamp, pd.Timestamp]] = []
    for idx, row in cands.sort_values(["mean_intensity", "start_utc"]).iterrows():
        if all(row["end_utc"] <= s or row["start_utc"] >= e for s, e in taken):
            chosen.append(idx)
            taken.append((row["start_utc"], row["end_utc"]))
            if len(chosen) == n:
                break
    return cands.loc[chosen].reset_index(drop=True)


def best_windows(
    df: pd.DataFrame,
    duration_minutes: int,
    value: str = "actual",
    min_coverage: float = 1.0,
    top_n: int = 5,
) -> BestWindowResult:
    """Find the lowest-intensity contiguous windows of a given duration.

    Method
    ------
    1. Reindex to the complete UTC half-hour grid so gaps become explicit NaNs.
    2. For every possible start slot, the window holds k = duration / 30 slots.
       Each slot is 30 minutes, so the duration-weighted mean equals the
       arithmetic mean of the slot values.
    3. coverage = valid slots / k; windows below `min_coverage` are rejected.
    4. Baseline = mean over all valid candidate windows, i.e. the expected
       intensity of the same load started at a uniformly random time in the
       period. The best window is compared against this baseline.
    """
    if duration_minutes <= 0 or duration_minutes % SLOT_MINUTES:
        raise ValueError(f"duration must be a positive multiple of {SLOT_MINUTES} minutes")
    if not 0 < min_coverage <= 1:
        raise ValueError("min_coverage must be in (0, 1]")
    k = duration_minutes // SLOT_MINUTES
    empty = BestWindowResult(
        duration_minutes,
        value,
        min_coverage,
        pd.DataFrame(),
        pd.DataFrame(),
        pd.DataFrame(),
        None,
        None,
        None,
        None,
        0,
        0,
    )
    s = df.set_index("interval_start_utc")[value].astype("float64").dropna()
    if s.empty:
        return empty
    grid = pd.date_range(s.index.min(), s.index.max(), freq=SLOT)
    s = s.reindex(grid)
    if len(grid) < k:
        return empty

    valid = s.notna().astype("float64")
    sums = s.fillna(0.0).rolling(k).sum().shift(-(k - 1))
    counts = valid.rolling(k).sum().shift(-(k - 1))
    cands = pd.DataFrame(
        {
            "start_utc": grid,
            "end_utc": grid + k * SLOT,
            "n_valid": counts.to_numpy(),
            "mean_intensity": (sums / counts.replace(0, np.nan)).to_numpy(),
        }
    ).dropna(subset=["n_valid"])
    cands["coverage"] = cands["n_valid"] / k
    ok = (cands["coverage"] >= min_coverage - 1e-9) & cands["mean_intensity"].notna()
    rejected = int((~ok).sum())
    cands = cands.loc[ok].reset_index(drop=True)
    if cands.empty:
        empty.n_rejected_incomplete = rejected
        return empty
    cands["n_valid"] = cands["n_valid"].astype(int)
    from gridgreen.config import LOCAL_TZ  # local import avoids a cycle in type checkers

    cands["start_local"] = cands["start_utc"].dt.tz_convert(LOCAL_TZ)
    cands["end_local"] = cands["end_utc"].dt.tz_convert(LOCAL_TZ)
    cands["start_time"] = cands["start_local"].dt.strftime("%H:%M")

    baseline = float(cands["mean_intensity"].mean())
    best = cands.loc[cands["mean_intensity"].idxmin()]
    worst = cands.loc[cands["mean_intensity"].idxmax()]
    typical = (
        cands.groupby("start_time")["mean_intensity"]
        .agg(mean="mean", median="median", n="count")
        .reset_index()
        .sort_values("start_time")
    )
    typical["pct_vs_baseline"] = (typical["mean"] - baseline) / baseline * 100
    return BestWindowResult(
        duration_minutes=duration_minutes,
        value=value,
        min_coverage=min_coverage,
        candidates=cands,
        top=_non_overlapping(cands, k, top_n),
        typical=typical,
        baseline=baseline,
        best=best,
        worst=worst,
        pct_vs_baseline=(float(best["mean_intensity"]) - baseline) / baseline * 100,
        n_candidates=len(cands),
        n_rejected_incomplete=rejected,
    )

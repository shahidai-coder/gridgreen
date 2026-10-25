"""Transform stage: pandas normalisation, deduplication, joins and features.

Timestamp policy
----------------
* The unique key of every half-hour is its UTC start (`interval_start_utc`).
* Local (Europe/London) fields are *derived* for analysis only. They are never
  used as keys, because 01:00-02:00 local repeats on the October DST day.
* A local calendar day therefore contains 46 (March), 48 or 50 (October) slots.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime

import numpy as np
import pandas as pd

from gridgreen.config import (
    FOSSIL_FUELS,
    LOCAL_TZ,
    SEASON_BY_MONTH,
    SEASON_ORDER,
    SLOT_MINUTES,
    ZERO_CARBON_FUELS,
    fuel_category,
)
from gridgreen.schemas import GenerationRecord, IntensityRecord

SLOT_FREQ = f"{SLOT_MINUTES}min"
INTENSITY_COLUMNS = [
    "interval_start_utc",
    "interval_end_utc",
    "forecast",
    "actual",
    "intensity_index",
]
WEEKDAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


# ------------------------------------------------------------- normalisation
def intensity_to_frame(records: Iterable[IntensityRecord]) -> pd.DataFrame:
    rows = [
        {
            "interval_start_utc": r.interval_start,
            "interval_end_utc": r.interval_end,
            "forecast": r.intensity.forecast,
            "actual": r.intensity.actual,
            "intensity_index": r.intensity.index,
        }
        for r in records
    ]
    df = pd.DataFrame(rows, columns=INTENSITY_COLUMNS)
    return _coerce_intensity(df)


def _coerce_intensity(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for col in ("interval_start_utc", "interval_end_utc"):
        df[col] = pd.to_datetime(df[col], utc=True)
    for col in ("forecast", "actual"):
        df[col] = pd.to_numeric(df[col]).astype("Int64")
    df["intensity_index"] = df["intensity_index"].astype("string")
    return df


def generation_to_frame(records: Iterable[GenerationRecord]) -> pd.DataFrame:
    rows = [
        {"interval_start_utc": r.interval_start, "fuel": share.fuel, "perc": share.perc}
        for r in records
        for share in r.generationmix
    ]
    df = pd.DataFrame(rows, columns=["interval_start_utc", "fuel", "perc"])
    df["interval_start_utc"] = pd.to_datetime(df["interval_start_utc"], utc=True)
    df["fuel"] = df["fuel"].astype("string")
    df["perc"] = df["perc"].astype("float64")
    return df


# ------------------------------------------------------------- deduplication
def dedupe_intensity(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Keep one row per slot: prefer rows with an actual, then with a forecast.

    The sort is stable and fully specified, so the result is deterministic.
    """
    if df.empty:
        return df, 0
    ranked = df.assign(
        _has_actual=df["actual"].notna().astype(int),
        _has_forecast=df["forecast"].notna().astype(int),
    ).sort_values(
        ["interval_start_utc", "_has_actual", "_has_forecast"],
        ascending=[True, False, False],
        kind="mergesort",
    )
    out = ranked.drop_duplicates("interval_start_utc", keep="first").drop(
        columns=["_has_actual", "_has_forecast"]
    )
    return out.reset_index(drop=True), len(df) - len(out)


def dedupe_generation(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    if df.empty:
        return df, 0
    out = df.sort_values(["interval_start_utc", "fuel"], kind="mergesort").drop_duplicates(
        ["interval_start_utc", "fuel"], keep="last"
    )
    return out.reset_index(drop=True), len(df) - len(out)


def filter_range(df: pd.DataFrame, start: datetime, end: datetime) -> pd.DataFrame:
    """Keep rows whose slot starts in [start, end)."""
    mask = (df["interval_start_utc"] >= pd.Timestamp(start)) & (df["interval_start_utc"] < pd.Timestamp(end))
    return df.loc[mask].reset_index(drop=True)


# ------------------------------------------------------------- data quality
def expected_slots(start: datetime, end: datetime) -> pd.DatetimeIndex:
    """All UTC half-hour slot starts in [start, end)."""
    s = pd.Timestamp(start).tz_convert("UTC").ceil(SLOT_FREQ)
    e = pd.Timestamp(end).tz_convert("UTC")
    return pd.date_range(s, e, freq=SLOT_FREQ, inclusive="left")


def detect_missing_intervals(
    df: pd.DataFrame, start: datetime, end: datetime, column: str | None = None
) -> pd.DatetimeIndex:
    """Expected slots absent from df (or present but with a null `column`)."""
    present = df
    if column is not None:
        present = df.loc[df[column].notna()]
    have = pd.DatetimeIndex(present["interval_start_utc"].unique())
    return expected_slots(start, end).difference(have)


def slots_per_local_day(start: datetime, end: datetime) -> pd.Series:
    """Number of half-hour slots in each local calendar day (46/48/50)."""
    local = expected_slots(start, end).tz_convert(LOCAL_TZ)
    return pd.Series(local.date).value_counts().sort_index()


# ------------------------------------------------------------- features
def season_of(month: int) -> str:
    return SEASON_BY_MONTH[month]


def add_time_features(df: pd.DataFrame, ts_col: str = "interval_start_utc") -> pd.DataFrame:
    out = df.copy()
    local = out[ts_col].dt.tz_convert(LOCAL_TZ)
    out["interval_start_local"] = local
    out["local_date"] = local.dt.date
    out["hour"] = local.dt.hour.astype("int16")
    out["minute"] = local.dt.minute.astype("int16")
    # Wall-clock slot of day (0..47). On the October change two different UTC
    # slots share a wall-clock slot; this is correct for time-of-day profiles.
    out["slot_of_day"] = (out["hour"] * 2 + out["minute"] // 30).astype("int16")
    out["time_label"] = local.dt.strftime("%H:%M")
    out["weekday_num"] = local.dt.day_of_week.astype("int16")
    out["weekday"] = pd.Categorical(
        [WEEKDAY_NAMES[d] for d in out["weekday_num"]], categories=WEEKDAY_NAMES, ordered=True
    )
    out["is_weekend"] = out["weekday_num"] >= 5
    out["day_type"] = np.where(out["is_weekend"], "Weekend", "Weekday")
    out["month"] = local.dt.month.astype("int16")
    out["year_month"] = local.dt.strftime("%Y-%m")
    out["season"] = pd.Categorical(
        [SEASON_BY_MONTH[m] for m in out["month"]], categories=list(SEASON_ORDER), ordered=True
    )
    out["utc_offset_hours"] = local.apply(lambda t: t.utcoffset().total_seconds() / 3600) if len(out) else []
    return out


def generation_wide(gen: pd.DataFrame) -> pd.DataFrame:
    """Pivot long generation shares to one column per fuel (`share_<fuel>`)."""
    if gen.empty:
        return pd.DataFrame(columns=["interval_start_utc"])
    wide = gen.pivot_table(index="interval_start_utc", columns="fuel", values="perc", aggfunc="first")
    wide.columns = [f"share_{c}" for c in wide.columns]
    wide = wide.reset_index()
    fuels = [c.removeprefix("share_") for c in wide.columns if c.startswith("share_")]

    def _sum(group: tuple[str, ...]) -> pd.Series:
        cols = [f"share_{f}" for f in fuels if f in group]
        return wide[cols].sum(axis=1, min_count=1) if cols else pd.Series(np.nan, index=wide.index)

    wide["share_zero_carbon"] = _sum(ZERO_CARBON_FUELS)
    wide["share_fossil"] = _sum(FOSSIL_FUELS)
    wide["fuels_reported"] = wide[[f"share_{f}" for f in fuels]].notna().sum(axis=1)
    return wide


def build_analytical_frame(intensity: pd.DataFrame, generation: pd.DataFrame) -> pd.DataFrame:
    """Left-join generation onto intensity by UTC slot and add features.

    Intensity is the analytical spine; slots lacking generation keep NaN shares
    (they are not imputed). `forecast_error` = forecast - actual, so a positive
    value means the forecast over-estimated intensity.
    """
    base = intensity.copy()
    if base.empty:
        return add_time_features(base.assign(forecast_error=pd.Series(dtype="float64")))
    wide = generation_wide(generation)
    merged = base.merge(wide, on="interval_start_utc", how="left", validate="one_to_one")
    for col in ("forecast", "actual"):
        merged[col] = merged[col].astype("Float64").to_numpy(dtype="float64", na_value=np.nan)
    merged["forecast_error"] = merged["forecast"] - merged["actual"]
    return add_time_features(merged).sort_values("interval_start_utc").reset_index(drop=True)


def fuel_columns(df: pd.DataFrame) -> list[str]:
    skip = {"share_zero_carbon", "share_fossil"}
    return [c for c in df.columns if c.startswith("share_") and c not in skip]


def fuel_categories_table(fuels: Iterable[str]) -> pd.DataFrame:
    return pd.DataFrame({"fuel": list(fuels)}).assign(category=lambda d: d["fuel"].map(fuel_category))

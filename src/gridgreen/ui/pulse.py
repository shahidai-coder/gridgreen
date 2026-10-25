"""Grid Pulse: the interactive Overview experience.

Python computes every number from the stored data using the shared analytics
functions. The browser side (pulse/index.html, ECharts) only draws it and
handles interaction, so nothing shown is invented in JavaScript.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import streamlit.components.v1 as components

from gridgreen.analytics import best_windows, day_type_comparison, fuel_correlations, profile, summary_stats
from gridgreen.config import LOCAL_TZ
from gridgreen.transform import fuel_columns, slots_per_local_day
from gridgreen.ui import theme

_COMPONENT = components.declare_component("gridgreen_pulse", path=str(Path(__file__).parent / "pulse"))


def _num(x: Any, nd: int = 1) -> float | None:
    """JSON-safe number: NaN/None become null (JSON has no NaN)."""
    if x is None:
        return None
    try:
        f = float(x)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(f) or math.isinf(f) else round(f, nd)


def _local_portable(ts: Any) -> str | None:
    if ts is None or pd.isna(ts):
        return None
    t = pd.Timestamp(ts).tz_convert(LOCAL_TZ)
    return f"{t:%a} {t.day} {t:%b %Y}, {t:%H:%M}"


def _sankey(runs: pd.DataFrame) -> dict[str, Any] | None:
    """Record flow of the most recent run that fetched intensity records."""
    if runs.empty:
        return None
    useful = runs.loc[runs["intensity_extracted"].fillna(0) > 0]
    if useful.empty:
        return None
    r = useful.iloc[0]
    ext, acc, rej = int(r["intensity_extracted"]), int(r["intensity_accepted"]), int(r["intensity_rejected"])
    loaded, new = int(r["intensity_upserted"]), int(r["intensity_new"])
    flows = [
        ("Fetched from API", "Passed validation", acc),
        ("Fetched from API", "Rejected and logged", rej),
        ("Fetched from API", "Exact duplicates", max(ext - acc - rej, 0)),
        ("Passed validation", "Loaded to DuckDB", loaded),
        ("Passed validation", "Outside range or merged", max(acc - loaded, 0)),
        ("Loaded to DuckDB", "New half-hours", new),
        ("Loaded to DuckDB", "Updated existing", max(loaded - new, 0)),
    ]
    links = [{"source": s, "target": t, "value": v} for s, t, v in flows if v > 0]
    names = sorted({n for link in links for n in (link["source"], link["target"])})
    return {
        "run_id": str(r["run_id"]),
        "started": _local_portable(r["started_at"]),
        "status": str(r["status"]),
        "nodes": [{"name": n} for n in names],
        "links": links,
    }


def build_payload(
    frame: pd.DataFrame,
    full: pd.DataFrame,
    runs: pd.DataFrame,
    is_demo: bool,
    palette: theme.Palette | None = None,
) -> dict[str, Any]:
    """Everything the page draws, as plain JSON-safe values."""
    p = palette or theme.pal()
    f = frame.dropna(subset=["actual"])
    stats = summary_stats(f)
    if stats["n"] == 0:
        return {"empty": True}

    observed = full.dropna(subset=["actual"])
    latest = observed.iloc[-1]
    previous = observed.iloc[-2] if len(observed) > 1 else None
    change_pct = (
        _num((latest["actual"] - previous["actual"]) / previous["actual"] * 100)
        if previous is not None and previous["actual"]
        else None
    )
    recent = observed.tail(48)
    # Completeness uses whole UK calendar days of the selected period, the same
    # definition as the Data Quality page, so both pages report the same figure.
    first_day, last_day = frame["local_date"].min(), frame["local_date"].max()
    start_utc = pd.Timestamp(first_day).tz_localize(LOCAL_TZ).tz_convert("UTC")
    end_utc = (pd.Timestamp(last_day) + pd.Timedelta(days=1)).tz_localize(LOCAL_TZ).tz_convert("UTC")

    # Daily series (local dates).
    g = f.groupby("local_date")["actual"]
    daily = pd.DataFrame(
        {"mean": g.mean(), "median": g.median(), "min": g.min(), "max": g.max(), "n": g.count()}
    )
    expected = slots_per_local_day(start_utc.to_pydatetime(), end_utc.to_pydatetime())
    expected.index = pd.Index(expected.index)
    daily["expected"] = expected.reindex(daily.index).fillna(48)
    daily["completeness"] = daily["n"] / daily["expected"] * 100
    dates = [str(d) for d in daily.index]

    # Per-day drill-down: 48 wall-clock slots + that day's average mix.
    slot_mat = f.pivot_table(index="local_date", columns="slot_of_day", values="actual", aggfunc="mean")
    slot_mat = slot_mat.reindex(columns=range(48))
    fcols = fuel_columns(f)
    day_mix = f.groupby("local_date")[fcols].mean() if fcols else pd.DataFrame()
    # Cleanest complete 2-hour (4-slot) window per day, on the wall-clock grid.
    arr = slot_mat.to_numpy(dtype="float64")
    win = np.lib.stride_tricks.sliding_window_view(arr, 4, axis=1)  # (days, 45, 4)
    complete = ~np.isnan(win).any(axis=2)
    win_mean = np.where(complete, np.nan_to_num(win).mean(axis=2), np.inf)
    best_start = {
        d: (int(win_mean[i].argmin()) if complete[i].any() else None) for i, d in enumerate(slot_mat.index)
    }
    days: dict[str, Any] = {}
    for d in daily.index:
        mix = {}
        if not day_mix.empty and d in day_mix.index:
            mix = {c.removeprefix("share_"): _num(v) for c, v in day_mix.loc[d].items() if _num(v)}
        days[str(d)] = {
            "slots": [_num(v, 0) for v in slot_mat.loc[d].to_numpy()] if d in slot_mat.index else [None] * 48,
            "mix": mix,
            "best2h": best_start.get(d),
        }

    # Carbon clock: mean by half-hour of day, for all days and by day type.
    def clock(sub: pd.DataFrame) -> list[float | None]:
        p = profile(sub, by="slot_of_day").set_index("slot_of_day").reindex(range(48))
        return [_num(v) for v in p["mean"]]

    clocks = {
        "All days": clock(f),
        "Weekdays": clock(f[f["day_type"] == "Weekday"]),
        "Weekends": clock(f[f["day_type"] == "Weekend"]),
    }

    # Generation mix: period average and monthly averages.
    mix_avg: dict[str, float] = {}
    monthly: dict[str, Any] = {"months": [], "series": {}}
    if fcols and f[fcols].notna().any().any():
        means = f[fcols].mean().dropna()
        mix_avg = {c.removeprefix("share_"): _num(v) for c, v in means.sort_values(ascending=False).items()}
        mm = f.groupby("year_month")[fcols].mean()
        monthly = {
            "months": list(mm.index),
            "series": {c.removeprefix("share_"): [_num(v) for v in mm[c]] for c in fcols},
        }

    # Insights from the shared analytics functions.
    hourly = profile(f, by="hour")
    best_h = hourly.loc[hourly["mean"].idxmin()]
    worst_h = hourly.loc[hourly["mean"].idxmax()]
    insights = [
        {
            "kind": "clock",
            "title": f"Cleanest hour: {int(best_h['hour']):02d}:00",
            "text": f"Averaged {best_h['mean']:.0f} gCO₂/kWh, versus {worst_h['mean']:.0f} at "
            f"{int(worst_h['hour']):02d}:00, the most intensive hour.",
        }
    ]
    bw = best_windows(f, 120)
    if bw.available:
        typ = bw.typical.loc[bw.typical["mean"].idxmin()]
        insights.append(
            {
                "kind": "plug",
                "title": f"Best 2-hour start: {typ['start_time']}",
                "text": f"{abs(typ['pct_vs_baseline']):.0f}% "
                f"{'below' if typ['pct_vs_baseline'] < 0 else 'above'} "
                f"a random start time, across {int(typ['n'])} days.",
            }
        )
    dt = day_type_comparison(f)
    if dt["available"]:
        diff = dt["hour_matched_diff"]
        insights.append(
            {
                "kind": "calendar",
                "title": f"Weekends {'cleaner' if diff < 0 else 'dirtier'} by {abs(diff):.0f} g",
                "text": f"Hour-matched across {dt['weekend_days']} weekend days "
                f"and {dt['weekday_days']} weekdays. "
                "An association, not proof of cause.",
            }
        )
    corr = fuel_correlations(f)
    corr = corr.loc[~corr["fuel"].isin(["zero_carbon", "fossil"])]
    if len(corr) >= 2:
        lo, hi = corr.iloc[0], corr.iloc[-1]
        insights.append(
            {
                "kind": "wind",
                "title": f"{lo['fuel'].capitalize()} pulls intensity down",
                "text": f"r = {lo['pearson_r']:.2f} with {lo['fuel']}, r = {hi['pearson_r']:+.2f} with "
                f"{hi['fuel']}. Correlation, not causation.",
            }
        )

    # Friendly tip for the yellow card, from the same best-window analysis.
    tip = None
    if bw.available:
        typ = bw.typical.loc[bw.typical["mean"].idxmin()]
        tip = {
            "start": str(typ["start_time"]),
            "pct": _num(abs(typ["pct_vs_baseline"]), 0),
            "direction": "lower" if typ["pct_vs_baseline"] < 0 else "higher",
        }

    # How the latest reading compares with the period's average for the same time of day.
    latest_slot = int(
        pd.Timestamp(latest["interval_start_utc"]).tz_convert(LOCAL_TZ).hour * 2
        + pd.Timestamp(latest["interval_start_utc"]).tz_convert(LOCAL_TZ).minute // 30
    )
    typical = clocks["All days"][latest_slot]
    vs_typical = (
        {
            "slot": f"{latest_slot // 2:02d}:{30 * (latest_slot % 2):02d}",
            "typical": typical,
            "pct": _num((float(latest["actual"]) - typical) / typical * 100, 0),
        }
        if typical
        else None
    )

    best_day = daily["mean"].idxmin()
    total_expected = float(daily["expected"].sum())
    return {
        "empty": False,
        "demo": bool(is_demo),
        "period": f"{dates[0]} to {dates[-1]}",
        "latest": {
            "value": _num(latest["actual"], 0),
            "when": _local_portable(latest["interval_start_utc"]),
            "band": None if pd.isna(latest["intensity_index"]) else str(latest["intensity_index"]),
            "change_pct": change_pct,
            "recent": [_num(v, 0) for v in recent["actual"]],
            "recent_labels": [
                pd.Timestamp(t).tz_convert(LOCAL_TZ).strftime("%H:%M") for t in recent["interval_start_utc"]
            ],
        },
        "tip": tip,
        "vs_typical": vs_typical,
        "kpi": {
            "mean": _num(stats["mean"], 0),
            "median": _num(stats["median"], 0),
            "min": _num(stats["min"], 0),
            "min_at": _local_portable(stats["min_at"]),
            "max": _num(stats["max"], 0),
            "max_at": _local_portable(stats["max_at"]),
            "n": int(stats["n"]),
            "completeness": _num(stats["n"] / total_expected * 100 if total_expected else None),
            "expected": int(total_expected),
        },
        "daily": {
            "dates": dates,
            "mean": [_num(v) for v in daily["mean"]],
            "median": [_num(v) for v in daily["median"]],
            "min": [_num(v, 0) for v in daily["min"]],
            "max": [_num(v, 0) for v in daily["max"]],
            "completeness": [_num(v) for v in daily["completeness"]],
            "missing": [int(max(e - n, 0)) for e, n in zip(daily["expected"], daily["n"], strict=True)],
        },
        "days": days,
        "best_day": str(best_day),
        "clocks": clocks,
        "mix": mix_avg,
        "monthly": monthly,
        "insights": insights,
        "sankey": _sankey(runs),
        "theme": {
            "bg": p.CANVAS,
            "surface": p.SURFACE,
            "surface2": p.SURFACE_2,
            "border": p.BORDER,
            "grid": p.GRID,
            "text": p.TEXT,
            "text2": p.TEXT_2,
            "accent": p.EMERALD,
            "accent2": p.ACCENT_2,
            "onAccent": p.ON_ACCENT,
            "warn": p.WARNING,
            "error": p.ERROR,
            "lime": p.LIME,
            "scale": [c for _, c in p.INTENSITY_SCALE],
            "fuels": p.FUEL_COLORS,
            "font": theme.FONT_STACK,
            "forest": p.FOREST,
            "lowBg": p.LOW_BG,
            "lowText": p.LOW_TEXT,
            "yellow": p.YELLOW,
            "yellowText": p.YELLOW_TEXT,
            "selected": p.SELECTED_BG,
            "scene": p.SCENE,
            "sceneDay": theme.LIGHT.SCENE,
            "sceneNight": theme.DARK.SCENE,
            "highBg": p.DEMO_BG,
            "highText": p.DEMO_TEXT,
            "shadow": p.SHADOW,
        },
    }


def grid_pulse(payload: dict[str, Any], key: str = "grid_pulse") -> Any:
    """Render the component. Returns the day the user last clicked (or None)."""
    return _COMPONENT(data=payload, key=key, default=None)

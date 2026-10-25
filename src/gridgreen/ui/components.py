"""Shared Streamlit building blocks: data access, filters and page chrome.

The dashboard only ever opens DuckDB read-only. It never runs ETL, so a page
refresh can never duplicate data.
"""

from __future__ import annotations

import html
import os
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

from gridgreen import database
from gridgreen.analytics import select_period
from gridgreen.config import (
    API_DOCS_URL,
    ATTRIBUTION,
    DATA_SOURCE_DEMO,
    DEFAULT_DB_PATH,
    DEMO_DB_PATH,
    LICENCE_URL,
    LOCAL_TZ,
    PROJECT_ROOT,
)
from gridgreen.transform import build_analytical_frame, expected_slots
from gridgreen.ui.theme import GLOBAL_CSS, register_plotly_template

FILTER_PREFIX = "gg_"


def day_month_year(d) -> str:
    """'1 Oct 2025'. Portable: the glibc 'no leading zero' strftime flag fails on Windows."""
    return f"{d.day} {d:%b %Y}"


# ----------------------------------------------------------------- data
@dataclass
class Dataset:
    db_path: str
    source: str | None
    frame: pd.DataFrame
    generation: pd.DataFrame
    runs: pd.DataFrame
    rejected: pd.DataFrame
    snapshots: pd.DataFrame
    counts: dict[str, int] = field(default_factory=dict)

    @property
    def is_demo(self) -> bool:
        return self.source == DATA_SOURCE_DEMO

    @property
    def empty(self) -> bool:
        return self.frame.empty


def resolve_db_path() -> Path | None:
    configured = os.getenv("GRIDGREEN_DB_PATH")
    candidates = [Path(configured)] if configured else [DEFAULT_DB_PATH, DEMO_DB_PATH]
    return next((p for p in candidates if p.exists()), None)


@st.cache_data(show_spinner="Loading data from DuckDB…", max_entries=4)
def _load(path: str, mtime: float) -> Dataset:  # mtime is part of the cache key
    con = database.connect(path, read_only=True)
    try:
        have = database.existing_tables(con)
        if "carbon_intensity" not in have:
            empty = pd.DataFrame()
            return Dataset(path, None, empty, empty, empty, empty, empty, {})
        intensity = database.read_intensity(con)
        generation = database.read_generation(con)
        return Dataset(
            db_path=path,
            source=database.get_metadata(con, "source"),
            frame=build_analytical_frame(intensity, generation),
            generation=generation,
            runs=database.read_runs(con),
            rejected=database.read_rejected(con),
            snapshots=database.read_snapshots(con) if "forecast_snapshots" in have else pd.DataFrame(),
            counts=database.table_counts(con),
        )
    finally:
        con.close()


def load_dataset() -> Dataset | None:
    path = resolve_db_path()
    if path is None:
        return None
    return _load(str(path), path.stat().st_mtime)


# ----------------------------------------------------------------- context
@dataclass
class Context:
    ds: Dataset
    start: date
    end: date
    frame: pd.DataFrame

    @property
    def period_label(self) -> str:
        return f"{day_month_year(self.start)} to {day_month_year(self.end)}"

    def expected_slot_count(self) -> int:
        s = pd.Timestamp(self.start).tz_localize(LOCAL_TZ)
        e = (pd.Timestamp(self.end) + pd.Timedelta(days=1)).tz_localize(LOCAL_TZ)
        return len(expected_slots(s.to_pydatetime(), e.to_pydatetime()))


def data_bounds(ds: Dataset) -> tuple[date, date]:
    return ds.frame["local_date"].min(), ds.frame["local_date"].max()


def get_context() -> Context | None:
    ds = load_dataset()
    if ds is None or ds.empty:
        return None
    lo, hi = data_bounds(ds)
    rng = st.session_state.get(f"{FILTER_PREFIX}range", (lo, hi))
    start, end = (rng[0], rng[1]) if isinstance(rng, (tuple, list)) and len(rng) == 2 else (lo, hi)
    start, end = max(start, lo), min(end, hi)
    return Context(ds=ds, start=start, end=end, frame=select_period(ds.frame, start, end))


# ----------------------------------------------------------------- chrome
def setup_page() -> None:
    assets = PROJECT_ROOT / "assets"
    st.set_page_config(
        page_title="GridGreen",
        page_icon=str(assets / "icon.svg"),
        layout="wide",
        initial_sidebar_state="auto",
    )
    st.logo(str(assets / "logo.svg"), size="large", icon_image=str(assets / "icon.svg"))
    register_plotly_template()
    st.markdown(GLOBAL_CSS, unsafe_allow_html=True)


def reset_filters() -> None:
    for key in [k for k in st.session_state if str(k).startswith(FILTER_PREFIX)]:
        del st.session_state[key]


def sidebar(ds: Dataset | None) -> None:
    with st.sidebar:
        st.markdown(
            '<p class="gg-tagline">Carbon intelligence for a cleaner grid.</p>', unsafe_allow_html=True
        )
        if ds is None or ds.empty:
            return
        lo, hi = data_bounds(ds)
        st.date_input(
            "Period (UK local dates)",
            value=(lo, hi),
            min_value=lo,
            max_value=hi,
            key=f"{FILTER_PREFIX}range",
            format="DD/MM/YYYY",
        )
        st.button("Reset all filters", on_click=reset_filters, width="stretch")
        st.caption(f"Database: `{Path(ds.db_path).name}`")


def _fmt_ts(ts: pd.Timestamp | None) -> str:
    if ts is None or pd.isna(ts):
        return "unknown"
    local = pd.Timestamp(ts).tz_convert(LOCAL_TZ)
    return f"{day_month_year(local)}, {local:%H:%M}"


def topbar(title: str, ctx: Context | None) -> None:
    status_html = ""
    period = "No data loaded"
    if ctx is not None:
        period = f"{ctx.period_label} (UK local dates)"
        last = ctx.ds.frame.loc[ctx.ds.frame["actual"].notna(), "interval_start_utc"].max()
        runs = ctx.ds.runs
        dot, run_txt = "warn", "no pipeline runs recorded"
        if not runs.empty:
            r = runs.iloc[0]
            dot = {"success": "", "partial": "warn"}.get(r["status"], "bad")
            run_txt = f"last pipeline run {_fmt_ts(r['started_at'])} ({r['status']})"
        status_html = (
            f'<span class="gg-status"><span class="gg-dot {dot}"></span>'
            f"Data to {_fmt_ts(last)}; {html.escape(run_txt)}</span>"
        )
    st.markdown(
        f'<div class="gg-topbar"><div><h1>{html.escape(title)}</h1>'
        f'<div class="gg-period">{html.escape(period)}</div></div>{status_html}</div>',
        unsafe_allow_html=True,
    )
    if ctx is not None and ctx.ds.is_demo:
        st.markdown(
            '<div class="gg-demo"><b>Demonstration mode: synthetic data.</b> This database was generated '
            "by the offline demo generator, not the NESO API. Use it to explore the interface only; "
            "nothing shown here is a finding about the GB grid. Run the pipeline to load real data.</div>",
            unsafe_allow_html=True,
        )


def signed(x: float, decimals: int = 0) -> str:
    """Format with an explicit sign and a true minus character (U+2212)."""
    return f"{x:+.{decimals}f}".replace("-", "\u2212")


def kpi(label: str, value: str, unit: str = "", sub: str = "") -> None:
    unit_html = f"<small>{html.escape(unit)}</small>" if unit else ""
    sub_html = f'<div class="gg-kpi-sub">{html.escape(sub)}</div>' if sub else ""
    st.markdown(
        f'<div class="gg-kpi"><div class="gg-kpi-label">{html.escape(label)}</div>'
        f'<div class="gg-kpi-value">{html.escape(value)}{unit_html}</div>{sub_html}</div>',
        unsafe_allow_html=True,
    )


def insight(text: str) -> None:
    st.markdown(f'<div class="gg-insight"><p>{text}</p></div>', unsafe_allow_html=True)


def note(text: str) -> None:
    st.markdown(f'<p class="gg-note">{text}</p>', unsafe_allow_html=True)


def empty_state(title: str, body: str) -> None:
    st.markdown(
        f'<div class="gg-empty"><h3>{html.escape(title)}</h3><p>{body}</p></div>', unsafe_allow_html=True
    )


def no_data_state() -> None:
    empty_state(
        "No data loaded yet",
        "Load real data with <code>python scripts/run_pipeline.py --start 2025-10-01</code>, "
        "then refresh this page. To explore the interface offline, build the synthetic demo database "
        "with <code>python scripts/build_demo_db.py</code>.",
    )


def footer() -> None:
    st.markdown(
        f'<div class="gg-footer">{html.escape(ATTRIBUTION)} '
        f'<a href="{LICENCE_URL}" target="_blank">Licence</a>. '
        f'<a href="{API_DOCS_URL}" target="_blank">API documentation</a>. '
        "Historical analysis only; nothing here is a live measurement or a prediction.</div>",
        unsafe_allow_html=True,
    )


def csv_download(df: pd.DataFrame, label: str, file_name: str, key: str) -> None:
    out = df.copy()
    for col in out.columns:
        if isinstance(out[col].dtype, pd.DatetimeTZDtype):
            out[col] = out[col].dt.strftime("%Y-%m-%dT%H:%M:%S%z")
    st.download_button(
        label,
        out.to_csv(index=False).encode(),
        file_name=file_name,
        mime="text/csv",
        key=key,
        on_click="ignore",
    )


def fmt_local(ts: pd.Timestamp | None) -> str:
    return _fmt_ts(ts)

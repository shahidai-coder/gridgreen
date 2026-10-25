import pandas as pd
import streamlit as st

from gridgreen.analytics import day_type_comparison, fuel_correlations, profile, summary_stats
from gridgreen.transform import fuel_columns
from gridgreen.ui import charts
from gridgreen.ui.components import (
    csv_download,
    empty_state,
    fmt_local,
    footer,
    get_context,
    insight,
    kpi,
    no_data_state,
    topbar,
)

ctx = get_context()
topbar("Overview", ctx)
if ctx is None:
    no_data_state()
    footer()
    st.stop()

f = ctx.frame
stats = summary_stats(f)
latest = ctx.ds.frame.dropna(subset=["actual"]).iloc[-1]

st.markdown(
    f"""<div class="gg-hero">
      <div>
        <div class="gg-h-label">Latest estimated intensity in the database</div>
        <div class="gg-h-value">{latest["actual"]:.0f}<small>gCO₂/kWh</small></div>
        <div class="gg-h-meta">Half-hour starting {fmt_local(latest["interval_start_utc"])} (UK time).<br>
        A stored historical value, refreshed only when the pipeline runs.</div>
        {f'<span class="gg-band">{latest["intensity_index"]}</span>' if pd.notna(latest["intensity_index"]) else ""}
      </div>
      <div class="gg-h-right">
        <p><b>When is Britain's electricity cleanest, and what makes it that way?</b></p>
        <p>GridGreen collects half-hourly carbon intensity and generation-mix data for Great Britain,
        validates it, stores it in DuckDB, and shows when the grid has historically been cleanest.</p>
      </div>
    </div>""",
    unsafe_allow_html=True,
)
st.write("")

if stats["n"] == 0:
    empty_state("No estimated actuals in this period", "Widen the period in the sidebar.")
    footer()
    st.stop()

expected = ctx.expected_slot_count()
c1, c2, c3, c4 = st.columns(4)
with c1:
    kpi(
        "Mean intensity",
        f"{stats['mean']:.0f}",
        "gCO₂/kWh",
        f"Median {stats['median']:.0f}, {stats['n']:,} half-hours",
    )
with c2:
    kpi("Lowest half-hour", f"{stats['min']:.0f}", "gCO₂/kWh", fmt_local(stats["min_at"]))
with c3:
    kpi("Highest half-hour", f"{stats['max']:.0f}", "gCO₂/kWh", fmt_local(stats["max_at"]))
with c4:
    kpi(
        "Data completeness",
        f"{stats['n'] / expected * 100:.1f}",
        "%",
        f"{stats['n']:,} of {expected:,} expected half-hours have an actual",
    )

st.write("")
st.plotly_chart(charts.grid_strip(f), width="stretch", config={"displaylogo": False})

left, right = st.columns([3, 2])
with left:
    prof = profile(f, by="slot_of_day")
    prof["time"] = [f"{s // 2:02d}:{30 * (s % 2):02d}" for s in prof["slot_of_day"]]
    st.plotly_chart(
        charts.band_line(prof, "time", "Typical day: intensity by time of day", "Time of day (UK local)"),
        width="stretch",
    )
with right:
    cols = fuel_columns(f)
    if cols and f[cols].notna().any().any():
        means = f[cols].mean().rename(lambda c: c.removeprefix("share_")).dropna()
        st.plotly_chart(charts.mean_share_bars(means, "Average generation mix"), width="stretch")
    else:
        empty_state("No generation mix data", "The selected period has no generation records.")

st.subheader("What the selected period shows")
hourly = profile(f, by="hour")
best_h, worst_h = hourly.loc[hourly["mean"].idxmin()], hourly.loc[hourly["mean"].idxmax()]
insight(
    f"The cleanest hour of the day was on average <b>{int(best_h['hour']):02d}:00–{int(best_h['hour']) + 1:02d}:00</b> "
    f"at {best_h['mean']:.0f} gCO₂/kWh, {abs(best_h['mean'] - stats['mean']) / stats['mean'] * 100:.0f}% below the "
    f"period mean. The most carbon-intensive was {int(worst_h['hour']):02d}:00–{int(worst_h['hour']) + 1:02d}:00 at "
    f"{worst_h['mean']:.0f} gCO₂/kWh."
)
dt = day_type_comparison(f)
if dt["available"]:
    direction = "lower" if dt["hour_matched_diff"] < 0 else "higher"
    insight(
        f"Matched hour by hour, weekends averaged <b>{abs(dt['hour_matched_diff']):.0f} gCO₂/kWh {direction}</b> than "
        f"weekdays ({dt['weekend_days']} weekend days vs {dt['weekday_days']} weekdays). This is an association, "
        "not proof that the weekend itself causes the difference."
    )
corr = fuel_correlations(f)
corr = corr.loc[~corr["fuel"].isin(["zero_carbon", "fossil"])]
if len(corr) >= 2:
    lo, hi = corr.iloc[0], corr.iloc[-1]
    insight(
        f"Intensity moved most strongly against the <b>{lo['fuel']}</b> share (r = {lo['pearson_r']:.2f}) and "
        f"with the <b>{hi['fuel']}</b> share (r = {hi['pearson_r']:.2f}). Correlation, not causation; see "
        "Generation Mix for detail."
    )

csv_download(
    f.drop(columns=["local_date"]),
    "Download filtered dataset (CSV)",
    "gridgreen_filtered.csv",
    "gg_dl_overview",
)
footer()

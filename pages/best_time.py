import streamlit as st

from gridgreen.analytics import best_windows
from gridgreen.ui import charts
from gridgreen.ui.components import (
    csv_download,
    day_month_year,
    empty_state,
    fmt_local,
    footer,
    get_context,
    kpi,
    no_data_state,
    note,
    signed,
    topbar,
)

ctx = get_context()
topbar("Best Time to Use", ctx)
if ctx is None:
    no_data_state()
    footer()
    st.stop()

st.markdown(
    "Pick how long your flexible load runs, such as charging an EV or running a heat pump boost. "
    "GridGreen finds the historical windows in the selected period with the lowest average carbon intensity."
)
DUR = {"30 min": 30, "1 hour": 60, "2 hours": 120, "3 hours": 180, "4 hours": 240, "6 hours": 360}
c1, c2, c3 = st.columns([3, 2, 1])
dur_label = c1.segmented_control(
    "Load duration", list(DUR), default="2 hours", required=True, key="gg_bt_dur"
)
cov = c2.slider(
    "Minimum data coverage per window",
    50,
    100,
    100,
    step=5,
    format="%d%%",
    key="gg_bt_cov",
    help="Share of half-hours in a window that must have an estimated actual.",
)
top_n = c3.number_input("Windows listed", 3, 20, 5, key="gg_bt_top")

res = best_windows(ctx.frame, DUR[dur_label], min_coverage=cov / 100, top_n=int(top_n))
if not res.available:
    empty_state(
        "No valid windows",
        "The period is shorter than the load or too many half-hours are missing. "
        "Lower the coverage requirement or widen the period.",
    )
    footer()
    st.stop()

b = res.best
k = res.duration_minutes // 30
st.caption(
    "Historical analytical recommendation. It describes what already happened, not a forecast or a "
    "guarantee of future grid conditions."
)
a, bb, c, d = st.columns(4)
with a:
    kpi(
        "Cleanest window found",
        b["start_local"].strftime("%H:%M"),
        "",
        f"{b['start_local']:%a} {day_month_year(b['start_local'])} until {b['end_local']:%H:%M}",
    )
with bb:
    kpi("Mean intensity in window", f"{b['mean_intensity']:.0f}", "gCO₂/kWh")
with c:
    kpi("Compared with baseline", signed(res.pct_vs_baseline), "%", f"Baseline {res.baseline:.0f} gCO₂/kWh")
with d:
    kpi(
        "Valid half-hours",
        f"{int(b['n_valid'])} of {k}",
        "",
        f"{res.n_candidates:,} candidate windows; {res.n_rejected_incomplete:,} excluded for low coverage",
    )

typ = res.typical
best_t = typ.loc[typ["mean"].idxmin()]
st.plotly_chart(
    charts.typical_start_chart(typ, best_t["start_time"], res.baseline, res.duration_minutes / 60),
    width="stretch",
)
note(
    f"On a typical day in this period, starting at <b>{best_t['start_time']}</b> gave the lowest average "
    f"({best_t['mean']:.0f} gCO₂/kWh, {signed(best_t['pct_vs_baseline'])}% vs baseline, across {int(best_t['n']):,} days). "
    "This is a pattern to plan around, while the single best window above is a one-off historical event."
)

st.subheader("Lowest-intensity windows (non-overlapping)")
top = res.top.assign(
    start=lambda x: x["start_local"].map(fmt_local),
    end=lambda x: x["end_local"].dt.strftime("%H:%M"),
    vs_baseline=lambda x: (x["mean_intensity"] - res.baseline) / res.baseline * 100,
)
st.dataframe(
    top[["start", "end", "mean_intensity", "vs_baseline", "n_valid", "coverage"]],
    hide_index=True,
    column_config={
        "start": "Start (UK local)",
        "end": "End",
        "mean_intensity": st.column_config.NumberColumn("Mean (gCO₂/kWh)", format="%.0f"),
        "vs_baseline": st.column_config.NumberColumn("vs baseline", format="%+.1f%%"),
        "n_valid": "Valid half-hours",
        "coverage": st.column_config.ProgressColumn("Coverage", min_value=0, max_value=1, format="percent"),
    },
)
csv_download(
    res.top.drop(columns=["start_time"]), "Download windows (CSV)", "gridgreen_best_windows.csv", "gg_dl_bt"
)
st.plotly_chart(charts.candidate_windows_chart(res.candidates, res.top), width="stretch")

with st.expander("How this is calculated"):
    st.markdown(f"""
* Every half-hour in the period is placed on a complete UTC grid, so gaps are explicit and DST changes cannot
  create or remove time.
* A {dur_label} load spans **{k}** consecutive half-hours. Each half-hour lasts 30 minutes, so the
  duration-weighted average equals the simple mean of those {k} values.
* A window counts only if at least **{cov}%** of its half-hours have an estimated actual.
* **Baseline** = the mean over all valid windows, which is the expected intensity if the same load started at
  a random time in the period.
* The top list is chosen greedily so windows never overlap.
""")
footer()

import streamlit as st

from gridgreen.analytics import heatmap_matrix, monthly_summary, profile, resample_intensity
from gridgreen.ui import charts
from gridgreen.ui.components import csv_download, footer, get_context, no_data_state, note, topbar

ctx = get_context()
topbar("Carbon Trends", ctx)
if ctx is None:
    no_data_state()
    footer()
    st.stop()
f = ctx.frame
days = f["local_date"].nunique()

AGG = {"Half-hourly": "30min", "Hourly": "h", "Daily": "D", "Weekly": "W", "Monthly": "MS"}
c1, c2 = st.columns([3, 2])
agg = c1.segmented_control("Aggregation", list(AGG), default="Daily", required=True, key="gg_tr_agg")
stat = c2.segmented_control("Statistic", ["Mean", "Median"], default="Mean", required=True, key="gg_tr_stat")

series = resample_intensity(f, AGG[agg])
if series.empty:
    no_data_state()
    st.stop()
st.plotly_chart(
    charts.time_series(
        series, f"{agg} {stat.lower()} carbon intensity", stat.lower(), show_range=agg != "Half-hourly"
    ),
    width="stretch",
)
note("Shaded range shows the minimum and maximum half-hour within each period.")

st.subheader("Hour-of-day profile")
show_median = st.toggle("Show median alongside mean", value=True, key="gg_tr_median")
prof = profile(f, by="hour")
prof["label"] = [f"{h:02d}:00" for h in prof["hour"]]
st.plotly_chart(
    charts.band_line(
        prof, "label", "Intensity by hour of day", "Hour starting (UK local)", show_median=show_median
    ),
    width="stretch",
)
note(
    "Averages hide day-to-day swings: the band shows where 80% of half-hours fell for each hour. "
    "A clean average hour can still have dirty days when the wind drops."
)

st.subheader("Patterns by month, weekday and season")
rows = st.segmented_control(
    "Heatmap rows", ["Month", "Weekday", "Season"], default="Month", required=True, key="gg_tr_heat"
)
key = {"Month": "year_month", "Weekday": "weekday", "Season": "season"}[rows]
mat = heatmap_matrix(f, key)
st.plotly_chart(charts.heatmap(mat, f"Mean intensity by {rows.lower()} and hour", rows), width="stretch")

left, right = st.columns(2)
with left:
    st.plotly_chart(charts.season_box(f), width="stretch")
with right:
    st.plotly_chart(
        charts.histogram(
            f["actual"],
            "Distribution of half-hourly intensity",
            "Carbon intensity (gCO₂/kWh)",
            vline=f["actual"].mean(),
        ),
        width="stretch",
    )
if days < 365:
    st.info(
        f"This period covers {days} days, so some seasons may be missing or represented by a single year. "
        "Treat seasonal differences as descriptive, not as long-term trends."
    )
else:
    note(f"Period covers {days} days. Seasonal comparisons describe these specific years only.")

st.subheader("Monthly summary")
ms = monthly_summary(f)
st.dataframe(
    ms,
    hide_index=True,
    column_config={
        "year_month": "Month",
        "mean": st.column_config.NumberColumn("Mean (gCO₂/kWh)", format="%.0f"),
        "median": st.column_config.NumberColumn("Median", format="%.0f"),
        "min": st.column_config.NumberColumn("Min", format="%.0f"),
        "max": st.column_config.NumberColumn("Max", format="%.0f"),
        "n": st.column_config.NumberColumn("Half-hours", format="%d"),
        "days": st.column_config.NumberColumn("Days"),
        "zero_carbon_share": st.column_config.NumberColumn("Zero-carbon share (%)", format="%.1f"),
    },
)
csv_download(ms, "Download monthly summary (CSV)", "gridgreen_monthly_summary.csv", "gg_dl_monthly")
footer()

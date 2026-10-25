import pandas as pd
import streamlit as st

from gridgreen.config import LOCAL_TZ
from gridgreen.transform import detect_missing_intervals, slots_per_local_day
from gridgreen.ui import charts
from gridgreen.ui.banners import page_banner
from gridgreen.ui.components import (
    csv_download,
    empty_state,
    fmt_local,
    footer,
    get_context,
    kpi,
    no_data_state,
    note,
    plot,
    topbar,
)
from gridgreen.ui.theme import P

ctx = get_context()
topbar("Data Quality", ctx)
if ctx is None:
    no_data_state()
    footer()
    st.stop()
page_banner("quality")
ds = ctx.ds
runs = ds.runs

st.subheader("Pipeline runs")
if runs.empty:
    empty_state("No pipeline runs recorded", "Run scripts/run_pipeline.py to populate run metadata.")
else:
    latest = runs.iloc[0]
    ok = runs.loc[runs["status"] == "success"]
    a, b, c, d = st.columns(4)
    with a:
        kpi("Latest run status", str(latest["status"]).capitalize(), "", fmt_local(latest["started_at"]))
    with b:
        kpi("Last successful run", fmt_local(ok.iloc[0]["finished_at"]) if not ok.empty else "None", "")
    with c:
        kpi(
            "Latest run: intensity",
            f"{int(latest['intensity_accepted']):,}",
            "accepted",
            f"{int(latest['intensity_extracted']):,} extracted, {int(latest['intensity_rejected']):,} rejected, "
            f"{int(latest['intensity_new']):,} new",
        )
    with d:
        kpi(
            "Latest run: generation",
            f"{int(latest['generation_accepted']):,}",
            "accepted",
            f"{int(latest['generation_extracted']):,} extracted, {int(latest['generation_rejected']):,} rejected, "
            f"{int(latest['generation_new']):,} new fuel rows",
        )
    if latest["message"]:
        note(f"Run message: {latest['message']}")
    st.dataframe(
        runs[
            [
                "run_id",
                "status",
                "started_at",
                "range_start_utc",
                "range_end_utc",
                "api_requests",
                "chunk_failures",
                "intensity_extracted",
                "intensity_accepted",
                "intensity_rejected",
                "intensity_new",
                "generation_accepted",
                "generation_rejected",
                "duplicates_removed",
                "missing_intervals",
                "message",
            ]
        ].head(50),
        hide_index=True,
    )

st.subheader("Completeness in the selected period")
s = pd.Timestamp(ctx.start).tz_localize(LOCAL_TZ).to_pydatetime()
e = (pd.Timestamp(ctx.end) + pd.Timedelta(days=1)).tz_localize(LOCAL_TZ).to_pydatetime()
f = ctx.frame
missing_actual = detect_missing_intervals(f, s, e, column="actual")
missing_gen = int(f["fuels_reported"].isna().sum()) if "fuels_reported" in f else len(f)
expected = slots_per_local_day(s, e)
present = f.dropna(subset=["actual"]).groupby("local_date").size()
daily = pd.DataFrame({"expected": expected, "present": present}).fillna(0)
daily["pct"] = daily["present"] / daily["expected"] * 100
a, b, c = st.columns(3)
with a:
    kpi(
        "Half-hours without an actual", f"{len(missing_actual):,}", "", f"of {int(expected.sum()):,} expected"
    )
with b:
    kpi("Half-hours without generation mix", f"{missing_gen:,}", "")
with c:
    kpi(
        "Duplicates removed (all runs)",
        f"{int(runs['duplicates_removed'].sum()) if not runs.empty else 0:,}",
        "",
    )
fig = charts.bar(
    daily.reset_index(names="date"),
    "date",
    "pct",
    "Daily completeness of estimated actuals",
    "Date (UK local)",
    "Half-hours with an actual (%)",
    hover_suffix="%",
)
fig.update_yaxes(range=[0, 105])
plot(fig, width="stretch", theme=None)
note("Expected half-hours per day follow the UK clock: 46 on the March change, 50 in October, 48 otherwise.")
if len(missing_actual):
    miss = pd.DataFrame({"interval_start_utc": missing_actual})
    miss["interval_start_local"] = miss["interval_start_utc"].dt.tz_convert(LOCAL_TZ)
    with st.expander(f"List missing half-hours ({len(miss):,})"):
        st.dataframe(miss, hide_index=True)
        csv_download(
            miss, "Download missing intervals (CSV)", "gridgreen_missing_intervals.csv", "gg_dl_miss"
        )

st.subheader("Rejected records")
rej = ds.rejected
if rej.empty:
    note("No records have been rejected by validation.")
else:
    reasons = rej.groupby(["dataset", "reason"]).size().reset_index(name="records").sort_values("records")
    reasons["label"] = reasons["dataset"] + ": " + reasons["reason"]
    plot(
        charts.bar(
            reasons,
            "records",
            "label",
            "Rejection reasons (distinct payloads, all runs)",
            "Records",
            "",
            color=P.ERROR,
        ).update_traces(
            orientation="h",
            x=reasons["records"],
            y=reasons["label"],
            hovertemplate="%{y}<br>%{x}<extra></extra>",
        ),
        width="stretch",
        theme=None,
    )
    st.dataframe(
        rej[
            [
                "dataset",
                "interval_start_utc",
                "reason",
                "times_seen",
                "first_run_id",
                "source_url",
                "raw_payload",
                "error_details",
            ]
        ],
        hide_index=True,
    )
    csv_download(rej, "Download rejected records (CSV)", "gridgreen_rejected.csv", "gg_dl_rej")

st.subheader("Stored data")
st.dataframe(pd.DataFrame(ds.counts.items(), columns=["Table", "Rows"]), hide_index=True)
lo, hi = ds.frame["interval_start_utc"].min(), ds.frame["interval_start_utc"].max()
note(
    f"Coverage: {fmt_local(lo)} to {fmt_local(hi)} (UK local half-hour starts). Source tag: "
    f"<code>{ds.source}</code>."
)
footer()

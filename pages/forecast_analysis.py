import pandas as pd
import streamlit as st

from gridgreen.forecasting import (
    HORIZON_LABELS,
    align_snapshots,
    compute_metrics,
    horizon_metrics,
    metrics_by,
    published_forecast_pairs,
)
from gridgreen.ui import charts
from gridgreen.ui.components import empty_state, footer, get_context, kpi, no_data_state, note, signed, topbar
from gridgreen.ui.theme import ERROR

ctx = get_context()
topbar("Forecast Analysis", ctx)
if ctx is None:
    no_data_state()
    footer()
    st.stop()

st.markdown(
    "How close was NESO's published forecast to the later estimated actual? Error is defined as "
    "**forecast minus actual**, so a positive bias means intensity was over-forecast."
)
pairs = published_forecast_pairs(ctx.frame)
m = compute_metrics(pairs["forecast"], pairs["actual"]) if not pairs.empty else None
if m is None:
    empty_state(
        "No forecast and actual pairs in this period",
        "Each half-hour needs both a published forecast and an estimated actual.",
    )
else:
    a, b, c, d = st.columns(4)
    with a:
        kpi("Mean absolute error", f"{m.mae:.1f}", "gCO₂/kWh")
    with b:
        kpi("Root mean squared error", f"{m.rmse:.1f}", "gCO₂/kWh", "Penalises large misses more")
    with c:
        kpi("Bias (mean error)", signed(m.bias, 1), "gCO₂/kWh", "Positive = over-forecast")
    with d:
        kpi(
            "Paired half-hours",
            f"{m.n:,}",
            "",
            f"{m.n / max(ctx.frame['actual'].notna().sum(), 1) * 100:.0f}% of actuals",
        )
    left, right = st.columns(2)
    with left:
        st.plotly_chart(charts.forecast_scatter(pairs), width="stretch")
    with right:
        st.plotly_chart(
            charts.histogram(
                pairs["error"],
                "Distribution of forecast errors",
                "Forecast − actual (gCO₂/kWh)",
                color=ERROR,
                vline=0,
            ),
            width="stretch",
        )
    by_hour = metrics_by(pairs, "hour")
    metric = st.segmented_control(
        "Error by hour of day", ["MAE", "Bias"], default="MAE", required=True, key="gg_fc_metric"
    )
    col = {"MAE": "mae", "Bias": "bias"}[metric]
    st.plotly_chart(
        charts.bar(
            by_hour,
            "hour",
            col,
            f"{metric} by hour of day",
            "Hour starting (UK local)",
            f"{metric} (gCO₂/kWh)",
            hover_suffix=" gCO₂/kWh",
        ),
        width="stretch",
    )
    note(
        "Limitation: the historical endpoint returns only the final forecast for each half-hour, without the time "
        "it was issued, so these figures describe short-range accuracy and cannot be split by lead time. "
        "'Actual' is itself a NESO estimate."
    )

st.subheader("Accuracy by forecast horizon")
snaps = ctx.ds.snapshots
aligned = align_snapshots(snaps, ctx.ds.frame) if not snaps.empty else pd.DataFrame()
if not aligned.empty:
    s, e = pd.Timestamp(ctx.start), pd.Timestamp(ctx.end) + pd.Timedelta(days=1)
    local = aligned["interval_start_utc"].dt.tz_convert("Europe/London").dt.tz_localize(None)
    aligned = aligned.loc[(local >= s) & (local < e)]
if aligned.empty:
    n_runs = snaps["run_id"].nunique() if not snaps.empty else 0
    empty_state(
        "Horizon analysis is not available yet",
        "The API has no archive of past forecasts with their issue times. GridGreen therefore stores the "
        f"48-hour forecast each time the pipeline runs. So far it holds {n_runs} snapshot(s) with "
        f"{len(snaps):,} forecast rows, and none can be matched to a published actual in this period. "
        "Schedule the pipeline regularly (for example every few hours) and this section will populate. "
        "No values are invented to fill it.",
    )
else:
    horizons = st.pills(
        "Horizons", HORIZON_LABELS, selection_mode="multi", default=HORIZON_LABELS, key="gg_fc_h"
    )
    hm = horizon_metrics(aligned)
    hm = hm.loc[hm["horizon_bucket"].astype(str).isin(horizons or [])]
    st.dataframe(hm, hide_index=True)
    st.plotly_chart(
        charts.bar(
            hm.assign(h=hm["horizon_bucket"].astype(str)),
            "h",
            "mae",
            "MAE by forecast horizon",
            "Lead time",
            "MAE (gCO₂/kWh)",
        ),
        width="stretch",
    )
footer()

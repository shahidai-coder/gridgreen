import numpy as np
import pandas as pd
import streamlit as st

from gridgreen.analytics import fuel_correlations, generation_share_series
from gridgreen.config import FOSSIL_FUELS, ZERO_CARBON_FUELS
from gridgreen.transform import fuel_columns
from gridgreen.ui import charts
from gridgreen.ui.banners import page_banner
from gridgreen.ui.components import (
    csv_download,
    empty_state,
    footer,
    get_context,
    no_data_state,
    note,
    plot,
    topbar,
)

ctx = get_context()
topbar("Generation Mix", ctx)
if ctx is None:
    no_data_state()
    footer()
    st.stop()
page_banner("mix")
f = ctx.frame
cols = fuel_columns(f)
with_gen = f.dropna(subset=["fuels_reported"]) if "fuels_reported" in f else f.iloc[0:0]
if not cols or with_gen.empty:
    empty_state(
        "No generation mix data in this period", "Run the pipeline for this period or widen the dates."
    )
    footer()
    st.stop()

fuels = [c.removeprefix("share_") for c in cols]
note(
    "The API reports each fuel as a <b>percentage share</b> of generation, not in MW, so GridGreen analyses "
    "shares directly and never infers absolute output."
)

c1, c2 = st.columns([3, 1])
selected = c1.pills("Fuels shown", fuels, selection_mode="multi", default=fuels, key="gg_gm_fuels")
res = c2.segmented_control(
    "Resolution", ["Daily", "Weekly", "Monthly"], default="Daily", required=True, key="gg_gm_res"
)
if not selected:
    st.warning("Select at least one fuel.")
    st.stop()
shares = generation_share_series(f, {"Daily": "D", "Weekly": "W", "Monthly": "MS"}[res])
plot(charts.stacked_shares(shares[selected], f"{res} mean generation shares"), width="stretch", theme=None)
if len(selected) < len(fuels):
    note("Some fuels are hidden, so the stack no longer reaches 100%. Shares are not re-normalised.")

left, right = st.columns([2, 3])
with left:
    plot(
        charts.mean_share_bars(
            f[[f"share_{x}" for x in selected]].mean().rename(lambda c: c.removeprefix("share_")),
            "Average share in period",
        ),
        width="stretch",
        theme=None,
    )
with right:
    fuel = st.selectbox(
        "Compare a fuel with intensity",
        selected,
        index=selected.index("wind") if "wind" in selected else 0,
        key="gg_gm_scatter",
    )
    plot(charts.share_scatter(f, f"share_{fuel}"), width="stretch", theme=None)

st.subheader("Which sources move with intensity?")
corr = fuel_correlations(f)
lc, rc = st.columns([3, 2])
with lc:
    plot(charts.correlation_bars(corr), width="stretch", theme=None)
with rc:
    st.dataframe(
        corr,
        hide_index=True,
        column_config={
            "fuel": "Fuel or group",
            "pearson_r": st.column_config.NumberColumn("Pearson r", format="%.2f"),
            "spearman_rho": st.column_config.NumberColumn("Spearman ρ", format="%.2f"),
            "mean_share": st.column_config.NumberColumn("Mean share (%)", format="%.1f"),
            "n": "Half-hours",
        },
    )
    note(
        f"Zero-carbon group: {', '.join(ZERO_CARBON_FUELS)}. Fossil group: {', '.join(FOSSIL_FUELS)} "
        "(where reported). Biomass and imports are kept separate because their emissions are non-zero "
        "or unknown."
    )
st.markdown(
    "Shares are compositional: when one fuel's share rises, others must fall. A negative correlation for "
    "wind therefore partly reflects gas being displaced. These are associations in historical data, "
    "not causal estimates."
)

st.subheader("Intensity against zero-carbon share")
d = f.dropna(subset=["share_zero_carbon", "actual"])
if not d.empty:
    bins = np.arange(0, 101, 10)
    d = d.assign(bin=pd.cut(d["share_zero_carbon"], bins=bins, right=False, include_lowest=True))
    g = d.groupby("bin", observed=True)["actual"].agg(["mean", "count"]).reset_index()
    g["label"] = [f"{int(b.left)}–{int(b.right)}%" for b in g["bin"]]
    fig = charts.bar(
        g,
        "label",
        "mean",
        "Mean intensity by zero-carbon share band",
        "Zero-carbon share of generation",
        "Mean carbon intensity (gCO₂/kWh)",
        hover_suffix=" gCO₂/kWh",
    )
    fig.update_traces(
        customdata=g["count"],
        hovertemplate="%{x}<br>%{y:.0f} gCO₂/kWh<br>%{customdata:,} half-hours<extra></extra>",
    )
    plot(fig, width="stretch", theme=None)

st.subheader("Coverage")
missing_gen = int(f["fuels_reported"].isna().sum())
counts = with_gen["fuels_reported"].value_counts().sort_index()
note(
    f"{len(with_gen):,} half-hours have a generation mix; {missing_gen:,} intensity half-hours have none "
    "(left as missing, never imputed). Fuels reported per half-hour: "
    + ", ".join(f"{int(k)} fuels in {v:,} half-hours" for k, v in counts.items())
    + "."
)
csv_download(shares.reset_index(), "Download shares (CSV)", "gridgreen_generation_shares.csv", "gg_dl_gen")
footer()

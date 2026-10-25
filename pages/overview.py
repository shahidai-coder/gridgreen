import streamlit as st

from gridgreen.ui.components import csv_download, footer, get_context, no_data_state, topbar
from gridgreen.ui.pulse import build_payload, grid_pulse

ctx = get_context()
topbar("Overview", ctx)
if ctx is None:
    no_data_state()
    footer()
    st.stop()

grid_pulse(build_payload(ctx.frame, ctx.ds.frame, ctx.ds.runs, ctx.ds.is_demo))
csv_download(
    ctx.frame.drop(columns=["local_date"]),
    "Download filtered dataset (CSV)",
    "gridgreen_filtered.csv",
    "gg_dl_overview",
)
footer()

import streamlit as st

from gridgreen.ui.components import csv_download, footer, get_context, no_data_state, topbar
from gridgreen.ui.pulse import build_payload, grid_pulse, nav_target

ctx = get_context()
topbar("Overview", ctx, show_title=False)  # the Overview draws its own title inside the component
if ctx is None:
    no_data_state()
    footer()
    st.stop()

clicked = grid_pulse(build_payload(ctx.frame, ctx.ds.frame, ctx.ds.runs, ctx.ds.is_demo))
target = nav_target(clicked, st.session_state.get("pulse_nav_t"))
if target:
    st.session_state["pulse_nav_t"] = clicked["t"]
    st.switch_page(target)
csv_download(
    ctx.frame.drop(columns=["local_date"]),
    "Download filtered dataset (CSV)",
    "gridgreen_filtered.csv",
    "gg_dl_overview",
)
footer()

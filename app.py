"""GridGreen Streamlit entry point: page setup, sidebar filters and navigation."""

from __future__ import annotations

import sys
from pathlib import Path

# Make `src/` importable when the package is not pip-installed (e.g. Streamlit Cloud).
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

import streamlit as st

from gridgreen.ui.components import load_dataset, setup_page, sidebar

setup_page()
pages = [
    st.Page("pages/overview.py", title="Overview", icon=":material/space_dashboard:", default=True),
    st.Page("pages/carbon_trends.py", title="Carbon Trends", icon=":material/show_chart:"),
    st.Page("pages/generation_mix.py", title="Generation Mix", icon=":material/stacked_bar_chart:"),
    st.Page("pages/best_time.py", title="Best Time to Use", icon=":material/schedule:"),
    st.Page("pages/forecast_analysis.py", title="Forecast Analysis", icon=":material/insights:"),
    st.Page("pages/data_quality.py", title="Data Quality", icon=":material/fact_check:"),
    st.Page("pages/methodology.py", title="Methodology", icon=":material/menu_book:"),
]
nav = st.navigation(pages)
sidebar(load_dataset())
nav.run()

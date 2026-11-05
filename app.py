"""GridGreen Streamlit entry point: page setup, top navigation and the filter bar."""

from __future__ import annotations

import sys
from pathlib import Path

# Make `src/` importable when the package is not pip-installed (e.g. Streamlit Cloud).
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

import streamlit as st

from gridgreen.ui.components import load_dataset, setup_page, toolbar

setup_page()
pages = [
    st.Page("views/overview.py", title="Overview", icon=":material/space_dashboard:", default=True),
    st.Page("views/carbon_trends.py", title="Carbon Trends", icon=":material/show_chart:"),
    st.Page("views/generation_mix.py", title="Generation Mix", icon=":material/stacked_bar_chart:"),
    st.Page("views/best_time.py", title="Best Time to Use", icon=":material/schedule:"),
    st.Page("views/forecast_analysis.py", title="Forecast Analysis", icon=":material/insights:"),
    st.Page("views/data_quality.py", title="Data Quality", icon=":material/fact_check:"),
    st.Page("views/methodology.py", title="Methodology", icon=":material/menu_book:"),
]
nav = st.navigation(pages, position="top")  # page links in the header, no sidebar
toolbar(load_dataset())
nav.run()

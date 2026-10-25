"""Headless render of every dashboard page with Streamlit's AppTest.

Uses a small SYNTHETIC database so the test runs offline. It checks that each
page renders without exceptions, that the demo banner appears, and that the
empty-database state is handled.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from gridgreen.config import DATA_SOURCE_DEMO
from gridgreen.demo import SyntheticClient
from gridgreen.pipeline import run_pipeline

ROOT = Path(__file__).resolve().parents[1]
PAGES = [
    "pages/overview.py",
    "pages/carbon_trends.py",
    "pages/generation_mix.py",
    "pages/best_time.py",
    "pages/forecast_analysis.py",
    "pages/data_quality.py",
    "pages/methodology.py",
]


@pytest.fixture(scope="module")
def demo_db(tmp_path_factory) -> Path:
    db = tmp_path_factory.mktemp("dash") / "demo.duckdb"
    s, e = datetime(2026, 3, 1, tzinfo=UTC), datetime(2026, 4, 15, tzinfo=UTC)
    run_pipeline(
        db_path=db,
        client=SyntheticClient(s, e),
        start=s,
        end=e,
        source=DATA_SOURCE_DEMO,
        snapshot_forecast=False,
        now=e,
    )
    return db


def _app(monkeypatch, db: Path) -> AppTest:
    monkeypatch.setenv("GRIDGREEN_DB_PATH", str(db))
    monkeypatch.chdir(ROOT)
    return AppTest.from_file(str(ROOT / "app.py"), default_timeout=60)


@pytest.mark.parametrize("page", PAGES)
def test_every_page_renders_without_exceptions(monkeypatch, demo_db, page):
    at = _app(monkeypatch, demo_db).run()
    at.switch_page(page).run()
    assert not at.exception, [e.value for e in at.exception]
    html = " ".join(m.value for m in at.markdown)
    if page != "pages/methodology.py":
        assert "synthetic data" in html  # demo banner is always shown on demo data


def test_filters_change_results(monkeypatch, demo_db):
    at = _app(monkeypatch, demo_db).run()
    at.switch_page("pages/best_time.py").run()
    before = " ".join(m.value for m in at.markdown)
    at.segmented_control(key="gg_bt_dur").set_value("6 hours").run()
    assert not at.exception
    after = " ".join(m.value for m in at.markdown)
    assert before != after and "6-hour load" not in before


def test_date_filter_narrows_period(monkeypatch, demo_db):
    import datetime as dt

    at = _app(monkeypatch, demo_db).run()
    at.date_input(key="gg_range").set_value((dt.date(2026, 3, 10), dt.date(2026, 3, 12))).run()
    assert not at.exception
    assert any("10 Mar 2026 to 12 Mar 2026" in m.value for m in at.markdown)


def test_reset_button_clears_filters(monkeypatch, demo_db):
    # AppTest only exposes sidebar widgets on the first run when st.navigation is used
    # (verified separately in a real browser), so the filter is pre-set in session state.
    import datetime as dt

    at = _app(monkeypatch, demo_db)
    at.session_state["gg_range"] = (dt.date(2026, 3, 10), dt.date(2026, 3, 12))
    at.run()
    assert any("10 Mar 2026 to 12 Mar 2026" in m.value for m in at.markdown)
    reset = next(b for b in at.sidebar.button if b.label == "Reset all filters")
    reset.click().run()
    assert not at.exception
    assert not any("10 Mar 2026 to 12 Mar 2026" in m.value for m in at.markdown)


def test_missing_database_shows_empty_state(monkeypatch, tmp_path):
    at = _app(monkeypatch, tmp_path / "does_not_exist.duckdb").run()
    assert not at.exception
    assert any("No data loaded yet" in m.value for m in at.markdown)

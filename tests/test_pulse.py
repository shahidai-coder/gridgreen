"""The Grid Pulse payload must be complete, consistent and JSON-safe (JSON has no NaN)."""

import json
import math
from datetime import UTC, datetime

import pandas as pd

from gridgreen import database
from gridgreen.config import DATA_SOURCE_DEMO
from gridgreen.demo import SyntheticClient
from gridgreen.pipeline import run_pipeline
from gridgreen.transform import build_analytical_frame
from gridgreen.ui.pulse import build_payload


def _payload(tmp_path):
    s, e = datetime(2026, 3, 20, tzinfo=UTC), datetime(2026, 4, 10, tzinfo=UTC)
    db = tmp_path / "p.duckdb"
    run_pipeline(
        db_path=db,
        client=SyntheticClient(s, e),
        start=s,
        end=e,
        source=DATA_SOURCE_DEMO,
        snapshot_forecast=False,
        now=e,
    )
    con = database.connect(db, read_only=True)
    frame = build_analytical_frame(database.read_intensity(con), database.read_generation(con))
    runs = database.read_runs(con)
    con.close()
    return frame, build_payload(frame, frame, runs, is_demo=True)


def _walk(x):
    if isinstance(x, dict):
        for v in x.values():
            yield from _walk(v)
    elif isinstance(x, list):
        for v in x:
            yield from _walk(v)
    else:
        yield x


def test_payload_is_json_safe_and_complete(tmp_path):
    frame, p = _payload(tmp_path)
    json.dumps(p, allow_nan=False)  # raises on NaN / inf
    assert not any(isinstance(v, float) and (math.isnan(v) or math.isinf(v)) for v in _walk(p))
    assert p["empty"] is False and p["demo"] is True
    n_days = frame["local_date"].nunique()
    assert len(p["daily"]["dates"]) == n_days == len(p["days"])
    assert all(len(v) == 48 for v in p["clocks"].values())
    assert all(len(d["slots"]) == 48 for d in p["days"].values())
    assert p["best_day"] in p["days"]


def test_payload_numbers_match_analytics(tmp_path):
    frame, p = _payload(tmp_path)
    a = frame.dropna(subset=["actual"])
    assert p["kpi"]["mean"] == round(a["actual"].mean())
    assert p["kpi"]["min"] == a["actual"].min() and p["kpi"]["max"] == a["actual"].max()
    day = p["daily"]["dates"][5]
    expected = a.loc[a["local_date"].astype(str) == day, "actual"].mean()
    assert abs(p["daily"]["mean"][5] - expected) < 0.06


def test_best_2h_window_is_correct_for_a_day(tmp_path):
    _, p = _payload(tmp_path)
    day = p["daily"]["dates"][3]
    slots = p["days"][day]["slots"]
    windows = [sum(slots[i : i + 4]) / 4 for i in range(45) if None not in slots[i : i + 4]]
    best = p["days"][day]["best2h"]
    assert abs(sum(slots[best : best + 4]) / 4 - min(windows)) < 1  # slots are rounded to whole grams


def test_sankey_flows_balance(tmp_path):
    _, p = _payload(tmp_path)
    links = pd.DataFrame(p["sankey"]["links"])
    out_fetched = links.loc[links["source"] == "Fetched from API", "value"].sum()
    out_loaded = links.loc[links["source"] == "Loaded to DuckDB", "value"].sum()
    into_loaded = links.loc[links["target"] == "Loaded to DuckDB", "value"].sum()
    assert out_loaded == into_loaded and out_fetched >= into_loaded
    assert (links["value"] > 0).all()


def test_empty_period_payload():
    from gridgreen.transform import generation_to_frame, intensity_to_frame

    empty = build_analytical_frame(intensity_to_frame([]), generation_to_frame([]))
    assert build_payload(empty, empty, pd.DataFrame(), False) == {"empty": True}


def test_completeness_matches_whole_day_definition(tmp_path):
    from gridgreen.transform import expected_slots

    frame, p = _payload(tmp_path)
    s = pd.Timestamp(frame["local_date"].min()).tz_localize("Europe/London")
    e = (pd.Timestamp(frame["local_date"].max()) + pd.Timedelta(days=1)).tz_localize("Europe/London")
    expected = len(expected_slots(s.to_pydatetime(), e.to_pydatetime()))
    assert p["kpi"]["expected"] == expected
    assert p["kpi"]["completeness"] == round(frame["actual"].notna().sum() / expected * 100, 1)


def test_day_cycle_has_both_scene_palettes_and_a_full_clock(tmp_path):
    _, p = _payload(tmp_path)
    day, night = p["theme"]["sceneDay"], p["theme"]["sceneNight"]
    assert set(day) == set(night) and {"sky_top", "sun", "window", "cloud"} <= set(day)
    assert len(p["clocks"]["All days"]) == 48  # the illustration cycles through every half-hour

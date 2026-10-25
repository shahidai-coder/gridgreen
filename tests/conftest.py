"""Shared deterministic fixtures. All data here is hand-written TEST DATA."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pandas as pd
import pytest

from gridgreen.transform import build_analytical_frame


def slot(y, m, d, h, mi=0) -> datetime:
    return datetime(y, m, d, h, mi, tzinfo=UTC)


def iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%MZ")


def intensity_payload(start: datetime, actual=200, forecast=210, index="moderate") -> dict:
    return {
        "from": iso(start),
        "to": iso(start + timedelta(minutes=30)),
        "intensity": {"forecast": forecast, "actual": actual, "index": index},
    }


MIX = {
    "gas": 40.0,
    "wind": 30.0,
    "nuclear": 15.0,
    "solar": 5.0,
    "imports": 5.0,
    "biomass": 3.0,
    "hydro": 1.5,
    "coal": 0.0,
    "other": 0.5,
}


def generation_payload(start: datetime, mix: dict[str, float] | None = None) -> dict:
    mix = MIX if mix is None else mix
    return {
        "from": iso(start),
        "to": iso(start + timedelta(minutes=30)),
        "generationmix": [{"fuel": f, "perc": p} for f, p in mix.items()],
    }


@pytest.fixture
def frame_from_values():
    """Build an analytical frame from {utc_start: actual} test values."""

    def _make(values: dict[datetime, float | None], forecast_offset: float = 0.0) -> pd.DataFrame:
        starts = sorted(values)
        df = pd.DataFrame(
            {
                "interval_start_utc": pd.to_datetime(starts, utc=True),
                "interval_end_utc": pd.to_datetime([s + timedelta(minutes=30) for s in starts], utc=True),
                "forecast": pd.array(
                    [None if values[s] is None else values[s] + forecast_offset for s in starts],
                    dtype="Float64",
                ),
                "actual": pd.array([values[s] for s in starts], dtype="Float64"),
                "intensity_index": pd.array(["moderate"] * len(starts), dtype="string"),
            }
        )
        return build_analytical_frame(df, pd.DataFrame(columns=["interval_start_utc", "fuel", "perc"]))

    return _make

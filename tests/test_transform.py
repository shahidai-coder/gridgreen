from datetime import UTC, datetime, timedelta

import pandas as pd
from conftest import MIX, generation_payload, intensity_payload, slot

from gridgreen.schemas import GenerationRecord, IntensityRecord
from gridgreen.transform import (
    add_time_features,
    build_analytical_frame,
    dedupe_intensity,
    detect_missing_intervals,
    filter_range,
    generation_to_frame,
    intensity_to_frame,
    season_of,
    slots_per_local_day,
)


def _intensity(rows):
    return intensity_to_frame([IntensityRecord.model_validate(r) for r in rows])


def test_spring_forward_day_has_46_slots_and_autumn_day_50():
    counts = slots_per_local_day(datetime(2026, 3, 28, tzinfo=UTC), datetime(2026, 3, 31, tzinfo=UTC))
    assert counts[pd.Timestamp("2026-03-29").date()] == 46
    # 23:00 UTC on 23 Oct is 00:00 BST on 24 Oct, so the 24th is a complete local day.
    counts = slots_per_local_day(datetime(2026, 10, 23, 23, tzinfo=UTC), datetime(2026, 10, 27, tzinfo=UTC))
    assert counts[pd.Timestamp("2026-10-25").date()] == 50
    assert counts[pd.Timestamp("2026-10-24").date()] == 48


def test_utc_to_uk_local_conversion_across_dst():
    df = pd.DataFrame(
        {
            "interval_start_utc": pd.to_datetime(
                ["2026-01-15T12:00Z", "2026-07-15T12:00Z", "2026-03-29T00:30Z", "2026-03-29T01:00Z"], utc=True
            )
        }
    )
    out = add_time_features(df)
    assert out["hour"].tolist() == [12, 13, 0, 2]  # 01:00 local never exists on 29 March
    assert out["utc_offset_hours"].tolist() == [0.0, 1.0, 0.0, 1.0]


def test_autumn_repeated_local_hour_keeps_distinct_utc_keys():
    starts = pd.date_range("2026-10-25T00:00Z", periods=4, freq="30min", tz="UTC")
    out = add_time_features(pd.DataFrame({"interval_start_utc": starts}))
    assert out["time_label"].tolist() == ["01:00", "01:30", "01:00", "01:30"]
    assert out["interval_start_utc"].is_unique


def test_weekend_month_and_season_features():
    out = add_time_features(
        pd.DataFrame(
            {
                "interval_start_utc": pd.to_datetime(
                    ["2026-10-24T12:00Z", "2026-10-26T12:00Z", "2026-12-01T12:00Z"], utc=True
                )
            }
        )
    )
    assert out["is_weekend"].tolist() == [True, False, False]
    assert out["season"].astype(str).tolist() == ["Autumn", "Autumn", "Winter"]
    assert [season_of(m) for m in (2, 3, 6, 9)] == ["Winter", "Spring", "Summer", "Autumn"]


def test_dedupe_prefers_row_with_actual_and_is_deterministic():
    t = slot(2026, 1, 1, 0)
    df = _intensity(
        [
            intensity_payload(t, actual=None, forecast=100),
            intensity_payload(t, actual=150, forecast=100),
            intensity_payload(t + timedelta(minutes=30)),
        ]
    )
    out, removed = dedupe_intensity(df)
    assert removed == 1 and len(out) == 2
    assert out.loc[out["interval_start_utc"] == pd.Timestamp(t), "actual"].item() == 150
    out2, _ = dedupe_intensity(df.iloc[::-1])
    pd.testing.assert_frame_equal(out, out2)


def test_missing_interval_detection_and_null_actuals():
    t = slot(2026, 1, 1, 0)
    df = _intensity([intensity_payload(t), intensity_payload(t + timedelta(hours=1), actual=None)])
    end = t + timedelta(hours=2)
    assert len(detect_missing_intervals(df, t, end)) == 2
    assert len(detect_missing_intervals(df, t, end, column="actual")) == 3


def test_filter_range_is_half_open():
    t = slot(2026, 1, 1, 0)
    df = _intensity([intensity_payload(t + timedelta(minutes=30 * i)) for i in range(4)])
    assert len(filter_range(df, t, t + timedelta(hours=1))) == 2


def test_join_is_by_utc_slot_and_derives_group_shares():
    t = slot(2026, 1, 1, 0)
    inten = _intensity(
        [
            intensity_payload(t, actual=180, forecast=200),
            intensity_payload(t + timedelta(minutes=30), actual=170),
        ]
    )
    gen = generation_to_frame([GenerationRecord.model_validate(generation_payload(t))])
    out = build_analytical_frame(inten, gen)
    assert len(out) == 2  # left join keeps intensity spine
    first = out.iloc[0]
    assert first["share_wind"] == MIX["wind"]
    assert first["share_zero_carbon"] == MIX["wind"] + MIX["nuclear"] + MIX["solar"] + MIX["hydro"]
    assert first["share_fossil"] == MIX["gas"] + MIX["coal"]
    assert first["forecast_error"] == 20  # forecast - actual
    assert pd.isna(out.iloc[1]["share_wind"])  # not imputed


def test_empty_inputs_produce_empty_frame():
    empty_i = intensity_to_frame([])
    out = build_analytical_frame(empty_i, generation_to_frame([]))
    assert out.empty and "hour" in out.columns

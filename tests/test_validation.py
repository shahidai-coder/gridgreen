from datetime import timedelta

import pytest
from conftest import generation_payload, intensity_payload, slot
from pydantic import ValidationError

from gridgreen.schemas import GenerationRecord, IntensityRecord
from gridgreen.validate import summarize_rejections, validate_records

T0 = slot(2026, 1, 10, 12)


def test_valid_intensity_record_is_utc_and_normalised():
    r = IntensityRecord.model_validate(intensity_payload(T0, index="Moderate"))
    assert r.interval_start == T0 and r.interval_start.utcoffset() == timedelta(0)
    assert r.intensity.index == "moderate"


def test_offset_timestamps_are_converted_to_utc():
    p = intensity_payload(T0)
    p["from"], p["to"] = "2026-07-10T13:00+01:00", "2026-07-10T13:30+01:00"
    assert IntensityRecord.model_validate(p).interval_start.hour == 12


@pytest.mark.parametrize("field,value", [("actual", 1001), ("actual", -1), ("forecast", 5000)])
def test_intensity_outside_plausible_range_rejected(field, value):
    p = intensity_payload(T0)
    p["intensity"][field] = value
    with pytest.raises(ValidationError):
        IntensityRecord.model_validate(p)


@pytest.mark.parametrize("value", [0, 1000])
def test_range_bounds_are_inclusive(value):
    p = intensity_payload(T0, actual=value)
    assert IntensityRecord.model_validate(p).intensity.actual == value


def test_misaligned_and_wrong_length_intervals_rejected():
    p = intensity_payload(T0)
    p["from"] = "2026-01-10T12:10Z"
    with pytest.raises(ValidationError, match="not aligned"):
        IntensityRecord.model_validate(p)
    p = intensity_payload(T0)
    p["to"] = "2026-01-10T13:30Z"
    with pytest.raises(ValidationError, match="not 30 minutes"):
        IntensityRecord.model_validate(p)


def test_naive_timestamp_rejected():
    p = intensity_payload(T0)
    p["from"], p["to"] = "2026-01-10T12:00", "2026-01-10T12:30"
    with pytest.raises(ValidationError):
        IntensityRecord.model_validate(p)


@pytest.mark.parametrize("drop", ["from", "to", "intensity"])
def test_missing_required_fields_rejected(drop):
    p = intensity_payload(T0)
    del p[drop]
    with pytest.raises(ValidationError):
        IntensityRecord.model_validate(p)


def test_record_without_any_value_rejected_but_forecast_only_accepted():
    with pytest.raises(ValidationError, match="neither"):
        IntensityRecord.model_validate(intensity_payload(T0, actual=None, forecast=None))
    assert IntensityRecord.model_validate(intensity_payload(T0, actual=None)).intensity.actual is None


def test_generation_shares_within_tolerance_accepted():
    mix = {"gas": 50.4, "wind": 50.4}  # 100.8 -> within 1 pp
    assert len(GenerationRecord.model_validate(generation_payload(T0, mix)).generationmix) == 2


@pytest.mark.parametrize("mix", [{"gas": 50.0, "wind": 48.5}, {"gas": 60.0, "wind": 41.5}])
def test_generation_shares_outside_tolerance_rejected(mix):
    with pytest.raises(ValidationError, match="do not sum"):
        GenerationRecord.model_validate(generation_payload(T0, mix))


def test_generation_negative_and_duplicate_fuels_rejected():
    with pytest.raises(ValidationError):
        GenerationRecord.model_validate(generation_payload(T0, {"gas": -1.0, "wind": 101.0}))
    p = generation_payload(T0, {"gas": 50.0})
    p["generationmix"].append({"fuel": " GAS ", "perc": 50.0})
    with pytest.raises(ValidationError, match="duplicate"):
        GenerationRecord.model_validate(p)


def test_unexpected_fuel_is_kept_and_canonicalised():
    p = generation_payload(T0, {"gas": 60.0, "Pumped Storage": 40.0})
    fuels = {f.fuel for f in GenerationRecord.model_validate(p).generationmix}
    assert fuels == {"gas", "storage"}


def test_validate_records_audits_every_rejection_and_counts_duplicates():
    good = intensity_payload(T0)
    bad = intensity_payload(T0 + timedelta(minutes=30), actual=4000)
    bad["_source_url"] = "https://api/x"
    out = validate_records([good, dict(good), bad, {"junk": True}], IntensityRecord, "intensity", "run-1")
    assert len(out.accepted) == 1 and out.exact_duplicates == 1 and len(out.rejected) == 2
    assert out.total == 4
    r = next(x for x in out.rejected if x.source_url)
    assert r.run_id == "run-1" and r.interval_start_utc == T0 + timedelta(minutes=30)
    assert "4000" in r.raw_payload and "less than or equal" in r.reason
    assert "less_than_equal" in r.error_details
    assert sum(summarize_rejections(out.rejected).values()) == 2

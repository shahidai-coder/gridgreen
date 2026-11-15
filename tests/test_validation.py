from datetime import timedelta

import pytest
from conftest import generation_payload, intensity_payload, slot
from pydantic import ValidationError

from gridgreen.schemas import GenerationRecord, IntensityMixCheck, IntensityRecord
from gridgreen.validate import cross_validate_intensity, summarize_rejections, validate_records

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


# ------------------------------------------------ cross-dataset plausibility (zero-intensity rule)
# The real case that motivated the rule: 2026-08-06 11:00 UTC, actual = 0 with gas 7.4% + biomass 8.1%.
REAL_BAD_MIX = {
    "wind": 30.2,
    "solar": 24.5,
    "imports": 17.1,
    "nuclear": 12.6,
    "biomass": 8.1,
    "gas": 7.4,
    "coal": 0.0,
    "other": 0.0,
    "hydro": 0.0,
}
CLEAN_MIX = {"wind": 55.0, "nuclear": 20.0, "solar": 15.0, "hydro": 5.0, "imports": 5.0}


def _cross(intensity: list[dict], generation: list[dict]):
    val_i = validate_records(intensity, IntensityRecord, "intensity", "run-1")
    val_g = validate_records(generation, GenerationRecord, "generation", "run-1")
    return cross_validate_intensity(val_i, val_g.accepted, "run-1")


def test_zero_intensity_with_emitting_generation_is_rejected_with_its_payload():
    bad = intensity_payload(T0, actual=0, forecast=62, index="very low")
    bad["_source_url"] = "https://api/x"
    good = intensity_payload(T0 + timedelta(minutes=30), actual=41, forecast=64, index="low")
    out = _cross(
        [bad, good],
        [generation_payload(T0, REAL_BAD_MIX), generation_payload(T0 + timedelta(minutes=30), REAL_BAD_MIX)],
    )
    assert [r.intensity.actual for r in out.accepted] == [41]
    assert len(out.accepted_raw) == 1 and out.total == 2
    (r,) = out.rejected
    assert r.dataset == "intensity" and r.interval_start_utc == T0 and r.source_url == "https://api/x"
    assert r.reason == "intensity.actual: actual intensity is 0 while carbon-emitting generation is present"
    assert "15.5% fossil + biomass" in r.error_details
    assert '"actual": 0' in r.raw_payload and "_source_url" not in r.raw_payload


def test_zero_intensity_is_kept_when_the_mix_has_no_emitting_fuel_or_is_unknown():
    zero = intensity_payload(T0, actual=0, forecast=5, index="very low")
    assert len(_cross([zero], [generation_payload(T0, CLEAN_MIX)]).rejected) == 0
    assert len(_cross([zero], []).rejected) == 0  # no mix for the slot: cannot be checked, so kept


@pytest.mark.parametrize(
    "actual,share,ok",
    [(0, 0.9, True), (0, 1.0, False), (0, 15.5, False), (1, 15.5, True), (None, 15.5, True)],
)
def test_intensity_mix_check_threshold(actual, share, ok):
    kwargs = {"interval_start": T0, "actual": actual, "emitting_share": share}
    if ok:
        IntensityMixCheck(**kwargs)
    else:
        with pytest.raises(ValidationError, match="carbon-emitting generation"):
            IntensityMixCheck(**kwargs)


def test_cross_validation_keeps_first_pass_rejections_and_duplicate_count():
    good = intensity_payload(T0)
    first_pass_bad = intensity_payload(T0 + timedelta(minutes=30), actual=4000)
    out = _cross([good, dict(good), first_pass_bad], [generation_payload(T0)])
    assert len(out.accepted) == 1 and len(out.rejected) == 1 and out.exact_duplicates == 1

"""Pydantic models describing the API payloads we accept.

A record that fails these models is never dropped silently: validate.py turns
the ValidationError into a RejectedRecord that is stored in DuckDB.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from gridgreen.config import (
    INTENSITY_MAX,
    INTENSITY_MIN,
    SHARE_TOLERANCE_PP,
    SLOT_MINUTES,
    standardize_fuel,
)

SLOT = timedelta(minutes=SLOT_MINUTES)
VALID_INDEX = {"very low", "low", "moderate", "high", "very high"}


def to_aligned_utc(value: datetime) -> datetime:
    """Convert to UTC and require exact half-hour alignment."""
    value = value.astimezone(UTC)
    if value.minute not in (0, 30) or value.second or value.microsecond:
        raise ValueError(f"timestamp not aligned to a half-hour slot ({value.isoformat()})")
    return value


class _Interval(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True, frozen=True)

    interval_start: AwareDatetime = Field(alias="from")
    interval_end: AwareDatetime = Field(alias="to")

    @field_validator("interval_start", "interval_end")
    @classmethod
    def _aligned(cls, v: datetime) -> datetime:
        return to_aligned_utc(v)

    @model_validator(mode="after")
    def _thirty_minutes(self):
        if self.interval_end - self.interval_start != SLOT:
            raise ValueError(
                f"interval is not {SLOT_MINUTES} minutes ({self.interval_end - self.interval_start})"
            )
        return self


class IntensityValues(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    forecast: int | None = Field(default=None, ge=INTENSITY_MIN, le=INTENSITY_MAX)
    actual: int | None = Field(default=None, ge=INTENSITY_MIN, le=INTENSITY_MAX)
    index: str | None = None

    @field_validator("index")
    @classmethod
    def _normalise_index(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip().lower()
        if v not in VALID_INDEX:
            raise ValueError(f"unknown intensity index ({v})")
        return v


class IntensityRecord(_Interval):
    intensity: IntensityValues

    @model_validator(mode="after")
    def _has_a_value(self):
        if self.intensity.forecast is None and self.intensity.actual is None:
            raise ValueError("record has neither a forecast nor an actual value")
        return self


class FuelShare(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    fuel: str = Field(min_length=1)
    perc: float = Field(ge=0, le=100, allow_inf_nan=False)

    @field_validator("fuel")
    @classmethod
    def _canonical(cls, v: str) -> str:
        v = standardize_fuel(v)
        if not v:
            raise ValueError("empty fuel name")
        return v


class GenerationRecord(_Interval):
    generationmix: list[FuelShare] = Field(min_length=1)

    @model_validator(mode="after")
    def _complete_distribution(self):
        fuels = [f.fuel for f in self.generationmix]
        dupes = sorted({f for f in fuels if fuels.count(f) > 1})
        if dupes:
            raise ValueError(f"duplicate fuel categories ({dupes})")
        total = sum(f.perc for f in self.generationmix)
        if abs(total - 100.0) > SHARE_TOLERANCE_PP:
            raise ValueError(f"fuel shares do not sum to 100 ± {SHARE_TOLERANCE_PP} pp ({total:.2f}%)")
        return self

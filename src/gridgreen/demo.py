"""SYNTHETIC demonstration data source. NOT REAL GRID DATA.

Produces payloads shaped exactly like the NESO API so that the real pipeline
(validate -> transform -> load) can be exercised when the API is unreachable,
for example in offline CI or a sandbox without internet access. Any database
built from this source is tagged `synthetic_demo` and the dashboard shows a
permanent warning banner. Nothing here may be reported as a finding.

The generator is a simple physically-motivated toy: a persistent random-walk
wind share, a diurnal/seasonal solar share, gas filling the remainder, and
intensity = sum(share x illustrative emission factor) + noise. A handful of
deliberately invalid records are injected to demonstrate rejection logging.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import numpy as np
import pandas as pd

from gridgreen.api_client import ApiResponse, format_api_time

# Illustrative factors (gCO2/kWh), loosely based on NESO's /intensity/factors.
_FACTORS = {
    "gas": 394,
    "coal": 937,
    "biomass": 120,
    "imports": 250,
    "other": 300,
    "wind": 0,
    "solar": 0,
    "nuclear": 0,
    "hydro": 0,
}


def _build(start: datetime, end: datetime, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.date_range(start, end, freq="30min", inclusive="left", tz="UTC")
    n = len(idx)
    local = idx.tz_convert("Europe/London")
    doy = local.day_of_year.to_numpy()
    hour = (local.hour + local.minute / 60).to_numpy()
    winter = 0.5 + 0.5 * np.cos(2 * np.pi * (doy - 15) / 365.25)  # 1 in Jan, 0 in Jul

    # Wind: AR(1) on a logit scale, windier in winter.
    z = np.zeros(n)
    for i in range(1, n):
        z[i] = 0.995 * z[i - 1] + rng.normal(0, 0.08)
    wind = 100 / (1 + np.exp(-(z + 0.6 * winter - 0.6))) * 0.55
    daylight = np.clip(np.sin(np.pi * (hour - 6 + 2 * (1 - winter)) / (12 + 4 * (1 - winter))), 0, None)
    solar = daylight * (4 + 14 * (1 - winter)) * rng.uniform(0.6, 1.0, n)
    nuclear = np.full(n, 13.0) + rng.normal(0, 0.3, n)
    biomass = 5 + rng.normal(0, 0.5, n)
    imports = 9 + 3 * np.sin(2 * np.pi * hour / 24) + rng.normal(0, 1, n)
    hydro = 1.5 + 0.8 * winter + rng.normal(0, 0.2, n)
    other = np.full(n, 1.0)
    coal = np.zeros(n)
    # Demand-shaped residual covered by gas; evening peak and weekdays push it up.
    weekday = (local.day_of_week < 5).astype(float)
    peak = 6 * np.exp(-((hour - 18) ** 2) / 4) + 2 * weekday
    fixed = wind + solar + nuclear + biomass + imports + hydro + other
    gas = np.clip(100 - fixed + peak - peak.mean(), 2, None)
    shares = pd.DataFrame(
        dict(
            gas=gas,
            coal=coal,
            biomass=biomass,
            nuclear=nuclear,
            hydro=hydro,
            imports=imports,
            other=other,
            wind=wind,
            solar=solar,
        ),
        index=idx,
    )
    shares = shares.clip(lower=0)
    shares = shares.div(shares.sum(axis=1), axis=0) * 100
    shares = shares.round(1)
    shares["gas"] += 100 - shares.sum(axis=1)  # exact rounding repair
    intensity = sum(shares[f] * _FACTORS[f] / 100 for f in _FACTORS) + rng.normal(0, 6, n)
    shares["actual"] = np.clip(intensity, 5, 900).round().astype(int)
    shares["forecast"] = np.clip(shares["actual"] + rng.normal(4, 18, n), 5, 900).round().astype(int)
    return shares


def _index_label(v: int) -> str:
    for limit, label in ((40, "very low"), (120, "low"), (200, "moderate"), (290, "high")):
        if v < limit:
            return label
    return "very high"


class SyntheticClient:
    """Drop-in stand-in for CarbonIntensityClient. Output is SYNTHETIC."""

    def __init__(self, start: datetime, end: datetime, seed: int = 7, inject_invalid: bool = True):
        self.frame = _build(start, end, seed)
        self.inject_invalid = inject_invalid
        self._bad_slots = set(self.frame.index[[10, 500, 4000]]) if len(self.frame) > 4000 else set()

    def close(self) -> None:  # API parity
        pass

    def _slice(self, start: datetime, end: datetime) -> pd.DataFrame:
        return self.frame.loc[(self.frame.index >= start) & (self.frame.index < end)]

    def _url(self, kind: str, start: datetime, end: datetime) -> str:
        return f"synthetic://{kind}/{format_api_time(start)}/{format_api_time(end)}"

    def intensity(self, start: datetime, end: datetime) -> ApiResponse:
        data = []
        for ts, row in self._slice(start, end).iterrows():
            rec = {
                "from": format_api_time(ts),
                "to": format_api_time(ts + timedelta(minutes=30)),
                "intensity": {
                    "forecast": int(row.forecast),
                    "actual": int(row.actual),
                    "index": _index_label(int(row.actual)),
                },
            }
            if self.inject_invalid and ts in self._bad_slots:
                rec["intensity"]["actual"] = 1450  # out of plausibility range
                data.append(
                    {
                        "from": ts.strftime("%Y-%m-%dT%H:%MZ").replace(":00Z", ":10Z"),
                        "to": format_api_time(ts),
                        "intensity": {"actual": 100},
                    }
                )
            data.append(rec)
        return ApiResponse(self._url("intensity", start, end), data)

    def generation(self, start: datetime, end: datetime) -> ApiResponse:
        fuels = [c for c in self.frame.columns if c not in ("actual", "forecast")]
        data = []
        for ts, row in self._slice(start, end).iterrows():
            mix = [{"fuel": f, "perc": float(round(row[f], 1))} for f in fuels]
            if self.inject_invalid and ts in self._bad_slots:
                mix = mix[:-1]  # drop a fuel -> shares no longer sum to 100
            data.append(
                {
                    "from": format_api_time(ts),
                    "to": format_api_time(ts + timedelta(minutes=30)),
                    "generationmix": mix,
                }
            )
        return ApiResponse(self._url("generation", start, end), data)

    def intensity_forecast_48h(self, start: datetime) -> ApiResponse:
        return ApiResponse(self._url("fw48h", start, start), [])


def default_demo_range() -> tuple[datetime, datetime]:
    return datetime(2025, 10, 1, tzinfo=UTC), datetime(2026, 10, 1, tzinfo=UTC)

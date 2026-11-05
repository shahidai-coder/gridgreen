import streamlit as st

from gridgreen.config import (
    API_DOCS_URL,
    ATTRIBUTION,
    FOSSIL_FUELS,
    INTENSITY_MAX,
    INTENSITY_MIN,
    LICENCE_URL,
    MAX_CHUNK_DAYS,
    SEASON_BY_MONTH,
    SHARE_TOLERANCE_PP,
    ZERO_CARBON_FUELS,
)
from gridgreen.ui.banners import page_banner
from gridgreen.ui.components import footer, get_context, topbar

topbar("Methodology", get_context())
page_banner("method")
seasons = {}
for m, s in SEASON_BY_MONTH.items():
    seasons.setdefault(s, []).append(m)
season_txt = "; ".join(f"{s}: months {', '.join(map(str, sorted(v)))}" for s, v in seasons.items())

st.markdown(f"""
## Research question
**When is Britain's electricity cleanest, and what makes it that way?** GridGreen describes daily and seasonal
patterns in carbon intensity, relates them to the generation mix, compares weekdays with weekends, identifies
historically low-intensity windows for flexible demand, and evaluates the published forecast.

## Data source and licence
* NESO Carbon Intensity API for Great Britain ([documentation]({API_DOCS_URL})), no API key required.
* Endpoints: `/intensity/{{from}}/{{to}}` (documented maximum range 14 days) and `/generation/{{from}}/{{to}}`.
  Requests are split into {MAX_CHUNK_DAYS}-day chunks with timeouts and bounded exponential-backoff retries.
* {ATTRIBUTION} [CC BY 4.0]({LICENCE_URL}).
* **Actual** values are NESO estimates derived from metered generation and modelled embedded wind and solar.
  They are not direct measurements. **Forecast** is NESO's published forecast for that half-hour.
* Generation mix is supplied as **percentage shares**, not MW. GridGreen never infers absolute output.

## Pipeline
1. **Extract** raw JSON per chunk; failed chunks are recorded, not fatal.
2. **Validate** each record with Pydantic. Rejected records are stored with reason, structured errors,
   raw payload, source URL and run identifier.
3. **Transform** with pandas: UTC normalisation, deterministic deduplication, range filtering, missing-interval
   detection, a left join of generation onto intensity by UTC slot, and time features.
4. **Load** into DuckDB in one transaction using `INSERT … ON CONFLICT DO UPDATE`, so repeated runs never
   duplicate rows. A later run fills in actuals that were not yet published.

## Validation rules
* Timestamps must be timezone-aware, aligned to :00 or :30, and exactly 30 minutes long.
* Intensity must be within {INTENSITY_MIN}–{INTENSITY_MAX} gCO₂/kWh; a record needs a forecast or an actual.
* Fuel shares must be 0–100%, fuel names unique, and the total within 100 ± {SHARE_TOLERANCE_PP} pp,
  because the API presents a complete percentage distribution rounded to one decimal place.
* Unrecognised fuel names are kept (lower-cased) and grouped as *other*, rather than discarded.

## Time and daylight saving
The unique key of every half-hour is its **UTC start**. UK local time (Europe/London) is derived for analysis
only. A local day has 46 half-hours on the March change, 50 in October, and 48 otherwise. On the October day
the 01:00–02:00 wall-clock hour occurs twice; both occurrences are kept as separate UTC slots.

## Definitions
* **Seasons** (meteorological): {season_txt}.
* **Zero-carbon share**: {", ".join(ZERO_CARBON_FUELS)}. **Fossil share**: {", ".join(FOSSIL_FUELS)} where reported.
* **Biomass** and **imports** are kept separate: biomass has a non-zero NESO emission factor and imports carry
  unknown foreign generation.
* **Forecast error** = forecast − actual. MAE is the mean absolute error, RMSE the root mean squared error
  (which weights large misses more), and bias the mean signed error.
* **Best window**: mean of the k half-hours in a window of k × 30 minutes on the complete UTC grid, subject to a
  coverage threshold, compared with the mean of all valid windows (a random-start baseline).

## Exploratory methods
Means with medians and 10th–90th percentile bands, hour-matched weekday/weekend comparison, heatmaps, Pearson
and Spearman correlations of fuel shares with intensity, and binned zero-carbon share analysis.

## Limitations
* Correlation is not causation, and shares are compositional (one rising forces others down).
* Short periods cannot support long-term or seasonal trend claims.
* Normal-approximation confidence intervals understate uncertainty because half-hours are autocorrelated.
* Forecast lead time is unavailable historically; horizon analysis relies on snapshots captured from now on.
* Results are national (GB) and historical. They are not live measurements or predictions.
""")
footer()

"""Central configuration and domain definitions.

Every analytical assumption (seasons, fuel groupings, tolerances) lives here so
that the notebook, the dashboard and the tests all share one definition.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
DEFAULT_DB_PATH = DATA_DIR / "gridgreen.duckdb"
DEMO_DB_PATH = DATA_DIR / "demo" / "gridgreen_demo.duckdb"
PARQUET_DIR = DATA_DIR / "parquet"

API_BASE_URL = "https://api.carbonintensity.org.uk"
LOCAL_TZ = ZoneInfo("Europe/London")
SLOT_MINUTES = 30

# The /intensity/{from}/{to} endpoint documents a 14-day maximum range.
# /generation/{from}/{to} documents no limit, so the same safe window is used.
MAX_CHUNK_DAYS = 14

# Plausibility range required by the project brief (gCO2/kWh).
INTENSITY_MIN = 0
INTENSITY_MAX = 1000

# The generation endpoint returns percentage shares ("perc"), never MW.
# A complete mix should sum to 100; rounding in the source justifies ±1 pp.
SHARE_TOLERANCE_PP = 1.0

KNOWN_FUELS: tuple[str, ...] = (
    "biomass",
    "coal",
    "gas",
    "hydro",
    "imports",
    "nuclear",
    "other",
    "solar",
    "wind",
)
FUEL_ALIASES: dict[str, str] = {
    "pumped storage": "storage",
    "pumped_storage": "storage",
    "ccgt": "gas",
    "ocgt": "gas",
    "interconnectors": "imports",
}

# Analytical groupings (documented in README > Methodology).
ZERO_CARBON_FUELS: tuple[str, ...] = ("hydro", "nuclear", "solar", "wind")
FOSSIL_FUELS: tuple[str, ...] = ("coal", "gas", "oil")
# biomass: combustion with non-zero NESO emission factor -> neither group.
# imports: mixed, unknown foreign generation -> reported separately.
# other / storage / unrecognised -> "other".

# Meteorological seasons (UK Met Office convention).
SEASON_BY_MONTH: dict[int, str] = {
    12: "Winter",
    1: "Winter",
    2: "Winter",
    3: "Spring",
    4: "Spring",
    5: "Spring",
    6: "Summer",
    7: "Summer",
    8: "Summer",
    9: "Autumn",
    10: "Autumn",
    11: "Autumn",
}
SEASON_ORDER: tuple[str, ...] = ("Winter", "Spring", "Summer", "Autumn")

DATA_SOURCE_LIVE = "neso_api"
DATA_SOURCE_DEMO = "synthetic_demo"

ATTRIBUTION = (
    "Data: NESO Carbon Intensity API (carbonintensity.org.uk), "
    "licensed under CC BY 4.0. 'Actual' values are NESO estimates, "
    "not direct meter readings."
)
LICENCE_URL = "https://creativecommons.org/licenses/by/4.0/"
API_DOCS_URL = "https://carbon-intensity.github.io/api-definitions/"


@dataclass(frozen=True)
class Settings:
    db_path: Path
    api_base_url: str
    timeout_s: float
    max_retries: int
    backoff_base_s: float


def get_settings() -> Settings:
    """Read settings from the environment, falling back to safe defaults."""
    return Settings(
        db_path=Path(os.getenv("GRIDGREEN_DB_PATH", str(DEFAULT_DB_PATH))),
        api_base_url=os.getenv("GRIDGREEN_API_BASE_URL", API_BASE_URL),
        timeout_s=float(os.getenv("GRIDGREEN_TIMEOUT_S", "30")),
        max_retries=int(os.getenv("GRIDGREEN_MAX_RETRIES", "4")),
        backoff_base_s=float(os.getenv("GRIDGREEN_BACKOFF_BASE_S", "1.0")),
    )


def standardize_fuel(name: str) -> str:
    """Normalise a fuel label to lowercase canonical form."""
    key = " ".join(name.strip().lower().split())
    return FUEL_ALIASES.get(key, key)


def fuel_category(fuel: str) -> str:
    """Map a canonical fuel to its analytical category."""
    if fuel in ZERO_CARBON_FUELS:
        return "zero_carbon"
    if fuel in FOSSIL_FUELS:
        return "fossil"
    if fuel == "biomass":
        return "biomass"
    if fuel == "imports":
        return "imports"
    return "other"

"""Run the hand-written sample fixtures through validation and transformation."""

import json
from pathlib import Path

import httpx
import respx

from gridgreen.api_client import CarbonIntensityClient
from gridgreen.extract import extract_generation, extract_intensity
from gridgreen.schemas import GenerationRecord, IntensityRecord
from gridgreen.transform import build_analytical_frame, generation_to_frame, intensity_to_frame
from gridgreen.validate import validate_records

SAMPLE = Path(__file__).resolve().parents[1] / "data" / "sample"
BASE = "https://api.test"


@respx.mock
def test_fixtures_flow_through_extract_validate_transform():
    from datetime import UTC, datetime

    s, e = datetime(2026, 3, 29, 0, tzinfo=UTC), datetime(2026, 3, 29, 2, tzinfo=UTC)
    for kind in ("intensity", "generation"):
        body = json.loads((SAMPLE / f"{kind}_sample.json").read_text())
        respx.get(f"{BASE}/{kind}/2026-03-29T00:00Z/2026-03-29T02:00Z").mock(
            return_value=httpx.Response(200, json=body)
        )
    client = CarbonIntensityClient(BASE, max_retries=0)
    vi = validate_records(extract_intensity(client, s, e).records, IntensityRecord, "intensity", "fx")
    vg = validate_records(extract_generation(client, s, e).records, GenerationRecord, "generation", "fx")
    assert (len(vi.accepted), len(vi.rejected)) == (3, 1)
    assert (len(vg.accepted), len(vg.rejected)) == (2, 1)
    assert "less than or equal" in vi.rejected[0].reason
    assert "do not sum" in vg.rejected[0].reason
    frame = build_analytical_frame(intensity_to_frame(vi.accepted), generation_to_frame(vg.accepted))
    # 01:00 UTC on 29 March 2026 is 02:00 BST: the clock skips 01:00-02:00 local.
    assert frame["time_label"].tolist() == ["00:00", "00:30", "02:00"]
    assert frame["share_wind"].notna().sum() == 2

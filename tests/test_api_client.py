from datetime import UTC, datetime

import httpx
import pytest
import respx

from gridgreen.api_client import ApiError, ApiSchemaError, CarbonIntensityClient, format_api_time
from gridgreen.extract import chunk_ranges, extract_intensity

BASE = "https://api.test"
START, END = datetime(2026, 1, 1, tzinfo=UTC), datetime(2026, 1, 2, tzinfo=UTC)
URL = f"{BASE}/intensity/2026-01-01T00:00Z/2026-01-02T00:00Z"


def client(**kw) -> CarbonIntensityClient:
    sleeps: list[float] = []
    c = CarbonIntensityClient(
        BASE, timeout_s=1, max_retries=kw.pop("retries", 2), backoff_base_s=0.5, sleep=sleeps.append
    )
    c.sleeps = sleeps  # type: ignore[attr-defined]
    return c


def test_format_api_time_requires_aware():
    assert format_api_time(datetime(2026, 3, 29, 1, 30, tzinfo=UTC)) == "2026-03-29T01:30Z"
    with pytest.raises(ValueError):
        format_api_time(datetime(2026, 1, 1))


@respx.mock
def test_success_returns_data_and_url():
    respx.get(URL).mock(return_value=httpx.Response(200, json={"data": [{"from": "x"}]}))
    r = client().intensity(START, END)
    assert r.url == URL and r.data == [{"from": "x"}]


@respx.mock
def test_single_object_data_is_wrapped():
    respx.get(f"{BASE}/intensity/2026-01-01T00:00Z/fw48h").mock(
        return_value=httpx.Response(200, json={"data": {"from": "x"}})
    )
    assert client().intensity_forecast_48h(START).data == [{"from": "x"}]


@respx.mock
def test_retries_on_503_then_succeeds_with_exponential_backoff():
    route = respx.get(URL).mock(
        side_effect=[httpx.Response(503), httpx.Response(503), httpx.Response(200, json={"data": []})]
    )
    c = client(retries=3)
    assert c.intensity(START, END).data == []
    assert route.call_count == 3
    assert c.sleeps == [0.5, 1.0]


@respx.mock
def test_retry_after_header_is_respected():
    respx.get(URL).mock(
        side_effect=[
            httpx.Response(429, headers={"Retry-After": "7"}),
            httpx.Response(200, json={"data": []}),
        ]
    )
    c = client()
    c.intensity(START, END)
    assert c.sleeps == [7.0]


@respx.mock
def test_timeouts_exhaust_retries_and_raise():
    route = respx.get(URL).mock(side_effect=httpx.ReadTimeout("slow"))
    c = client(retries=2)
    with pytest.raises(ApiError, match="after 3 attempts"):
        c.intensity(START, END)
    assert route.call_count == 3


@respx.mock
def test_client_error_is_not_retried():
    route = respx.get(URL).mock(return_value=httpx.Response(400, json={"error": {"code": "400"}}))
    with pytest.raises(ApiError, match="HTTP 400"):
        client().intensity(START, END)
    assert route.call_count == 1


@respx.mock
@pytest.mark.parametrize("body", [b"not json", b'{"nodata": 1}', b'{"data": "oops"}', b'{"data": [1, 2]}'])
def test_bad_envelope_raises_schema_error(body):
    respx.get(URL).mock(return_value=httpx.Response(200, content=body))
    with pytest.raises(ApiSchemaError):
        client().intensity(START, END)


def test_chunk_ranges_respects_14_day_limit_and_covers_range():
    s, e = datetime(2026, 1, 1, tzinfo=UTC), datetime(2026, 2, 15, tzinfo=UTC)
    chunks = chunk_ranges(s, e)
    assert chunks[0][0] == s and chunks[-1][1] == e
    assert all((b - a).days <= 14 for a, b in chunks)
    assert all(chunks[i][1] == chunks[i + 1][0] for i in range(len(chunks) - 1))
    assert chunk_ranges(e, s) == []


@respx.mock
def test_failed_chunk_is_recorded_and_others_continue():
    s, e = datetime(2026, 1, 1, tzinfo=UTC), datetime(2026, 1, 29, tzinfo=UTC)
    respx.get(f"{BASE}/intensity/2026-01-01T00:00Z/2026-01-15T00:00Z").mock(return_value=httpx.Response(500))
    respx.get(f"{BASE}/intensity/2026-01-15T00:00Z/2026-01-29T00:00Z").mock(
        return_value=httpx.Response(200, json={"data": [{"from": "a"}]})
    )
    res = extract_intensity(client(retries=0), s, e)
    assert len(res.failures) == 1 and res.failures[0].start == s
    assert len(res.records) == 1 and res.records[0]["_source_url"].endswith("2026-01-29T00:00Z")

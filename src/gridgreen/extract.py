"""Extract stage: chunked, failure-tolerant retrieval of raw API records."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from gridgreen.api_client import ApiError, ApiResponse, CarbonIntensityClient
from gridgreen.config import MAX_CHUNK_DAYS

log = logging.getLogger(__name__)
SOURCE_URL_KEY = "_source_url"


@dataclass(frozen=True)
class ChunkFailure:
    dataset: str
    start: datetime
    end: datetime
    error: str


@dataclass
class ExtractResult:
    dataset: str
    records: list[dict[str, Any]] = field(default_factory=list)
    failures: list[ChunkFailure] = field(default_factory=list)
    requests: int = 0


def chunk_ranges(
    start: datetime, end: datetime, max_days: int = MAX_CHUNK_DAYS
) -> list[tuple[datetime, datetime]]:
    """Split [start, end) into consecutive windows of at most max_days."""
    if start.tzinfo is None or end.tzinfo is None:
        raise ValueError("start and end must be timezone-aware")
    if end <= start:
        return []
    step = timedelta(days=max_days)
    out, cursor = [], start
    while cursor < end:
        nxt = min(cursor + step, end)
        out.append((cursor, nxt))
        cursor = nxt
    return out


def _extract(
    dataset: str,
    fetch: Callable[[datetime, datetime], ApiResponse],
    start: datetime,
    end: datetime,
) -> ExtractResult:
    result = ExtractResult(dataset=dataset)
    for c_start, c_end in chunk_ranges(start, end):
        result.requests += 1
        try:
            response = fetch(c_start, c_end)
        except ApiError as exc:
            log.error("%s chunk %s..%s failed: %s", dataset, c_start, c_end, exc)
            result.failures.append(ChunkFailure(dataset, c_start, c_end, str(exc)))
            continue
        for record in response.data:
            result.records.append({**record, SOURCE_URL_KEY: response.url})
        log.info("%s %s..%s: %d records", dataset, c_start.date(), c_end.date(), len(response.data))
    return result


def extract_intensity(client: CarbonIntensityClient, start: datetime, end: datetime) -> ExtractResult:
    return _extract("intensity", client.intensity, start, end)


def extract_generation(client: CarbonIntensityClient, start: datetime, end: datetime) -> ExtractResult:
    return _extract("generation", client.generation, start, end)


def extract_forecast_snapshot(client: CarbonIntensityClient, at: datetime) -> ExtractResult:
    """Capture the forward 48h forecast as published at `at` (for horizon analysis)."""
    result = ExtractResult(dataset="forecast_snapshot", requests=1)
    try:
        response = client.intensity_forecast_48h(at)
    except ApiError as exc:
        result.failures.append(ChunkFailure("forecast_snapshot", at, at, str(exc)))
        return result
    result.records = [{**r, SOURCE_URL_KEY: response.url} for r in response.data]
    return result

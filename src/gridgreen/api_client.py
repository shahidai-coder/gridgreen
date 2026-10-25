"""Thin HTTP client for the NESO Carbon Intensity API.

Responsibilities: build URLs, enforce timeouts, retry transient failures with
bounded exponential backoff, and check the response envelope. It knows nothing
about analytics.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx

from gridgreen.config import API_BASE_URL

log = logging.getLogger(__name__)
RETRYABLE_STATUS = {429, 500, 502, 503, 504}
MAX_BACKOFF_S = 30.0


class ApiError(RuntimeError):
    """Raised when the API cannot provide a usable response."""


class ApiSchemaError(ApiError):
    """Raised when the response body does not match the documented envelope."""


@dataclass(frozen=True)
class ApiResponse:
    url: str
    data: list[dict[str, Any]]


def format_api_time(dt: datetime) -> str:
    """Format a datetime in the API's ISO8601 form, e.g. 2026-01-01T00:00Z."""
    if dt.tzinfo is None:
        raise ValueError("API timestamps must be timezone-aware")
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%MZ")


class CarbonIntensityClient:
    def __init__(
        self,
        base_url: str = API_BASE_URL,
        timeout_s: float = 30.0,
        max_retries: int = 4,
        backoff_base_s: float = 1.0,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.max_retries = max_retries
        self.backoff_base_s = backoff_base_s
        self._sleep = sleep
        self._client = httpx.Client(
            timeout=httpx.Timeout(timeout_s),
            headers={"Accept": "application/json", "User-Agent": "GridGreen/1.0 (university ETL)"},
            transport=transport,
        )

    def __enter__(self) -> CarbonIntensityClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    # ---------------------------------------------------------------- core
    def _backoff(self, attempt: int, response: httpx.Response | None) -> float:
        if response is not None and (ra := response.headers.get("Retry-After")):
            try:
                return min(float(ra), MAX_BACKOFF_S)
            except ValueError:
                pass
        return min(self.backoff_base_s * (2**attempt), MAX_BACKOFF_S)

    def get(self, path: str) -> ApiResponse:
        url = f"{self.base_url}{path}"
        last_error: str = "unknown error"
        for attempt in range(self.max_retries + 1):
            response: httpx.Response | None = None
            try:
                response = self._client.get(url)
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_error = f"{type(exc).__name__}: {exc}"
            else:
                if response.status_code == 200:
                    return ApiResponse(url=url, data=self._parse(url, response))
                last_error = f"HTTP {response.status_code}: {response.text[:200]}"
                if response.status_code not in RETRYABLE_STATUS:
                    raise ApiError(f"{url} -> {last_error}")
            if attempt < self.max_retries:
                delay = self._backoff(attempt, response)
                log.warning("Retrying %s in %.1fs (%s)", url, delay, last_error)
                self._sleep(delay)
        raise ApiError(f"{url} failed after {self.max_retries + 1} attempts: {last_error}")

    @staticmethod
    def _parse(url: str, response: httpx.Response) -> list[dict[str, Any]]:
        try:
            body = response.json()
        except ValueError as exc:
            raise ApiSchemaError(f"{url} returned non-JSON body") from exc
        if not isinstance(body, dict) or "data" not in body:
            raise ApiSchemaError(f"{url} response has no 'data' field")
        data = body["data"]
        if isinstance(data, dict):  # the single-slot endpoints return an object
            data = [data]
        if not isinstance(data, list) or not all(isinstance(r, dict) for r in data):
            raise ApiSchemaError(f"{url} 'data' is not a list of objects")
        return data

    # ------------------------------------------------------------ endpoints
    def intensity(self, start: datetime, end: datetime) -> ApiResponse:
        return self.get(f"/intensity/{format_api_time(start)}/{format_api_time(end)}")

    def generation(self, start: datetime, end: datetime) -> ApiResponse:
        return self.get(f"/generation/{format_api_time(start)}/{format_api_time(end)}")

    def intensity_forecast_48h(self, start: datetime) -> ApiResponse:
        return self.get(f"/intensity/{format_api_time(start)}/fw48h")

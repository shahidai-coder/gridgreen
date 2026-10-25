"""Validate stage: Pydantic validation with full rejection auditing."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ValidationError

from gridgreen.extract import SOURCE_URL_KEY


@dataclass(frozen=True)
class RejectedRecord:
    record_id: str
    run_id: str
    dataset: str
    interval_start_utc: datetime | None
    reason: str
    error_details: str
    raw_payload: str
    source_url: str | None
    rejected_at: datetime


@dataclass
class ValidationOutcome[M: BaseModel]:
    accepted: list[M] = field(default_factory=list)
    rejected: list[RejectedRecord] = field(default_factory=list)
    exact_duplicates: int = 0

    @property
    def total(self) -> int:
        return len(self.accepted) + len(self.rejected) + self.exact_duplicates


def canonical_payload(record: dict[str, Any]) -> str:
    clean = {k: v for k, v in record.items() if k != SOURCE_URL_KEY}
    return json.dumps(clean, sort_keys=True, default=str)


def record_hash(dataset: str, payload: str) -> str:
    return hashlib.sha256(f"{dataset}|{payload}".encode()).hexdigest()[:32]


def _best_effort_start(record: dict[str, Any]) -> datetime | None:
    raw = record.get("from")
    if not isinstance(raw, str):
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(UTC)
    except ValueError:
        return None


def _reason(exc: ValidationError) -> str:
    first = exc.errors()[0]
    loc = ".".join(str(p) for p in first["loc"]) or "record"
    # Stable category for grouping; specifics stay in error_details.
    msg = first["msg"].removeprefix("Value error, ").split(" (")[0]
    return f"{loc}: {msg}"


def validate_records[M: BaseModel](
    raw_records: list[dict[str, Any]],
    model: type[M],
    dataset: str,
    run_id: str,
    rejected_at: datetime | None = None,
) -> ValidationOutcome[M]:
    """Validate raw dicts; exact duplicates are counted, invalid ones recorded."""
    rejected_at = rejected_at or datetime.now(UTC)
    outcome: ValidationOutcome[M] = ValidationOutcome()
    seen: set[str] = set()
    for record in raw_records:
        payload = canonical_payload(record)
        if payload in seen:
            outcome.exact_duplicates += 1
            continue
        seen.add(payload)
        try:
            outcome.accepted.append(model.model_validate(record))
        except ValidationError as exc:
            outcome.rejected.append(
                RejectedRecord(
                    record_id=record_hash(dataset, payload),
                    run_id=run_id,
                    dataset=dataset,
                    interval_start_utc=_best_effort_start(record),
                    reason=_reason(exc),
                    error_details=json.dumps(exc.errors(include_url=False), default=str),
                    raw_payload=payload,
                    source_url=record.get(SOURCE_URL_KEY),
                    rejected_at=rejected_at,
                )
            )
    return outcome


def summarize_rejections(rejected: list[RejectedRecord]) -> dict[str, int]:
    return dict(Counter(r.reason for r in rejected).most_common())

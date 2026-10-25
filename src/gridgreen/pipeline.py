"""Orchestrates Extract -> Validate -> Transform -> Load for one run.

Restartability: each run is logged as 'running' before work starts and all
analytical writes happen in a single transaction, so a crash leaves either
the previous state or the complete new state. Failed 14-day chunks are
recorded in the run message; re-running the same range is always safe
because every load is an idempotent upsert.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pandas as pd

from gridgreen import database, load, transform
from gridgreen.api_client import CarbonIntensityClient
from gridgreen.config import DATA_SOURCE_LIVE, SLOT_MINUTES
from gridgreen.extract import (
    extract_forecast_snapshot,
    extract_generation,
    extract_intensity,
)
from gridgreen.schemas import GenerationRecord, IntensityRecord
from gridgreen.validate import summarize_rejections, validate_records

log = logging.getLogger(__name__)


@dataclass
class RunSummary:
    run_id: str
    status: str
    source: str
    range_start_utc: datetime | None = None
    range_end_utc: datetime | None = None
    api_requests: int = 0
    chunk_failures: int = 0
    intensity_extracted: int = 0
    intensity_accepted: int = 0
    intensity_rejected: int = 0
    intensity_new: int = 0
    intensity_upserted: int = 0
    generation_extracted: int = 0
    generation_accepted: int = 0
    generation_rejected: int = 0
    generation_new: int = 0
    generation_upserted: int = 0
    duplicates_removed: int = 0
    missing_intervals: int = 0
    forecast_snapshot_rows: int = 0
    message: str = ""
    rejection_reasons: dict[str, int] = field(default_factory=dict)


def floor_slot(dt: datetime) -> datetime:
    dt = dt.astimezone(UTC)
    return dt.replace(minute=0 if dt.minute < 30 else 30, second=0, microsecond=0)


def new_run_id(now: datetime) -> str:
    return f"{now:%Y%m%dT%H%M%SZ}-{uuid.uuid4().hex[:8]}"


def _write_run(con, summary: RunSummary, started_at: datetime, finished: bool) -> None:
    cols = {k: v for k, v in asdict(summary).items() if k != "rejection_reasons"}
    cols["started_at"] = started_at
    cols["finished_at"] = datetime.now(UTC) if finished else None
    names = ", ".join(cols)
    marks = ", ".join("?" for _ in cols)
    updates = ", ".join(f"{k} = excluded.{k}" for k in cols if k != "run_id")
    con.execute(
        f"INSERT INTO pipeline_runs ({names}) VALUES ({marks}) ON CONFLICT (run_id) DO UPDATE SET {updates}",
        list(cols.values()),
    )


def resolve_range(
    con, start: datetime | None, end: datetime | None, now: datetime, lookback_days: int
) -> tuple[datetime, datetime]:
    """Explicit range wins; otherwise resume from the last slot with an actual."""
    end = floor_slot(end or now)
    if start is None:
        last = database.last_actual_slot(con)
        start = last if last is not None else end - timedelta(days=lookback_days)
    return floor_slot(start), end


def run_pipeline(
    *,
    db_path: Path | str,
    client: CarbonIntensityClient,
    start: datetime | None = None,
    end: datetime | None = None,
    lookback_days: int = 30,
    source: str = DATA_SOURCE_LIVE,
    snapshot_forecast: bool = True,
    parquet_dir: Path | None = None,
    now: datetime | None = None,
) -> RunSummary:
    now = (now or datetime.now(UTC)).astimezone(UTC)
    con = database.connect(db_path)
    database.init_schema(con)

    existing_source = database.get_metadata(con, "source")
    if existing_source and existing_source != source:
        con.close()
        raise ValueError(
            f"Refusing to mix data sources: database holds '{existing_source}', run is '{source}'. "
            "Use a separate database file."
        )

    run_id = new_run_id(now)
    started_at = datetime.now(UTC)
    range_start, range_end = resolve_range(con, start, end, now, lookback_days)
    summary = RunSummary(
        run_id=run_id, status="running", source=source, range_start_utc=range_start, range_end_utc=range_end
    )
    _write_run(con, summary, started_at, finished=False)
    log.info("Run %s: %s -> %s (%s)", run_id, range_start, range_end, source)

    if range_start >= range_end:
        summary.status = "success"
        summary.message = "Nothing to do: database is already up to date."
        _write_run(con, summary, started_at, finished=True)
        con.close()
        return summary

    try:
        # ---------------- Extract
        ext_i = extract_intensity(client, range_start, range_end)
        ext_g = extract_generation(client, range_start, range_end)
        ext_f = extract_forecast_snapshot(client, now) if snapshot_forecast else None
        failures = ext_i.failures + ext_g.failures + (ext_f.failures if ext_f else [])
        summary.api_requests = ext_i.requests + ext_g.requests + (ext_f.requests if ext_f else 0)
        summary.chunk_failures = len(failures)
        summary.intensity_extracted = len(ext_i.records)
        summary.generation_extracted = len(ext_g.records)

        # ---------------- Validate
        val_i = validate_records(ext_i.records, IntensityRecord, "intensity", run_id)
        val_g = validate_records(ext_g.records, GenerationRecord, "generation", run_id)
        val_f = (
            validate_records(ext_f.records, IntensityRecord, "forecast_snapshot", run_id) if ext_f else None
        )
        summary.intensity_accepted = len(val_i.accepted)
        summary.intensity_rejected = len(val_i.rejected)
        summary.generation_accepted = len(val_g.accepted)
        summary.generation_rejected = len(val_g.rejected)
        all_rejected = val_i.rejected + val_g.rejected + (val_f.rejected if val_f else [])
        summary.rejection_reasons = summarize_rejections(all_rejected)

        # ---------------- Transform
        df_i, dup_i = transform.dedupe_intensity(transform.intensity_to_frame(val_i.accepted))
        df_g, dup_g = transform.dedupe_generation(transform.generation_to_frame(val_g.accepted))
        # Chunk boundaries may return a neighbouring slot; keep the requested range only.
        df_i = transform.filter_range(df_i, range_start, range_end)
        df_g = transform.filter_range(df_g, range_start, range_end)
        summary.duplicates_removed = dup_i + dup_g + val_i.exact_duplicates + val_g.exact_duplicates
        summary.missing_intervals = len(
            transform.detect_missing_intervals(df_i, range_start, range_end, column="actual")
        )
        snap = pd.DataFrame()
        if val_f and val_f.accepted:
            snap = transform.intensity_to_frame(val_f.accepted)
            snap = snap.loc[snap["forecast"].notna(), ["interval_start_utc", "forecast"]]
            snap = snap.loc[snap["interval_start_utc"] >= pd.Timestamp(floor_slot(now))]
            snap = snap.drop_duplicates("interval_start_utc").assign(
                run_id=run_id, retrieved_at=pd.Timestamp(now)
            )
            snap["horizon_minutes"] = (
                (snap["interval_start_utc"] - snap["retrieved_at"]).dt.total_seconds() // 60
            ).astype("int64")

        # ---------------- Load (single transaction)
        con.execute("BEGIN TRANSACTION")
        try:
            loaded_at = datetime.now(UTC)
            summary.intensity_new = load.upsert_intensity(con, df_i, run_id, source, loaded_at)
            summary.intensity_upserted = len(df_i)
            summary.generation_new = load.upsert_generation(con, df_g, run_id, source, loaded_at)
            summary.generation_upserted = len(df_g)
            load.upsert_rejected(con, all_rejected)
            summary.forecast_snapshot_rows = load.insert_forecast_snapshot(con, snap)
            database.set_metadata(con, "source", source)
            con.execute("COMMIT")
        except Exception:
            con.execute("ROLLBACK")
            raise

        if failures:
            summary.status = "partial"
            summary.message = "Failed chunks (re-run to retry): " + "; ".join(
                f"{f.dataset} {f.start:%Y-%m-%dT%H:%MZ}..{f.end:%Y-%m-%dT%H:%MZ}" for f in failures
            )
        else:
            summary.status = "success"
            summary.message = "Completed."
        if parquet_dir is not None:
            load.export_parquet(con, parquet_dir)
    except Exception as exc:
        summary.status = "failed"
        summary.message = f"{type(exc).__name__}: {exc}"
        log.exception("Run %s failed", run_id)
        _write_run(con, summary, started_at, finished=True)
        con.close()
        raise
    _write_run(con, summary, started_at, finished=True)
    con.close()
    log.info("Run %s finished with status %s", run_id, summary.status)
    return summary


SLOT = timedelta(minutes=SLOT_MINUTES)

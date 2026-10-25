"""Load stage: transactional, idempotent upserts into DuckDB."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from pathlib import Path

import duckdb
import pandas as pd

from gridgreen.database import TABLES, scalar
from gridgreen.validate import RejectedRecord


def _count(con: duckdb.DuckDBPyConnection, table: str) -> int:
    return scalar(con, f"SELECT count(*) FROM {table}")


def upsert_intensity(
    con: duckdb.DuckDBPyConnection, df: pd.DataFrame, run_id: str, source: str, loaded_at: datetime
) -> int:
    """Upsert by UTC slot. Returns the number of new slots.

    COALESCE keeps an existing estimated actual if a later payload omits it,
    and fills a previously-null actual once NESO publishes one.
    """
    if df.empty:
        return 0
    if df["interval_start_utc"].duplicated().any():
        raise ValueError("incoming intensity frame contains duplicate slots; dedupe first")
    before = _count(con, "carbon_intensity")
    incoming = df[["interval_start_utc", "interval_end_utc", "forecast", "actual", "intensity_index"]].assign(
        source=source, run_id=run_id, loaded_at=pd.Timestamp(loaded_at)
    )
    con.register("incoming_intensity", incoming)
    try:
        con.execute(
            """
            INSERT INTO carbon_intensity
            SELECT interval_start_utc, interval_end_utc, forecast, actual, intensity_index,
                   source, run_id, loaded_at
            FROM incoming_intensity
            ON CONFLICT (interval_start_utc) DO UPDATE SET
                interval_end_utc = excluded.interval_end_utc,
                forecast = COALESCE(excluded.forecast, carbon_intensity.forecast),
                actual = COALESCE(excluded.actual, carbon_intensity.actual),
                intensity_index = COALESCE(excluded.intensity_index, carbon_intensity.intensity_index),
                source = excluded.source,
                run_id = excluded.run_id,
                loaded_at = excluded.loaded_at
            """
        )
    finally:
        con.unregister("incoming_intensity")
    return _count(con, "carbon_intensity") - before


def upsert_generation(
    con: duckdb.DuckDBPyConnection, df: pd.DataFrame, run_id: str, source: str, loaded_at: datetime
) -> int:
    if df.empty:
        return 0
    if df.duplicated(["interval_start_utc", "fuel"]).any():
        raise ValueError("incoming generation frame contains duplicate keys; dedupe first")
    before = _count(con, "generation_mix")
    incoming = df[["interval_start_utc", "fuel", "perc"]].assign(
        source=source, run_id=run_id, loaded_at=pd.Timestamp(loaded_at)
    )
    con.register("incoming_generation", incoming)
    try:
        con.execute(
            """
            INSERT INTO generation_mix
            SELECT interval_start_utc, fuel, perc, source, run_id, loaded_at FROM incoming_generation
            ON CONFLICT (interval_start_utc, fuel) DO UPDATE SET
                perc = excluded.perc, source = excluded.source,
                run_id = excluded.run_id, loaded_at = excluded.loaded_at
            """
        )
    finally:
        con.unregister("incoming_generation")
    return _count(con, "generation_mix") - before


def upsert_rejected(con: duckdb.DuckDBPyConnection, rejected: Iterable[RejectedRecord]) -> int:
    """Idempotent audit log: one row per distinct bad payload, with sighting counts."""
    rows = list(rejected)
    for r in rows:
        con.execute(
            """
            INSERT INTO rejected_records VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
            ON CONFLICT (record_id) DO UPDATE SET
                last_run_id = excluded.last_run_id,
                last_seen_at = excluded.last_seen_at,
                times_seen = rejected_records.times_seen + 1
            """,
            [
                r.record_id,
                r.dataset,
                r.interval_start_utc,
                r.reason,
                r.error_details,
                r.raw_payload,
                r.source_url,
                r.run_id,
                r.run_id,
                r.rejected_at,
                r.rejected_at,
            ],
        )
    return len(rows)


def insert_forecast_snapshot(con: duckdb.DuckDBPyConnection, df: pd.DataFrame) -> int:
    if df.empty:
        return 0
    con.register("incoming_snapshot", df)
    try:
        con.execute(
            """
            INSERT INTO forecast_snapshots
            SELECT run_id, retrieved_at, interval_start_utc, forecast, horizon_minutes
            FROM incoming_snapshot
            ON CONFLICT (run_id, interval_start_utc) DO NOTHING
            """
        )
    finally:
        con.unregister("incoming_snapshot")
    return len(df)


def export_parquet(con: duckdb.DuckDBPyConnection, out_dir: Path) -> list[Path]:
    """Write every table to Parquet via DuckDB's native COPY."""
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for table in TABLES:
        target = out_dir / f"{table}.parquet"
        con.execute(f"COPY {table} TO '{target.as_posix()}' (FORMAT parquet)")
        written.append(target)
    return written

"""DuckDB connection, schema and read helpers."""

from __future__ import annotations

import warnings
from datetime import UTC, datetime, timedelta
from pathlib import Path

import duckdb
import pandas as pd

SCHEMA_SQL: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS carbon_intensity (
        interval_start_utc TIMESTAMPTZ PRIMARY KEY,
        interval_end_utc   TIMESTAMPTZ NOT NULL,
        forecast           INTEGER CHECK (forecast BETWEEN 0 AND 1000),
        actual             INTEGER CHECK (actual BETWEEN 0 AND 1000),
        intensity_index    VARCHAR,
        source             VARCHAR NOT NULL,
        run_id             VARCHAR NOT NULL,
        loaded_at          TIMESTAMPTZ NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS generation_mix (
        interval_start_utc TIMESTAMPTZ NOT NULL,
        fuel               VARCHAR NOT NULL,
        perc               DOUBLE NOT NULL CHECK (perc BETWEEN 0 AND 100),
        source             VARCHAR NOT NULL,
        run_id             VARCHAR NOT NULL,
        loaded_at          TIMESTAMPTZ NOT NULL,
        PRIMARY KEY (interval_start_utc, fuel)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS pipeline_runs (
        run_id                VARCHAR PRIMARY KEY,
        started_at            TIMESTAMPTZ NOT NULL,
        finished_at           TIMESTAMPTZ,
        status                VARCHAR NOT NULL,
        source                VARCHAR NOT NULL,
        range_start_utc       TIMESTAMPTZ,
        range_end_utc         TIMESTAMPTZ,
        api_requests          INTEGER DEFAULT 0,
        chunk_failures        INTEGER DEFAULT 0,
        intensity_extracted   INTEGER DEFAULT 0,
        intensity_accepted    INTEGER DEFAULT 0,
        intensity_rejected    INTEGER DEFAULT 0,
        intensity_new         INTEGER DEFAULT 0,
        intensity_upserted    INTEGER DEFAULT 0,
        generation_extracted  INTEGER DEFAULT 0,
        generation_accepted   INTEGER DEFAULT 0,
        generation_rejected   INTEGER DEFAULT 0,
        generation_new        INTEGER DEFAULT 0,
        generation_upserted   INTEGER DEFAULT 0,
        duplicates_removed    INTEGER DEFAULT 0,
        missing_intervals     INTEGER DEFAULT 0,
        forecast_snapshot_rows INTEGER DEFAULT 0,
        message               VARCHAR
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS rejected_records (
        record_id          VARCHAR PRIMARY KEY,
        dataset            VARCHAR NOT NULL,
        interval_start_utc TIMESTAMPTZ,
        reason             VARCHAR NOT NULL,
        error_details      VARCHAR NOT NULL,
        raw_payload        VARCHAR NOT NULL,
        source_url         VARCHAR,
        first_run_id       VARCHAR NOT NULL,
        last_run_id        VARCHAR NOT NULL,
        first_seen_at      TIMESTAMPTZ NOT NULL,
        last_seen_at       TIMESTAMPTZ NOT NULL,
        times_seen         INTEGER NOT NULL DEFAULT 1
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS forecast_snapshots (
        run_id             VARCHAR NOT NULL,
        retrieved_at       TIMESTAMPTZ NOT NULL,
        interval_start_utc TIMESTAMPTZ NOT NULL,
        forecast           INTEGER NOT NULL CHECK (forecast BETWEEN 0 AND 1000),
        horizon_minutes    INTEGER NOT NULL,
        PRIMARY KEY (run_id, interval_start_utc)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS dataset_metadata (
        key   VARCHAR PRIMARY KEY,
        value VARCHAR NOT NULL
    )
    """,
)

TABLES = (
    "carbon_intensity",
    "generation_mix",
    "pipeline_runs",
    "rejected_records",
    "forecast_snapshots",
    "dataset_metadata",
)


def connect(path: Path | str, read_only: bool = False) -> duckdb.DuckDBPyConnection:
    path = Path(path)
    if read_only and not path.exists():
        raise FileNotFoundError(f"DuckDB file not found: {path}")
    if not read_only and str(path) != ":memory:":
        path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(path), read_only=read_only)
    con.execute("SET TimeZone = 'UTC'")
    return con


def scalar(con: duckdb.DuckDBPyConnection, sql: str, params: list | None = None):
    """Run a query and return the first value, always draining the result.

    DuckDB 2.0 keeps a partially-fetched result open (fetchone() is not enough),
    and register() refuses to run while one is pending, so every read drains.
    """
    rows = con.execute(sql, params or []).fetchall()
    return rows[0][0] if rows else None


def init_schema(con: duckdb.DuckDBPyConnection) -> None:
    for stmt in SCHEMA_SQL:
        con.execute(stmt)


def existing_tables(con: duckdb.DuckDBPyConnection) -> set[str]:
    rows = con.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'"
    ).fetchall()
    return {r[0] for r in rows}


def get_metadata(con: duckdb.DuckDBPyConnection, key: str) -> str | None:
    if "dataset_metadata" not in existing_tables(con):
        return None
    return scalar(con, "SELECT value FROM dataset_metadata WHERE key = ?", [key])


def set_metadata(con: duckdb.DuckDBPyConnection, key: str, value: str) -> None:
    con.execute(
        "INSERT INTO dataset_metadata VALUES (?, ?) ON CONFLICT (key) DO UPDATE SET value = excluded.value",
        [key, value],
    )


def last_actual_slot(con: duckdb.DuckDBPyConnection) -> datetime | None:
    """Start of the most recent slot that already has an estimated actual."""
    # Fetched as epoch microseconds: DuckDB 2.0 needs pytz to return a
    # TIMESTAMPTZ as a Python object, and we avoid that extra dependency.
    us = scalar(
        con,
        "SELECT epoch_us(max(interval_start_utc)) FROM carbon_intensity WHERE actual IS NOT NULL",
    )
    return None if us is None else datetime(1970, 1, 1, tzinfo=UTC) + timedelta(microseconds=us)


def table_counts(con: duckdb.DuckDBPyConnection) -> dict[str, int]:
    have = existing_tables(con)
    return {t: scalar(con, f"SELECT count(*) FROM {t}") for t in TABLES if t in have}


def _df(con: duckdb.DuckDBPyConnection, sql: str) -> pd.DataFrame:
    with warnings.catch_warnings():
        # Raised inside DuckDB's own pandas conversion (pandas 3.1 deprecation), not our code.
        warnings.filterwarnings("ignore", message="The inplace keyword in DataFrame.drop")
        df = con.execute(sql).df()
    for col in df.columns:
        if isinstance(df[col].dtype, pd.DatetimeTZDtype):
            df[col] = df[col].dt.tz_convert("UTC")
    return df


def read_intensity(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    df = _df(
        con,
        "SELECT interval_start_utc, interval_end_utc, forecast, actual, intensity_index "
        "FROM carbon_intensity ORDER BY interval_start_utc",
    )
    for col in ("forecast", "actual"):
        df[col] = df[col].astype("Int64")
    return df


def read_generation(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    return _df(
        con,
        "SELECT interval_start_utc, fuel, perc FROM generation_mix ORDER BY interval_start_utc, fuel",
    )


def read_runs(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    return _df(con, "SELECT * FROM pipeline_runs ORDER BY started_at DESC")


def read_rejected(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    return _df(con, "SELECT * FROM rejected_records ORDER BY last_seen_at DESC")


def read_snapshots(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    return _df(con, "SELECT * FROM forecast_snapshots ORDER BY retrieved_at, interval_start_utc")

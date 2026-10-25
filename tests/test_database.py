from datetime import UTC, datetime, timedelta

import pandas as pd
import pytest

from gridgreen import database, load
from gridgreen.config import DATA_SOURCE_DEMO, DATA_SOURCE_LIVE
from gridgreen.demo import SyntheticClient
from gridgreen.pipeline import floor_slot, run_pipeline

S, E = datetime(2026, 3, 25, tzinfo=UTC), datetime(2026, 4, 2, tzinfo=UTC)


def _intensity_df(n=3, actual=200):
    t = pd.date_range("2026-01-01T00:00Z", periods=n, freq="30min", tz="UTC")
    return pd.DataFrame(
        {
            "interval_start_utc": t,
            "interval_end_utc": t + pd.Timedelta("30min"),
            "forecast": pd.array([210] * n, dtype="Int64"),
            "actual": pd.array([actual] * n, dtype="Int64"),
            "intensity_index": pd.array(["moderate"] * n, dtype="string"),
        }
    )


@pytest.fixture
def con(tmp_path):
    c = database.connect(tmp_path / "t.duckdb")
    database.init_schema(c)
    yield c
    c.close()


def test_upsert_is_idempotent_and_coalesces_actual(con):
    now = datetime.now(UTC)
    assert load.upsert_intensity(con, _intensity_df(), "r1", DATA_SOURCE_LIVE, now) == 3
    assert load.upsert_intensity(con, _intensity_df(), "r2", DATA_SOURCE_LIVE, now) == 0
    nulls = _intensity_df(actual=None)
    nulls["actual"] = pd.array([None] * 3, dtype="Int64")
    load.upsert_intensity(con, nulls, "r3", DATA_SOURCE_LIVE, now)
    df = database.read_intensity(con)
    assert len(df) == 3 and df["actual"].tolist() == [200, 200, 200]


def test_upsert_rejects_duplicate_keys_in_batch(con):
    df = pd.concat([_intensity_df(1), _intensity_df(1)])
    with pytest.raises(ValueError, match="duplicate"):
        load.upsert_intensity(con, df, "r", DATA_SOURCE_LIVE, datetime.now(UTC))


def test_transaction_rollback_leaves_no_partial_load(con):
    con.execute("BEGIN TRANSACTION")
    load.upsert_intensity(con, _intensity_df(), "r", DATA_SOURCE_LIVE, datetime.now(UTC))
    con.execute("ROLLBACK")
    assert database.table_counts(con)["carbon_intensity"] == 0


def test_check_constraint_blocks_implausible_values(con):
    with pytest.raises(Exception, match=r"(?i)constraint"):
        load.upsert_intensity(con, _intensity_df(actual=1500), "r", DATA_SOURCE_LIVE, datetime.now(UTC))


def test_full_pipeline_is_idempotent_and_logs_rejections(tmp_path):
    db = tmp_path / "p.duckdb"
    client = SyntheticClient(S - timedelta(days=200), E)  # big enough to inject bad rows
    first = run_pipeline(
        db_path=db, client=client, start=S, end=E, source=DATA_SOURCE_DEMO, snapshot_forecast=False, now=E
    )
    c = database.connect(db, read_only=True)
    counts1 = database.table_counts(c)
    c.close()
    second = run_pipeline(
        db_path=db, client=client, start=S, end=E, source=DATA_SOURCE_DEMO, snapshot_forecast=False, now=E
    )
    c = database.connect(db, read_only=True)
    counts2 = database.table_counts(c)
    runs = database.read_runs(c)
    c.close()
    assert first.status == second.status == "success"
    expected = int((E - S).total_seconds() // 1800)
    assert counts1["carbon_intensity"] == expected
    assert first.intensity_new == expected and second.intensity_new == 0
    assert {k: v for k, v in counts2.items() if k != "pipeline_runs"} == {
        k: v for k, v in counts1.items() if k != "pipeline_runs"
    }
    assert counts2["pipeline_runs"] == 2 and set(runs["status"]) == {"success"}


def test_incremental_run_resumes_from_last_actual(tmp_path):
    db = tmp_path / "i.duckdb"
    client = SyntheticClient(S, E, inject_invalid=False)
    run_pipeline(
        db_path=db,
        client=client,
        start=S,
        end=S + timedelta(days=2),
        source=DATA_SOURCE_DEMO,
        snapshot_forecast=False,
        now=E,
    )
    second = run_pipeline(
        db_path=db, client=client, end=E, source=DATA_SOURCE_DEMO, snapshot_forecast=False, now=E
    )
    assert second.range_start_utc == S + timedelta(days=2) - timedelta(minutes=30)
    c = database.connect(db, read_only=True)
    assert database.table_counts(c)["carbon_intensity"] == int((E - S).total_seconds() // 1800)
    c.close()


def test_refuses_to_mix_demo_and_live_sources(tmp_path):
    db = tmp_path / "m.duckdb"
    client = SyntheticClient(S, E, inject_invalid=False)
    run_pipeline(
        db_path=db,
        client=client,
        start=S,
        end=S + timedelta(days=1),
        source=DATA_SOURCE_DEMO,
        snapshot_forecast=False,
        now=E,
    )
    with pytest.raises(ValueError, match="mix data sources"):
        run_pipeline(db_path=db, client=client, start=S, end=E, source=DATA_SOURCE_LIVE, now=E)


def test_failed_run_is_logged_and_nothing_is_loaded(tmp_path):
    class Boom(SyntheticClient):
        def generation(self, start, end):
            raise RuntimeError("unexpected crash")

    db = tmp_path / "f.duckdb"
    with pytest.raises(RuntimeError):
        run_pipeline(
            db_path=db,
            client=Boom(S, E),
            start=S,
            end=E,
            source=DATA_SOURCE_DEMO,
            snapshot_forecast=False,
            now=E,
        )
    c = database.connect(db, read_only=True)
    runs = database.read_runs(c)
    assert runs.iloc[0]["status"] == "failed" and "unexpected crash" in runs.iloc[0]["message"]
    assert database.table_counts(c)["carbon_intensity"] == 0
    c.close()


def test_rejected_records_are_deduplicated_across_runs(con):
    from gridgreen.schemas import IntensityRecord
    from gridgreen.validate import validate_records

    bad = [{"from": "2026-01-01T00:00Z", "to": "2026-01-01T00:30Z", "intensity": {"actual": 9999}}]
    for run in ("r1", "r2"):
        load.upsert_rejected(con, validate_records(bad, IntensityRecord, "intensity", run).rejected)
    rej = database.read_rejected(con)
    assert len(rej) == 1 and rej.iloc[0]["times_seen"] == 2
    assert rej.iloc[0]["first_run_id"] == "r1" and rej.iloc[0]["last_run_id"] == "r2"


def test_parquet_export_round_trips(con, tmp_path):
    load.upsert_intensity(con, _intensity_df(), "r", DATA_SOURCE_LIVE, datetime.now(UTC))
    paths = load.export_parquet(con, tmp_path / "pq")
    assert len(pd.read_parquet(tmp_path / "pq" / "carbon_intensity.parquet")) == 3
    assert all(p.exists() for p in paths)


def test_floor_slot():
    assert floor_slot(datetime(2026, 1, 1, 10, 47, 12, tzinfo=UTC)) == datetime(
        2026, 1, 1, 10, 30, tzinfo=UTC
    )

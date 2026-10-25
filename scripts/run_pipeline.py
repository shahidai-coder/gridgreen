"""Run the GridGreen ETL pipeline against the NESO Carbon Intensity API.

Examples
--------
  python scripts/run_pipeline.py                         # incremental (or last 30 days)
  python scripts/run_pipeline.py --start 2025-10-01 --end 2026-10-01
  python scripts/run_pipeline.py --export-parquet
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from gridgreen.api_client import CarbonIntensityClient
from gridgreen.config import PARQUET_DIR, get_settings
from gridgreen.logging_config import configure_logging
from gridgreen.pipeline import run_pipeline


def _date(value: str) -> datetime:
    dt = datetime.fromisoformat(value)
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)


def main(argv: list[str] | None = None) -> int:
    settings = get_settings()
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--start", type=_date, help="UTC start (YYYY-MM-DD or ISO datetime)")
    p.add_argument("--end", type=_date, help="UTC end, exclusive (default: now)")
    p.add_argument("--db", type=Path, default=settings.db_path)
    p.add_argument("--lookback-days", type=int, default=30, help="first run only, if --start omitted")
    p.add_argument("--no-forecast-snapshot", action="store_true")
    p.add_argument("--export-parquet", action="store_true")
    p.add_argument("--log-level", default="INFO")
    args = p.parse_args(argv)
    configure_logging(args.log_level)

    with CarbonIntensityClient(
        settings.api_base_url, settings.timeout_s, settings.max_retries, settings.backoff_base_s
    ) as client:
        summary = run_pipeline(
            db_path=args.db,
            client=client,
            start=args.start,
            end=args.end,
            lookback_days=args.lookback_days,
            snapshot_forecast=not args.no_forecast_snapshot,
            parquet_dir=PARQUET_DIR if args.export_parquet else None,
        )
    print(json.dumps(summary.__dict__, indent=2, default=str))
    return {"success": 0, "partial": 2}.get(summary.status, 1)


if __name__ == "__main__":
    sys.exit(main())

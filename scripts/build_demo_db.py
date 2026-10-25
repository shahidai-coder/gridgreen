"""Build a SYNTHETIC demo database through the real pipeline code.

The output (data/demo/gridgreen_demo.duckdb) is tagged 'synthetic_demo'.
It exists only to demonstrate and test the software offline. It is not
NESO data and must never be used for findings.
"""

from __future__ import annotations

import json
from pathlib import Path

from gridgreen.config import DATA_SOURCE_DEMO, DEMO_DB_PATH
from gridgreen.demo import SyntheticClient, default_demo_range
from gridgreen.logging_config import configure_logging
from gridgreen.pipeline import run_pipeline


def main() -> None:
    configure_logging()
    start, end = default_demo_range()
    db = Path(DEMO_DB_PATH)
    db.unlink(missing_ok=True)
    summary = run_pipeline(
        db_path=db,
        client=SyntheticClient(start, end),
        start=start,
        end=end,
        source=DATA_SOURCE_DEMO,
        snapshot_forecast=False,
        now=end,
    )
    print(json.dumps(summary.__dict__, indent=2, default=str))


if __name__ == "__main__":
    main()

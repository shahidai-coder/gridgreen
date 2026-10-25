# Data directory

| Path | What it is | Committed? |
|---|---|---|
| `gridgreen.duckdb` | Real analytical database written by `scripts/run_pipeline.py` from the NESO API. | Yes, for deployment (a year is a few MB). |
| `parquet/` | Optional Parquet export of every table (`--export-parquet`). | No, it is reproducible. |
| `demo/gridgreen_demo.duckdb` | **Synthetic** demo database from `scripts/build_demo_db.py`. Tagged `synthetic_demo`. | No. |
| `sample/` | Tiny hand-written **test fixtures** in the API's JSON shape, used by the tests. | Yes. |

Nothing in `demo/` or `sample/` is real grid data. Licence for real data: NESO Carbon Intensity
API, CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/).

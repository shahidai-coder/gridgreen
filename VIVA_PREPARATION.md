# GridGreen viva preparation

Answers describe the code as it exists. File references point to where you can show the examiner.
Practise saying each answer in under a minute, then be ready for the follow-up.

---

## 1. ETL

**Q: Walk me through the pipeline.**
`scripts/run_pipeline.py` calls `pipeline.run_pipeline`, which does four things:
1. **Extract** (`extract.py`, `api_client.py`): request intensity and generation in 14-day chunks and tag
   each raw record with its source URL.
2. **Validate** (`validate.py`, `schemas.py`): parse each record with Pydantic. Failures become
   `RejectedRecord`s rather than being dropped.
3. **Transform** (`transform.py`): build DataFrames, deduplicate deterministically, keep only the requested
   range, and count missing half-hours.
4. **Load** (`load.py`): upsert everything into DuckDB in one transaction, then log the run.

**Q: Why separate the stages into modules?**
Each stage can be tested on its own with fixtures: `test_api_client`, `test_validation`, `test_transform`
and `test_database`. The dashboard and notebook reuse `transform.build_analytical_frame` and
`analytics.py`, so every view computes from the same definitions.

**Q: What happens if the API fails halfway through a backfill?**
- A failed chunk is recorded as a `ChunkFailure` and the remaining chunks continue.
- Whatever succeeded is loaded, and the run is marked `partial` with the failed ranges listed in
  `pipeline_runs.message`. The script exits with code 2.
- Re-running is safe because loads are idempotent upserts.
- If something unexpected crashes, the transaction rolls back and the run is logged as `failed`
  (tested in `test_failed_run_is_logged_and_nothing_is_loaded`).

## 2. Dataset choice

**Q: Why this dataset?**
- It is official (NESO is the GB system operator) and openly licensed under CC BY 4.0.
- It needs no key, and it is half-hourly, which supports daily, weekly and seasonal analysis.
- It has awkward real-world properties worth handling: DST days with 46 or 50 half-hours, late-arriving
  actuals, and a 14-day range limit.

**Q: What are its weaknesses?**
- "Actual" is a modelled estimate, not a measurement.
- Generation is percentage shares, so there are no MW or demand figures.
- History only keeps the final forecast, without its issue time.
- It is national, not regional.

## 3. API integration

**Q: How do you handle failures?**
`CarbonIntensityClient.get`:
- **Timeouts:** each request has an httpx timeout.
- **Transient failures:** timeouts, transport errors, 429 and 5xx are retried with exponential backoff
  (base × 2^attempt, capped at 30 s). A `Retry-After` header is honoured.
- **Client errors:** 4xx are not retried, because repeating a bad request will not fix it.
- **Bad bodies:** the response envelope must be a JSON object with a `data` list; anything else raises
  `ApiSchemaError`.

The sleep function is injected, so tests check the exact backoff sequence without waiting.

**Q: Why 14-day chunks?**
The documentation limits `/intensity/{from}/{to}` to 14 days. `/generation` documents no limit, but using
the same window is the safe choice.

**Q: Chunk boundaries could return a neighbouring half-hour twice. What then?**
`transform.filter_range` keeps only half-open `[start, end)`, and deduplication plus upserts make any
overlap harmless.

## 4. Pydantic

**Q: What does Pydantic do here that pandas couldn't?**
It validates each record against a declared contract before it enters the analytical data:
- types and required fields;
- timezone-aware timestamps converted to UTC and aligned to :00 or :30;
- 30-minute intervals;
- intensity within 0–1000 gCO₂/kWh;
- shares within 0–100% that sum to 100 ± 1 pp, with no duplicate fuels.

It also produces structured errors (field location, type, message), which we store for auditing.

**Q: Why ±1 percentage point?**
The API presents a complete percentage distribution rounded to one decimal place, so rounding alone can
move the sum by a few tenths. One point allows for rounding but catches a missing fuel. That case is
tested: a record with a fuel dropped sums to ~97% and is rejected.

**Q: Why not reject unknown fuel names?**
A new category such as storage is new information, not invalid data. It is kept, lower-cased, and grouped
as *other* (`config.fuel_category`).

## 5. pandas

**Q: Where is pandas used?**
Normalisation, deterministic deduplication, pivoting generation to wide format, the left join onto
intensity, time features, rolling windows for the best-window search, and every grouped summary.

**Q: How is deduplication deterministic?**
`dedupe_intensity` sorts with a stable mergesort by slot, has-actual and has-forecast, then keeps the
first row. Shuffled input gives an identical result (tested).

**Q: Why a left join, and why not fill missing shares?**
Intensity is the analytical spine. Half-hours without a generation mix keep NaN shares, because imputing
them would invent data. The join uses `validate="one_to_one"`, so a key problem raises immediately.

**Q: pandas 3 changed things. Did it matter?**
Yes. Copy-on-write is the default, so the code avoids chained assignment. Several deprecations
(`dayofweek` → `day_of_week`) were fixed so the tests run without warnings.

## 6. DuckDB

**Q: Why DuckDB rather than SQLite or PostgreSQL?**
It is an embedded, columnar, analytical database: a single file, no server, fast aggregations, native
Parquet export, and direct pandas interchange. That fits a read-heavy analytical workload deployed as a
single app. SQLite is row-oriented; PostgreSQL needs a server.

**Q: Did anything about DuckDB surprise you?**
Two DuckDB 2.0 behaviours, both caught by running the code:
- `fetchone()` leaves a result open, and a later `register()` fails. The fix is `database.scalar`, which
  always drains with `fetchall()`.
- Returning a `TIMESTAMPTZ` as a Python object needs `pytz`. That would have crashed the second real
  pipeline run. The query now uses `epoch_us()` and converts in Python.

## 7. Idempotency

**Q: How do you guarantee re-running doesn't duplicate data?**
- Primary keys on the UTC slot (and fuel), with `INSERT … ON CONFLICT DO UPDATE`.
- Incoming batches are deduplicated first. DuckDB cannot update the same row twice in one statement,
  so `upsert_intensity` raises if a batch has duplicate keys.
- `test_full_pipeline_is_idempotent_and_logs_rejections` runs the whole pipeline twice: the second run
  adds zero rows, and every table count except `pipeline_runs` is unchanged.

**Q: Why `COALESCE` in the upsert?**
Actuals arrive after forecasts. If a later payload has a null actual, `COALESCE(excluded.actual, existing)`
keeps the stored value. If the stored value was null, the new one fills it.

**Q: How does an incremental run know where to start?**
From the last half-hour that has an actual (`database.last_actual_slot`), not the last row. Half-hours
loaded before NESO published their actual are therefore fetched again and completed.

## 8. Rejected records

**Q: What do you store, and why?**
- **Stored fields:** dataset, best-effort timestamp, reason category, full Pydantic errors as JSON, raw
  payload, source URL, first and last run IDs, and a sighting count.
- **Why:** this makes every exclusion auditable and reproducible, because you can see exactly what was
  dropped and why.
- **No duplication:** `record_id` is a hash of dataset + payload, so re-runs increment `times_seen`
  instead of adding rows.

**Q: Why a "reason category" separate from the details?**
Grouping needs stable labels. Messages that embed timestamps would make every rejection unique, so
specifics are kept in `error_details`.

## 9. Timezones and daylight saving

**Q: How do you handle DST?**
- **Keys:** the key is always the **UTC** half-hour start, and local time is derived only for analysis.
- **Day lengths:** UK local days have 46 half-hours on the last Sunday in March, 50 on the last Sunday in
  October, and 48 otherwise. Tests check each case (`slots_per_local_day`).
- **The repeated hour:** on the October day, 01:00–01:30 local happens twice. Both are separate UTC
  slots, and both contribute to the 01:00 time-of-day profile.
- **Best windows:** the search uses the UTC grid, so a 2-hour window across the March change really is
  two hours, even though the local clock moves three hours (tested).

**Q: Why not use local timestamps as keys?**
They are ambiguous (repeated in October) and non-existent (skipped in March).

## 10. Generation quantities versus shares

**Q: The brief mentions MW. Do you use MW?**
No. The generation endpoint returns only percentage shares, so validation checks the shares sum to 100%
and the analysis works in shares. Deriving MW would need total generation or demand, which this API does
not provide. Inventing it would be fabrication.

## 11. EDA and correlation

**Q: Wind correlates strongly and negatively with intensity. Does wind cause lower intensity?**
Physically it plausibly displaces gas, but the correlation alone doesn't prove the size of the effect:
- **Compositional shares:** shares sum to 100, so when wind rises another share must fall.
- **Built-in link:** NESO calculates intensity from the generation mix using emission factors, so a strong
  correlation exists partly by construction.
- **Confounders:** weather and demand move several shares at once.

The notebook reports Pearson and Spearman and says all of this explicitly.

**Q: Why report medians and percentile bands?**
Averages hide variation. The notebook compares the daily swing in the mean with the average width of the
10th–90th percentile band within each half-hour. That shows whether variation between days outweighs
the typical daily pattern.

**Q: Why hour-matched weekday/weekend comparison?**
It compares like with like. Comparing raw means could be biased if missing data were concentrated in
particular hours. Even so, it is an association: weather on those specific weekends is a confounder.

**Q: Your confidence intervals: are they valid?**
They are normal approximations that assume independent observations. Half-hours are strongly
autocorrelated, so the intervals are too narrow. A block bootstrap would be better; this is listed as
future work.

**Q: How did you implement Spearman?**
As the Pearson correlation of average ranks, which is its definition. pandas' built-in version silently
requires SciPy, which the dashboard exposed at runtime. A test pins it against a hand-computed value
with ties.

## 12. Cleanest-window calculation

**Q: Explain `best_windows`.**
1. Reindex values to the complete UTC half-hour grid, so gaps become NaN rather than being bridged.
2. For a duration of k × 30 minutes, compute rolling sums and counts of valid half-hours, shifted so each
   row describes the window *starting* there.
3. Window mean = sum / valid count. All half-hours are 30 minutes, so this equals the duration-weighted
   mean.
4. Reject windows whose coverage (valid / k) is below the threshold, which is 100% by default.
5. Baseline = mean of all valid windows, the expected intensity if the load started at a random time.
   Report the best window, its percentage versus baseline, and a non-overlapping top-N.
6. Also report the typical best *start time of day*, averaged over all days.

**Q: Why two answers, a single best window and a typical start time?**
The single best window is a historical one-off, usually a very windy or sunny day. The typical start time
is the pattern someone can actually plan around. Neither is a forecast.

**Q: How did you test it?**
Hand-computed series: the exact best window and baseline value, the 30-minute edge case, gaps inside
windows at 100% and 50% coverage, gaps in timestamps, non-overlap, invalid durations, empty input, and a
window crossing the March clock change.

## 13. MAE and RMSE

**Q: Define them and say why you report both.**
With error e = forecast − actual:
- **MAE** = mean(|e|).
- **RMSE** = √mean(e²).
- **Bias** = mean(e).

RMSE weights large errors more. For normally distributed errors, RMSE/MAE ≈ 1.25; a larger ratio means
occasional big misses. Bias shows systematic over- or under-forecasting, and positive means over-forecast.

**Q: How do you know the metric code is right?**
Unit tests use hand-calculated values. As an end-to-end check, the synthetic generator adds forecast noise
with mean +4 and SD 18. The notebook recovered bias +4.0 and RMSE 18.5, against a theoretical
√(4² + 18²) ≈ 18.4.

**Q: Can you evaluate accuracy by forecast horizon?**
Not from history: the historical endpoint returns only the final forecast with no issue time. The pipeline
therefore stores the 48-hour forecast with its retrieval time on every run (`forecast_snapshots`). Once
actuals exist, `forecasting.align_snapshots` joins each forecast to its *target* half-hour and buckets it
by lead time. Until enough snapshots accumulate, the dashboard shows an explicit "not available yet"
state rather than invented numbers.

## 14. Automated testing

**Q: What do the tests cover, and how do you avoid hitting the API?**
82 tests. API calls are mocked with `respx`, the backoff sleep is injected, and the data come from
deterministic hand-written fixtures plus a seeded synthetic generator.

Dashboard tests render all seven pages with Streamlit's `AppTest`. The app was also driven in headless
Chromium. That caught a bug no unit test could: CSS that turned icons into raw text.

**Q: Did testing find real bugs?**
Yes. Examples:
- the DuckDB result-draining and `pytz` issues;
- pandas Spearman's hidden SciPy dependency;
- a wrong DST test fixture, where the test was wrong rather than the code;
- the icon CSS problem.

These make good viva material because they show why running code beats assuming.

## 15. CI and deployment

**Q: What does CI do?**
GitHub Actions on push and pull request, with read-only permissions:
- installs locked dependencies with uv on Python 3.15 and 3.12;
- runs Ruff lint and format checks, then pytest;
- executes the notebook against synthetic data as a smoke test.

Any failed step fails the build.

**Q: Why test on 3.12 too?**
3.15 is the latest stable release and the primary target. Hosting platforms often lag behind new Python
releases, so 3.12 is the declared and tested minimum.

**Q: How is it deployed, given Streamlit Cloud has no persistent disk?**
- The dashboard is read-only. A prebuilt `data/gridgreen.duckdb` is committed and opened read-only.
- Data refresh is a separate concern: the optional `refresh-data.yml` workflow runs the pipeline and
  commits the new snapshot.
- Trade-off: committing a binary repeatedly grows git history, so the schedule is off by default. Object
  storage is the scalable alternative.

## 16. Limitations

Be ready to state these without being asked:
- "Actual" is an estimate.
- There are no MW or demand figures.
- Results are national only.
- One year cannot separate season from weather.
- Correlation is not causation, and the shares are compositional.
- The confidence intervals are too narrow.
- There is no historical forecast horizon.
- The CI workflow and the deployment had not been run at the time of writing.

---

### Likely curveballs
* *"What would you do with another month?"* Regional analysis, block-bootstrap uncertainty, weather
  covariates, and a forward-looking recommender built on the live 48-hour forecast, clearly separated from
  the historical analysis.
* *"Why not Airflow or dbt?"* A single scheduled job with idempotent loads doesn't justify an orchestrator.
  The run log and upserts give the needed restartability with far less complexity.
* *"Is your best window useful for EV charging tomorrow?"* As a habit, yes: the typical start time. As a
  guarantee, no. Tomorrow depends on tomorrow's weather, which is what the live forecast is for.

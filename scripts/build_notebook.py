"""Generate notebooks/gridgreen_eda.ipynb (kept as code so the notebook is reviewable in diffs)."""

from __future__ import annotations

from pathlib import Path

import nbformat as nbf

md = nbf.v4.new_markdown_cell
code = nbf.v4.new_code_cell
cells = []

cells += [
    md("""# GridGreen: exploratory data analysis

## 1. Research question and objectives
**When is Britain's electricity cleanest, and what makes it that way?**

Objectives:

* **A.** Describe the typical daily carbon-intensity pattern and its variability.
* **B.** Compare months and seasons.
* **C.** Relate intensity to the generation mix.
* **D.** Compare weekdays with weekends.
* **E.** Find the historically cleanest windows for flexible loads.
* **F.** Evaluate the published forecast against NESO's estimated actual.

Every number below is computed from the DuckDB database produced by the ETL pipeline. Interpretation cells
print text generated from the data, so the narrative cannot drift from the numbers. Re-run the whole
notebook after each pipeline run."""),
    code("""import os
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.io as pio
from IPython.display import Markdown, display

from gridgreen import database
from gridgreen.analytics import (best_windows, day_type_comparison, fuel_correlations, heatmap_matrix,
                                 monthly_summary, profile, summary_stats)
from gridgreen.config import (ATTRIBUTION, DATA_SOURCE_DEMO, DEFAULT_DB_PATH, PROJECT_ROOT, FOSSIL_FUELS, SEASON_BY_MONTH,
                              ZERO_CARBON_FUELS)
from gridgreen.forecasting import align_snapshots, compute_metrics, horizon_metrics, metrics_by, published_forecast_pairs
from gridgreen.transform import build_analytical_frame, detect_missing_intervals, fuel_columns, slots_per_local_day
from gridgreen.ui import charts
from gridgreen.ui.theme import register_plotly_template

register_plotly_template()
pio.renderers.default = "plotly_mimetype+notebook"
pd.set_option("display.precision", 2)

def say(text: str) -> None:
    display(Markdown(text))"""),
    md("## 2. Dataset source and collection period"),
    code("""DB_PATH = Path(os.getenv("GRIDGREEN_DB_PATH", DEFAULT_DB_PATH))
if not DB_PATH.is_absolute():  # Jupyter runs from notebooks/, so resolve against the project root
    DB_PATH = PROJECT_ROOT / DB_PATH
if not DB_PATH.exists():
    raise FileNotFoundError(f"{DB_PATH} not found. Run: python scripts/run_pipeline.py --start 2025-10-01")

con = database.connect(DB_PATH, read_only=True)
SOURCE = database.get_metadata(con, "source")
intensity = database.read_intensity(con)
generation = database.read_generation(con)
runs = database.read_runs(con)
rejected = database.read_rejected(con)
snapshots = database.read_snapshots(con)
counts = database.table_counts(con)
con.close()

if SOURCE == DATA_SOURCE_DEMO:
    say("> **WARNING: this database contains SYNTHETIC demonstration data, not NESO data. "
        "Nothing in this notebook is a finding about the GB grid. Point GRIDGREEN_DB_PATH at a real "
        "pipeline database before writing conclusions.**")

df = build_analytical_frame(intensity, generation)
first, last = df["interval_start_utc"].min(), df["interval_start_utc"].max()
say(f"Source tag: `{SOURCE}`. Database: `{DB_PATH.name}`. Half-hours from **{first:%Y-%m-%d %H:%M} UTC** to "
    f"**{last:%Y-%m-%d %H:%M} UTC** ({df['local_date'].nunique()} local days). {ATTRIBUTION}")
pd.Series(counts, name="rows").to_frame()"""),
    md("""## 3. Data dictionary

| Column | Meaning |
|---|---|
| `interval_start_utc` | Start of the half-hour (UTC). The unique key. |
| `forecast` | NESO's published forecast intensity for that half-hour (gCO₂/kWh). |
| `actual` | NESO's *estimated* actual intensity (gCO₂/kWh). Not a direct measurement. |
| `intensity_index` | NESO band: very low, low, moderate, high or very high. |
| `share_<fuel>` | Percentage share of generation reported by the API. Shares, not MW. |
| `share_zero_carbon` | Sum of the zero-carbon fuel shares. |
| `share_fossil` | Sum of the fossil fuel shares. |
| `interval_start_local`, `hour`, `slot_of_day` | Europe/London wall-clock features. |
| `weekday`, `day_type`, `month`, `season` | Calendar features (meteorological seasons). |
| `forecast_error` | forecast − actual. Positive means over-forecast. |"""),
    code("""say(f"Zero-carbon group: {', '.join(ZERO_CARBON_FUELS)}. Fossil group: {', '.join(FOSSIL_FUELS)}. "
    "Biomass and imports are reported separately.")
df.dtypes.to_frame("dtype").T"""),
    md(
        "## 4. Data loading\nThe frame is built with the same `build_analytical_frame` used by the dashboard: a left join of generation onto intensity by UTC slot."
    ),
    code("df.head()"),
    md("## 5. Data-quality assessment"),
    code("""s, e = first.to_pydatetime(), (last + pd.Timedelta(minutes=30)).to_pydatetime()
missing_rows = detect_missing_intervals(df, s, e)
missing_actual = detect_missing_intervals(df, s, e, column="actual")
expected = len(missing_actual) + int(df["actual"].notna().sum())
no_gen = int(df["fuels_reported"].isna().sum()) if "fuels_reported" in df else len(df)
dup_keys = int(df["interval_start_utc"].duplicated().sum())
say(f"Expected half-hours: **{expected:,}**. Missing rows: **{len(missing_rows):,}**. "
    f"Missing actuals: **{len(missing_actual):,}** ({len(missing_actual) / expected:.2%}). "
    f"Half-hours without generation mix: **{no_gen:,}**. Duplicate keys after load: **{dup_keys}**. "
    f"Rejected payloads (all runs): **{len(rejected):,}**. Pipeline runs: **{len(runs)}**.")
spd = slots_per_local_day(s, e).iloc[1:-1]  # first and last local days are partial, so excluded
say("Half-hours per **complete** local day (DST check; partial first/last days excluded): "
    + ", ".join(f"{v} day(s) with {k}" for k, v in spd.value_counts().sort_index().items())
    + ". Expect 46 on a March clock change, 50 on an October change, 48 otherwise.")
rejected.groupby(["dataset", "reason"]).size().rename("records").to_frame() if not rejected.empty else "No rejected records."
"""),
    md("""## 6. Cleaning and transformation
Cleaning happens in the pipeline, not here, so the dashboard and notebook use identical data:

* Records failing Pydantic validation are stored in `rejected_records`, never silently dropped.
* Duplicates are resolved deterministically by preferring rows that have an actual.
* Missing half-hours stay missing; nothing is imputed.
* Local-time features are derived from UTC, so DST days have 46 or 50 half-hours.

The only notebook-level step is restricting each analysis to rows with an estimated actual."""),
    code("""a = df.dropna(subset=["actual"])
say(f"Analysis rows with an actual: **{len(a):,}**.")"""),
    md("## 7. Univariate analysis"),
    code("""st_ = summary_stats(a)
say(f"Mean **{st_['mean']:.0f}**, median **{st_['median']:.0f}**, SD {st_['std']:.0f} gCO₂/kWh. "
    f"10th–90th percentile {st_['p10']:.0f}–{st_['p90']:.0f}. Minimum {st_['min']:.0f} "
    f"({st_['min_at']:%Y-%m-%d %H:%M} UTC), maximum {st_['max']:.0f} ({st_['max_at']:%Y-%m-%d %H:%M} UTC). "
    f"Skewness {a['actual'].skew():.2f}: " + ("roughly symmetric." if abs(a['actual'].skew()) < 0.5 else
    ("a long tail of high-intensity half-hours." if a['actual'].skew() > 0 else "a long tail of low-intensity half-hours.")))
charts.histogram(a["actual"], "Distribution of half-hourly intensity", "Carbon intensity (gCO₂/kWh)", vline=st_["mean"])"""),
    md("""## 8. Daily and hourly patterns (Research question A)
**Question.** What does a typical day look like?
**Method.** Group by local half-hour of day; show the mean, median and 10th–90th percentile band."""),
    code("""prof = profile(a, by="slot_of_day")
prof["time"] = [f"{x // 2:02d}:{30 * (x % 2):02d}" for x in prof["slot_of_day"]]
charts.band_line(prof, "time", "Typical day: intensity by time of day", "Time of day (UK local)")"""),
    code("""lo, hi = prof.loc[prof["mean"].idxmin()], prof.loc[prof["mean"].idxmax()]
spread = (prof["p90"] - prof["p10"]).mean()
say(f"On average the cleanest half-hour of the day starts at **{lo['time']}** ({lo['mean']:.0f} gCO₂/kWh) and the "
    f"most intensive at **{hi['time']}** ({hi['mean']:.0f}). The daily swing in the mean is "
    f"{hi['mean'] - lo['mean']:.0f} gCO₂/kWh, but the average 10th–90th percentile width within a single "
    f"half-hour is {spread:.0f} gCO₂/kWh. Variation **between days** is therefore "
    f"{'larger' if spread > hi['mean'] - lo['mean'] else 'smaller'} than the typical within-day pattern, "
    "which is why averages hide a lot.")"""),
    code("charts.grid_strip(a)"),
    md(
        "**Limitation.** Each day's profile mixes weather regimes; a mean profile is not what any single day looks like."
    ),
    md("""## 9. Monthly and seasonal comparisons (Research question B)
**Method.** Monthly summaries with sample sizes, month × hour heatmap, and seasonal distributions."""),
    code("""ms = monthly_summary(a)
ms"""),
    code("charts.heatmap(heatmap_matrix(a, 'year_month'), 'Mean intensity by month and hour', 'Month')"),
    code("charts.season_box(a)"),
    code("""ss = a.groupby("season", observed=True)["actual"].agg(["mean", "median", "count"])
days = a["local_date"].nunique()
best_s, worst_s = ss["mean"].idxmin(), ss["mean"].idxmax()
say(f"Cleanest season by mean: **{best_s}** ({ss.loc[best_s, 'mean']:.0f}); most intensive: **{worst_s}** "
    f"({ss.loc[worst_s, 'mean']:.0f}). The data cover **{days} days**"
    + (", i.e. at most one example of each season, so this describes these specific months and is **not** "
       "evidence of a long-term seasonal trend." if days < 2 * 365 else "."))
ss"""),
    md("""## 10. Generation-mix relationships (Research question C)
**Method.** Pearson and Spearman correlations of each fuel share with intensity, scatterplots, and intensity by
zero-carbon share band. Shares are compositional (they sum to 100%), so they are not independent."""),
    code("""corr = fuel_correlations(a)
corr"""),
    code("charts.correlation_bars(corr)"),
    code("charts.share_scatter(a, 'share_wind') if 'share_wind' in a else 'No wind share column.'"),
    code("""b = a.dropna(subset=["share_zero_carbon"]).copy()
b["band"] = pd.cut(b["share_zero_carbon"], bins=range(0, 101, 10), right=False)
band = b.groupby("band", observed=True)["actual"].agg(["mean", "count"])
fuels_only = corr[~corr["fuel"].isin(["zero_carbon", "fossil"])]
if len(fuels_only) >= 2:
    neg, pos = fuels_only.iloc[0], fuels_only.iloc[-1]
    say(f"Strongest negative association: **{neg['fuel']}** (r = {neg['pearson_r']:.2f}, ρ = {neg['spearman_rho']:.2f}); "
        f"strongest positive: **{pos['fuel']}** (r = {pos['pearson_r']:.2f}). These are correlations in observational "
        "data. NESO computes intensity from the mix using emission factors, so a strong link is expected by "
        "construction, and it does not show that changing one fuel alone would change intensity by the "
        "fitted slope.")
band"""),
    md("""## 11. Weekday versus weekend (Research question D)
**Method.** Compare overall and **hour-matched** means (weekend 14:00 vs weekday 14:00), with sample sizes and
approximate 95% intervals per hour."""),
    code("""dt = day_type_comparison(a)
hp = profile(a, by=["day_type", "hour"])
import plotly.graph_objects as go
fig = go.Figure()
for name, colour in (("Weekday", "#16845B"), ("Weekend", "#2B8CBE")):
    d = hp[hp["day_type"] == name]
    fig.add_trace(go.Scatter(x=d["hour"], y=d["mean"], name=f"{name} mean", line=dict(color=colour, width=2.4),
                             error_y=dict(type="data", symmetric=False, array=d["ci_high"] - d["mean"],
                                          arrayminus=d["mean"] - d["ci_low"], thickness=1)))
fig.update_layout(title="Hour-matched weekday vs weekend profile (bars: approx. 95% CI)",
                  xaxis_title="Hour (UK local)", yaxis_title="Carbon intensity (gCO₂/kWh)")
fig"""),
    code("""if dt["available"]:
    say(f"Weekday mean {dt['weekday_mean']:.0f} (n = {dt['weekday_n']:,} half-hours, {dt['weekday_days']} days); "
        f"weekend mean {dt['weekend_mean']:.0f} (n = {dt['weekend_n']:,}, {dt['weekend_days']} days). Hour-matched "
        f"difference (weekend − weekday): **{dt['hour_matched_diff']:+.0f} gCO₂/kWh**; weekends were lower in "
        f"{dt['hours_weekend_lower']} of {dt['hours_compared']} hours. Half-hours are strongly autocorrelated and "
        "weekends are few, so the intervals above are optimistic. Lower weekend demand is a plausible mechanism, "
        "but weather on those particular weekends is a confounder; this is not proof of a weekend effect.")"""),
    md("""## 12. Cleanest historical window (Research question E)
**Method** (`analytics.best_windows`): place values on the complete UTC half-hour grid; for each start, average
the k = duration / 30 slots (equal-length slots, so this is the duration-weighted mean); keep windows with full
coverage; compare with the mean of all valid windows (a random-start baseline)."""),
    code("""rows = []
for minutes in (30, 60, 120, 240):
    r = best_windows(a, minutes, min_coverage=1.0)
    if r.available:
        typ = r.typical.loc[r.typical["mean"].idxmin()]
        rows.append({"duration_h": minutes / 60, "best_start_local": r.best["start_local"],
                     "best_mean": r.best["mean_intensity"], "baseline": r.baseline,
                     "best_vs_baseline_pct": r.pct_vs_baseline, "valid_intervals": int(r.best["n_valid"]),
                     "candidates": r.n_candidates, "excluded_incomplete": r.n_rejected_incomplete,
                     "typical_best_start": typ["start_time"], "typical_vs_baseline_pct": typ["pct_vs_baseline"]})
bw = pd.DataFrame(rows)
bw"""),
    code("""r2 = best_windows(a, 120)
charts.typical_start_chart(r2.typical, r2.typical.loc[r2.typical['mean'].idxmin(), 'start_time'], r2.baseline, 2)"""),
    code("""if not bw.empty:
    row = bw[bw["duration_h"] == 2].iloc[0] if (bw["duration_h"] == 2).any() else bw.iloc[0]
    say(f"For a {row['duration_h']:g}-hour load, the single lowest historical window started "
        f"**{row['best_start_local']:%a %d %b %Y %H:%M}** UK time at {row['best_mean']:.0f} gCO₂/kWh, "
        f"{row['best_vs_baseline_pct']:+.0f}% versus the {row['baseline']:.0f} gCO₂/kWh random-start baseline. "
        f"As a repeatable habit, starting at **{row['typical_best_start']}** was on average "
        f"{row['typical_vs_baseline_pct']:+.0f}% versus baseline. This is a historical analytical result, not a "
        "prediction of future conditions.")"""),
    md("""## 13. Forecast evaluation (Research question F)
Error = forecast − actual (positive = over-forecast). The historical endpoint gives only the **final**
published forecast with no issue time, so horizon analysis uses the `forecast_snapshots` table when available."""),
    code("""pairs = published_forecast_pairs(a)
m = compute_metrics(pairs["forecast"], pairs["actual"]) if not pairs.empty else None
if m:
    say(f"n = **{m.n:,}** paired half-hours. MAE **{m.mae:.1f}**, RMSE **{m.rmse:.1f}**, bias **{m.bias:+.1f}** "
        f"gCO₂/kWh. Median absolute error {m.median_abs_error:.1f}, 95th percentile {m.p95_abs_error:.1f}. "
        f"RMSE/MAE = {m.rmse / m.mae:.2f} (≈1.25 for normal errors; larger implies occasional big misses).")
    display(charts.histogram(pairs["error"], "Forecast error distribution", "Forecast − actual (gCO₂/kWh)", vline=0))
    display(metrics_by(pairs, "hour"))
else:
    say("No forecast/actual pairs are available, so forecast accuracy cannot be evaluated.")"""),
    code("""aligned = align_snapshots(snapshots, intensity) if not snapshots.empty else pd.DataFrame()
if aligned.empty:
    say(f"**Horizon analysis unavailable.** {snapshots['run_id'].nunique() if not snapshots.empty else 0} snapshot(s) "
        "stored, none matched to a published actual yet. No values are fabricated; schedule the pipeline to "
        "accumulate snapshots.")
else:
    display(horizon_metrics(aligned))"""),
    md("""## 14. Findings, limitations and conclusions

### Findings
The cell below assembles the findings from the computed results. **Before submitting, read it against the
charts above and write your own interpretation underneath.**"""),
    code("""lines = [f"* Period: {first:%d %b %Y} to {last:%d %b %Y} ({days} days); source `{SOURCE}`."]
lines.append(f"* Mean intensity {st_['mean']:.0f} gCO₂/kWh (median {st_['median']:.0f}).")
lines.append(f"* Cleanest time of day on average: {lo['time']}; most intensive: {hi['time']}.")
lines.append(f"* Cleanest season in this sample: {best_s}; most intensive: {worst_s} (descriptive only).")
if len(fuels_only) >= 2:
    lines.append(f"* Intensity fell most with the {neg['fuel']} share and rose most with the {pos['fuel']} share (correlational).")
if dt["available"]:
    lines.append(f"* Hour-matched weekend − weekday difference: {dt['hour_matched_diff']:+.0f} gCO₂/kWh.")
if not bw.empty:
    lines.append(f"* Best typical start for a {row['duration_h']:g} h load: {row['typical_best_start']} "
                 f"({row['typical_vs_baseline_pct']:+.0f}% vs baseline).")
if m:
    lines.append(f"* Published forecast: MAE {m.mae:.1f}, RMSE {m.rmse:.1f}, bias {m.bias:+.1f} gCO₂/kWh.")
if SOURCE == DATA_SOURCE_DEMO:
    lines.insert(0, "* **SYNTHETIC DATA: these lines are placeholders produced by the demo generator.**")
say("\\n".join(lines))"""),
    md("""### Limitations
* 'Actual' is a NESO estimate; forecasts are compared with an estimate, not a meter reading.
* Generation is reported as percentage shares only, so absolute output and demand cannot be analysed.
* Correlation is not causation, and shares are compositional.
* A single year cannot separate seasonal patterns from that year's weather.
* Confidence intervals ignore autocorrelation and are too narrow.
* Forecast horizon cannot be recovered from history.
* Results are national; regional intensity can differ substantially.

### Conclusion
*(Write your conclusion here, after reviewing the real-data results above.)*"""),
]

nb = nbf.v4.new_notebook(
    cells=cells,
    metadata={
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python"},
    },
)
out = Path(__file__).resolve().parents[1] / "notebooks" / "gridgreen_eda.ipynb"
out.parent.mkdir(parents=True, exist_ok=True)
nbf.write(nb, out)
print(f"wrote {out}")

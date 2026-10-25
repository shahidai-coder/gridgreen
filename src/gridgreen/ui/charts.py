"""Reusable Plotly figure builders. Every chart carries units and a title."""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from gridgreen.ui.theme import FUEL_ORDER, P, fuel_color

UNIT = "gCO₂/kWh"


def _rgba(hex_color: str, alpha: float) -> str:
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i : i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r},{g},{b},{alpha})"


def band_line(
    df: pd.DataFrame,
    x: str,
    title: str,
    x_title: str,
    show_median: bool = True,
    low: str = "p10",
    high: str = "p90",
    band_label: str = "10th–90th percentile",
) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df[x], y=df[high], line=dict(width=0), hoverinfo="skip", showlegend=False))
    fig.add_trace(
        go.Scatter(
            x=df[x],
            y=df[low],
            fill="tonexty",
            fillcolor=_rgba(P.EMERALD, 0.14),
            line=dict(width=0),
            name=band_label,
            hoverinfo="skip",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=df[x],
            y=df["mean"],
            name="Mean",
            line=dict(color=P.EMERALD, width=2.6),
            hovertemplate="%{y:.0f} " + UNIT + "<extra>Mean</extra>",
        )
    )
    if show_median and "median" in df:
        fig.add_trace(
            go.Scatter(
                x=df[x],
                y=df["median"],
                name="Median",
                line=dict(color=P.FOREST, width=1.6, dash="dot"),
                hovertemplate="%{y:.0f} " + UNIT + "<extra>Median</extra>",
            )
        )
    fig.update_layout(title=title, xaxis_title=x_title, yaxis_title=f"Carbon intensity ({UNIT})")
    return fig


def time_series(df: pd.DataFrame, title: str, stat: str = "mean", show_range: bool = True) -> go.Figure:
    fig = go.Figure()
    if show_range and {"min", "max"} <= set(df.columns) and len(df) < 3000:
        fig.add_trace(
            go.Scatter(
                x=df["interval_start_local"],
                y=df["max"],
                line=dict(width=0),
                hoverinfo="skip",
                showlegend=False,
            )
        )
        fig.add_trace(
            go.Scatter(
                x=df["interval_start_local"],
                y=df["min"],
                fill="tonexty",
                fillcolor=_rgba(P.EMERALD, 0.12),
                line=dict(width=0),
                name="Range (min–max)",
                hoverinfo="skip",
            )
        )
    trace = go.Scattergl if len(df) > 3000 else go.Scatter
    fig.add_trace(
        trace(
            x=df["interval_start_local"],
            y=df[stat],
            name=stat.capitalize(),
            line=dict(color=P.EMERALD, width=1.8 if len(df) > 500 else 2.4),
            hovertemplate="%{y:.0f} " + UNIT + f"<extra>{stat}</extra>",
        )
    )
    fig.update_layout(title=title, xaxis_title="Time (UK local)", yaxis_title=f"Carbon intensity ({UNIT})")
    return fig


def grid_strip(df: pd.DataFrame, value: str = "actual", title: str | None = None) -> go.Figure:
    """Signature view: every half-hour as a cell, day by time of day."""
    d = df.dropna(subset=[value])
    mat = d.pivot_table(index="time_label", columns="local_date", values=value, aggfunc="mean")
    mat = mat.sort_index()
    fig = go.Figure(
        go.Heatmap(
            z=mat.to_numpy(),
            x=[pd.Timestamp(c) for c in mat.columns],
            y=mat.index,
            colorscale=P.INTENSITY_SCALE,
            zmin=float(np.nanpercentile(mat, 2)) if mat.size else 0,
            zmax=float(np.nanpercentile(mat, 98)) if mat.size else 1,
            colorbar=dict(title=dict(text=UNIT, side="right"), thickness=12, outlinewidth=0),
            hovertemplate="%{x|%a %d %b %Y}, %{y}<br><b>%{z:.0f}</b> " + UNIT + "<extra></extra>",
        )
    )
    fig.update_layout(
        title=title or "Every half-hour in the selected period",
        xaxis_title="Date",
        yaxis_title="Time of day (UK local)",
        hovermode="closest",
        height=420,
    )
    fig.update_yaxes(autorange="reversed", nticks=9, showgrid=False)
    fig.update_xaxes(showgrid=False)
    return fig


def heatmap(
    mat: pd.DataFrame, title: str, y_title: str, x_title: str = "Hour of day (UK local)"
) -> go.Figure:
    fig = go.Figure(
        go.Heatmap(
            z=mat.to_numpy(),
            x=list(mat.columns),
            y=[str(i) for i in mat.index],
            colorscale=P.INTENSITY_SCALE,
            colorbar=dict(title=dict(text=UNIT, side="right"), thickness=12, outlinewidth=0),
            hovertemplate="%{y}, %{x}:00<br><b>%{z:.0f}</b> " + UNIT + "<extra></extra>",
        )
    )
    fig.update_layout(
        title=title,
        xaxis_title=x_title,
        yaxis_title=y_title,
        hovermode="closest",
        height=max(300, 34 * len(mat) + 120),
    )
    fig.update_yaxes(autorange="reversed", showgrid=False, type="category")
    fig.update_xaxes(showgrid=False, dtick=2)
    return fig


def season_box(df: pd.DataFrame, value: str = "actual") -> go.Figure:
    fig = go.Figure()
    for season in df["season"].cat.categories:
        vals = df.loc[df["season"] == season, value].dropna()
        if len(vals):
            fig.add_trace(
                go.Box(
                    y=vals,
                    name=f"{season} (n={len(vals):,})",
                    marker_color=P.EMERALD,
                    line=dict(width=1.4),
                    boxmean=True,
                    fillcolor=_rgba(P.EMERALD, 0.18),
                )
            )
    fig.update_layout(
        title="Distribution by meteorological season",
        yaxis_title=f"Carbon intensity ({UNIT})",
        showlegend=False,
        hovermode="closest",
    )
    return fig


def histogram(
    values: pd.Series, title: str, x_title: str, color: str = P.EMERALD, vline: float | None = None
) -> go.Figure:
    fig = go.Figure(
        go.Histogram(
            x=values.dropna(),
            nbinsx=50,
            marker_color=_rgba(color, 0.8),
            marker_line=dict(color="white", width=0.5),
            hovertemplate="%{x}<br>%{y:,} half-hours<extra></extra>",
        )
    )
    if vline is not None:
        fig.add_vline(x=vline, line=dict(color=P.FOREST, dash="dot", width=1.5))
    fig.update_layout(
        title=title, xaxis_title=x_title, yaxis_title="Number of half-hours", hovermode="closest", bargap=0.02
    )
    return fig


def stacked_shares(shares: pd.DataFrame, title: str) -> go.Figure:
    fig = go.Figure()
    cols = [f for f in FUEL_ORDER if f in shares.columns] + [c for c in shares.columns if c not in FUEL_ORDER]
    for fuel in cols:
        fig.add_trace(
            go.Scatter(
                x=shares.index,
                y=shares[fuel],
                name=fuel.capitalize(),
                stackgroup="one",
                line=dict(width=0.5, color=fuel_color(fuel)),
                fillcolor=fuel_color(fuel),
                hovertemplate="%{y:.1f}%<extra>" + fuel + "</extra>",
            )
        )
    fig.update_layout(
        title=title,
        xaxis_title="Time (UK local)",
        yaxis_title="Share of generation (%)",
        yaxis_range=[0, 100],
    )
    return fig


def mean_share_bars(means: pd.Series, title: str) -> go.Figure:
    means = means.sort_values()
    fig = go.Figure(
        go.Bar(
            x=means.to_numpy(),
            y=[f.capitalize() for f in means.index],
            orientation="h",
            marker_color=[fuel_color(f) for f in means.index],
            hovertemplate="%{y}: %{x:.1f}%<extra></extra>",
        )
    )
    fig.update_layout(
        title=title,
        xaxis_title="Mean share of generation (%)",
        yaxis_title=None,
        hovermode="closest",
        height=max(280, 30 * len(means) + 110),
    )
    return fig


def share_scatter(df: pd.DataFrame, share_col: str, value: str = "actual") -> go.Figure:
    d = df[[share_col, value, "interval_start_local"]].dropna()
    fuel = share_col.removeprefix("share_")
    sample = d.sample(min(len(d), 6000), random_state=0) if len(d) else d
    fig = go.Figure(
        go.Scattergl(
            x=sample[share_col],
            y=sample[value],
            mode="markers",
            marker=dict(size=4, color=_rgba(fuel_color(fuel), 0.35)),
            customdata=sample["interval_start_local"].dt.strftime("%d %b %Y %H:%M"),
            hovertemplate="%{customdata}<br>" + fuel + " %{x:.1f}%<br>%{y:.0f} " + UNIT + "<extra></extra>",
            name="Half-hours",
        )
    )
    if len(d) > 2 and d[share_col].nunique() > 1:
        slope, intercept = np.polyfit(d[share_col], d[value], 1)
        xs = np.linspace(d[share_col].min(), d[share_col].max(), 50)
        fig.add_trace(
            go.Scatter(
                x=xs,
                y=slope * xs + intercept,
                mode="lines",
                name="Least-squares line",
                line=dict(color=P.FOREST, width=2),
                hovertemplate=f"slope {slope:.2f} {UNIT} per pp<extra></extra>",
            )
        )
    note = f" (random sample of {len(sample):,} of {len(d):,})" if len(sample) < len(d) else ""
    fig.update_layout(
        title=f"{fuel.capitalize()} share vs carbon intensity{note}",
        xaxis_title=f"{fuel.capitalize()} share of generation (%)",
        yaxis_title=f"Carbon intensity ({UNIT})",
        hovermode="closest",
    )
    return fig


def correlation_bars(corr: pd.DataFrame) -> go.Figure:
    colors = [P.EMERALD if r < 0 else P.ERROR for r in corr["pearson_r"]]
    fig = go.Figure(
        go.Bar(
            x=corr["pearson_r"],
            y=[f.replace("_", " ").capitalize() for f in corr["fuel"]],
            orientation="h",
            marker_color=colors,
            customdata=np.stack([corr["spearman_rho"], corr["n"]], axis=1),
            hovertemplate="%{y}<br>Pearson r = %{x:.2f}<br>Spearman ρ = %{customdata[0]:.2f}"
            "<br>n = %{customdata[1]:,}<extra></extra>",
        )
    )
    fig.add_vline(x=0, line=dict(color=P.BORDER, width=1))
    fig.update_layout(
        title="Correlation of each fuel share with carbon intensity",
        xaxis_title="Pearson correlation coefficient (r)",
        xaxis_range=[-1, 1],
        hovermode="closest",
        height=max(300, 30 * len(corr) + 110),
    )
    return fig


def typical_start_chart(
    typical: pd.DataFrame, best_time: str | None, baseline: float, hours: float
) -> go.Figure:
    """Line (not bars) so a non-zero y-axis does not exaggerate differences."""
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=typical["start_time"],
            y=typical["mean"],
            mode="lines+markers",
            name="Mean by start time",
            line=dict(color=P.EMERALD, width=2.4),
            marker=dict(size=5, color=P.EMERALD),
            customdata=np.stack([typical["n"], typical["pct_vs_baseline"]], axis=1),
            hovertemplate="Start %{x}<br>Mean %{y:.0f} "
            + UNIT
            + "<br>%{customdata[1]:+.1f}% vs baseline<br>%{customdata[0]:,} days<extra></extra>",
        )
    )
    if best_time is not None:
        row = typical.loc[typical["start_time"] == best_time].iloc[0]
        fig.add_trace(
            go.Scatter(
                x=[best_time],
                y=[row["mean"]],
                mode="markers",
                name="Lowest typical start",
                marker=dict(size=14, color=P.LIME, line=dict(color=P.FOREST, width=2)),
                hovertemplate="Best start %{x}<br>%{y:.0f} " + UNIT + "<extra></extra>",
            )
        )
    fig.add_hline(
        y=baseline,
        line=dict(color=P.TEXT_2, dash="dot", width=1.2),
        annotation_text=f"Baseline (random start) {baseline:.0f}",
        annotation_position="bottom left",
        annotation_font=dict(color=P.TEXT_2, size=12),
        annotation_bgcolor="rgba(255,255,255,0.85)",
    )
    fig.update_layout(
        title=f"Average intensity of a {hours:g}-hour load by start time",
        xaxis_title="Start time (UK local)",
        yaxis_title=f"Mean carbon intensity ({UNIT})",
        hovermode="closest",
    )
    fig.update_xaxes(nticks=12)
    return fig


def candidate_windows_chart(cands: pd.DataFrame, top: pd.DataFrame) -> go.Figure:
    d = cands if len(cands) <= 20000 else cands.iloc[:: len(cands) // 20000 + 1]
    fig = go.Figure(
        go.Scattergl(
            x=d["start_local"],
            y=d["mean_intensity"],
            mode="lines",
            line=dict(color=_rgba(P.EMERALD, 0.55), width=1),
            name="All valid windows",
            hovertemplate="%{x|%d %b %Y %H:%M}<br>%{y:.0f} " + UNIT + "<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=top["start_local"],
            y=top["mean_intensity"],
            mode="markers",
            marker=dict(size=11, color=P.LIME, line=dict(color=P.FOREST, width=1.5)),
            name="Lowest non-overlapping windows",
            hovertemplate="%{x|%a %d %b %Y %H:%M}<br><b>%{y:.0f}</b> " + UNIT + "<extra></extra>",
        )
    )
    fig.update_layout(
        title="Every candidate window in the period, by start time",
        xaxis_title="Window start (UK local)",
        yaxis_title=f"Mean carbon intensity ({UNIT})",
        hovermode="closest",
    )
    return fig


def forecast_scatter(pairs: pd.DataFrame) -> go.Figure:
    d = pairs.sample(min(len(pairs), 8000), random_state=0)
    lo = float(min(d["forecast"].min(), d["actual"].min()))
    hi = float(max(d["forecast"].max(), d["actual"].max()))
    fig = go.Figure(
        go.Scattergl(
            x=d["actual"],
            y=d["forecast"],
            mode="markers",
            marker=dict(size=4, color=_rgba(P.EMERALD, 0.3)),
            name="Half-hours",
            hovertemplate="Actual %{x:.0f}<br>Forecast %{y:.0f}<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=[lo, hi],
            y=[lo, hi],
            mode="lines",
            name="Perfect forecast (y = x)",
            line=dict(color=P.FOREST, dash="dot", width=1.5),
            hoverinfo="skip",
        )
    )
    fig.update_layout(
        title="Published forecast vs NESO estimated actual",
        xaxis_title=f"Actual ({UNIT})",
        yaxis_title=f"Forecast ({UNIT})",
        hovermode="closest",
    )
    return fig


def bar(
    df: pd.DataFrame,
    x: str,
    y: str,
    title: str,
    x_title: str,
    y_title: str,
    color: str = P.EMERALD,
    hover_suffix: str = "",
) -> go.Figure:
    fig = go.Figure(
        go.Bar(
            x=df[x],
            y=df[y],
            marker_color=color,
            hovertemplate="%{x}<br>%{y:.1f}" + hover_suffix + "<extra></extra>",
        )
    )
    fig.update_layout(title=title, xaxis_title=x_title, yaxis_title=y_title, hovermode="closest")
    return fig

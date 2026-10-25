"""Design tokens, global CSS and the Plotly template for GridGreen."""

from __future__ import annotations

import plotly.graph_objects as go
import plotly.io as pio

FOREST = "#12352B"
EMERALD = "#16845B"
LIME = "#B9E769"
CANVAS = "#F5F7F2"
SURFACE = "#FFFFFF"
TEXT = "#17231F"
TEXT_2 = "#65736B"
BORDER = "#DFE6DE"
ERROR = "#C64C45"
SAND = "#EFE6D2"

# Design choices for readability, not official NESO colours.
FUEL_COLORS = {
    "wind": "#2B8CBE",
    "solar": "#E9B949",
    "gas": "#D96C54",
    "nuclear": "#8066B3",
    "hydro": "#4A90A4",
    "biomass": "#7A9A57",
    "imports": "#9AA5A0",
    "coal": "#4B4B4B",
    "other": "#C7CFC9",
    "storage": "#6FB7B0",
    "zero_carbon": EMERALD,
    "fossil": "#B8573F",
}
FUEL_ORDER = ["nuclear", "wind", "solar", "hydro", "biomass", "imports", "other", "storage", "gas", "coal"]

# Low intensity reads green (clean), high reads warm red. Mid stop is a quiet sand.
INTENSITY_SCALE = [[0.0, "#0F6B49"], [0.25, "#4FA47A"], [0.5, SAND], [0.75, "#E09A6E"], [1.0, ERROR]]

FONT_STACK = "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"
HEADING_STACK = "Manrope, Inter, -apple-system, 'Segoe UI', sans-serif"


def fuel_color(fuel: str) -> str:
    return FUEL_COLORS.get(fuel, "#B5BDB7")


def register_plotly_template() -> None:
    axis = dict(
        gridcolor="#EAEFE8",
        linecolor=BORDER,
        zerolinecolor=BORDER,
        ticks="outside",
        tickcolor=BORDER,
        tickfont=dict(size=12, color=TEXT_2),
        title_font=dict(size=12, color=TEXT_2),
    )
    pio.templates["gridgreen"] = go.layout.Template(
        layout=go.Layout(
            font=dict(family=FONT_STACK, size=13, color=TEXT),
            title=dict(
                font=dict(family=HEADING_STACK, size=16, color=TEXT),
                x=0,
                xanchor="left",
                y=0.97,
                yanchor="top",
                pad=dict(l=2),
            ),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            colorway=[EMERALD, "#2B8CBE", "#E9B949", "#D96C54", "#8066B3", "#4A90A4", FOREST],
            xaxis=axis,
            yaxis=axis,
            hoverlabel=dict(bgcolor=SURFACE, bordercolor=BORDER, font=dict(family=FONT_STACK, color=TEXT)),
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.0,
                xanchor="left",
                x=0,
                font=dict(size=12, color=TEXT_2),
                bgcolor="rgba(0,0,0,0)",
            ),
            margin=dict(l=8, r=8, t=56, b=8),
            hovermode="x unified",
        )
    )
    pio.templates.default = "gridgreen"


GLOBAL_CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Manrope:wght@600;700;800&display=swap');

html, body, .stApp, .stMarkdown, button, input, select, textarea, label {{
  font-family: {FONT_STACK};
}}
/* Keep Streamlit's icon font: overriding it turns icon ligatures into raw text. */
[data-testid="stIconMaterial"], .material-symbols-rounded {{
  font-family: "Material Symbols Rounded" !important;
}}
/* Leave room for Streamlit's top toolbar. On Streamlit Community Cloud it carries the
   Share / star / edit / GitHub buttons and is taller than in local runs. */
.block-container {{ padding-top: 4.75rem; padding-bottom: 3rem; max-width: 1320px; }}
h1, h2, h3, h4 {{ font-family: {HEADING_STACK}; color: {TEXT}; letter-spacing: -0.01em; }}
h1 {{ font-size: 30px !important; font-weight: 800 !important; }}
h2 {{ font-size: 21px !important; font-weight: 700 !important; margin-top: 0.6rem; }}
h3 {{ font-size: 17px !important; font-weight: 700 !important; }}
p, li {{ font-size: 15px; line-height: 1.6; }}

section[data-testid="stSidebar"] {{ background: {SURFACE}; border-right: 1px solid {BORDER}; }}
section[data-testid="stSidebar"] [data-testid="stSidebarNavLink"] {{ border-radius: 10px; }}
section[data-testid="stSidebar"] [data-testid="stSidebarNavLink"][aria-current="page"] {{
  background: #E7F2EC;
}}
section[data-testid="stSidebar"] [data-testid="stSidebarNavLink"][aria-current="page"] span {{
  color: {FOREST}; font-weight: 600;
}}

.gg-tagline {{ color: {TEXT_2}; font-size: 12.5px; margin: 0 0 6px 0; }}

.gg-topbar {{ display: flex; flex-wrap: wrap; justify-content: space-between; align-items: flex-end;
  gap: 12px; border-bottom: 1px solid {BORDER}; padding-bottom: 14px; margin-bottom: 22px; }}
.gg-topbar h1 {{ margin: 0; padding: 0; line-height: 1.15; }}
.gg-topbar .gg-period {{ color: {TEXT_2}; font-size: 14px; margin-top: 4px; }}
.gg-status {{ display: inline-flex; align-items: center; gap: 8px; font-size: 13px; color: {TEXT_2};
  background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 999px; padding: 6px 12px; }}
.gg-dot {{ width: 8px; height: 8px; border-radius: 50%; background: {EMERALD}; display: inline-block; }}
.gg-dot.warn {{ background: #D9A23B; }} .gg-dot.bad {{ background: {ERROR}; }}

@property --gg-n {{ syntax: "<integer>"; initial-value: 0; inherits: false; }}
.gg-count {{ --gg-n: var(--to); counter-reset: ggn var(--gg-n); animation: gg-count 1.1s cubic-bezier(.2,.7,.2,1) both; }}
.gg-count::after {{ content: counter(ggn); }}
@keyframes gg-count {{ from {{ --gg-n: 0; }} }}
.gg-sr {{ position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; }}
@keyframes gg-rise {{ from {{ opacity: 0; transform: translateY(8px); }} to {{ opacity: 1; transform: none; }} }}
.gg-kpi {{ animation: gg-rise .5s cubic-bezier(.2,.7,.2,1) both; transition: transform .18s ease, box-shadow .18s ease; }}
.gg-kpi:hover {{ transform: translateY(-2px); box-shadow: 0 8px 22px rgba(18,53,43,.08); }}
.gg-hero {{ animation: gg-rise .6s cubic-bezier(.2,.7,.2,1) both; }}
.gg-dot {{ position: relative; }}
.gg-dot:not(.warn):not(.bad)::after {{ content: ""; position: absolute; inset: -4px; border-radius: 50%;
  border: 2px solid {EMERALD}; animation: gg-pulse 2.4s ease-out infinite; }}
@keyframes gg-pulse {{ from {{ transform: scale(.5); opacity: .7; }} to {{ transform: scale(1.6); opacity: 0; }} }}
.gg-kpi {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 14px; padding: 16px 18px;
  height: 100%; }}
.gg-kpi-label {{ color: {TEXT_2}; font-size: 13px; font-weight: 500; }}
.gg-kpi-value {{ font-family: {HEADING_STACK}; font-size: 30px; font-weight: 800; color: {TEXT};
  line-height: 1.2; margin-top: 4px; font-variant-numeric: tabular-nums; }}
.gg-kpi-value small {{ font-size: 14px; font-weight: 600; color: {TEXT_2}; margin-left: 4px; }}
.gg-kpi-sub {{ color: {TEXT_2}; font-size: 12.5px; margin-top: 6px; }}

.gg-hero {{ background: {FOREST}; color: #F1F6F0; border-radius: 16px; padding: 22px 24px;
  display: grid; grid-template-columns: minmax(0, 1.1fr) minmax(0, 1fr); gap: 20px; }}
.gg-hero .gg-h-label {{ color: #B9CBBF; font-size: 13px; }}
.gg-hero .gg-h-value {{ font-family: {HEADING_STACK}; font-size: 52px; font-weight: 800; line-height: 1;
  margin: 8px 0 6px; font-variant-numeric: tabular-nums; }}
.gg-hero .gg-h-value small {{ font-size: 16px; font-weight: 600; color: #B9CBBF; margin-left: 6px; }}
.gg-hero .gg-h-meta {{ color: #CFDCD3; font-size: 13.5px; line-height: 1.5; }}
.gg-band {{ display: inline-block; background: {LIME}; color: {FOREST}; font-weight: 700; font-size: 12.5px;
  border-radius: 999px; padding: 3px 10px; margin-top: 6px; }}
.gg-hero .gg-h-right p {{ color: #E4ECE6; font-size: 15px; margin: 0 0 6px; }}
@media (max-width: 760px) {{
  .gg-hero {{ grid-template-columns: 1fr; }}
  .gg-hero .gg-h-value {{ font-size: 40px; }}
}}

.gg-insight {{ border-left: 3px solid {EMERALD}; background: {SURFACE}; border-radius: 0 12px 12px 0;
  padding: 12px 16px; margin: 6px 0 10px; border-top: 1px solid {BORDER}; border-right: 1px solid {BORDER};
  border-bottom: 1px solid {BORDER}; }}
.gg-insight p {{ margin: 0; font-size: 14.5px; }}
.gg-note {{ color: {TEXT_2}; font-size: 13px; line-height: 1.5; }}
.gg-demo {{ background: #FBEDEC; border: 1px solid #EBC3BF; color: #7A2B26; border-radius: 12px;
  padding: 10px 14px; font-size: 14px; margin-bottom: 16px; }}
.gg-empty {{ background: {SURFACE}; border: 1px dashed #C9D3C8; border-radius: 14px; padding: 28px;
  text-align: left; }}
.gg-empty h3 {{ margin-top: 0; }}
.gg-footer {{ color: {TEXT_2}; font-size: 12.5px; border-top: 1px solid {BORDER}; margin-top: 32px;
  padding-top: 12px; }}

[data-testid="stPlotlyChart"], [data-testid="stDataFrame"] {{
  background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 14px; padding: 6px 8px;
}}
div[data-testid="stExpander"] details {{
  border-radius: 12px; border-color: {BORDER}; background: {SURFACE};
}}
:focus-visible {{ outline: 2px solid {EMERALD} !important; outline-offset: 2px; }}
@media (prefers-reduced-motion: reduce) {{ * {{ transition: none !important; animation: none !important; }} }}
</style>
"""

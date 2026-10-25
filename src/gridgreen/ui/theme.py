"""Design tokens, global CSS and the Plotly template for GridGreen."""

from __future__ import annotations

from dataclasses import dataclass

import plotly.graph_objects as go
import plotly.io as pio

# ============================================================================
# BRAND PALETTE "Skyline Blue": the single place to change GridGreen's colours.
# Cool off-white canvas, white rounded cards, calm blues with a warm yellow accent.
# The intensity scale is blue (clean) to coral (carbon-intensive): a diverging
# scale that stays readable with red-green colour blindness. Mirrored (and
# checked by tests/test_theme.py) in .streamlit/config.toml and assets/*.svg.
# ============================================================================
CANVAS = "#F3F6FB"  # cool off-white page background
SURFACE = "#FFFFFF"  # cards, charts, sidebar
SURFACE_2 = "#EEF3FB"  # pale blue tint for raised / hover areas
BORDER = "#E1E7F0"
GRID = "#EBEFF6"  # chart gridlines
TEXT = "#16213A"  # deep navy text
TEXT_2 = "#55627A"  # secondary text (6.2:1 on white)
EMERALD = "#2563C9"  # primary brand blue: buttons, links, selected states (role name kept for stability)
ON_ACCENT = "#FFFFFF"  # text placed on the primary blue
ACCENT_2 = "#6D4FC2"  # secondary accent (violet)
MINT = "#A9C8F5"
LIME = "#D6E6FB"  # pale highlight chips
FOREST = "#183B73"  # deep navy for text on pale chips
LOW_BG, LOW_TEXT = "#DCE9FB", "#1D4E9E"  # "Low" status pill
YELLOW, YELLOW_TEXT = "#FFF1C9", "#5B4710"  # warm tip card (complements the blues)
WARNING = "#E0A43A"
ERROR = "#C9473F"
SAND = "#F5E9C9"  # pale midpoint of the intensity scale
SELECTED_BG = "#E2ECFB"  # sidebar selected page
HERO_GLOW = "#2563C9"
HERO_TEXT = "#F3F7FE"
HERO_TEXT_2 = "#C3D6F3"
DEMO_BG, DEMO_BORDER, DEMO_TEXT = "#FDEEEE", "#F3C9C9", "#8A2E2E"
SHADOW = "0 1px 2px rgba(22,33,58,.05), 0 10px 28px rgba(22,33,58,.08)"

# Illustration palette (hero scene). Changing the brand recolours the picture too.
SCENE = {
    "sky_top": "#E3EEFC",
    "sky_bottom": "#F7F3EA",
    "sun": "#FCE3A0",
    "hill_back": "#CFE0F6",
    "hill_mid": "#A9C7EE",
    "hill_front": "#7FA8E2",
    "water": "#BFD8F6",
    "tree": "#6E9BDB",
    "tree_2": "#8FB4E8",
    "trunk": "#8C7A6B",
    "turbine": "#FFFFFF",
    "turbine_edge": "#C9D4E5",
    "house": "#FFFDF8",
    "roof": "#F08A6C",
    "panel": "#2F4E8F",
    "window": "#BFD8F6",
    "door": "#C98F6B",
    "cloud": "#FFFFFF",
}

# Design choices for readability, not official NESO colours.
FUEL_COLORS = {
    "wind": "#3B82F6",
    "solar": "#F2B84B",
    "gas": "#F08A6C",
    "nuclear": "#8B7CE0",
    "hydro": "#38BDD6",
    "biomass": "#7DBF72",
    "imports": "#A3AEC4",
    "coal": "#5B6475",
    "other": "#CBD2DE",
    "storage": "#5CCFC0",
    "zero_carbon": EMERALD,
    "fossil": "#E0614F",
}
FUEL_ORDER = ["nuclear", "wind", "solar", "hydro", "biomass", "imports", "other", "storage", "gas", "coal"]

# Low intensity reads blue (clean), high reads coral. Pale sand midpoint. Colour-blind friendly.
INTENSITY_SCALE = [[0.0, "#2F6FD1"], [0.25, "#8DB7EE"], [0.5, SAND], [0.75, "#F5A86E"], [1.0, "#E0614F"]]

FONT_STACK = "Poppins, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"
HEADING_STACK = FONT_STACK


# ============================================================================
# LIGHT and DARK palettes. The module-level names above are the light palette
# (kept so config.toml, logos and tests can mirror them). Everything that draws
# asks pal() for the palette of the *current session*, so one viewer switching
# to dark mode never changes another viewer's page on a shared server.
# ============================================================================
THEME_KEY = "theme_dark"  # session_state key of the sidebar toggle (no "gg_" prefix: Reset keeps it)


@dataclass(frozen=True)
class Palette:
    name: str
    CANVAS: str
    SURFACE: str
    SURFACE_2: str
    BORDER: str
    GRID: str
    TEXT: str
    TEXT_2: str
    EMERALD: str
    ON_ACCENT: str
    ACCENT_2: str
    MINT: str
    LIME: str
    FOREST: str
    LOW_BG: str
    LOW_TEXT: str
    YELLOW: str
    YELLOW_TEXT: str
    WARNING: str
    ERROR: str
    SAND: str
    SELECTED_BG: str
    HERO_GLOW: str
    HERO_TEXT: str
    HERO_TEXT_2: str
    DEMO_BG: str
    DEMO_BORDER: str
    DEMO_TEXT: str
    SHADOW: str
    SCENE: dict
    FUEL_COLORS: dict
    INTENSITY_SCALE: list


LIGHT = Palette(
    name="light",
    CANVAS=CANVAS,
    SURFACE=SURFACE,
    SURFACE_2=SURFACE_2,
    BORDER=BORDER,
    GRID=GRID,
    TEXT=TEXT,
    TEXT_2=TEXT_2,
    EMERALD=EMERALD,
    ON_ACCENT=ON_ACCENT,
    ACCENT_2=ACCENT_2,
    MINT=MINT,
    LIME=LIME,
    FOREST=FOREST,
    LOW_BG=LOW_BG,
    LOW_TEXT=LOW_TEXT,
    YELLOW=YELLOW,
    YELLOW_TEXT=YELLOW_TEXT,
    WARNING=WARNING,
    ERROR=ERROR,
    SAND=SAND,
    SELECTED_BG=SELECTED_BG,
    HERO_GLOW=HERO_GLOW,
    HERO_TEXT=HERO_TEXT,
    HERO_TEXT_2=HERO_TEXT_2,
    DEMO_BG=DEMO_BG,
    DEMO_BORDER=DEMO_BORDER,
    DEMO_TEXT=DEMO_TEXT,
    SHADOW=SHADOW,
    SCENE=SCENE,
    FUEL_COLORS=FUEL_COLORS,
    INTENSITY_SCALE=INTENSITY_SCALE,
)

DARK = Palette(
    name="dark",
    CANVAS="#0B1220",
    SURFACE="#121B2E",
    SURFACE_2="#18233A",
    BORDER="#26334F",
    GRID="#1E2A44",
    TEXT="#E7EDF7",
    TEXT_2="#A3B1C8",
    EMERALD="#6EA8FE",
    ON_ACCENT="#0B1220",
    ACCENT_2="#B39DFF",
    MINT="#9CC3FF",
    LIME="#1F3A66",
    FOREST="#DCE8FF",
    LOW_BG="#173257",
    LOW_TEXT="#A9CBFF",
    YELLOW="#3A3216",
    YELLOW_TEXT="#FFE7A3",
    WARNING="#F5B83D",
    ERROR="#FF7B72",
    SAND="#E9DDB2",
    SELECTED_BG="#1C2D4D",
    HERO_GLOW="#2B4C86",
    HERO_TEXT="#F3F7FE",
    HERO_TEXT_2="#C3D6F3",
    DEMO_BG="#3A1820",
    DEMO_BORDER="#7A2E3B",
    DEMO_TEXT="#FFD3D8",
    SHADOW="0 1px 2px rgba(0,0,0,.35), 0 10px 28px rgba(0,0,0,.30)",
    SCENE={
        "sky_top": "#0F1C38",
        "sky_bottom": "#1D2F55",
        "sun": "#F3E7B5",
        "hill_back": "#1E3560",
        "hill_mid": "#25427A",
        "hill_front": "#2E5394",
        "water": "#3B64A8",
        "tree": "#3E6FB8",
        "tree_2": "#5583C9",
        "trunk": "#5B4E45",
        "turbine": "#DCE6F5",
        "turbine_edge": "#8EA2C4",
        "house": "#E9EEF7",
        "roof": "#C9715A",
        "panel": "#0E1A33",
        "window": "#FFD66B",
        "door": "#8F6A4E",
        "cloud": "#3A4B70",
    },
    FUEL_COLORS={
        "wind": "#5B9BF8",
        "solar": "#F5C55C",
        "gas": "#F59A7E",
        "nuclear": "#A497F0",
        "hydro": "#4FCBE0",
        "biomass": "#8FD083",
        "imports": "#A9B4CA",
        "coal": "#7C879B",
        "other": "#55627F",
        "storage": "#6FDBCB",
        "zero_carbon": "#6EA8FE",
        "fossil": "#F0705E",
    },
    INTENSITY_SCALE=[
        [0.0, "#4C8DF0"],
        [0.25, "#93BDF5"],
        [0.5, "#E9DDB2"],
        [0.75, "#F5A86E"],
        [1.0, "#F0705E"],
    ],
)


def is_dark() -> bool:
    """Dark mode for the current Streamlit session (False outside a running app)."""
    try:
        import streamlit as st

        return bool(st.session_state.get(THEME_KEY, False))
    except Exception:
        return False


def pal() -> Palette:
    return DARK if is_dark() else LIGHT


class _ActivePalette:
    """Attribute access resolves against the current session's palette: P.TEXT, P.EMERALD..."""

    def __getattr__(self, name: str):
        return getattr(pal(), name)


P = _ActivePalette()


def template_name() -> str:
    return f"gridgreen_{pal().name}"


def fuel_color(fuel: str) -> str:
    return pal().FUEL_COLORS.get(fuel, "#A3ADC2")


def _template(p: Palette) -> go.layout.Template:
    axis = dict(
        gridcolor=p.GRID,
        linecolor=p.BORDER,
        zerolinecolor=p.BORDER,
        ticks="outside",
        tickcolor=p.BORDER,
        tickfont=dict(size=12, color=p.TEXT_2),
        title_font=dict(size=12, color=p.TEXT_2),
        automargin=True,  # reserve room for tick labels (Streamlit's own theme used to do this)
        title_standoff=10,
    )
    fc = p.FUEL_COLORS
    return go.layout.Template(
        layout=go.Layout(
            font=dict(family=FONT_STACK, size=13, color=p.TEXT),
            title=dict(
                font=dict(family=HEADING_STACK, size=16, color=p.TEXT, weight=600),
                x=0,
                xanchor="left",
                y=0.97,
                yanchor="top",
                pad=dict(l=2),
            ),
            paper_bgcolor=p.SURFACE,
            plot_bgcolor=p.SURFACE,
            colorway=[
                p.EMERALD,
                p.ACCENT_2,
                fc["solar"],
                fc["gas"],
                fc["hydro"],
                fc["nuclear"],
                fc["biomass"],
            ],
            xaxis=axis,
            yaxis=axis,
            hoverlabel=dict(
                bgcolor=p.SURFACE, bordercolor=p.BORDER, font=dict(family=FONT_STACK, color=p.TEXT)
            ),
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.0,
                xanchor="left",
                x=0,
                font=dict(size=12, color=p.TEXT_2),
                bgcolor="rgba(0,0,0,0)",
            ),
            margin=dict(l=12, r=12, t=64, b=12),
            hovermode="x unified",
        )
    )


def register_plotly_template() -> None:
    """Register light and dark templates; light is the default (notebook, exports)."""
    for p in (LIGHT, DARK):
        pio.templates[f"gridgreen_{p.name}"] = _template(p)
    pio.templates["gridgreen"] = pio.templates["gridgreen_light"]
    pio.templates.default = "gridgreen"


def global_css(p: Palette) -> str:
    """All page CSS for one palette. Injected on every run so the dark-mode toggle applies at once."""
    scheme = "dark" if p.name == "dark" else "light"
    return f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700;800&display=swap');

/* Streamlit styles its own elements with class selectors, so a plain body rule loses.
   Element selectors under .stApp plus !important make the brand font apply everywhere. */
html, body, .stApp, .stApp p, .stApp span, .stApp div, .stApp label, .stApp li, .stApp a,
.stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp button, .stApp input, .stApp select, .stApp textarea {{
  font-family: {FONT_STACK} !important;
}}
/* Pin surfaces and text colours explicitly, so the page stays coherent even if the browser
   has a different Streamlit theme cached (that mismatch caused white-on-white text). */
.stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"] {{ background: {p.CANVAS} !important; color: {p.TEXT}; }}
[data-testid="stHeader"] {{ background: transparent !important; }}
section[data-testid="stSidebar"], section[data-testid="stSidebar"] > div {{ background: {p.SURFACE} !important; }}
section[data-testid="stSidebar"] p, section[data-testid="stSidebar"] label, section[data-testid="stSidebar"] span {{ color: {p.TEXT}; }}
section[data-testid="stSidebar"] [data-testid="stSidebarNavLink"] span {{ color: {p.TEXT_2} !important; }}
section[data-testid="stSidebar"] [data-testid="stSidebarNavLink"]:hover {{ background: {p.SURFACE_2}; }}
.stApp h1, .stApp h2, .stApp h3, .stApp p, .stApp li, [data-testid="stWidgetLabel"] p {{ color: {p.TEXT}; }}
.stApp [data-baseweb="input"], .stApp [data-baseweb="select"] > div, .stApp [data-baseweb="base-input"] {{
  background: {p.SURFACE} !important; border-color: {p.BORDER} !important; border-radius: 12px !important; }}
.stApp [data-baseweb="input"] input, .stApp [data-baseweb="select"] div {{ color: {p.TEXT} !important; -webkit-text-fill-color: {p.TEXT}; }}
.stApp button[kind="secondary"], .stApp [data-testid="stDownloadButton"] button {{
  background: {p.SURFACE} !important; color: {p.TEXT} !important; border: 1px solid {p.BORDER} !important; border-radius: 12px !important; }}
.stApp button[kind="secondary"]:hover, .stApp [data-testid="stDownloadButton"] button:hover {{ border-color: {p.EMERALD} !important; color: {p.EMERALD} !important; }}
/* Keep Streamlit's icon font (otherwise icon ligatures render as raw text) and monospace code. */
.stApp [data-testid="stIconMaterial"], .stApp .material-symbols-rounded, [data-testid="stIconMaterial"] {{
  font-family: "Material Symbols Rounded" !important;
}}
.stApp code, .stApp pre, .stApp code span {{
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace !important;
}}
/* Leave room for Streamlit's top toolbar. On Streamlit Community Cloud it carries the
   Share / star / edit / GitHub buttons and is taller than in local runs. */
.block-container {{ padding-top: 4.75rem; padding-bottom: 3rem; max-width: 1320px; }}
h1, h2, h3, h4 {{ font-family: {HEADING_STACK}; color: {p.TEXT}; letter-spacing: -0.02em; }}
h1 {{ font-size: 30px !important; font-weight: 700 !important; }}
h2 {{ font-size: 20px !important; font-weight: 600 !important; margin-top: 0.6rem; }}
h3 {{ font-size: 16.5px !important; font-weight: 600 !important; }}
p, li {{ font-size: 14.5px; line-height: 1.65; }}

section[data-testid="stSidebar"] {{ background: {p.SURFACE}; border-right: 1px solid {p.BORDER}; }}
section[data-testid="stSidebar"] [data-testid="stSidebarNavLink"] {{ border-radius: 10px; }}
section[data-testid="stSidebar"] [data-testid="stSidebarNavLink"][aria-current="page"] {{
  background: {p.SELECTED_BG};
}}
section[data-testid="stSidebar"] [data-testid="stSidebarNavLink"][aria-current="page"] span {{
  color: {p.TEXT}; font-weight: 600;
}}

.gg-tagline {{ color: {p.TEXT_2}; font-size: 12.5px; margin: 0 0 6px 0; }}

.gg-topbar {{ display: flex; flex-wrap: wrap; justify-content: space-between; align-items: flex-end;
  gap: 12px; border-bottom: 1px solid {p.BORDER}; padding-bottom: 14px; margin-bottom: 22px; }}
.gg-topbar h1 {{ margin: 0; padding: 0; line-height: 1.15; }}
.gg-topbar .gg-period {{ color: {p.TEXT_2}; font-size: 14px; margin-top: 4px; }}
.gg-status {{ display: inline-flex; align-items: center; gap: 8px; font-size: 13px; color: {p.TEXT_2};
  background: {p.SURFACE}; border: 1px solid {p.BORDER}; border-radius: 999px; padding: 6px 12px; }}
.gg-dot {{ width: 8px; height: 8px; border-radius: 50%; background: {p.EMERALD}; display: inline-block; }}
.gg-dot.warn {{ background: {p.WARNING}; }} .gg-dot.bad {{ background: {p.ERROR}; }}

@property --gg-n {{ syntax: "<integer>"; initial-value: 0; inherits: false; }}
.gg-count {{ --gg-n: var(--to); counter-reset: ggn var(--gg-n); animation: gg-count 1.1s cubic-bezier(.2,.7,.2,1) both; }}
.gg-count::after {{ content: counter(ggn); }}
@keyframes gg-count {{ from {{ --gg-n: 0; }} }}
.gg-sr {{ position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; }}
@keyframes gg-rise {{ from {{ opacity: 0; transform: translateY(8px); }} to {{ opacity: 1; transform: none; }} }}
.gg-kpi {{ animation: gg-rise .5s cubic-bezier(.2,.7,.2,1) both; transition: transform .18s ease, box-shadow .18s ease; }}
.gg-kpi:hover {{ transform: translateY(-2px); border-color: {p.EMERALD}; }}
.gg-hero {{ animation: gg-rise .6s cubic-bezier(.2,.7,.2,1) both; }}
.gg-dot {{ position: relative; }}
.gg-dot:not(.warn):not(.bad)::after {{ content: ""; position: absolute; inset: -4px; border-radius: 50%;
  border: 2px solid {p.EMERALD}; animation: gg-pulse 2.4s ease-out infinite; }}
@keyframes gg-pulse {{ from {{ transform: scale(.5); opacity: .7; }} to {{ transform: scale(1.6); opacity: 0; }} }}
.gg-kpi {{ background: {p.SURFACE}; border: 1px solid {p.BORDER}; border-radius: 20px; padding: 16px 18px; box-shadow: {p.SHADOW};
  height: 100%; }}
.gg-kpi-label {{ color: {p.TEXT_2}; font-size: 13px; font-weight: 500; }}
.gg-kpi-value {{ font-family: {HEADING_STACK}; font-size: 28px; font-weight: 700; color: {p.TEXT};
  line-height: 1.2; margin-top: 4px; font-variant-numeric: tabular-nums; }}
.gg-kpi-value small {{ font-size: 14px; font-weight: 600; color: {p.TEXT_2}; margin-left: 4px; }}
.gg-kpi-sub {{ color: {p.TEXT_2}; font-size: 12.5px; margin-top: 6px; }}

.gg-hero {{ background: radial-gradient(120% 140% at 100% 0%, {p.HERO_GLOW} 0%, {p.FOREST} 60%); color: {p.HERO_TEXT};
  border: 1px solid {p.BORDER};
  border-radius: 18px; padding: 24px 26px;
  display: grid; grid-template-columns: minmax(0, 1.1fr) minmax(0, 1fr); gap: 20px; }}
.gg-hero .gg-h-label {{ color: {p.HERO_TEXT_2}; font-size: 13px; }}
.gg-hero .gg-h-value {{ font-family: {HEADING_STACK}; font-size: 52px; font-weight: 700; line-height: 1; color: {p.MINT};
  margin: 8px 0 6px; font-variant-numeric: tabular-nums; }}
.gg-hero .gg-h-value small {{ font-size: 16px; font-weight: 500; color: {p.HERO_TEXT_2}; margin-left: 6px; }}
.gg-hero .gg-h-meta {{ color: {p.HERO_TEXT_2}; font-size: 13.5px; line-height: 1.5; }}
.gg-band {{ display: inline-block; background: {p.LIME}; color: {p.FOREST}; font-weight: 700; font-size: 12.5px;
  border-radius: 999px; padding: 3px 10px; margin-top: 6px; }}
.gg-hero .gg-h-right p {{ color: {p.HERO_TEXT}; font-size: 15px; margin: 0 0 6px; }}
@media (max-width: 760px) {{
  .gg-hero {{ grid-template-columns: 1fr; }}
  .gg-hero .gg-h-value {{ font-size: 40px; }}
}}

.gg-insight {{ border-left: 3px solid {p.EMERALD}; background: {p.SURFACE}; border-radius: 0 12px 12px 0;
  padding: 12px 16px; margin: 6px 0 10px; border-top: 1px solid {p.BORDER}; border-right: 1px solid {p.BORDER};
  border-bottom: 1px solid {p.BORDER}; }}
.gg-insight p {{ margin: 0; font-size: 14.5px; }}
.gg-note {{ color: {p.TEXT_2}; font-size: 13px; line-height: 1.5; }}
.gg-demo {{ background: {p.DEMO_BG}; border: 1px solid {p.DEMO_BORDER}; color: {p.DEMO_TEXT}; border-radius: 12px;
  padding: 10px 14px; font-size: 14px; margin-bottom: 16px; }}
.gg-empty {{ background: {p.SURFACE}; border: 1px dashed {p.BORDER}; border-radius: 14px; padding: 28px;
  text-align: left; }}
.gg-empty h3 {{ margin-top: 0; }}
.gg-footer {{ color: {p.TEXT_2}; font-size: 12.5px; border-top: 1px solid {p.BORDER}; margin-top: 32px;
  padding-top: 12px; }}

/* Streamlit paints Plotly's SVG with the page background; let the white chart card show. */
[data-testid="stPlotlyChart"] .main-svg {{ background: transparent !important; }}
[data-testid="stPlotlyChart"], [data-testid="stDataFrame"] {{
  background: {p.SURFACE}; border: 1px solid {p.BORDER}; border-radius: 20px; padding: 8px 10px; box-shadow: {p.SHADOW};
}}
div[data-testid="stExpander"] details {{
  border-radius: 12px; border-color: {p.BORDER}; background: {p.SURFACE};
}}
:focus-visible {{ outline: 2px solid {p.EMERALD} !important; outline-offset: 2px; }}
@media (prefers-reduced-motion: reduce) {{ * {{ transition: none !important; animation: none !important; }} }}
/* Living page titles: a slow gradient sweep through the brand blues (off for reduced motion). */
:root {{ color-scheme: {scheme}; }}
.stApp .gg-topbar h1 {{ background: linear-gradient(90deg, {p.TEXT} 0%, {p.EMERALD} 32%, {p.ACCENT_2} 52%, {p.TEXT} 78%);
  background-size: 260% 100%; -webkit-background-clip: text; background-clip: text; -webkit-text-fill-color: transparent;
  animation: gg-shimmer 10s ease-in-out infinite; }}
@keyframes gg-shimmer {{ 0%, 100% {{ background-position: 100% 0; }} 50% {{ background-position: 0% 0; }} }}
/* Streamlit-native inputs, targeted by their real structure in Streamlit 1.66. */
.stApp [data-testid="stDateInputField"] {{ background: {p.SURFACE} !important; border: 1px solid {p.BORDER} !important;
  border-radius: 12px !important; }}
.stApp [data-testid="stDateInputField"] *, .stApp [data-testid="stSelectbox"] *, .stApp [data-testid="stNumberInput"] input {{
  color: {p.TEXT} !important; -webkit-text-fill-color: {p.TEXT}; }}
.stApp [data-testid="stSelectbox"] > div > div, .stApp [data-testid="stNumberInputContainer"],
.stApp [data-testid="stNumberInput"] input {{ background: {p.SURFACE} !important; border-color: {p.BORDER} !important; }}
.stApp [data-testid="stNumberInput"] button {{ background: {p.SURFACE_2} !important; color: {p.TEXT} !important; }}
[role="listbox"], [data-baseweb="menu"], [data-baseweb="popover"] > div {{ background: {p.SURFACE} !important; color: {p.TEXT} !important; }}
[role="option"] {{ color: {p.TEXT} !important; }}
.stApp [data-testid="stButtonGroup"] button {{ background: {p.SURFACE}; color: {p.TEXT}; border-color: {p.BORDER}; }}
.stApp [data-testid="stExpander"] summary, .stApp [data-testid="stCaptionContainer"], .stApp small {{ color: {p.TEXT_2}; }}
.stApp [data-testid="stAlert"] {{ background: {p.SURFACE_2}; color: {p.TEXT}; }}
.stApp [data-testid="stMarkdownContainer"] code {{ background: {p.SURFACE_2}; color: {p.TEXT}; }}
</style>
"""


GLOBAL_CSS = global_css(LIGHT)  # light CSS, kept for compatibility

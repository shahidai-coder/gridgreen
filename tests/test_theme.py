"""Keep the colour scheme consistent and accessible.

theme.py is the single source of truth. Files that cannot import Python
(.streamlit/config.toml, the SVG logos) must mirror it, and text colours must
meet WCAG 2.1 contrast minimums.
"""

import re
import tomllib
from pathlib import Path

import pytest

from gridgreen.ui import theme

ROOT = Path(__file__).resolve().parents[1]


def contrast(a: str, b: str) -> float:
    def lum(h: str) -> float:
        c = [int(h.lstrip("#")[i : i + 2], 16) / 255 for i in (0, 2, 4)]
        c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
        return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]

    hi, lo = sorted((lum(a), lum(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


PAIRS = [
    ("TEXT", "CANVAS", 4.5),
    ("TEXT", "SURFACE", 4.5),
    ("TEXT_2", "SURFACE", 4.5),
    ("TEXT_2", "CANVAS", 4.5),
    ("TEXT_2", "SURFACE_2", 4.5),
    ("EMERALD", "SURFACE", 4.5),  # accent text and links
    ("EMERALD", "CANVAS", 4.5),
    ("ON_ACCENT", "EMERALD", 4.5),  # text on accent fills
    ("ACCENT_2", "SURFACE", 4.5),
    ("FOREST", "LIME", 4.5),  # highlight chip
    ("TEXT", "SELECTED_BG", 4.5),  # selected sidebar item
    ("LOW_TEXT", "LOW_BG", 4.5),  # status pill
    ("YELLOW_TEXT", "YELLOW", 4.5),  # tip card
    ("DEMO_TEXT", "DEMO_BG", 4.5),
    ("ERROR", "SURFACE", 3.0),  # non-text UI
]


@pytest.mark.parametrize("palette", [theme.LIGHT, theme.DARK], ids=["light", "dark"])
@pytest.mark.parametrize("fg,bg,minimum", PAIRS)
def test_colour_pairs_meet_wcag_contrast(palette, fg, bg, minimum):
    assert contrast(getattr(palette, fg), getattr(palette, bg)) >= minimum


@pytest.mark.parametrize("palette", [theme.LIGHT, theme.DARK], ids=["light", "dark"])
def test_shimmer_title_colours_stay_readable(palette):
    # The animated page-title gradient passes through these colours; each must be legible on the canvas.
    for colour in (palette.TEXT, palette.EMERALD, palette.ACCENT_2):
        assert contrast(colour, palette.CANVAS) >= 4.5


def test_palettes_define_the_same_tokens():
    assert set(theme.LIGHT.SCENE) == set(theme.DARK.SCENE)
    assert set(theme.LIGHT.FUEL_COLORS) == set(theme.DARK.FUEL_COLORS)
    assert theme.LIGHT.TEXT == theme.TEXT  # module constants mirror the light palette


def test_streamlit_config_mirrors_theme():
    cfg = tomllib.loads((ROOT / ".streamlit" / "config.toml").read_text(encoding="utf-8"))["theme"]
    assert cfg["primaryColor"].upper() == theme.EMERALD.upper()
    assert cfg["backgroundColor"].upper() == theme.CANVAS.upper()
    assert cfg["secondaryBackgroundColor"].upper() == theme.SURFACE.upper()
    assert cfg["textColor"].upper() == theme.TEXT.upper()


@pytest.mark.parametrize("name", ["logo.svg", "icon.svg"])
def test_logos_use_brand_colours(name):
    svg = (ROOT / "assets" / name).read_text(encoding="utf-8").upper()
    for token in ("EMERALD", "FOREST", "LIME"):
        assert getattr(theme, token).upper() in svg, f"{name} should use {token}"


def test_no_hardcoded_colours_outside_theme():
    for rel in [
        "src/gridgreen/ui/animated.py",
        "src/gridgreen/ui/charts.py",
        "src/gridgreen/ui/components.py",
        "src/gridgreen/ui/pulse.py",
    ]:
        found = re.findall(r"#[0-9A-Fa-f]{6}\b", (ROOT / rel).read_text(encoding="utf-8"))
        assert not found, f"{rel} has hard-coded colours {found}; add them to theme.py"


def test_dark_logo_wordmark_is_readable_on_dark_sidebar():
    svg = (ROOT / "assets" / "logo-dark.svg").read_text(encoding="utf-8").upper()
    assert theme.DARK.TEXT.upper() in svg

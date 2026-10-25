"""Animated visual overviews: one small, theme-aware illustration per page.

Each banner explains what the page is about with an animated SVG scene and a
headline whose words rise in one by one. Colours come from the active palette,
so the banners follow the dark-mode toggle. Motion stops for viewers who ask
their system to reduce motion.
"""

from __future__ import annotations

import html

import streamlit.components.v1 as components

from gridgreen.ui.theme import FONT_STACK, Palette, pal

BANNERS: dict[str, tuple[str, str, list[str]]] = {
    "trends": (
        "Watch the grid breathe through the day and the seasons",
        "Every line here is built from half-hourly NESO estimates.",
        ["Half-hourly data", "Hour profiles", "Seasonal heatmaps"],
    ),
    "mix": (
        "Wind, sun, gas and atoms: who keeps the lights on",
        "Shares of generation, and how each one moves with carbon intensity.",
        ["Fuel shares", "Correlations", "Zero-carbon bands"],
    ),
    "best": (
        "Plug in when the grid is cleanest",
        "Find the historical windows with the lowest intensity for a flexible load.",
        ["EV charging", "Heat pumps", "Any 30 min to 6 h load"],
    ),
    "forecast": (
        "How good was the forecast?",
        "Published forecasts compared with NESO's later estimates.",
        ["MAE and RMSE", "Bias", "Error by hour"],
    ),
    "quality": (
        "Every record checked, nothing silently dropped",
        "Pipeline runs, missing half-hours and rejected records, all on the record.",
        ["Validation", "Idempotent loads", "Audit trail"],
    ),
    "method": (
        "From raw API to trusted answer",
        "How GridGreen extracts, validates, transforms and stores the data.",
        ["Extract", "Validate", "Load", "Analyse"],
    ),
}


def _scene(kind: str, p: Palette) -> str:
    a, a2, t2, f = p.EMERALD, p.ACCENT_2, p.TEXT_2, p.FUEL_COLORS
    s0, s4, s2 = p.INTENSITY_SCALE[0][1], p.INTENSITY_SCALE[4][1], p.SURFACE_2
    if kind == "trends":
        path = "M10 110 C40 70 60 120 90 88 S140 40 170 78 S220 120 250 70 S300 50 340 82"
        return f"""
        <g stroke="{p.GRID}" stroke-width="1">{"".join(f'<line x1="10" x2="350" y1="{y}" y2="{y}"/>' for y in (40, 70, 100, 130))}</g>
        <circle cx="300" cy="34" r="12" fill="{f["solar"]}" opacity=".9">
          <animateTransform attributeName="transform" type="rotate" from="0 300 34" to="360 300 34" dur="20s" repeatCount="indefinite"/></circle>
        <path d="{path} L340 150 L10 150Z" fill="{a}" opacity=".12"/>
        <path d="{path}" fill="none" stroke="{a}" stroke-width="3" stroke-linecap="round" class="draw"/>
        <circle r="6" fill="{a}" stroke="{p.SURFACE}" stroke-width="2"><animateMotion dur="6s" repeatCount="indefinite" path="{path}"/></circle>"""
    if kind == "mix":

        def puff(x: int, delay: float) -> str:
            return (
                f'<circle cx="{x}" cy="78" r="6" fill="{t2}" opacity="0"><animate attributeName="cy" values="78;30" dur="3s" '
                f'begin="{delay}s" repeatCount="indefinite"/><animate attributeName="opacity" values=".55;0" dur="3s" '
                f'begin="{delay}s" repeatCount="indefinite"/><animate attributeName="r" values="5;12" dur="3s" begin="{delay}s" '
                f'repeatCount="indefinite"/></circle>'
            )

        blades = "".join(
            f'<path d="M60 52 q3 -12 0 -34 q-3 12 0 34" fill="{p.SURFACE}" stroke="{t2}" stroke-width="1" '
            f'transform="rotate({r} 60 52)"/>'
            for r in (0, 120, 240)
        )
        return f"""
        <rect x="0" y="130" width="360" height="30" fill="{s2}"/>
        <path d="M58 132 L59 52 L61 52 L62 132Z" fill="{p.SURFACE}" stroke="{t2}" stroke-width="1"/>
        <g>{blades}<animateTransform attributeName="transform" type="rotate" from="0 60 52" to="360 60 52" dur="4s" repeatCount="indefinite"/></g>
        <g transform="translate(105 96)">{"".join(f'<rect x="{i * 22}" y="{i % 2 * 0}" width="20" height="30" rx="2" fill="{f["wind"]}" transform="skewX(-18)" class="shine" style="animation-delay:{i * 0.4}s"/>' for i in range(3))}</g>
        <rect x="205" y="80" width="18" height="52" fill="{f["gas"]}" rx="2"/>{puff(214, 0)}{puff(214, 1.5)}
        <path d="M262 132 C266 104 262 92 268 76 L300 76 C306 92 302 104 306 132Z" fill="{f["nuclear"]}" opacity=".85"/>
        {puff(284, 0.7).replace('cy="78"', 'cy="74"')}"""
    if kind == "best":
        return f"""
        <rect x="0" y="132" width="360" height="28" fill="{s2}"/>
        <path d="M40 132 V86 L80 60 L120 86 V132Z" fill="{p.SURFACE}" stroke="{t2}" stroke-width="1.5"/>
        <rect x="70" y="104" width="20" height="28" rx="2" fill="{a2}" opacity=".7"/>
        <path d="M170 132 h80 c8 0 10 -6 10 -12 l-6 -14 c-2 -6 -8 -8 -14 -8 h-44 c-6 0 -10 2 -14 8 l-10 14 c-2 6 0 12 -2 12z" fill="{a}"/>
        <circle cx="190" cy="134" r="8" fill="{p.TEXT}"/><circle cx="240" cy="134" r="8" fill="{p.TEXT}"/>
        <path d="M120 112 C140 112 150 118 172 118" fill="none" stroke="{t2}" stroke-width="3" stroke-dasharray="6 6" class="flow"/>
        <rect x="282" y="58" width="44" height="22" rx="4" fill="none" stroke="{t2}" stroke-width="2"/><rect x="326" y="64" width="4" height="10" rx="1" fill="{t2}"/>
        <rect x="285" y="61" width="0" height="16" rx="2" fill="{s0}"><animate attributeName="width" values="0;38;38" keyTimes="0;.8;1" dur="4s" repeatCount="indefinite"/></rect>
        <path d="M304 30 l-6 12 h6 l-4 12 l12 -16 h-6 l4 -8z" fill="{f["solar"]}" class="blink"/>
        <circle cx="210" cy="40" r="22" fill="{p.SURFACE}" stroke="{t2}" stroke-width="2"/>
        <line x1="210" y1="40" x2="210" y2="25" stroke="{a}" stroke-width="3" stroke-linecap="round">
          <animateTransform attributeName="transform" type="rotate" from="0 210 40" to="360 210 40" dur="8s" repeatCount="indefinite"/></line>
        <line x1="210" y1="40" x2="220" y2="40" stroke="{p.TEXT}" stroke-width="3" stroke-linecap="round"/>"""
    if kind == "forecast":
        actual = "M10 100 C50 80 80 110 120 90 S170 60 190 76"
        fc = "M190 76 C220 90 250 70 290 80 S330 96 350 84"
        return f"""
        <g stroke="{p.GRID}">{"".join(f'<line x1="10" x2="350" y1="{y}" y2="{y}"/>' for y in (40, 70, 100, 130))}</g>
        <path d="M190 76 L350 40 L350 128Z" fill="{a2}" class="breathe"/>
        <path d="{actual}" fill="none" stroke="{a}" stroke-width="3" stroke-linecap="round"/>
        <path d="{fc}" fill="none" stroke="{a2}" stroke-width="3" stroke-dasharray="8 7" stroke-linecap="round" class="flow"/>
        <line x1="190" x2="190" y1="24" y2="140" stroke="{t2}" stroke-dasharray="3 4"/>
        <circle cx="190" cy="76" r="6" fill="{a}" stroke="{p.SURFACE}" stroke-width="2" class="blink"/>
        <text x="196" y="34" fill="{t2}" font-size="11" font-family="{FONT_STACK}">now</text>"""
    if kind == "quality":
        pipe = "M10 80 H120 C150 80 160 80 180 80 H350"
        good = "".join(
            f'<circle r="5" fill="{a}"><animateMotion dur="4s" begin="{i * 0.5}s" repeatCount="indefinite" path="{pipe}"/></circle>'
            for i in range(8)
        )
        bad = (
            f'<circle r="5" fill="{s4}"><animateMotion dur="2.4s" begin="1.1s" repeatCount="indefinite" '
            f'path="M10 80 H175 C185 80 190 95 192 128"/></circle>'
        )
        return f"""
        <rect x="6" y="68" width="348" height="24" rx="12" fill="{s2}"/>
        {good}{bad}
        <path d="M160 52 h44 l-12 22 v12 h-20 v-12z" fill="{a2}" opacity=".85"/>
        <rect x="176" y="118" width="34" height="26" rx="4" fill="none" stroke="{s4}" stroke-width="2"/>
        <text x="214" y="136" fill="{t2}" font-size="11" font-family="{FONT_STACK}">rejected, logged</text>
        <path d="M300 66 l8 8 l16 -18" fill="none" stroke="{a}" stroke-width="4" stroke-linecap="round" stroke-linejoin="round" class="blink"/>"""
    # method
    steps = [("API", a2), ("Validate", a), ("DuckDB", f["hydro"]), ("Charts", f["solar"])]

    def ink(bg: str) -> str:  # dark or light label, whichever reads better on this box
        r, g, b = (int(bg[i : i + 2], 16) / 255 for i in (1, 3, 5))
        return "#16213A" if 0.2126 * r + 0.7152 * g + 0.0722 * b > 0.45 else "#FFFFFF"

    boxes = "".join(
        f'<g class="pop" style="animation-delay:{i * 0.25}s"><rect x="{12 + i * 88}" y="56" width="70" height="48" rx="12" fill="{c}" '
        f'opacity=".9"/><text x="{47 + i * 88}" y="85" text-anchor="middle" fill="{ink(c)}" font-size="12" font-weight="600" '
        f'font-family="{FONT_STACK}">{name}</text></g>'
        for i, (name, c) in enumerate(steps)
    )
    arrows = "".join(
        f'<path d="M{84 + i * 88} 80 h16" stroke="{t2}" stroke-width="3" stroke-dasharray="4 4" class="flow"/>'
        for i in range(3)
    )
    return boxes + arrows


def page_banner(kind: str, height: int = 178) -> None:
    """Render the animated overview for one page ('trends', 'mix', 'best', 'forecast', 'quality', 'method')."""
    p = pal()
    title, sub, chips = BANNERS[kind]
    words = "".join(
        f'<span style="animation-delay:{i * 70}ms">{html.escape(w)}&nbsp;</span>'
        for i, w in enumerate(title.split())
    )
    chip_html = "".join(f'<span class="chip">{html.escape(c)}</span>' for c in chips)
    doc = f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; font-family: {FONT_STACK}; background: transparent; }}
  .wrap {{ display: grid; grid-template-columns: minmax(0, 1.05fr) minmax(0, 1fr); align-items: center; gap: 12px; height: {height - 6}px;
          background: linear-gradient(120deg, {p.SURFACE} 0%, {p.SURFACE_2} 100%); border: 1px solid {p.BORDER}; border-radius: 22px;
          padding: 16px 22px; box-shadow: {p.SHADOW}; overflow: hidden; }}
  h2 {{ margin: 0; font-size: clamp(17px, 2.3vw, 23px); line-height: 1.25; font-weight: 700; letter-spacing: -0.02em;
        background: linear-gradient(90deg, {p.TEXT} 0%, {p.EMERALD} 40%, {p.ACCENT_2} 60%, {p.TEXT} 85%); background-size: 260% 100%;
        -webkit-background-clip: text; background-clip: text; -webkit-text-fill-color: transparent; animation: shimmer 9s ease-in-out infinite; }}
  h2 span {{ display: inline-block; opacity: 0; transform: translateY(10px); animation: rise .55s cubic-bezier(.2,.7,.2,1) forwards;
             -webkit-text-fill-color: transparent; background: inherit; -webkit-background-clip: text; background-clip: text; }}
  p {{ margin: 6px 0 10px; color: {p.TEXT_2}; font-size: 13px; }}
  .chip {{ display: inline-block; margin: 0 6px 6px 0; padding: 4px 11px; border-radius: 999px; font-size: 12px; font-weight: 600;
           background: {p.LOW_BG}; color: {p.LOW_TEXT}; }}
  svg {{ width: 100%; height: {height - 40}px; }}
  .draw {{ stroke-dasharray: 600; stroke-dashoffset: 600; animation: draw 3.5s ease-out forwards; }}
  .flow {{ animation: flow 1s linear infinite; }}
  .blink {{ animation: blink 1.6s ease-in-out infinite; }}
  .breathe {{ animation: breathe 3s ease-in-out infinite; }}
  .shine {{ animation: shine 2.4s ease-in-out infinite; }}
  .pop {{ opacity: 0; animation: rise .5s cubic-bezier(.2,.7,.2,1) forwards; transform-box: fill-box; }}
  @keyframes rise {{ to {{ opacity: 1; transform: none; }} }}
  @keyframes shimmer {{ 0%, 100% {{ background-position: 100% 0; }} 50% {{ background-position: 0 0; }} }}
  @keyframes draw {{ to {{ stroke-dashoffset: 0; }} }}
  @keyframes flow {{ to {{ stroke-dashoffset: -14; }} }}
  @keyframes blink {{ 50% {{ opacity: .35; }} }}
  @keyframes breathe {{ 0%, 100% {{ opacity: .10; }} 50% {{ opacity: .26; }} }}
  @keyframes shine {{ 50% {{ opacity: .55; }} }}
  @media (max-width: 560px) {{ .wrap {{ grid-template-columns: 1fr 0.8fr; padding: 12px 14px; }} p, .chip:nth-child(n+3) {{ display: none; }} }}
  @media (prefers-reduced-motion: reduce) {{ *, *::before, *::after {{ animation: none !important; opacity: 1 !important; transform: none !important; }}
    .draw {{ stroke-dashoffset: 0; }} }}
</style></head><body>
<div class="wrap" role="img" aria-label="{html.escape(title)}">
  <div><h2>{words}</h2><p>{html.escape(sub)}</p><div>{chip_html}</div></div>
  <svg viewBox="0 0 360 160" preserveAspectRatio="xMidYMid meet" aria-hidden="true">{_scene(kind, p)}</svg>
</div>
<script>if (matchMedia("(prefers-reduced-motion: reduce)").matches) document.querySelectorAll("svg").forEach((s) => s.pauseAnimations());</script>
</body></html>"""
    components.html(doc, height=height)

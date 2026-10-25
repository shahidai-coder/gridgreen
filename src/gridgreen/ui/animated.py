"""Data-driven animated components (rendered in a sandboxed iframe).

`grid_replay` draws the real half-hourly values for the selected period and
replays them day by day. The animation shows the data; it adds nothing to it.
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import streamlit.components.v1 as components

from gridgreen.ui import theme


def _matrix(df: pd.DataFrame, value: str) -> tuple[list[str], list[list[int | None]]]:
    d = df.dropna(subset=[value])
    if d.empty:
        return [], []
    # Wall-clock slot by local date. On the October change two UTC slots share a
    # wall-clock slot and are averaged; on the March change one hour is absent (null).
    mat = d.pivot_table(index="slot_of_day", columns="local_date", values=value, aggfunc="mean")
    mat = mat.reindex(range(48))
    days = [pd.Timestamp(c).strftime("%Y-%m-%d") for c in mat.columns]
    rows = [[None if np.isnan(v) else round(float(v)) for v in row] for row in mat.to_numpy()]
    return days, rows


def grid_replay(df: pd.DataFrame, value: str = "actual", height: int = 430) -> bool:
    """Render the animated grid. Returns False (and renders nothing) if there is no data."""
    days, rows = _matrix(df, value)
    if not days:
        return False
    flat = [v for r in rows for v in r if v is not None]
    payload = {
        "days": days,
        "rows": rows,
        "zmin": float(np.percentile(flat, 2)),
        "zmax": float(np.percentile(flat, 98)),
        "scale": [[s, c] for s, c in theme.pal().INTENSITY_SCALE],
    }
    html = _HTML.replace("__DATA__", json.dumps(payload, separators=(",", ":")))
    for token in ("ON_ACCENT", "TEXT_2", "FOREST", "EMERALD", "LIME", "TEXT", "BORDER", "SURFACE", "GRID"):
        html = html.replace(f"__{token}__", getattr(theme.pal(), token))
    html = html.replace("__FONT__", theme.FONT_STACK)
    components.html(html, height=height)
    return True


_HTML = r"""
<!DOCTYPE html><html><head><meta charset="utf-8">
<style>
  @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600&display=swap');
  :root { --forest:__FOREST__; --emerald:__EMERALD__; --lime:__LIME__; --text:__TEXT__; --text2:__TEXT_2__; --border:__BORDER__; }
  * { box-sizing: border-box; }
  body { margin:0; font: 13px/1.4 __FONT__; color: var(--text); background: transparent; }
  .card { background:__SURFACE__; border:1px solid var(--border); border-radius:14px; padding:14px 16px 10px; }
  .top { display:flex; flex-wrap:wrap; align-items:center; gap:10px 14px; margin-bottom:10px; }
  h3 { font: 600 16px/1.2 __FONT__; letter-spacing:-0.01em; margin:0; flex: 1 1 260px; }
  button { font: 600 13px/1 __FONT__; border:0; border-radius:999px; padding:8px 14px; cursor:pointer;
           background: var(--emerald); color: __ON_ACCENT__; min-width: 74px; }
  button:hover { filter: brightness(1.12); }
  button:focus-visible, input:focus-visible { outline:2px solid var(--emerald); outline-offset:2px; }
  .date { font-variant-numeric: tabular-nums; color: var(--text2); min-width: 120px; }
  input[type=range] { flex: 1 1 160px; accent-color: var(--emerald); }
  .stage { position:relative; }
  canvas { display:block; width:100%; height:300px; cursor:crosshair; }
  .tip { position:absolute; pointer-events:none; background:var(--forest); color:#fff; font-weight:600; font-size:12.5px;
         padding:6px 9px; border-radius:8px; white-space:nowrap; opacity:0; transition:opacity .1s; transform:translate(-50%,-120%);
         font-variant-numeric: tabular-nums; }
  .tip.on { opacity:1; }
  .foot { display:flex; justify-content:space-between; flex-wrap:wrap; gap:6px; color:var(--text2); font-size:12px; margin-top:8px; }
  .legend { display:inline-flex; align-items:center; gap:8px; }
  .legend i { width:110px; height:8px; border-radius:4px; display:inline-block; }
</style></head><body>
<div class="card">
  <div class="top">
    <h3>Replay of every half-hour in the period</h3>
    <button id="play" aria-label="Pause replay">Pause</button>
    <input id="scrub" type="range" min="1" value="1" aria-label="Replay position">
    <span class="date" id="date" aria-live="off"></span>
  </div>
  <div class="stage">
    <canvas id="c" role="img" aria-label="Heatmap of carbon intensity: columns are days, rows are times of day."></canvas>
    <div class="tip" id="tip"></div>
  </div>
  <div class="foot">
    <span>Columns are days, rows are UK local time. Hover for the value. Blank cells have no data.</span>
    <span class="legend" id="legend"></span>
  </div>
</div>
<script>
const D = __DATA__;
const N = D.days.length, ROWS = 48, LEFT = 40, BOTTOM = 18, TOP = 8;
const canvas = document.getElementById("c"), ctx = canvas.getContext("2d");
const play = document.getElementById("play"), scrub = document.getElementById("scrub");
const dateEl = document.getElementById("date"), tip = document.getElementById("tip");
const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
const stops = D.scale.map(([s, c]) => [s, parseInt(c.slice(1,3),16), parseInt(c.slice(3,5),16), parseInt(c.slice(5,7),16)]);
document.getElementById("legend").innerHTML =
  `${Math.round(D.zmin)} <i style="background:linear-gradient(90deg,${D.scale.map(s=>s[1]).join(",")})"></i> ${Math.round(D.zmax)} gCO₂/kWh`;
scrub.max = N;

function color(v) {
  let x = (v - D.zmin) / (D.zmax - D.zmin); x = Math.min(1, Math.max(0, x));
  for (let i = 1; i < stops.length; i++) if (x <= stops[i][0]) {
    const a = stops[i-1], b = stops[i], f = (x - a[0]) / (b[0] - a[0] || 1);
    return `rgb(${a[1]+(b[1]-a[1])*f|0},${a[2]+(b[2]-a[2])*f|0},${a[3]+(b[3]-a[3])*f|0})`;
  }
  return `rgb(${stops.at(-1).slice(1).join(",")})`;
}
const fmtDay = (iso) => new Date(iso + "T12:00:00Z").toLocaleDateString("en-GB", { weekday:"short", day:"numeric", month:"short", year:"numeric", timeZone:"UTC" });
const slotLabel = (r) => `${String(r >> 1).padStart(2,"0")}:${r & 1 ? "30" : "00"}`;

let W = 0, H = 0, cw = 0, ch = 0, shown = reduce ? N : 0, playing = !reduce, started = reduce, raf = 0, hover = null;

function resize() {
  const dpr = Math.min(devicePixelRatio || 1, 2), rect = canvas.getBoundingClientRect();
  W = rect.width; H = rect.height; canvas.width = W * dpr; canvas.height = H * dpr; ctx.setTransform(dpr,0,0,dpr,0,0);
  cw = (W - LEFT) / N; ch = (H - BOTTOM - TOP) / ROWS; draw();
}
function draw() {
  ctx.clearRect(0, 0, W, H);
  const k = Math.floor(shown);
  ctx.fillStyle = "__GRID__"; ctx.fillRect(LEFT + k * cw, TOP, (N - k) * cw, ROWS * ch);
  for (let r = 0; r < ROWS; r++) {
    const row = D.rows[r];
    for (let d = 0; d < k; d++) {
      const v = row[d]; if (v === null) continue;
      ctx.fillStyle = color(v); ctx.fillRect(LEFT + d * cw, TOP + r * ch, Math.ceil(cw), Math.ceil(ch));
    }
  }
  if (k > 0 && k < N) { ctx.fillStyle = "__LIME__"; ctx.fillRect(LEFT + k * cw - 1, TOP, 2.5, ROWS * ch); }
  if (hover && hover.d < k) { ctx.strokeStyle = "__FOREST__"; ctx.lineWidth = 1.5; ctx.strokeRect(LEFT + hover.d * cw, TOP + hover.r * ch, Math.max(cw, 2), ch); }
  ctx.fillStyle = "__TEXT_2__"; ctx.font = "11px __FONT__"; ctx.textBaseline = "middle"; ctx.textAlign = "right";
  for (const r of [0, 12, 24, 36]) ctx.fillText(slotLabel(r), LEFT - 6, TOP + r * ch + ch / 2);
  ctx.textAlign = "left"; ctx.textBaseline = "alphabetic";
  let lastX = -999;
  D.days.forEach((iso, d) => {
    if (d === 0 || iso.slice(8) === "01") {
      const x = LEFT + d * cw; if (x - lastX < 46) return;
      ctx.fillText(new Date(iso + "T12:00:00Z").toLocaleDateString("en-GB", { month:"short", year: N > 200 ? "2-digit" : undefined, timeZone:"UTC" }), x + 2, H - 3);
      lastX = x;
    }
  });
  const cur = Math.min(N - 1, Math.max(0, k - 1));
  dateEl.textContent = k ? fmtDay(D.days[cur]) : "";
  scrub.value = Math.max(1, k);
}
function step() {
  if (!playing) return;
  shown = Math.min(N, shown + Math.max(N / 360, 0.25));   // whole period in about 6 seconds
  draw();
  if (shown >= N) { playing = false; play.textContent = "Replay"; play.setAttribute("aria-label", "Replay"); return; }
  raf = requestAnimationFrame(step);
}
function setPlaying(p) {
  playing = p; cancelAnimationFrame(raf);
  play.textContent = p ? "Pause" : (shown >= N ? "Replay" : "Play");
  play.setAttribute("aria-label", play.textContent + " replay");
  if (p) raf = requestAnimationFrame(step);
}
play.addEventListener("click", () => {
  if (playing) return setPlaying(false);
  if (shown >= N) shown = 0;
  setPlaying(true);
});
scrub.addEventListener("input", () => { shown = +scrub.value; setPlaying(false); draw(); });
canvas.addEventListener("pointermove", (e) => {
  const rect = canvas.getBoundingClientRect(), x = e.clientX - rect.left, y = e.clientY - rect.top;
  const d = Math.floor((x - LEFT) / cw), r = Math.floor((y - TOP) / ch);
  if (d < 0 || d >= Math.floor(shown) || r < 0 || r >= ROWS) { hover = null; tip.classList.remove("on"); draw(); return; }
  hover = { d, r }; const v = D.rows[r][d];
  tip.textContent = `${fmtDay(D.days[d])}, ${slotLabel(r)}: ${v === null ? "no data" : v + " gCO₂/kWh"}`;
  tip.style.left = Math.min(Math.max(x, 120), W - 120) + "px"; tip.style.top = y + "px"; tip.classList.add("on"); draw();
});
canvas.addEventListener("pointerleave", () => { hover = null; tip.classList.remove("on"); draw(); });
addEventListener("resize", resize);
new IntersectionObserver(([e]) => {
  if (e.isIntersecting && !started) { started = true; setPlaying(true); }
}).observe(canvas);
if (reduce) { play.textContent = "Replay"; }
resize();
</script></body></html>
"""

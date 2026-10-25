#!/usr/bin/env bash
# GridGreen one-click launcher for macOS / Linux.  Run: ./run_mac_linux.sh
set -euo pipefail
cd "$(dirname "$0")"
export PATH="$HOME/.local/bin:$PATH"

if ! command -v uv >/dev/null 2>&1; then
  echo "[GridGreen] Installing uv, the Python package manager..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi

echo "[GridGreen] Installing Python and dependencies. The first run takes a few minutes..."
uv sync

if uv run python scripts/launcher_check.py online; then
  if uv run python scripts/launcher_check.py has-data; then
    echo "[GridGreen] Updating data from the NESO API..."
    uv run python scripts/run_pipeline.py || echo "[GridGreen] Update incomplete; using existing data."
  else
    echo "[GridGreen] Downloading one year of data from the NESO API, about a minute..."
    rm -f data/gridgreen.duckdb
    uv run python scripts/run_pipeline.py --start 2025-10-01 --end 2026-10-01 || true
  fi
else
  echo "[GridGreen] NESO API not reachable. Skipping the data update."
fi

if ! uv run python scripts/launcher_check.py has-data; then
  echo "[GridGreen] No real data available. Starting with SYNTHETIC demo data instead."
  rm -f data/gridgreen.duckdb
  uv run python scripts/build_demo_db.py >/dev/null
fi

URL="http://localhost:8501"
echo "[GridGreen] Starting the dashboard at $URL  (Ctrl+C to stop)"
( sleep 7; (command -v open >/dev/null && open "$URL") || (command -v xdg-open >/dev/null && xdg-open "$URL") || true ) >/dev/null 2>&1 &
exec uv run streamlit run app.py --server.port 8501

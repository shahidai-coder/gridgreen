"""Tiny checks used by the one-click launchers.

python scripts/launcher_check.py online    -> exit 0 if the NESO API answers within 5 s
python scripts/launcher_check.py has-data  -> exit 0 if data/gridgreen.duckdb holds real rows
"""

from __future__ import annotations

import sys

import httpx

from gridgreen.config import API_BASE_URL, DEFAULT_DB_PATH


def online() -> bool:
    try:
        return httpx.get(f"{API_BASE_URL}/intensity", timeout=5).status_code == 200
    except httpx.HTTPError:
        return False


def has_data() -> bool:
    if not DEFAULT_DB_PATH.exists():
        return False
    import duckdb

    try:
        con = duckdb.connect(str(DEFAULT_DB_PATH), read_only=True)
        n = con.execute("SELECT count(*) FROM carbon_intensity").fetchall()[0][0]
        con.close()
        return n > 0
    except duckdb.Error:
        return False


if __name__ == "__main__":
    checks = {"online": online, "has-data": has_data}
    if len(sys.argv) != 2 or sys.argv[1] not in checks:
        sys.exit(f"usage: {sys.argv[0]} {{online|has-data}}")
    sys.exit(0 if checks[sys.argv[1]]() else 1)

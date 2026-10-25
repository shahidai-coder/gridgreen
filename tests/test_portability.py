"""Guard against platform-specific code that passes on Linux but breaks on Windows."""

import re
from pathlib import Path

from gridgreen.ui.components import day_month_year

ROOT = Path(__file__).resolve().parents[1]


def test_no_glibc_only_strftime_codes():
    # '%-d', '%-H' etc. are glibc extensions; Windows raises "Invalid format string".
    offenders = [
        f"{p.relative_to(ROOT)}:{i}"
        for p in [*ROOT.glob("src/**/*.py"), *ROOT.glob("pages/*.py"), ROOT / "app.py"]
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1)
        if re.search(r"%-[a-zA-Z]", line)
    ]
    assert not offenders, offenders


def test_day_month_year_has_no_leading_zero():
    import datetime as dt

    assert day_month_year(dt.date(2025, 10, 1)) == "1 Oct 2025"
    assert day_month_year(dt.datetime(2026, 3, 29, 2, 30)) == "29 Mar 2026"

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


def test_text_files_are_read_with_explicit_utf8():
    # Without encoding=, Python on Windows decodes with cp1252 and fails on UTF-8 text such as "CO₂".
    pattern = re.compile(r"\.read_text\(\s*\)|\bopen\((?![^)]*encoding=)[^)]*\)")
    offenders = [
        f"{p.relative_to(ROOT)}:{i}"
        for p in [
            *ROOT.glob("src/**/*.py"),
            *ROOT.glob("tests/*.py"),
            *ROOT.glob("scripts/*.py"),
            ROOT / "app.py",
        ]
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1)
        if pattern.search(line) and "# binary" not in line and "pattern = re.compile" not in line
    ]
    assert not offenders, offenders

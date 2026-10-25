@echo off
REM GridGreen one-click launcher for Windows. Double-click this file.
setlocal
cd /d "%~dp0"
REM Python 3.14 on Windows: PyYAML (via Jupyter) has no Windows wheel for 3.15.
set UV_PYTHON=3.14
set PATH=%USERPROFILE%\.local\bin;%PATH%

where uv >nul 2>nul
if errorlevel 1 (
    echo [GridGreen] Installing uv, the Python package manager...
    powershell -NoProfile -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    if errorlevel 1 goto :fail
)

echo [GridGreen] Installing Python and dependencies. The first run takes a few minutes...
uv python install 3.14 || goto :fail
uv sync || goto :fail

uv run python scripts\launcher_check.py online
if errorlevel 1 (
    echo [GridGreen] NESO API not reachable. Skipping the data update.
) else (
    uv run python scripts\launcher_check.py has-data
    if errorlevel 1 (
        echo [GridGreen] Downloading one year of data from the NESO API, about a minute...
        if exist "data\gridgreen.duckdb" del "data\gridgreen.duckdb"
        uv run python scripts\run_pipeline.py --start 2025-10-01 --end 2026-10-01
    ) else (
        echo [GridGreen] Updating data from the NESO API...
        uv run python scripts\run_pipeline.py
    )
)

uv run python scripts\launcher_check.py has-data
if errorlevel 1 (
    echo [GridGreen] No real data available. Starting with SYNTHETIC demo data instead.
    if exist "data\gridgreen.duckdb" del "data\gridgreen.duckdb"
    uv run python scripts\build_demo_db.py || goto :fail
)

echo [GridGreen] Starting the dashboard at http://localhost:8501  (close this window to stop)
start "" cmd /c "timeout /t 7 >nul & start http://localhost:8501"
uv run streamlit run app.py --server.port 8501
goto :eof

:fail
echo.
echo [GridGreen] Setup failed. Copy the error above and send it to the team.
pause
exit /b 1

@echo off
TITLE XAUUSD Trading Decision Assistant
echo ===================================================
echo Starting XAUUSD Trading Decision Assistant Server...
echo ===================================================

cd /d "%~dp0"

REM Ensure PostgreSQL instance is running
if exist "%LOCALAPPDATA%\pgsql\bin\pg_ctl.exe" (
    "%LOCALAPPDATA%\pgsql\bin\pg_ctl.exe" status -D "%LOCALAPPDATA%\pgsql\data" >nul 2>&1
    if errorlevel 1 (
        echo Starting PostgreSQL server...
        "%LOCALAPPDATA%\pgsql\bin\pg_ctl.exe" start -D "%LOCALAPPDATA%\pgsql\data" -l "%LOCALAPPDATA%\pgsql\pg.log" >nul 2>&1
    )
)

REM Activate Virtual Environment
call .venv\Scripts\activate.bat

REM Run FastAPI server with auto-reload disabled for production stability
"%~dp0.venv\Scripts\python.exe" -m uvicorn api.main:app --host 0.0.0.0 --port 8000

pause

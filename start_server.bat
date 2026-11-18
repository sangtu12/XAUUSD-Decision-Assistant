@echo off
TITLE XAUUSD Trading Decision Assistant
echo ===================================================
echo Starting XAUUSD Trading Decision Assistant Server...
echo ===================================================

cd /d "%~dp0"

REM Activate Virtual Environment
call .venv\Scripts\activate.bat

REM Run FastAPI server with auto-reload disabled for production stability
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000

pause

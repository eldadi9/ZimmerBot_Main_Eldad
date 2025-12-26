@echo off
setlocal
cd /d "%~dp0"

if not exist "venv\Scripts\python.exe" (
  echo ERROR: venv not found. Run: python -m venv venv
  pause
  exit /b 1
)

echo Starting ZimmerBot API...
venv\Scripts\python.exe -m uvicorn src.api_server:app --reload --port 8000 --no-use-colors

echo Server stopped.
pause

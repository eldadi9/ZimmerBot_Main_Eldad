@echo off
setlocal
cd /d "%~dp0"

set "PY=venv\Scripts\python.exe"
if not exist "%PY%" (
  echo ERROR: venv not found in: %cd%\venv
  echo Run:
  echo   python -m venv venv
  echo   venv\Scripts\pip.exe install -r requirements.txt
  pause
  exit /b 1
)

echo Starting ZimmerBot API in a new window...
start "ZimmerBot API" cmd /k "%PY% -m uvicorn src.api_server:app --reload --port 8000 --no-use-colors"

timeout /t 2 /nobreak >nul

start "" "http://127.0.0.1:8000/docs"
start "" "http://127.0.0.1:8000/tools/features_picker.html"

echo Browser opened. Server is running in the "ZimmerBot API" window.
pause

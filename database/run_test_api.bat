@echo off
setlocal
cd /d "%~dp0\.."

echo ========================================
echo בדיקת כל ה-API Endpoints
echo ========================================
echo.

if not exist "venv\Scripts\python.exe" (
  echo ERROR: venv not found
  pause
  exit /b 1
)

set PYTHONIOENCODING=utf-8
venv\Scripts\python.exe database\test_api_endpoints.py

if errorlevel 1 (
  echo.
  echo ========================================
  echo יש בעיות שצריך לתקן!
  echo ========================================
  pause
  exit /b 1
) else (
  echo.
  echo ========================================
  echo כל הבדיקות עברו בהצלחה!
  echo ========================================
  pause
  exit /b 0
)


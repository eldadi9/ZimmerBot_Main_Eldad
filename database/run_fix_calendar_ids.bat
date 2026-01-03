@echo off
setlocal
cd /d "%~dp0\.."

echo ========================================
echo תיקון calendar_id ב-DB
echo ========================================
echo.

if not exist "venv\Scripts\python.exe" (
  echo ERROR: venv not found
  pause
  exit /b 1
)

set PYTHONIOENCODING=utf-8
venv\Scripts\python.exe database\fix_calendar_ids.py

if errorlevel 1 (
  echo.
  echo ========================================
  echo יש בעיות!
  echo ========================================
  pause
  exit /b 1
) else (
  echo.
  echo ========================================
  echo הושלם בהצלחה!
  echo ========================================
  pause
  exit /b 0
)


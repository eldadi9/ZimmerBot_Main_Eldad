@echo off
setlocal
cd /d "%~dp0"

if not exist "..\venv\Scripts\python.exe" (
  echo ERROR: venv not found. Run: python -m venv venv
  pause
  exit /b 1
)

echo ============================================================
echo Running Migration: A4 Business Facts
echo ============================================================

..\venv\Scripts\python.exe -c "import sys; sys.path.insert(0, '..'); from src.db import get_db_connection; conn = get_db_connection().__enter__(); cursor = conn.cursor(); sql = open('migration_a4_business_facts.sql', 'r', encoding='utf-8').read(); cursor.execute(sql); conn.commit(); conn.close(); print('Migration completed successfully!')"

if %ERRORLEVEL% EQU 0 (
  echo.
  echo ============================================================
  echo Migration completed successfully!
  echo ============================================================
) else (
  echo.
  echo ============================================================
  echo Migration failed!
  echo ============================================================
)

pause


@echo off
chcp 65001 >nul
echo ========================================
echo Running Migration: Add event fields
echo ========================================
echo.

cd /d "%~dp0\.."
python database/run_migration.py

echo.
echo ========================================
if %ERRORLEVEL% EQU 0 (
    echo Migration completed successfully!
) else (
    echo Migration failed!
)
echo ========================================
pause


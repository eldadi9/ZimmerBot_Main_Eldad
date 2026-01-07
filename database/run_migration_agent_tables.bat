@echo off
REM הרצת migration לטבלאות Agent Chat (שלב A1)

echo.
echo ========================================
echo הרצת Migration - טבלאות Agent Chat
echo ========================================
echo.

cd /d %~dp0
python run_migration_agent_tables.py

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ========================================
    echo Migration הושלם בהצלחה!
    echo ========================================
    echo.
    echo כעת תוכל להריץ את הבדיקה:
    echo database\run_check_agent_tables.bat
    pause
) else (
    echo.
    echo ========================================
    echo Migration נכשל
    echo ========================================
    pause
)


@echo off
chcp 65001 >nul
echo ========================================
echo Importing Bookings from Google Calendar
echo ========================================
echo.

cd /d "%~dp0\.."
python database/import_bookings_from_calendar.py

echo.
echo ========================================
if %ERRORLEVEL% EQU 0 (
    echo Import completed successfully!
) else (
    echo Import failed!
)
echo ========================================
pause


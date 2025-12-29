@echo off
chcp 65001 >nul
echo ========================================
echo Importing Cabins to Database
echo ========================================
echo.

cd /d "%~dp0\.."
python database\import_cabins_to_db.py

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ========================================
    echo Import completed successfully!
    echo ========================================
) else (
    echo.
    echo ========================================
    echo Import failed!
    echo ========================================
)

pause


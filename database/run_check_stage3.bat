@echo off
REM תיקון encoding ל-PowerShell
chcp 65001 >nul 2>&1
REM הרצת בדיקת שלב 3: מנוע תמחור
REM Windows batch script

echo ========================================
echo Stage 3: Pricing Engine Tests
echo ========================================
echo.

REM בדוק אם יש venv
if exist "..\venv\Scripts\activate.bat" (
    echo Activating virtual environment...
    call ..\venv\Scripts\activate.bat
) else if exist "..\.venv\Scripts\activate.bat" (
    echo Activating virtual environment...
    call ..\.venv\Scripts\activate.bat
) else (
    echo Warning: Virtual environment not found
    echo Continuing anyway...
    echo.
)

REM עבור לתיקיית database
cd /d "%~dp0"

REM הרץ את הבדיקה
echo Running tests...
echo.
REM הפעל Python עם UTF-8 encoding
python -X utf8 check_stage3.py
if errorlevel 1 (
    python check_stage3.py
)

REM שמור את קוד היציאה
set EXIT_CODE=%ERRORLEVEL%

echo.
if %EXIT_CODE% EQU 0 (
    echo ========================================
    echo SUCCESS: All tests passed!
    echo ========================================
) else (
    echo ========================================
    echo FAIL: Some tests failed
    echo ========================================
)

pause
exit /b %EXIT_CODE%


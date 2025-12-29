@echo off
chcp 65001 >nul
echo ========================================
echo Stage 4: Hold Mechanism Tests
echo ========================================
echo.

cd /d "%~dp0\.."
python database\check_stage4.py

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ========================================
    echo All tests passed!
    echo ========================================
) else (
    echo.
    echo ========================================
    echo Some tests failed!
    echo ========================================
)

pause


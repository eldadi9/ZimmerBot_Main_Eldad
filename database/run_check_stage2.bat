@echo off
REM סקריפט הרצה לבדיקת שלב 2 - Windows

echo ========================================
echo בדיקת שלב 2: חיבור ליומן וזמינות
echo ========================================
echo.

REM בדוק אם Python מותקן
python --version >nul 2>&1
if errorlevel 1 (
    echo שגיאה: Python לא מותקן או לא ב-PATH
    pause
    exit /b 1
)

REM הרץ את סקריפט הבדיקה
echo מריץ בדיקות...
echo.
python database\check_stage2.py

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


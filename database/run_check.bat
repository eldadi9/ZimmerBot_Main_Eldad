@echo off
REM סקריפט הרצה לבדיקת שלב 1 - Windows

echo ========================================
echo בדיקת שלב 1: מודל נתונים
echo ========================================
echo.

REM בדוק אם Python מותקן
python --version >nul 2>&1
if errorlevel 1 (
    echo שגיאה: Python לא מותקן או לא ב-PATH
    pause
    exit /b 1
)

REM בדוק אם psycopg2 מותקן
python -c "import psycopg2" >nul 2>&1
if errorlevel 1 (
    echo התקנת חבילות נדרשות...
    pip install psycopg2-binary python-dotenv
)

REM הרץ את סקריפט הבדיקה
echo מריץ בדיקות...
echo.
python check_stage1.py

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


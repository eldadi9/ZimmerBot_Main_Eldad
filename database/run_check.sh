#!/bin/bash
# סקריפט הרצה לבדיקת שלב 1 - Linux/Mac

echo "========================================"
echo "בדיקת שלב 1: מודל נתונים"
echo "========================================"
echo ""

# בדוק אם Python מותקן
if ! command -v python3 &> /dev/null; then
    echo "שגיאה: Python3 לא מותקן"
    exit 1
fi

# בדוק אם psycopg2 מותקן
python3 -c "import psycopg2" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "התקנת חבילות נדרשות..."
    pip3 install psycopg2-binary python-dotenv
fi

# הרץ את סקריפט הבדיקה
echo "מריץ בדיקות..."
echo ""
python3 check_stage1.py

if [ $? -eq 0 ]; then
    echo ""
    echo "========================================"
    echo "כל הבדיקות עברו בהצלחה!"
    echo "========================================"
    exit 0
else
    echo ""
    echo "========================================"
    echo "יש בעיות שצריך לתקן!"
    echo "========================================"
    exit 1
fi


#!/bin/bash
# הרצת בדיקת שלב 3: מנוע תמחור
# Linux/Mac shell script

echo "========================================"
echo "בדיקת שלב 3: מנוע תמחור"
echo "========================================"
echo ""

# מצא virtual environment
if [ -f "../venv/bin/activate" ]; then
    echo "מפעיל virtual environment..."
    source ../venv/bin/activate
elif [ -f "../.venv/bin/activate" ]; then
    echo "מפעיל virtual environment..."
    source ../.venv/bin/activate
else
    echo "אזהרה: לא נמצא virtual environment"
    echo "ממשיך בכל זאת..."
    echo ""
fi

# עבור לתיקיית database
cd "$(dirname "$0")"

# הרץ את הבדיקה
echo "מריץ בדיקות..."
echo ""
python3 check_stage3.py

# שמור את קוד היציאה
EXIT_CODE=$?

echo ""
if [ $EXIT_CODE -eq 0 ]; then
    echo "========================================"
    echo "✅ כל הבדיקות עברו בהצלחה!"
    echo "========================================"
else
    echo "========================================"
    echo "❌ חלק מהבדיקות נכשלו"
    echo "========================================"
fi

exit $EXIT_CODE


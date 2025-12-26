@echo off
REM סקריפט לתיקון בעיית scopes ב-token
REM מוחק את token_api.json כדי שייווצר מחדש עם scopes נכונים

echo ========================================
echo תיקון בעיית scopes ב-token
echo ========================================
echo.

if exist "data\token_api.json" (
    echo נמצא token ישן: data\token_api.json
    echo מוחק את ה-token הישן...
    del "data\token_api.json"
    echo ✓ ה-token נמחק בהצלחה
    echo.
    echo בהרצה הבאה של check_stage2.py, תתבקש לאשר מחדש את ההרשאות
    echo זה ייצור token חדש עם ה-scopes הנכונים
) else (
    echo לא נמצא token ב-data\token_api.json
    echo זה בסדר - ה-token ייווצר אוטומטית בפעם הראשונה
)

echo.
echo ========================================
echo סיום
echo ========================================
pause


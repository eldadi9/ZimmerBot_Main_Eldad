# פתרון בעיות - שגיאת HTTP 500 ב-Admin Panel

## איך לראות את השגיאה המדויקת

### 1. בדוק את הטרמינל של השרת
כשמקבלים שגיאת HTTP 500, השרת מדפיס את השגיאה המדויקת בטרמינל.

**מה לחפש:**
- `Error in /admin/bookings: ...`
- `Traceback (most recent call last):`
- `psycopg2.errors...`

### 2. בדוק את ה-Console בדפדפן
1. פתח את Developer Tools (F12)
2. לך ל-Console
3. חפש שגיאות אדומות

### 3. בדוק את Network Tab
1. פתח את Developer Tools (F12)
2. לך ל-Network
3. לחץ על `/admin/bookings`
4. לחץ על Response - תראה את השגיאה המדויקת

## שגיאות נפוצות ופתרונות

### שגיאה: "column does not exist"
**פתרון:** החסר עמודה בטבלה. הרץ את ה-migration המתאים.

### שגיאה: "relation does not exist"
**פתרון:** הטבלה לא קיימת. הרץ את `database/schema.sql`.

### שגיאה: "syntax error at or near"
**פתרון:** בעיה ב-SQL query. בדוק את הקוד ב-`src/api_server.py`.

### שגיאה: "could not connect to server"
**פתרון:** השרת PostgreSQL לא רץ או ההגדרות ב-`.env` שגויות.

## איך לשלוח את השגיאה

1. העתק את כל הטקסט מהטרמינל (החל מ-`Error in /admin/bookings`)
2. שלח את זה אליי
3. או צלם את המסך

## בדיקה מהירה

הרץ את זה בטרמינל כדי לבדוק את החיבור ל-DB:
```bash
python -c "from src.db import get_db_connection; conn = get_db_connection(); print('✅ DB connection OK')"
```


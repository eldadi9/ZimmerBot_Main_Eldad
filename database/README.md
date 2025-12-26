# שלב 1: מודל נתונים - מדריך בדיקה

## 📋 איך לבדוק את שלב 1?

### דרישות מקדימות

1. **PostgreSQL מותקן ופועל**
   ```bash
   # בדוק אם PostgreSQL פועל
   psql --version
   ```

2. **התקן את החבילות הנדרשות**
   ```bash
   pip install psycopg2-binary python-dotenv
   ```

3. **הגדר משתני סביבה**
   
   צור קובץ `.env` בשורש הפרויקט:
   ```env
   DB_HOST=localhost
   DB_PORT=5432
   DB_NAME=zimmerbot_db
   DB_USER=postgres
   DB_PASSWORD=postgres
   ```

### שלבים לביצוע

#### 1. צור את מסד הנתונים

```bash
# התחבר ל-PostgreSQL
psql -U postgres

# צור מסד נתונים
CREATE DATABASE zimmerbot_db;

# צא
\q
```

#### 2. הרץ את סקריפט ה-SQL

```bash
# Windows (PowerShell)
psql -U postgres -d zimmerbot_db -f database/schema.sql

# Linux/Mac
psql -U postgres -d zimmerbot_db -f database/schema.sql
```

או דרך psql:
```bash
psql -U postgres -d zimmerbot_db
\i database/schema.sql
\q
```

#### 3. הרץ את סקריפט הבדיקה

```bash
python database/check_stage1.py
```

### תוצאות צפויות

אם הכל תקין, תראה:
```
╔==========================================================╗
║          בדיקת שלב 1: מודל נתונים                        ║
╚==========================================================╝

============================================================
1. בדיקת קיום טבלאות
============================================================

✓ טבלה 'cabins' קיימת
✓ טבלה 'customers' קיימת
✓ טבלה 'bookings' קיימת
...

🎉 כל הבדיקות עברו! שלב 1 מוכן.
```

### פתרון בעיות

#### שגיאת חיבור למסד הנתונים
- ודא ש-PostgreSQL פועל: `pg_isready`
- בדוק את הפרטים ב-`.env`
- ודא שהמשתמש `postgres` קיים ויש לו הרשאות

#### טבלאות חסרות
- הרץ שוב את `schema.sql`
- בדוק שאין שגיאות ב-SQL

#### Foreign Keys חסרים
- ודא שהטבלאות נוצרו בסדר הנכון (customers לפני bookings)
- הרץ שוב את `schema.sql`

### Definition of Done

הסקריפט בודק את כל הנקודות:

- [x] כל הטבלאות נוצרו
- [x] קשרים (Relations) מוגדרים
- [x] Indexes על שדות חיפוש
- [x] Constraints מוגדרים
- [x] נתוני דמה הוכנסו והוצאו בהצלחה

### שלב הבא

לאחר שכל הבדיקות עברו, תוכל לעבור לשלב 2: חיבור ליומן וזמינות.


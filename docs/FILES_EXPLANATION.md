# 📚 הסבר מפורט על כל הקבצים בתיקיית `database/`

## 📋 קבצי בדיקה (Test Scripts)

### 1. `check_stage1.py`
**תפקיד:** בדיקת שלב 1 - מודל נתונים (Database Schema)
- **מה הוא בודק:**
  - קיום כל הטבלאות הנדרשות (cabins, customers, bookings, pricing_rules, transactions, notifications, audit_log)
  - קיום Foreign Keys (קשרים בין טבלאות)
  - קיום Indexes (מפתחות חיפוש)
  - Constraints (אילוצים)
  - יכולת CRUD (יצירה, קריאה, עדכון, מחיקה)
- **איך להריץ:** `python database/check_stage1.py`
- **מתי להשתמש:** אחרי יצירת מסד הנתונים והרצת `schema.sql`

#### ✅ תוצאה מתבקשת (כשהכל תקין):
```
╔==========================================================╗
║          בדיקת שלב 1: מודל נתונים                        ║
╚==========================================================================================╝

============================================================
1. בדיקת קיום טבלאות
============================================================

✓ טבלה 'cabins' קיימת
✓ טבלה 'customers' קיימת
✓ טבלה 'bookings' קיימת
✓ טבלה 'pricing_rules' קיימת
✓ טבלה 'transactions' קיימת
✓ טבלה 'notifications' קיימת
✓ טבלה 'audit_log' קיימת

============================================================
2. בדיקת Foreign Keys
============================================================

✓ Foreign Key: bookings.cabin_id → cabins.id
✓ Foreign Key: bookings.customer_id → customers.id
...

============================================================
3. בדיקת Indexes
============================================================

✓ Index: idx_cabins_calendar_id
✓ Index: idx_bookings_cabin_id
...

============================================================
4. בדיקת Constraints
============================================================

✓ Constraint: bookings.check_dates
✓ Constraint: bookings.status
...

============================================================
5. בדיקת CRUD Operations
============================================================

✓ CREATE: הצלחה
✓ READ: הצלחה
✓ UPDATE: הצלחה
✓ DELETE: הצלחה

🎉 כל הבדיקות עברו! שלב 1 מוכן.
```

#### ❌ שגיאות אפשריות ופתרונות:

1. **`psycopg2.OperationalError: could not connect to server`**
   - **סיבה:** PostgreSQL לא פועל או פרטי חיבור שגויים
   - **פתרון:**
     - ודא ש-PostgreSQL פועל: `pg_isready` או `services.msc` (Windows)
     - בדוק את הפרטים ב-`.env`: `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`
     - נסה להתחבר ידנית: `psql -U postgres -d zimmerbot_db`

2. **`relation "cabins" does not exist`**
   - **סיבה:** הטבלאות לא נוצרו
   - **פתרון:** הרץ `psql -U postgres -d zimmerbot_db -f database/schema.sql`

3. **`foreign key constraint "bookings_cabin_id_fkey" does not exist`**
   - **סיבה:** Foreign Keys לא נוצרו
   - **פתרון:** הרץ שוב את `schema.sql` (ודא שהטבלאות נוצרו בסדר הנכון)

4. **`ModuleNotFoundError: No module named 'psycopg2'`**
   - **סיבה:** החבילה לא מותקנת
   - **פתרון:** `pip install psycopg2-binary`

5. **`KeyError: 'DB_HOST'`**
   - **סיבה:** קובץ `.env` חסר או לא נטען
   - **פתרון:** צור קובץ `.env` בשורש הפרויקט עם הפרטים הנכונים

### 2. `check_stage2.py`
**תפקיד:** בדיקת שלב 2 - חיבור ליומן Google Calendar ובדיקת זמינות
- **מה הוא בודק:**
  - חיבור ל-Google Calendar API
  - קריאת צימרים מ-Google Sheets
  - רשימת אירועים ביומן
  - יצירת אירוע חדש
  - בדיקת זמינות צימר
- **איך להריץ:** `python database/check_stage2.py`
- **מתי להשתמש:** אחרי הגדרת Google Calendar credentials

#### ✅ תוצאה מתבקשת (כשהכל תקין):
```
============================================================
1. בדיקת חיבור ל-Google Calendar API
============================================================

✓ Credentials נטענו בהצלחה
✓ Calendar Service נוצר בהצלחה
✓ חיבור ל-API עובד - נמצאו 3 יומנים

============================================================
2. בדיקת יומנים לכל צימר (מ-Google Sheets)
============================================================

✓ נטענו 3 צימרים מ-Google Sheets
✓ הצימר של יולי: calendar_id קיים
✓ הצימר של אמי: calendar_id קיים
✓ הצימר של מורן: calendar_id קיים

============================================================
3. בדיקת רשימת אירועים ביומן
============================================================

✓ נמצאו X אירועים ביומן של הצימר של יולי

============================================================
4. בדיקת יצירת אירוע חדש
============================================================

✓ אירוע בדיקה נוצר בהצלחה (ID: ...)
✓ אירוע בדיקה נמחק בהצלחה

============================================================
5. בדיקת זמינות צימר
============================================================

✓ הצימר של יולי זמין בתאריכים 2026-03-01 עד 2026-03-03

🎉 כל הבדיקות עברו! שלב 2 מוכן.
```

#### ❌ שגיאות אפשריות ופתרונות:

1. **`FileNotFoundError: [Errno 2] No such file or directory: 'credentials.json'`**
   - **סיבה:** קובץ `credentials.json` לא נמצא
   - **פתרון:**
     - ודא שיש קובץ `credentials.json` ב-`data/` או בשורש הפרויקט
     - הורד את הקובץ מ-Google Cloud Console (Service Account או OAuth2)

2. **`google.auth.exceptions.RefreshError: The credentials do not contain the necessary fields`**
   - **סיבה:** Token פג תוקף או credentials לא תקינים
   - **פתרון:**
     - מחק את `token_api.json` (אם קיים)
     - הרץ שוב את הסקריפט - זה יפתח דפדפן לאימות מחדש

3. **`HttpError 404 when requesting https://www.googleapis.com/calendar/v3/calendars/...`**
   - **סיבה:** `calendar_id` שגוי או אין הרשאות ליומן
   - **פתרון:**
     - בדוק את `calendar_id` ב-Google Sheets
     - ודא שה-Service Account או OAuth2 יש לו גישה ליומן
     - הרץ `fix_calendar_ids.py` כדי לעדכן את ה-`calendar_id` ב-DB

4. **`ModuleNotFoundError: No module named 'google'`**
   - **סיבה:** חבילות Google לא מותקנות
   - **פתרון:** `pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client`

5. **`gspread.exceptions.SpreadsheetNotFound`**
   - **סיבה:** Google Sheet לא נמצא או אין גישה
   - **פתרון:**
     - בדוק את `SHEET_ID` ב-`.env`
     - ודא שה-Service Account יש לו גישה ל-Sheet
     - שתף את ה-Sheet עם ה-email של ה-Service Account

6. **`UnicodeEncodeError: 'charmap' codec can't encode character`**
   - **סיבה:** בעיית encoding ב-Windows PowerShell
   - **פתרון:** הרץ עם `chcp 65001` או `$env:PYTHONIOENCODING="utf-8"`

### 3. `check_stage3.py`
**תפקיד:** בדיקת שלב 3 - מנוע תמחור (Pricing Engine)
- **מה הוא בודק:**
  - חישוב מחיר בסיסי
  - חישוב מחיר סופ"ש
  - חישוב מחיר חג
  - חישוב מחיר עונה גבוהה
  - חישוב תוספות (addons)
  - הנחות
- **איך להריץ:** `python database/check_stage3.py`
- **מתי להשתמש:** אחרי התקנת `src/pricing.py`

#### ✅ תוצאה מתבקשת (כשהכל תקין):
```
Check 1: Basic pricing...
PASS: Check 1 passed - Basic pricing correct

Check 2: Weekend pricing...
PASS: Check 2 passed - Weekend pricing correct

Check 3: Holiday pricing...
PASS: Check 3 passed - Holiday pricing correct

Check 4: High season pricing...
PASS: Check 4 passed - High season pricing correct

Check 5: Holiday season pricing...
PASS: Check 5 passed - Holiday season pricing correct

Check 6: Addons pricing...
PASS: Check 6 passed - Addons pricing correct

Check 7: Discounts (long stay)...
PASS: Check 7 passed - Discounts correct

============================================================
🎉 כל הבדיקות עברו! שלב 3 מוכן.
============================================================
```

#### ❌ שגיאות אפשריות ופתרונות:

1. **`ModuleNotFoundError: No module named 'src.pricing'`**
   - **סיבה:** הקובץ `src/pricing.py` לא קיים
   - **פתרון:** ודא שהקובץ קיים ושה-`PricingEngine` class מוגדר

2. **`AssertionError: Expected 1000, got 1200`**
   - **סיבה:** חישוב המחיר לא נכון
   - **פתרון:**
     - בדוק את הלוגיקה ב-`PricingEngine.calculate_price_breakdown()`
     - ודא שהתאריכים נכונים (לא כוללים יום יציאה)

3. **`TypeError: 'NoneType' object is not subscriptable`**
   - **סיבה:** `cabin` dict לא מכיל את השדות הנדרשים
   - **פתרון:** ודא ש-`cabin` מכיל `base_price_night` ו-`weekend_price`

4. **`UnicodeEncodeError: 'charmap' codec can't encode character`**
   - **סיבה:** בעיית encoding ב-Windows PowerShell
   - **פתרון:** הרץ עם `chcp 65001` או `$env:PYTHONIOENCODING="utf-8"`

5. **`AttributeError: 'PricingEngine' object has no attribute 'calculate_price_breakdown'`**
   - **סיבה:** שם הפונקציה שונה או לא קיים
   - **פתרון:** בדוק את שם הפונקציה ב-`src/pricing.py` ועדכן את הסקריפט

### 4. `check_stage4.py`
**תפקיד:** בדיקת שלב 4 - מנגנון Hold (החזקת צימר)
- **מה הוא בודק:**
  - חיבור ל-Redis
  - יצירת Hold
  - שחרור Hold
  - המרת Hold להזמנה
  - מניעת הזמנה כפולה
- **איך להריץ:** `python database/check_stage4.py`
- **מתי להשתמש:** אחרי התקנת Redis והגדרת `src/hold.py`
- **הערה:** דורש Redis מותקן ופועל

#### ✅ תוצאה מתבקשת (כשהכל תקין):
```
Check 1: Redis connection...
  OK: Redis connection successful

Check 2: Create hold...
  OK: Hold created successfully (ID: hold-...)

Check 3: Check if hold exists...
  OK: Hold exists check passed

Check 4: Release hold...
  OK: Hold released successfully

Check 5: Prevent double booking...
  OK: Double booking prevention works

Check 6: Convert hold to booking...
  OK: Hold converted to booking successfully

============================================================
🎉 כל הבדיקות עברו! שלב 4 מוכן.
============================================================
```

**⚠️ אם Redis לא מותקן:**
```
Check 1: Redis connection...
  WARNING: Redis not available - hold functionality will be limited
  Install Redis to enable full hold protection
  Windows: Download from https://github.com/microsoftarchive/redis/releases
  Or use WSL: wsl --install
  Linux/Mac: sudo apt-get install redis-server (or brew install redis)
  Then start: redis-server

Check 2: Create hold...
  SKIP: Redis not available - cannot test hold creation
...
```

#### ❌ שגיאות אפשריות ופתרונות:

1. **`ModuleNotFoundError: No module named 'redis'`**
   - **סיבה:** חבילת Redis לא מותקנת
   - **פתרון:** `pip install redis==5.0.1`

2. **`redis.exceptions.ConnectionError: Error connecting to Redis`**
   - **סיבה:** Redis לא פועל
   - **פתרון:**
     - Windows: התקן Redis או השתמש ב-WSL
     - Linux/Mac: `sudo systemctl start redis` או `redis-server`
     - בדוק ש-Redis רץ: `redis-cli ping` (צריך להחזיר `PONG`)

3. **`ModuleNotFoundError: No module named 'src.hold'`**
   - **סיבה:** הקובץ `src/hold.py` לא קיים
   - **פתרון:** ודא שהקובץ קיים ושה-`HoldManager` class מוגדר

4. **`AssertionError: Hold should have hold_id`**
   - **סיבה:** יצירת Hold נכשלה
   - **פתרון:**
     - בדוק ש-Redis פועל
     - בדוק את הלוגיקה ב-`HoldManager.create_hold()`

5. **`psycopg2.OperationalError: could not connect to server`**
   - **סיבה:** PostgreSQL לא פועל (נדרש להמרת Hold להזמנה)
   - **פתרון:** ודא ש-PostgreSQL פועל והפרטים ב-`.env` נכונים

### 5. `full_flow_test.py`
**תפקיד:** בדיקה מלאה end-to-end של כל התהליך
- **מה הוא בודק:**
  1. קריאה מ-Google Sheets
  2. ייבוא ל-DB
  3. קריאה מ-DB
  4. בדיקת זמינות
  5. יצירת Hold
  6. המרת Hold להזמנה
- **איך להריץ:** `python database/full_flow_test.py`
- **מתי להשתמש:** בדיקה סופית אחרי שכל השלבים עובדים

#### ✅ תוצאה מתבקשת (כשהכל תקין):
```
============================================================
בדיקה מלאה End-to-End
============================================================

1. קריאה מ-Google Sheets...
   ✓ נמצאו 3 צימרים ב-Sheets

2. ייבוא ל-DB...
   ✓ יובאו 3 צימרים ל-DB

3. קריאה מ-DB...
   ✓ נקראו 3 צימרים מ-DB

4. בדיקת זמינות...
   ✓ נמצאו X צימרים זמינים

5. יצירת Hold...
   ✓ Hold נוצר בהצלחה (ID: hold-...)

6. המרת Hold להזמנה...
   ✓ Hold הומר להזמנה בהצלחה

🎉 כל הבדיקות עברו! המערכת עובדת מקצה לקצה.
```

#### ❌ שגיאות אפשריות ופתרונות:

1. **כל השגיאות מהשלבים הקודמים** - ראה פתרונות ב-`check_stage1.py`, `check_stage2.py`, `check_stage3.py`, `check_stage4.py`

2. **`ValueError: No cabins found in database`**
   - **סיבה:** לא יובאו צימרים ל-DB
   - **פתרון:** הרץ `import_cabins_to_db.py` לפני הבדיקה

3. **`KeyError: 'הצימר של מורן'`**
   - **סיבה:** שם הצימר לא תואם
   - **פתרון:** בדוק את שמות הצימרים ב-Google Sheets וב-DB

### 6. `test_api_endpoints.py`
**תפקיד:** בדיקת כל ה-API endpoints
- **מה הוא בודק:**
  - `/health` - בריאות השרת
  - `/cabins` - רשימת צימרים
  - `/availability` - בדיקת זמינות
  - `/quote` - הצעת מחיר
  - `/book` - יצירת הזמנה
  - `/admin/bookings` - רשימת הזמנות
  - `/admin/audit` - לוגים
- **איך להריץ:** `python database/test_api_endpoints.py`
- **מתי להשתמש:** אחרי שהשרת רץ (`run_api.bat`)
- **דרישה:** השרת צריך לרוץ על `http://127.0.0.1:8000`

#### ✅ תוצאה מתבקשת (כשהכל תקין):
```
╔==========================================================╗
║          בדיקת כל ה-API Endpoints                    ║
╚==========================================================╝

============================================================
בדיקה 1: האם השרת רץ?
============================================================

✓ השרת רץ (Status: 200)

============================================================
בדיקה 2: GET /cabins
============================================================

✓ הצלחה: נמצאו 3 צימרים

============================================================
בדיקה 3: POST /availability
============================================================

✓ הצלחה: נמצאו X צימרים זמינים

============================================================
בדיקה 4: POST /quote
============================================================

✓ הצלחה: מחיר חושב בהצלחה (₪X,XXX)

============================================================
בדיקה 5: POST /book
============================================================

✓ הצלחה: הזמנה נוצרה (ID: ...)

============================================================
בדיקה 6: GET /admin/bookings
============================================================

✓ הצלחה: נמצאו X הזמנות

============================================================
בדיקה 7: GET /admin/audit
============================================================

✓ הצלחה: נמצאו X לוגים

🎉 כל הבדיקות עברו!
```

#### ❌ שגיאות אפשריות ופתרונות:

1. **`requests.exceptions.ConnectionError: Connection refused`**
   - **סיבה:** השרת לא רץ
   - **פתרון:** הרץ `run_api.bat` או `python -m uvicorn src.api_server:app --reload --port 8000`

2. **`HTTP 500 Internal Server Error`**
   - **סיבה:** שגיאה בשרת
   - **פתרון:**
     - בדוק את הלוגים בטרמינל של השרת
     - ודא ש-PostgreSQL פועל
     - ודא ש-Google Calendar credentials תקינים

3. **`HTTP 422 Validation Error`**
   - **סיבה:** נתונים לא תקינים בבקשה
   - **פתרון:**
     - בדוק את פורמט התאריכים (YYYY-MM-DD)
     - ודא שכל השדות הנדרשים נשלחים
     - ראה `docs/SWAGGER_TESTING_GUIDE.md` לדוגמאות

4. **`HTTP 404 Not Found`**
   - **סיבה:** Endpoint לא קיים או נתיב שגוי
   - **פתרון:**
     - בדוק את הנתיב (למשל `/admin/bookings` ולא `/admin/booking`)
     - ודא שהשרת רץ על הפורט הנכון (8000)

5. **`KeyError: 'cabin_id'`**
   - **סיבה:** `cabin_id` לא נמצא בתגובה
   - **פתרון:** בדוק שהצימרים יובאו ל-DB עם `cabin_id_string`

### 7. `show_all_data.py`
**תפקיד:** הצגת כל הנתונים במסד הנתונים
- **מה הוא מציג:**
  - רשימת כל הצימרים
  - רשימת כל הלקוחות
  - רשימת כל ההזמנות
  - רשימת כל התשלומים
  - רשימת כל הלוגים
- **איך להריץ:** `python database/show_all_data.py`
- **מתי להשתמש:** לבדיקה מהירה של מה יש במסד הנתונים

#### ✅ תוצאה מתבקשת (כשהכל תקין):
```
============================================================
כל הנתונים במסד הנתונים
============================================================

📦 צימרים (3):
  - הצימר של יולי (ZB01)
  - הצימר של אמי (ZB02)
  - הצימר של מורן (ZB03)

👥 לקוחות (5):
  - שם: יוסי כהן, Email: yossi@example.com
  ...

📅 הזמנות (4):
  - הזמנה #1: הצימר של יולי, 2026-03-01 עד 2026-03-03
  ...

💳 תשלומים (4):
  - תשלום #1: ₪1,500, סטטוס: pending
  ...

📋 לוגים (10):
  - לוג #1: INSERT, table: bookings, 2026-01-15 10:30:00
  ...
```

#### ❌ שגיאות אפשריות ופתרונות:

1. **`psycopg2.OperationalError: could not connect to server`**
   - **סיבה:** PostgreSQL לא פועל
   - **פתרון:** ודא ש-PostgreSQL פועל והפרטים ב-`.env` נכונים

2. **`relation "cabins" does not exist`**
   - **סיבה:** הטבלאות לא נוצרו
   - **פתרון:** הרץ `psql -U postgres -d zimmerbot_db -f database/schema.sql`

---

## 📥 קבצי ייבוא (Import Scripts)

### 8. `import_cabins_to_db.py`
**תפקיד:** ייבוא צימרים מ-Google Sheets למסד הנתונים PostgreSQL
- **מה הוא עושה:**
  1. קורא צימרים מ-Google Sheets
  2. ממיר אותם לפורמט DB
  3. יוצר UUID דטרמיניסטי מ-cabin_id המקורי (ZB01, ZB02, וכו')
  4. שומר ב-`cabins` table
  5. מעדכן `cabin_id_string` עם ה-ID המקורי
- **איך להריץ:** `python database/import_cabins_to_db.py`
- **מתי להשתמש:** בפעם הראשונה או כשמעדכנים צימרים ב-Sheets
- **הערה:** אם הצימר כבר קיים (לפי UUID, calendar_id, או name), הוא יעודכן

#### ✅ תוצאה מתבקשת (כשהכל תקין):
```
========================================
Importing cabins from Google Sheets to PostgreSQL
==========================================

1. Reading cabins from Google Sheets...
   Found 3 cabins in Sheets

2. Connecting to database...
   ✓ Connected to PostgreSQL

3. Importing cabins...
   ✓ Imported הצימר של יולי (ZB01)
   ✓ Imported הצימר של אמי (ZB02)
   ✓ Imported הצימר של מורן (ZB03)

===========================================
Import Summary:
Imported: 3
Updated: 0
Errors: 0
Total: 3
===========================================
```

#### ❌ שגיאות אפשריות ופתרונות:

1. **`gspread.exceptions.SpreadsheetNotFound`**
   - **סיבה:** Google Sheet לא נמצא או אין גישה
   - **פתרון:**
     - בדוק את `SHEET_ID` ב-`.env`
     - שתף את ה-Sheet עם ה-email של ה-Service Account

2. **`column "updated_at" of relation "cabins" does not exist`**
   - **סיבה:** העמודה לא קיימת בטבלה
   - **פתרון:** הסקריפט אמור להוסיף את העמודה אוטומטית, אבל אם לא - הרץ:
     ```sql
     ALTER TABLE cabins ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
     ```

3. **`duplicate key value violates unique constraint "cabins_pkey"`**
   - **סיבה:** ניסיון ליצור צימר עם UUID שכבר קיים
   - **פתרון:** הסקריפט אמור לבדוק ולעדכן - אם זה קורה, בדוק את הלוגיקה

4. **`invalid input syntax for type uuid: "ZB01"`**
   - **סיבה:** ניסיון להשתמש ב-ZB01 כ-UUID ישירות
   - **פתרון:** הסקריפט אמור ליצור UUID דטרמיניסטי - בדוק את הלוגיקה

5. **`column "cabin_id_string" of relation "cabins" does not exist`**
   - **סיבה:** העמודה לא קיימת
   - **פתרון:** הסקריפט אמור להוסיף את העמודה אוטומטית, אבל אם לא - הרץ:
     ```sql
     ALTER TABLE cabins ADD COLUMN IF NOT EXISTS cabin_id_string VARCHAR(20);
     CREATE INDEX IF NOT EXISTS idx_cabins_cabin_id_string ON cabins(cabin_id_string);
     ```

### 9. `import_bookings_from_calendar.py`
**תפקיד:** ייבוא הזמנות קיימות מ-Google Calendar למסד הנתונים
- **מה הוא עושה:**
  1. קורא אירועים מכל יומני Google Calendar
  2. מפרסר את תיאור האירוע (description) לחילוץ פרטים
  3. יוצר לקוח חדש או מוצא קיים
  4. יוצר הזמנה חדשה ב-DB
  5. שומר `event_id` ו-`event_link`
- **איך להריץ:** `python database/import_bookings_from_calendar.py`
- **מתי להשתמש:** בפעם הראשונה כדי להעביר הזמנות קיימות מה-Calendar ל-DB
- **הערה:** מנסה לחלץ פרטים מתיאור האירוע (Cabin, Customer, Phone, וכו')

#### ✅ תוצאה מתבקשת (כשהכל תקין):
```
========================================
Importing bookings from Google Calendar to PostgreSQL
==========================================

1. Connecting to Google Calendar...
   ✓ Connected successfully

2. Reading events from calendars...
   ✓ Found 5 events across 3 calendars

3. Processing events...
   ✓ Processed event: הזמנה #1 (2026-03-01)
   ✓ Processed event: הזמנה #2 (2026-03-05)
   ...

4. Saving to database...
   ✓ Saved customer: יוסי כהן
   ✓ Saved booking: ID=..., Cabin=הצימר של יולי

===========================================
Import Summary:
Imported: 5 bookings
Created: 3 customers
Errors: 0
===========================================
```

#### ❌ שגיאות אפשריות ופתרונות:

1. **`null value in column "id" of relation "customers" violates not-null constraint`**
   - **סיבה:** UUID לא נוצר אוטומטית
   - **פתרון:** הסקריפט אמור ליצור UUID מפורש - בדוק את `save_customer_to_db()` ב-`src/db.py`

2. **`foreign key constraint "bookings_cabin_id_fkey" violated`**
   - **סיבה:** `cabin_id` לא נמצא בטבלת `cabins`
   - **פתרון:**
     - ודא שהצימרים יובאו ל-DB לפני ייבוא ההזמנות
     - הרץ `import_cabins_to_db.py` קודם

3. **`KeyError: 'Cabin'`**
   - **סיבה:** לא ניתן לחלץ את שם הצימר מתיאור האירוע
   - **פתרון:** הסקריפט אמור לנסות חילוץ - אם זה נכשל, עדכן את תיאור האירוע ב-Calendar

4. **`ValueError: Invalid date format`**
   - **סיבה:** תאריך לא תקין באירוע
   - **פתרון:** בדוק את תאריכי האירועים ב-Calendar

---

## 🔧 קבצי תיקון (Fix Scripts)

### 10. `fix_calendar_ids.py`
**תפקיד:** תיקון `calendar_id` ב-DB לפי Google Sheets
- **מה הוא עושה:**
  1. קורא צימרים מ-Google Sheets
  2. קורא צימרים מ-DB
  3. מתאים בין Sheets ל-DB לפי שם הצימר
  4. מעדכן `calendar_id` ב-DB לפי מה שיש ב-Sheets
- **איך להריץ:** `python database/fix_calendar_ids.py`
- **מתי להשתמש:** אם `calendar_id` ב-DB לא תואם ל-Sheets

#### ✅ תוצאה מתבקשת (כשהכל תקין):
```
========================================
Fixing calendar_id in database
==========================================

1. Reading cabins from Google Sheets...
   ✓ Found 3 cabins in Sheets

2. Reading cabins from database...
   ✓ Found 3 cabins in DB

3. Matching and updating...
   ✓ Updated הצימר של יולי: calendar_id=...
   ✓ Updated הצימר של אמי: calendar_id=...
   ✓ Updated הצימר של מורן: calendar_id=...

===========================================
Summary:
Updated: 3
Skipped: 0
Errors: 0
===========================================
```

#### ❌ שגיאות אפשריות ופתרונות:

1. **`No matching cabin found for: הצימר של יולי`**
   - **סיבה:** שם הצימר ב-Sheets לא תואם ל-DB
   - **פתרון:** בדוק את שמות הצימרים ב-Sheets וב-DB והתאם אותם

2. **`gspread.exceptions.SpreadsheetNotFound`**
   - **סיבה:** Google Sheet לא נמצא
   - **פתרון:** בדוק את `SHEET_ID` ב-`.env` ושתף את ה-Sheet עם ה-Service Account

---

## 🗄️ קבצי SQL (Database Schema)

### 11. `schema.sql`
**תפקיד:** יצירת כל הטבלאות במסד הנתונים
- **מה הוא מכיל:**
  - `cabins` - טבלת צימרים
  - `customers` - טבלת לקוחות
  - `bookings` - טבלת הזמנות
  - `quotes` - טבלת הצעות מחיר
  - `pricing_rules` - טבלת כללי תמחור
  - `transactions` - טבלת תשלומים
  - `notifications` - טבלת הודעות
  - `audit_log` - טבלת לוגים
  - Foreign Keys, Indexes, Constraints
- **איך להריץ:** `psql -U postgres -d zimmerbot_db -f database/schema.sql`
- **מתי להשתמש:** בפעם הראשונה או כשצריך ליצור מחדש את המסד

#### ✅ תוצאה מתבקשת (כשהכל תקין):
```
CREATE TABLE
CREATE TABLE
CREATE TABLE
CREATE TABLE
CREATE TABLE
CREATE TABLE
CREATE TABLE
CREATE TABLE
CREATE INDEX
CREATE INDEX
...
CREATE TRIGGER
CREATE TRIGGER
CREATE TRIGGER
```

#### ❌ שגיאות אפשריות ופתרונות:

1. **`ERROR: database "zimmerbot_db" does not exist`**
   - **סיבה:** מסד הנתונים לא נוצר
   - **פתרון:** צור את המסד: `psql -U postgres -c "CREATE DATABASE zimmerbot_db;"`

2. **`ERROR: relation "cabins" already exists`**
   - **סיבה:** הטבלאות כבר קיימות
   - **פתרון:** השתמש ב-`DROP TABLE IF EXISTS` או מחק את הטבלאות ידנית לפני הרצה

3. **`ERROR: syntax error at or near "CREATE"`**
   - **סיבה:** שגיאת syntax ב-SQL
   - **פתרון:** בדוק את הקובץ `schema.sql` - אולי יש שגיאת כתיב או נקודה-פסיק חסר

4. **`ERROR: permission denied for database zimmerbot_db`**
   - **סיבה:** אין הרשאות למשתמש
   - **פתרון:** ודא שהמשתמש `postgres` (או המשתמש ב-`.env`) יש לו הרשאות

5. **`ERROR: function "gen_random_uuid()" does not exist`**
   - **סיבה:** Extension לא מופעל
   - **פתרון:** הרץ: `psql -U postgres -d zimmerbot_db -c "CREATE EXTENSION IF NOT EXISTS pgcrypto;"`

### 12. `schema_stage1.sql`
**תפקיד:** גרסה מוקדמת של schema (למטרות היסטוריות)
- **הערה:** לא בשימוש פעיל, נשמר למטרות גיבוי

### 13. `schema_stage1_fix_names.sql`
**תפקיד:** תיקון שמות טבלאות (למטרות היסטוריות)
- **הערה:** לא בשימוש פעיל, נשמר למטרות גיבוי

### 14. `add_cabin_id_string.sql`
**תפקיד:** הוספת עמודה `cabin_id_string` לטבלת `cabins`
- **מה הוא עושה:**
  - מוסיף עמודה `cabin_id_string VARCHAR(20)`
  - יוצר index על העמודה
- **איך להריץ:** `psql -U postgres -d zimmerbot_db -f database/add_cabin_id_string.sql`
- **מתי להשתמש:** אם העמודה לא קיימת (אבל `import_cabins_to_db.py` כבר עושה את זה)

### 15. `migration_add_event_fields.sql`
**תפקיד:** הוספת `event_id` ו-`event_link` לטבלת `bookings`
- **מה הוא עושה:**
  - מוסיף עמודות `event_id` ו-`event_link` ל-`bookings`
  - יוצר טבלת `quotes` אם לא קיימת
  - יוצר indexes
- **איך להריץ:** `psql -U postgres -d zimmerbot_db -f database/migration_add_event_fields.sql`
- **מתי להשתמש:** אם העמודות לא קיימות (אבל `run_migration.py` כבר עושה את זה)

---

## 🚀 קבצי הרצה (Run Scripts)

### 16. `run_migration.py`
**תפקיד:** הרצת migration להוספת `event_id` ו-`event_link`
- **מה הוא עושה:** כמו `migration_add_event_fields.sql` אבל דרך Python
- **איך להריץ:** `python database/run_migration.py`
- **מתי להשתמש:** אם צריך להריץ migration דרך Python

#### ✅ תוצאה מתבקשת (כשהכל תקין):
```
========================================
Running Migration: Add event_id and event_link
==========================================

1. Checking if columns exist...
   ✓ Column 'event_id' does not exist - will add
   ✓ Column 'event_link' does not exist - will add

2. Adding columns...
   ✓ Added column 'event_id' to 'bookings'
   ✓ Added column 'event_link' to 'bookings'

3. Creating indexes...
   ✓ Created index on 'event_id'

===========================================
Migration completed successfully!
===========================================
```

#### ❌ שגיאות אפשריות ופתרונות:

1. **`psycopg2.OperationalError: could not connect to server`**
   - **סיבה:** PostgreSQL לא פועל
   - **פתרון:** ודא ש-PostgreSQL פועל והפרטים ב-`.env` נכונים

2. **`column "event_id" of relation "bookings" already exists`**
   - **סיבה:** העמודות כבר קיימות
   - **פתרון:** זה לא שגיאה - הסקריפט אמור לבדוק ולקפוץ אם כבר קיים

3. **`relation "bookings" does not exist`**
   - **סיבה:** הטבלה לא קיימת
   - **פתרון:** הרץ `schema.sql` לפני הרצת ה-migration

### 17. `run_check.bat` / `run_check.sh`
**תפקיד:** הרצת כל בדיקות השלבים (1-4)
- **מה הוא עושה:** מריץ `check_stage1.py`, `check_stage2.py`, `check_stage3.py`, `check_stage4.py`
- **איך להריץ:** Windows: `database\run_check.bat` | Linux/Mac: `bash database/run_check.sh`
- **מתי להשתמש:** בדיקה מלאה של כל השלבים

### 18. `run_check_stage2.bat` / `run_check_stage2.sh`
**תפקיד:** הרצת בדיקת שלב 2 בלבד
- **איך להריץ:** Windows: `database\run_check_stage2.bat` | Linux/Mac: `bash database/run_check_stage2.sh`

### 19. `run_check_stage3.bat` / `run_check_stage3.sh` / `run_check_stage3.ps1`
**תפקיד:** הרצת בדיקת שלב 3 בלבד
- **איך להריץ:** Windows: `database\run_check_stage3.bat` או `powershell database/run_check_stage3.ps1` | Linux/Mac: `bash database/run_check_stage3.sh`

### 20. `run_check_stage4.bat`
**תפקיד:** הרצת בדיקת שלב 4 בלבד
- **איך להריץ:** `database\run_check_stage4.bat`

### 21. `run_import_cabins.bat`
**תפקיד:** הרצת ייבוא צימרים
- **איך להריץ:** `database\run_import_cabins.bat`

### 22. `run_import_bookings.bat`
**תפקיד:** הרצת ייבוא הזמנות
- **איך להריץ:** `database\run_import_bookings.bat`

### 23. `run_fix_calendar_ids.bat`
**תפקיד:** הרצת תיקון calendar_id
- **איך להריץ:** `database\run_fix_calendar_ids.bat`

### 24. `run_test_api.bat`
**תפקיד:** הרצת בדיקת API endpoints
- **איך להריץ:** `database\run_test_api.bat`
- **דרישה:** השרת צריך לרוץ על `http://127.0.0.1:8000`

### 25. `fix_token_scopes.bat`
**תפקיד:** תיקון scopes של Google OAuth token
- **מה הוא עושה:** מוחק את `token_api.json` כדי לכפות re-authentication עם scopes חדשים
- **איך להריץ:** `database\fix_token_scopes.bat`
- **מתי להשתמש:** אם יש שגיאת permissions ב-Google API

---

## 📖 קבצי תיעוד

### 26. `DATABASE_README.md` (בתיקיית `docs/`)
**תפקיד:** מדריך בדיקה לשלב 1
- **מה הוא מכיל:** הוראות מפורטות איך לבדוק את שלב 1

---

## 🔍 סיכום - מתי להשתמש בכל קובץ

### בפעם הראשונה (Setup):
1. `schema.sql` - יצירת מסד הנתונים
2. `import_cabins_to_db.py` - ייבוא צימרים
3. `import_bookings_from_calendar.py` - ייבוא הזמנות קיימות
4. `check_stage1.py` - בדיקה שהכל עובד

### בדיקות תקופתיות:
- `test_api_endpoints.py` - בדיקת API
- `show_all_data.py` - הצגת נתונים
- `full_flow_test.py` - בדיקה מלאה

### תיקונים:
- `fix_calendar_ids.py` - אם calendar_id לא תואם
- `fix_token_scopes.bat` - אם יש בעיית permissions

### Migrations:
- `run_migration.py` - אם צריך להוסיף עמודות חדשות

---

## ⚠️ הערות חשובות

1. **סדר הרצה חשוב:**
   - קודם `schema.sql`
   - אחר כך `import_cabins_to_db.py`
   - אחר כך `import_bookings_from_calendar.py`

2. **דרישות:**
   - PostgreSQL מותקן ופועל
   - Google Calendar credentials מוגדרים
   - Redis (רק לשלב 4 - Hold)

3. **קבצי Batch:**
   - כל קבצי ה-`.bat` הם wrappers ל-Python scripts
   - הם פשוט קוראים ל-Python script המתאים
   - אפשר להריץ ישירות את ה-Python scripts


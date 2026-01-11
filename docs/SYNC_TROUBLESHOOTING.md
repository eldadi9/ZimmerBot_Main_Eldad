# פתרון בעיות סנכרון (Sync Troubleshooting)

## סטטוס נוכחי
- **Calendar → DB**: 17 שגיאות (0 הועתקו, 0 עודכנו)
- **Sheets → DB**: 4 שגיאות (0 הועתקו, 0 עודכנו)

## איך לראות את השגיאות המדויקות

### שלב 1: בדוק את הטרמינל של FastAPI Server
1. פתח את הטרמינל שבו רץ ה-FastAPI server (איפה הרצת `uvicorn` או `python -m uvicorn`)
2. הרץ שוב את הסנכרון דרך Admin Panel → Sync
3. חפש הודעות שמתחילות ב-`❌ Error` או `❌ Failed`
4. העתק את ההודעות המדויקות

### שלב 2: בדוק את הקונסול בדפדפן (F12)
1. לחץ F12 בדפדפן
2. פתח את הטאב "Console"
3. הרץ שוב את הסנכרון
4. חפש הודעות שגיאה ב-Console

## שגיאות נפוצות ופתרונות

### Calendar → DB: 17 שגיאות

#### סיבה אפשרית 1: אירועים ללא event_id תקין
**תסמין**: `Warning: Event has no ID, skipping`
**פתרון**: זה תקין - אירועים מסוימים אולי לא ניתנים לזיהוי. זה לא בעיה קריטית.

#### סיבה אפשרית 2: בעיות עם cabin_id
**תסמין**: `Error: Cabin has no id/cabin_id` או `invalid input syntax for type uuid`
**פתרון**: 
- ודא שכל הצימרים בטבלת `cabins` יש להם `id` (UUID)
- ודא שה-`calendar_id` קיים לכל צימר

#### סיבה אפשרית 3: בעיות עם parsing תאריכים
**תסמין**: `Error parsing dates for event...`
**פתרון**: 
- ודא שאירועי Calendar יש להם `start.dateTime` או `start.date` תקינים
- בדוק את format של התאריכים

#### סיבה אפשרית 4: בעיות עם שמירת booking/customer
**תסמין**: `Failed to create booking` או `Failed to create/find customer`
**פתרון**:
- בדוק את הטרמינל לראות את השגיאה המדויקת
- ודא שה-DB connection עובד
- בדוק שאין בעיות עם UUID format

### Sheets → DB: 4 שגיאות

#### סיבה אפשרית 1: עמודות חסרות ב-Google Sheets
**תסמין**: `Error syncing cabin...: KeyError` או `column does not exist`
**פתרון**:
- ודא שב-Google Sheets יש את כל העמודות הנדרשות:
  - `Cabin ID` (או `cabin_id`)
  - `Name`
  - `Calendar ID` (או `calendar_id`)
  - `Street name + number` (אופציונלי)
  - `City` (אופציונלי)
  - `Postal code` (אופציונלי)

#### סיבה אפשרית 2: בעיות עם format של נתונים
**תסמין**: `Error syncing cabin...: invalid literal for int()` או `could not convert string to float`
**פתרון**:
- ודא ש-`max_adults`, `max_kids`, `base_price_night` הם מספרים תקינים
- בדוק שאין תווים מיוחדים בשמות

#### סיבה אפשרית 3: בעיות עם features JSON
**תסמין**: `Error syncing cabin...: invalid input syntax for type jsonb`
**פתרון**:
- ודא ש-`Features` ב-Sheets הוא רשימה מופרדת בפסיקים (למשל: `jacuzzi,pool,bbq`)
- או שמור אותו ריק אם אין תכונות

## צעדים לפתרון

### 1. בדוק את השגיאות המדויקות בטרמינל
```bash
# בטרמינל שבו רץ FastAPI server
# אחרי הרצת סנכרון, חפש:
❌ Error processing event...
❌ Error syncing cabin...
❌ Failed to create booking...
```

### 2. בדוק את ה-DB
```sql
-- בדוק שכל הצימרים יש להם id ו-calendar_id
SELECT id, name, calendar_id FROM cabins WHERE calendar_id IS NULL;

-- בדוק שיש bookings עם event_id
SELECT id, event_id, cabin_id, customer_id FROM bookings WHERE event_id IS NOT NULL LIMIT 10;
```

### 3. בדוק את Google Calendar
- ודא שה-`calendar_id` של כל צימר תקין
- ודא שיש הרשאות ל-Google Calendar API
- בדוק שיש אירועים ביומן בתאריכים המבוקשים

### 4. בדוק את Google Sheets
- ודא שיש גישה ל-Google Sheets
- ודא שכל העמודות הנדרשות קיימות
- בדוק את format של הנתונים

## הוספת logging מפורט

כבר הוספתי logging מפורט יותר. עכשיו אמורות להופיע הודעות כמו:
- `✅ Imported new booking...`
- `✅ Updated booking...`
- `❌ Error processing event...`
- `⚠️ Warning: Cabin... has no calendar_id`

אם אתה עדיין רואה שגיאות, העתק את ההודעות המדויקות מהטרמינל ושלח אותן.

## בדיקה מהירה

נסה להריץ את זה ב-Python כדי לבדוק את החיבורים:
```python
from src.db import get_db_connection
from src.sync_calendar import sync_calendar_to_db
from src.sync_sheets import sync_sheets_to_db

# בדוק DB connection
try:
    with get_db_connection() as conn:
        print("✅ DB connection OK")
except Exception as e:
    print(f"❌ DB connection error: {e}")

# הרץ סנכרון (זה ידפיס את כל השגיאות)
print("\n=== Testing Calendar → DB ===")
sync_calendar_to_db(days_back=30, days_forward=365)

print("\n=== Testing Sheets → DB ===")
sync_sheets_to_db()
```

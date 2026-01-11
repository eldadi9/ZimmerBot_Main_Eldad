 # ✅ סיכום תיקונים ותכנית סנכרון

> 📅 **תאריך:** ינואר 2026

---

## ✅ תיקון 1: "תזמין" לא יוצר HOLD ישירות ✅

### הבעיה:
המשתמש אומר "תזמין" או "עשה הזמנה", הסוכן יוצר HOLD ישירות בלי לעבור דרך:
1. הצעת מחיר
2. טופס פרטי לקוח

### הפתרון:
- ✅ תיקון `src/agent.py` - "תזמין" בודק אם יש quote קודם
- ✅ תיקון `src/api_server.py` - אם אין quote, מבקש quote קודם
- ✅ הסרת קוד ישן שיצר HOLD ישירות

### תהליך חדש:
```
משתמש: "תזמין"
→ אם אין quote: "בואו נתחיל בהצעת מחיר..." + trigger quote
→ אם יש quote: "מעולה! בואו נתחיל בהזמנה..." + request customer details
→ רק אחרי customer details → יצירת HOLD
```

### קבצים ששונו:
- `src/agent.py` - שורות 112-118 (תיקון detect_intent)
- `src/api_server.py` - שורות 2693-2760 (תיקון booking_flow logic)

---

## 🔄 תכנית סנכרון 2: Google Sheets ↔ DB

### מה צריך:

#### 2.1 סנכרון Sheets → DB (קיים, צריך שיפור)
- ✅ `database/import_cabins_to_db.py` - קיים
- ⚠️ צריך: endpoint אוטומטי או scheduled task

#### 2.2 סנכרון DB → Sheets (חדש)
- ❌ עדכון Google Sheets כשמשנים נתונים ב-DB
- ❌ הוספת צימרים חדשים ל-Sheets

### פתרון מוצע:

**Option A: Endpoints (מומלץ לשלב ראשון)**
- `POST /admin/sync/sheets-to-db` - סנכרון Sheets → DB
- `POST /admin/sync/db-to-sheets` - סנכרון DB → Sheets
- `POST /admin/sync/bidirectional` - סנכרון דו-כיווני

**Option B: Scheduled Task (אופציונלי)**
- סקריפט שרץ כל X דקות/שעות
- מסנכרן אוטומטית

---

## 📅 תכנית סנכרון 3: Google Calendar ↔ DB

### מה צריך:

#### 3.1 סנכרון Calendar → DB (קיים חלקית)
- ✅ `database/import_bookings_from_calendar.py` - קיים
- ⚠️ צריך: זיהוי שינויים (שם, מייל, תאריכים) ועדכון DB

#### 3.2 סנכרון DB → Calendar (קיים)
- ✅ `create_calendar_event()` - קיים
- ⚠️ צריך: `update_calendar_event()` - עדכון אירוע קיים

### פתרון מוצע:

**Option A: Endpoint + Polling (מומלץ)**
- `POST /admin/sync/calendar-to-db` - סנכרון Calendar → DB
- `POST /admin/sync/db-to-calendar` - סנכרון DB → Calendar
- סקריפט `database/sync_calendar_auto.py` - רץ כל X דקות, בודק שינויים

**Option B: Webhook (מורכב יותר)**
- Google Calendar Push Notifications
- דורש HTTPS endpoint

---

## 🎯 מה לעשות עכשיו?

### שלב 1: בדיקת תיקון "תזמין" ✅
1. הפעל את השרת
2. פתח `tools/features_picker.html` → Agent Chat
3. נסה: "הצימר של יולי - תזמין"
4. **צריך לראות:** "בואו נתחיל בהצעת מחיר..." (לא HOLD ישירות!)

### שלב 2: בניית ממשקי סנכרון ❌

#### 2.1 Endpoint לסנכרון Sheets → DB
- [ ] `POST /admin/sync/sheets-to-db`
- [ ] שימוש ב-`database/import_cabins_to_db.py`
- [ ] החזרת סטטוס

#### 2.2 Endpoint לסנכרון DB → Sheets
- [ ] `POST /admin/sync/db-to-sheets`
- [ ] קריאה ל-Google Sheets API
- [ ] עדכון/הוספת שורות

#### 2.3 Endpoint לסנכרון Calendar → DB
- [ ] `POST /admin/sync/calendar-to-db`
- [ ] זיהוי שינויים (שם, מייל, תאריכים)
- [ ] עדכון DB

#### 2.4 פונקציה `update_calendar_event()`
- [ ] `src/main.py` - פונקציה חדשה
- [ ] עדכון אירוע קיים ב-Google Calendar

---

## 📁 קבצים שצריך ליצור

### קבצים חדשים:
1. `src/sync_sheets.py` - פונקציות סנכרון Google Sheets
2. `src/sync_calendar.py` - פונקציות סנכרון Google Calendar
3. `database/sync_calendar_auto.py` - סקריפט סנכרון אוטומטי (Calendar)

### קבצים שצריך לשנות:
1. `src/api_server.py`:
   - הוספת endpoints: `/admin/sync/sheets-to-db`, `/admin/sync/db-to-sheets`, `/admin/sync/calendar-to-db`
   
2. `src/main.py`:
   - הוספת `update_calendar_event()` - עדכון אירוע קיים

---

## 📝 הערות חשובות

### סנכרון דו-כיווני:
- צריך לזהות איזה מקור הוא "מקור האמת" (source of truth)
- למנוע לולאות אינסופיות של עדכונים
- להשתמש ב-`updated_at` timestamps

### זיהוי שינויים ב-Calendar:
- Google Calendar: `event.updated` timestamp
- Database: `bookings.updated_at` column
- השוואה: אם `event.updated > booking.updated_at` → עדכן DB

### זיהוי שינויים ב-Sheets:
- Google Sheets: אין `updated_at` מובנה
- Database: `cabins.updated_at` column
- פתרון: השוואת hash או כל השורות

---

**סיכום:** תיקנתי את הלוגיקה של "תזמין" כך שלא יוצר HOLD ישירות. עכשיו צריך לבנות את ממשקי הסנכרון.

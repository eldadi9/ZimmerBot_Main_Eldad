# 🔄 סיכום ממשקי סנכרון

> 📅 **תאריך:** ינואר 2026

---

## ✅ מה נבנה

### 1. קבצים חדשים:
- ✅ `src/sync_sheets.py` - פונקציות סנכרון Google Sheets ↔ DB
- ✅ `src/sync_calendar.py` - פונקציות סנכרון Google Calendar ↔ DB

### 2. Endpoints חדשים ב-`src/api_server.py`:
- ✅ `POST /admin/sync/sheets-to-db` - סנכרון Sheets → DB
- ✅ `POST /admin/sync/db-to-sheets` - סנכרון DB → Sheets
- ✅ `POST /admin/sync/calendar-to-db` - סנכרון Calendar → DB (זיהוי שינויים)
- ✅ `POST /admin/sync/db-to-calendar` - סנכרון DB → Calendar

### 3. פונקציות חדשות ב-`src/main.py`:
- ✅ `update_calendar_event()` - עדכון אירוע קיים ב-Google Calendar

---

## 📋 איך להשתמש

### סנכרון Google Sheets → DB:
```bash
curl -X POST http://127.0.0.1:8000/admin/sync/sheets-to-db
```

**תגובה:**
```json
{
  "success": true,
  "imported": 2,
  "updated": 1,
  "errors": 0,
  "message": "Synced 2 imported, 1 updated, 0 errors"
}
```

### סנכרון DB → Google Sheets:
```bash
curl -X POST http://127.0.0.1:8000/admin/sync/db-to-sheets
```

**תגובה:**
```json
{
  "success": true,
  "updated": 3,
  "errors": 0,
  "message": "Synced 3 rows to Sheets, 0 errors"
}
```

### סנכרון Google Calendar → DB:
```bash
curl -X POST "http://127.0.0.1:8000/admin/sync/calendar-to-db?days_back=30&days_forward=365"
```

**תגובה:**
```json
{
  "success": true,
  "imported": 5,
  "updated": 2,
  "errors": 0,
  "message": "Synced 5 imported, 2 updated, 0 errors"
}
```

**מה זה עושה:**
- בודק שינויים ב-Google Calendar (שם, מייל, תאריכים)
- מעדכן DB אם `event.updated > booking.updated_at`
- יוצר bookings חדשים אם לא קיימים

### סנכרון DB → Google Calendar:
```bash
# סנכרון כל ההזמנות האחרונות (30 יום אחורה, 365 יום קדימה)
curl -X POST http://127.0.0.1:8000/admin/sync/db-to-calendar

# סנכרון הזמנה ספציפית
curl -X POST "http://127.0.0.1:8000/admin/sync/db-to-calendar?booking_id=123e4567-e89b-12d3-a456-426614174000"
```

**תגובה:**
```json
{
  "success": true,
  "updated": 3,
  "errors": 0,
  "message": "Synced 3 bookings to Calendar, 0 errors"
}
```

---

## 🔧 פרטים טכניים

### סנכרון Sheets → DB:
- קורא מ-Google Sheets
- בודק אם cabin קיים (by `calendar_id` or `name`)
- מעדכן אם קיים, מוסיף אם חדש
- מעדכן `updated_at` timestamp

### סנכרון DB → Sheets:
- קורא מ-DB
- מוצא שורה ב-Sheets (by `cabin_id_string`, `calendar_id`, or `name`)
- מעדכן שורה קיימת או מוסיף שורה חדשה

### סנכרון Calendar → DB:
- בודק `event.updated` timestamp
- משווה ל-`booking.updated_at` ב-DB
- מעדכן DB אם Calendar חדש יותר
- מעדכן שם לקוח, תאריכים, event_link

### סנכרון DB → Calendar:
- קורא bookings מ-DB
- מעדכן אירועים ב-Google Calendar
- משתמש ב-`update_calendar_event()` ב-`src/main.py`

---

## 🎯 איפה לבדוק

1. **Swagger UI:**
   - פתח `http://127.0.0.1:8000/docs`
   - חפש `/admin/sync/*` endpoints

2. **Postman/curl:**
   - השתמש ב-endpoints למעלה

3. **Admin Panel:**
   - אפשר להוסיף כפתורים ב-`tools/features_picker.html` לסנכרון

---

## 📝 הערות חשובות

### זיהוי שינויים:
- **Calendar → DB:** משתמש ב-`event.updated` timestamp
- **DB → Calendar:** משתמש ב-`booking.updated_at` timestamp
- **Sheets ↔ DB:** אין timestamps מובנים - צריך השוואת hash או כל השורות

### Error Handling:
- כל endpoint מחזיר `success`, `errors`, ו-`message`
- שגיאות לא עוצרות את התהליך - ממשיך עם שאר הפריטים

### Performance:
- סנכרון Calendar → DB: בודק רק 30 יום אחורה + 365 יום קדימה (ברירת מחדל)
- סנכרון DB → Calendar: בודק רק 30 יום אחורה + 365 יום קדימה (ברירת מחדל)

---

**סיכום:** כל ממשקי הסנכרון מוכנים לשימוש! 🎉

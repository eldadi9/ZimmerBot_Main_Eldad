# 🔄 תכנית סנכרון - Google Sheets ↔ DB ↔ Google Calendar

> 📅 **תאריך:** ינואר 2026  
> 🎯 **מטרה:** יצירת ממשקי סנכרון דו-כיווניים

---

## 📊 סטטוס נוכחי

### ✅ קיים:
- ✅ `database/import_cabins_to_db.py` - סנכרון חד-כיווני: Google Sheets → DB
- ✅ `database/import_bookings_from_calendar.py` - סנכרון חד-כיווני: Google Calendar → DB

### ❌ חסר:
- ❌ סנכרון דו-כיווני: Google Sheets ↔ DB
- ❌ סנכרון דו-כיווני: Google Calendar ↔ DB
- ❌ Webhook/Polling לזיהוי שינויים ב-Google Calendar
- ❌ Endpoint לסנכרון אוטומטי

---

## 🔄 סנכרון 1: Google Sheets ↔ DB

### מה צריך:

#### 1.1 סנכרון Sheets → DB (קיים, צריך שיפור)
- ✅ `database/import_cabins_to_db.py` - קיים
- ⚠️ צריך: endpoint אוטומטי, webhook, או scheduled task

#### 1.2 סנכרון DB → Sheets (חדש)
- ❌ עדכון Google Sheets כשמשנים נתונים ב-DB
- ❌ הוספת צימרים חדשים ל-Sheets
- ❌ עדכון מחירים, תכונות, וכו'

### פתרון מוצע:

**Option A: Scheduled Task (מומלץ)**
- סקריפט שרץ כל X דקות/שעות
- בודק שינויים ב-`updated_at` ב-DB
- מסנכרן עם Google Sheets

**Option B: Manual Endpoint**
- `POST /admin/sync/sheets-to-db` - סנכרון Sheets → DB
- `POST /admin/sync/db-to-sheets` - סנכרון DB → Sheets
- `POST /admin/sync/bidirectional` - סנכרון דו-כיווני

**Option C: Webhook (מורכב יותר)**
- Google Apps Script ב-Sheets
- שולח webhook כשמשנים נתונים
- מעדכן DB

---

## 📅 סנכרון 2: Google Calendar ↔ DB

### מה צריך:

#### 2.1 סנכרון Calendar → DB (קיים חלקית)
- ✅ `database/import_bookings_from_calendar.py` - קיים
- ⚠️ צריך: זיהוי שינויים (שם, מייל, תאריכים)

#### 2.2 סנכרון DB → Calendar (קיים)
- ✅ `create_calendar_event()` - קיים
- ✅ `update_calendar_event()` - צריך ליצור

### פתרון מוצע:

**Option A: Polling (מומלץ)**
- סקריפט שרץ כל X דקות
- בודק שינויים ב-Google Calendar (על בסיס `updated` timestamp)
- מעדכן DB בהתאם

**Option B: Webhook (מורכב יותר)**
- Google Calendar Push Notifications
- דורש HTTPS endpoint
- מורכב יותר להגדרה

**Option C: Manual Endpoint**
- `POST /admin/sync/calendar-to-db` - סנכרון Calendar → DB
- `POST /admin/sync/db-to-calendar` - סנכרון DB → Calendar

---

## 🎯 תכנית יישום

### שלב 1: תיקון לוגיקת "תזמין" ✅ (בתהליך)
- [x] תיקון `src/agent.py` - "תזמין" לא יוצר HOLD ישירות
- [x] תיקון `src/api_server.py` - בדיקת quote לפני יצירת HOLD

### שלב 2: סנכרון Google Sheets ↔ DB ❌

#### 2.1 Endpoint לסנכרון Sheets → DB
- [ ] `POST /admin/sync/sheets-to-db`
- [ ] שימוש ב-`database/import_cabins_to_db.py`
- [ ] החזרת סטטוס: כמה עודכן, כמה נוסף

#### 2.2 Endpoint לסנכרון DB → Sheets
- [ ] `POST /admin/sync/db-to-sheets`
- [ ] קריאה ל-Google Sheets API
- [ ] עדכון שורות קיימות / הוספת שורות חדשות

#### 2.3 Scheduled Task (אופציונלי)
- [ ] סקריפט `database/sync_sheets_auto.py`
- [ ] רץ כל X דקות/שעות
- [ ] מסנכרן אוטומטית

### שלב 3: סנכרון Google Calendar → DB ❌

#### 3.1 Endpoint לסנכרון Calendar → DB
- [ ] `POST /admin/sync/calendar-to-db`
- [ ] קריאה ל-Google Calendar API
- [ ] זיהוי שינויים (שם, מייל, תאריכים)
- [ ] עדכון DB בהתאם

#### 3.2 פונקציה `update_calendar_event()`
- [ ] `src/main.py` - פונקציה חדשה
- [ ] עדכון אירוע קיים ב-Google Calendar
- [ ] שימוש ב-`event_id` לזיהוי

#### 3.3 Polling לזיהוי שינויים (אופציונלי)
- [ ] סקריפט `database/sync_calendar_auto.py`
- [ ] רץ כל X דקות
- [ ] בודק שינויים ב-Google Calendar
- [ ] מעדכן DB

---

## 📁 קבצים שצריך ליצור/לשנות

### קבצים חדשים:
1. `src/sync_sheets.py` - פונקציות סנכרון Google Sheets
2. `src/sync_calendar.py` - פונקציות סנכרון Google Calendar
3. `database/sync_sheets_auto.py` - סקריפט סנכרון אוטומטי (Sheets)
4. `database/sync_calendar_auto.py` - סקריפט סנכרון אוטומטי (Calendar)

### קבצים שצריך לשנות:
1. `src/api_server.py`:
   - הוספת endpoints: `/admin/sync/sheets-to-db`, `/admin/sync/db-to-sheets`, `/admin/sync/calendar-to-db`
   
2. `src/main.py`:
   - הוספת `update_calendar_event()` - עדכון אירוע קיים
   
3. `src/db.py`:
   - פונקציות לעדכון bookings מה-Calendar
   - פונקציות לעדכון cabins מה-Sheets

---

## 🔧 פרטים טכניים

### Google Sheets API:
- **Read:** `read_cabins_from_sheet()` - קיים
- **Write:** צריך ליצור `write_cabins_to_sheet()`
- **Update:** צריך ליצור `update_cabin_in_sheet()`

### Google Calendar API:
- **Read:** `list_calendar_events()` - קיים
- **Create:** `create_calendar_event()` - קיים
- **Update:** צריך ליצור `update_calendar_event()`
- **Watch:** Google Calendar Push Notifications (אופציונלי)

### Database:
- **Cabins:** טבלה `cabins` עם `updated_at`
- **Bookings:** טבלה `bookings` עם `event_id`, `updated_at`
- **Sync Log:** טבלה `sync_log` (אופציונלי) - לוג של סנכרונים

---

## 📝 הערות חשובות

### סנכרון דו-כיווני:
- צריך לזהות איזה מקור הוא "מקור האמת" (source of truth)
- למנוע לולאות אינסופיות של עדכונים
- להשתמש ב-`updated_at` timestamps

### זיהוי שינויים:
- Google Calendar: `event.updated` timestamp
- Google Sheets: `updated_at` column (אם קיים) או השוואת hash
- Database: `updated_at` column

### Error Handling:
- טיפול בשגיאות API
- Retry logic
- Logging של שגיאות

---

**סיכום:** צריך ליצור ממשקים לסנכרון דו-כיווני בין Google Sheets ↔ DB ו-Google Calendar ↔ DB, עם endpoints ידניים ו/או scheduled tasks אוטומטיים.

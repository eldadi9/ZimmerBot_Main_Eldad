# מדריך בדיקה מפורט - שלב 4: Hold Mechanism

## 📋 תוכן עניינים

1. [הכנה לבדיקה](#הכנה-לבדיקה)
2. [זרימת עבודה מלאה](#זרימת-עבודה-מלאה)
3. [בדיקות שלב אחר שלב](#בדיקות-שלב-אחר-שלב)
4. [מה רואים ואיפה](#מה-רואים-ואיפה)
5. [ביטול Hold](#ביטול-hold)
6. [המרה להזמנה](#המרה-להזמנה)

---

## 🔧 הכנה לבדיקה

### 1. התקנת Redis (אופציונלי אבל מומלץ)

**Windows:**
```bash
# הורד מ: https://github.com/microsoftarchive/redis/releases
# או השתמש ב-WSL
wsl --install
```

**הרצת Redis:**
```bash
# Windows (אם הותקן)
redis-server

# WSL/Linux
sudo systemctl start redis
# או
redis-server
```

**בדיקה ש-Redis עובד:**
```bash
redis-cli ping
# צריך להחזיר: PONG
```

### 2. בדיקת חיבור למערכת

```bash
# בדוק שהשרת רץ
curl http://127.0.0.1:8000/health

# בדוק שיש צימרים
curl http://127.0.0.1:8000/cabins
```

---

## 🔄 זרימת עבודה מלאה

### תרשים זרימה:

```
1. לקוח בוחר צימר
        ↓
2. POST /hold → יצירת Hold (15 דקות)
   ├─ Redis: שמירת Hold
   └─ Calendar: יצירת אירוע HOLD (צהוב)
        ↓
3. לקוח משלם (בתוך 15 דקות)
        ↓
4. POST /book עם hold_id → המרה להזמנה
   ├─ Redis: מחיקת Hold
   ├─ Calendar: עדכון אירוע ל-CONFIRMED (ירוק)
   └─ DB: שמירת הזמנה
        ↓
5. אם לא שולם תוך 15 דקות:
   ├─ Redis: Hold מתפוגג אוטומטית
   └─ Calendar: אירוע HOLD נשאר (ניתן למחיקה ידנית)
```

---

## 🧪 בדיקות שלב אחר שלב

### בדיקה 1: יצירת Hold

**בדיקה ב-Swagger:**
1. פתח: `http://127.0.0.1:8000/docs`
2. מצא: `POST /hold`
3. לחץ על "Try it out"
4. הזן:
```json
{
  "cabin_id": "ZB01",
  "check_in": "2026-03-01 15:00",
  "check_out": "2026-03-03 11:00",
  "customer_name": "ישראל ישראלי"
}
```
5. לחץ "Execute"

**תוצאה צפויה:**
```json
{
  "hold_id": "uuid-here",
  "cabin_id": "ZB01",
  "check_in": "2026-03-01 15:00",
  "check_out": "2026-03-03 11:00",
  "expires_at": "2026-03-01T15:15:00",
  "status": "active",
  "message": "Hold created successfully"
}
```

**מה קורה בפועל:**
- ✅ Hold נשמר ב-Redis (אם זמין)
- ✅ אירוע HOLD נוצר ב-Google Calendar
- ✅ Hold תקף ל-15 דקות

**איפה רואים:**
1. **Redis:** `redis-cli KEYS "hold:*"` - רשימת כל ה-Holds
2. **Calendar:** פתח את יומן הצימר - תראה אירוע "🔒 HOLD | ישראל ישראלי"
3. **API Response:** `hold_id` ו-`expires_at` בתשובה

---

### בדיקה 2: בדיקת סטטוס Hold

**בדיקה ב-Swagger:**
1. מצא: `GET /hold/{hold_id}`
2. הזן את ה-`hold_id` מהבדיקה הקודמת
3. לחץ "Execute"

**תוצאה צפויה:**
```json
{
  "hold_id": "uuid-here",
  "cabin_id": "ZB01",
  "check_in": "2026-03-01",
  "check_out": "2026-03-03",
  "expires_at": "2026-03-01T15:15:00",
  "status": "active",
  "customer_name": "ישראל ישראלי"
}
```

**מה קורה בפועל:**
- ✅ בדיקת Hold ב-Redis
- ✅ החזרת פרטי Hold

**איפה רואים:**
- **API Response:** כל פרטי ה-Hold
- **Redis:** `redis-cli GET "hold:by_id:{hold_id}"`

---

### בדיקה 3: מניעת Hold כפול

**בדיקה ב-Swagger:**
1. נסה ליצור Hold נוסף לאותו צימר ותאריכים
2. `POST /hold` עם אותם פרטים

**תוצאה צפויה:**
```json
{
  "detail": "Cabin ZB01 is already on hold until 2026-03-01T15:15:00"
}
```

**מה קורה בפועל:**
- ❌ Hold שני נדחה
- ✅ המערכת מונעת דאבל בוקינג

**איפה רואים:**
- **API Response:** שגיאה 400 או 409
- **Redis:** רק Hold אחד קיים

---

### בדיקה 4: המרה להזמנה (Convert Hold to Booking)

**בדיקה ב-Swagger:**
1. מצא: `POST /book`
2. לחץ "Try it out"
3. הזן:
```json
{
  "cabin_id": "ZB01",
  "check_in": "2026-03-01 15:00",
  "check_out": "2026-03-03 11:00",
  "customer": "ישראל ישראלי",
  "phone": "050-1234567",
  "email": "israel@example.com",
  "adults": 2,
  "kids": 0,
  "total_price": 1000.0,
  "hold_id": "hold-id-from-step-1"
}
```

**תוצאה צפויה:**
```json
{
  "success": true,
  "cabin_id": "ZB01",
  "event_id": "calendar-event-id",
  "event_link": "https://calendar.google.com/...",
  "message": "Booking created successfully"
}
```

**מה קורה בפועל:**
- ✅ Hold נמחק מ-Redis
- ✅ אירוע HOLD ב-Calendar מתעדכן ל-CONFIRMED
- ✅ הזמנה נשמרת ב-DB
- ✅ לקוח נשמר ב-DB
- ✅ Transaction נוצר ב-DB

**איפה רואים:**
1. **Redis:** `redis-cli KEYS "hold:*"` - Hold נעלם
2. **Calendar:** אירוע משתנה מ-"🔒 HOLD" ל-"הזמנה | ישראל ישראלי"
3. **DB:** `SELECT * FROM bookings WHERE cabin_id = '...'`
4. **DB:** `SELECT * FROM customers WHERE name = 'ישראל ישראלי'`

---

### בדיקה 5: ביטול Hold ידני

**בדיקה ב-Swagger:**
1. צור Hold חדש (כמו בבדיקה 1)
2. מצא: `DELETE /hold/{hold_id}`
3. הזן את ה-`hold_id`
4. לחץ "Execute"

**תוצאה צפויה:**
```json
{
  "success": true,
  "message": "Hold released successfully",
  "hold_id": "uuid-here"
}
```

**מה קורה בפועל:**
- ✅ Hold נמחק מ-Redis
- ⚠️ אירוע HOLD ב-Calendar נשאר (ניתן למחיקה ידנית)

**איפה רואים:**
- **Redis:** `redis-cli KEYS "hold:*"` - Hold נעלם
- **Calendar:** אירוע HOLD עדיין קיים (צריך למחוק ידנית)

---

### בדיקה 6: Hold מתפוגג אוטומטית (15 דקות)

**בדיקה:**
1. צור Hold
2. חכה 15 דקות (או שנה `HOLD_DURATION_SECONDS` ב-`.env` ל-60 שניות לבדיקה)
3. נסה לבדוק את ה-Hold: `GET /hold/{hold_id}`

**תוצאה צפויה:**
```json
{
  "detail": "Hold not found or expired"
}
```

**מה קורה בפועל:**
- ✅ Redis מוחק את ה-Hold אוטומטית אחרי 15 דקות
- ⚠️ אירוע HOLD ב-Calendar נשאר (ניתן למחיקה ידנית)

**איפה רואים:**
- **Redis:** `redis-cli TTL "hold:ZB01:2026-03-01:2026-03-03"` - מציג כמה שניות נשארו
- **API:** `GET /hold/{hold_id}` מחזיר 404 אחרי 15 דקות

---

## 📊 מה רואים ואיפה

### 1. Redis (אם מותקן)

```bash
# התחבר ל-Redis
redis-cli

# רשימת כל ה-Holds
KEYS "hold:*"

# פרטי Hold ספציפי
GET "hold:ZB01:2026-03-01:2026-03-03"

# כמה זמן נשאר ל-Hold (TTL)
TTL "hold:ZB01:2026-03-01:2026-03-03"

# מצא Hold לפי ID
GET "hold:by_id:{hold_id}"
```

**מה רואים:**
- כל ה-Holds הפעילים
- זמן תפוגה (TTL) של כל Hold
- פרטי Hold (JSON)

---

### 2. Google Calendar

**איך לראות:**
1. פתח Google Calendar
2. מצא את יומן הצימר (למשל: "Cabin ZB01 - הצימר של...")
3. חפש אירועים עם "🔒 HOLD" או "הזמנה"

**מה רואים:**
- **Hold:** אירוע צהוב עם "🔒 HOLD | שם לקוח"
- **Confirmed:** אירוע ירוק עם "הזמנה | שם לקוח"
- **תאריכים:** תאריך כניסה ויציאה

---

### 3. Database (PostgreSQL)

```sql
-- כל ההזמנות
SELECT * FROM bookings ORDER BY created_at DESC;

-- לקוחות
SELECT * FROM customers ORDER BY created_at DESC;

-- Transactions
SELECT * FROM transactions ORDER BY created_at DESC;

-- Audit Logs
SELECT * FROM audit_log WHERE table_name = 'bookings' ORDER BY created_at DESC;
```

**מה רואים:**
- כל ההזמנות עם סטטוס
- פרטי לקוחות
- תשלומים
- לוג של כל הפעולות

---

### 4. API Endpoints

**רשימת Endpoints:**
- `POST /hold` - יצירת Hold
- `GET /hold/{hold_id}` - בדיקת Hold
- `DELETE /hold/{hold_id}` - ביטול Hold
- `POST /book` - יצירת הזמנה (עם/בלי Hold)

**איך לבדוק:**
1. פתח: `http://127.0.0.1:8000/docs`
2. בחר endpoint
3. לחץ "Try it out"
4. הזן פרטים
5. לחץ "Execute"

---

## ⏰ התראות ותזמון

### Hold Duration (15 דקות)

**איפה מוגדר:**
- `.env` file: `HOLD_DURATION_SECONDS=900` (15 דקות)
- `src/hold.py`: משתמש ב-`HOLD_DURATION`

**איך זה עובד:**
- Redis מגדיר TTL (Time To Live) של 15 דקות
- אחרי 15 דקות, Redis מוחק את ה-Hold אוטומטית
- אין צורך ב-background job - Redis עושה זאת אוטומטית

**איך לבדוק:**
```bash
# בדוק TTL של Hold
redis-cli TTL "hold:ZB01:2026-03-01:2026-03-03"

# תוצאה: מספר שניות (לדוגמה: 847 = 14 דקות ו-7 שניות)
```

---

## 🔄 זרימה מלאה - דוגמה מעשית

### תרחיש: לקוח מזמין צימר

**שלב 1: לקוח בוחר צימר**
```
לקוח → /availability → רואה צימרים זמינים
לקוח → /quote → רואה מחיר מפורט
```

**שלב 2: יצירת Hold**
```
לקוח → POST /hold
  ↓
Redis: hold:ZB01:2026-03-01:2026-03-03 = {...} (TTL: 900 שניות)
  ↓
Calendar: אירוע "🔒 HOLD | ישראל ישראלי" (צהוב)
  ↓
תשובה: {hold_id: "abc-123", expires_at: "2026-03-01T15:15:00"}
```

**שלב 3: לקוח משלם (תוך 15 דקות)**
```
לקוח → POST /book עם hold_id
  ↓
Redis: מחיקת Hold
  ↓
Calendar: עדכון אירוע ל-"הזמנה | ישראל ישראלי" (ירוק)
  ↓
DB: שמירת booking, customer, transaction
  ↓
תשובה: {success: true, event_id: "...", event_link: "..."}
```

**שלב 4: אם לא שולם (אחרי 15 דקות)**
```
Redis: Hold נמחק אוטומטית
  ↓
Calendar: אירוע HOLD נשאר (ניתן למחיקה ידנית)
  ↓
לקוח: אם ינסה /book → יקבל שגיאה "Hold expired"
```

---

## 🧹 ניקוי ובדיקות

### ניקוי Holds ישנים

```bash
# מחיקת כל ה-Holds (זהירות!)
redis-cli FLUSHDB

# או מחיקה ספציפית
redis-cli DEL "hold:ZB01:2026-03-01:2026-03-03"
```

### בדיקת מצב המערכת

```bash
# בדיקת Redis
redis-cli ping

# בדיקת DB
psql -U postgres -d zimmerbot_db -c "SELECT COUNT(*) FROM bookings;"

# בדיקת API
curl http://127.0.0.1:8000/health
```

---

## 📝 סיכום

### מה עובד:
- ✅ יצירת Hold (15 דקות)
- ✅ מניעת Hold כפול
- ✅ בדיקת סטטוס Hold
- ✅ ביטול Hold ידני
- ✅ המרה להזמנה
- ✅ Hold מתפוגג אוטומטית

### איפה רואים:
- **Redis:** כל ה-Holds הפעילים
- **Calendar:** אירועי HOLD והזמנות
- **DB:** הזמנות, לקוחות, transactions
- **API:** כל הפעולות דרך Swagger

### מה חשוב לזכור:
- Hold תקף ל-15 דקות בלבד
- Hold מונע דאבל בוקינג
- אחרי תשלום, Hold מומר להזמנה
- אם לא שולם, Hold מתפוגג אוטומטית

---

## 🚀 הצעד הבא

אחרי שבדקת את שלב 4:
- שלב 5: תשלומים + Webhooks
- שלב 6: הודעות אוטומטיות
- שלב 7: צ'אט באתר


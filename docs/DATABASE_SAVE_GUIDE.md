# 💾 מדריך: מה נשמר ב-Database ואיפה?

## 📊 סקירה כללית

כל הנתונים נשמרים ב-**PostgreSQL Database** בשם `zimmerbot_db` (או השם שמוגדר ב-`.env`).

---

## 🗄️ טבלאות במסד הנתונים

### 1. **`cabins`** - טבלת צימרים
**מה נשמר:**
- `id` (UUID) - מזהה ייחודי
- `name` - שם הצימר
- `area` - אזור
- `max_adults`, `max_kids` - מספר מקסימלי של מבוגרים וילדים
- `features` (JSONB) - תכונות (jacuzzi, pool, וכו')
- `base_price_night` - מחיר בסיסי ללילה
- `weekend_price` - מחיר סופ"ש
- `images_urls` (TEXT[]) - קישורים לתמונות
- `calendar_id` - מזהה יומן Google Calendar
- `cabin_id_string` - מזהה מקורי (ZB01, ZB02, וכו')
- `created_at`, `updated_at` - תאריכי יצירה ועדכון

**מתי נשמר:**
- ייבוא מ-Google Sheets דרך `import_cabins_to_db.py`
- עדכון ידני דרך `fix_calendar_ids.py`

**איפה בקוד:**
- `database/import_cabins_to_db.py` - ייבוא ראשוני
- `src/db.py` - קריאה בלבד (`read_cabins_from_db`)

---

### 2. **`customers`** - טבלת לקוחות
**מה נשמר:**
- `id` (UUID) - מזהה ייחודי
- `name` - שם הלקוח
- `email` - אימייל (ייחודי)
- `phone` - טלפון
- `created_at` - תאריך יצירה

**מתי נשמר:**
- **אוטומטית** בכל יצירת הזמנה (`/book`)
- אם הלקוח כבר קיים (לפי email), משתמשים בו

**איפה בקוד:**
- `src/api_server.py` - שורה 719: `save_customer_to_db()`
- `src/db.py` - שורה 145: `save_customer_to_db()`

**דוגמה:**
```python
# ב-/book endpoint
customer_id = save_customer_to_db(
    name=customer,
    email=request.email,
    phone=phone,
)
```

---

### 3. **`bookings`** - טבלת הזמנות
**מה נשמר:**
- `id` (UUID) - מזהה ייחודי
- `cabin_id` (UUID) - קישור לצימר
- `customer_id` (UUID) - קישור ללקוח
- `check_in`, `check_out` - תאריכי כניסה ויציאה
- `adults`, `kids` - מספר מבוגרים וילדים
- `status` - סטטוס ('hold', 'confirmed', 'cancelled')
- `total_price` - מחיר כולל
- `event_id` - מזהה אירוע ב-Google Calendar
- `event_link` - קישור לאירוע ב-Google Calendar
- `created_at`, `updated_at` - תאריכי יצירה ועדכון

**מתי נשמר:**
- **אוטומטית** בכל יצירת הזמנה (`/book`)
- **אוטומטית** בייבוא הזמנות קיימות מ-Google Calendar

**איפה בקוד:**
- `src/api_server.py` - שורה 765: `save_booking_to_db()`
- `src/db.py` - שורה 190: `save_booking_to_db()`
- `database/import_bookings_from_calendar.py` - ייבוא הזמנות קיימות

**דוגמה:**
```python
# ב-/book endpoint
booking_id = save_booking_to_db(
    cabin_id=chosen.get("cabin_id"),
    customer_id=customer_id,
    check_in=check_in_local.date().isoformat(),
    check_out=check_out_local.date().isoformat(),
    adults=request.adults,
    kids=request.kids,
    total_price=total_price,  # מחושב אוטומטית אם לא נשלח
    status="confirmed",
    event_id=event_id,  # מ-Google Calendar
    event_link=event_link,  # מ-Google Calendar
)
```

---

### 4. **`quotes`** - טבלת הצעות מחיר
**מה נשמר:**
- `id` (UUID) - מזהה ייחודי
- `cabin_id` (UUID) - קישור לצימר
- `check_in`, `check_out` - תאריכי כניסה ויציאה
- `adults`, `kids` - מספר מבוגרים וילדים
- `total_price` - מחיר כולל
- `quote_data` (JSONB) - breakdown מלא של המחיר
- `created_at` - תאריך יצירה

**מתי נשמר:**
- **אופציונלי** בכל בקשת הצעת מחיר (`/quote`)
- לא נכשל אם השמירה נכשלת

**איפה בקוד:**
- `src/api_server.py` - שורה 601: `save_quote()`
- `src/db.py` - שורה 500: `save_quote()`

**דוגמה:**
```python
# ב-/quote endpoint
try:
    save_quote(
        cabin_id=request.cabin_id,
        check_in=request.check_in,
        check_out=request.check_out,
        adults=request.adults,
        kids=request.kids,
        total_price=pricing["total"],
        quote_data=pricing  # Full breakdown
    )
except Exception as e:
    # Don't fail if quote save fails
    print(f"Warning: Could not save quote: {e}")
```

---

### 5. **`transactions`** - טבלת תשלומים
**מה נשמר:**
- `id` (UUID) - מזהה ייחודי
- `booking_id` (UUID) - קישור להזמנה
- `payment_id` - מזהה מספק הסליקה
- `amount` - סכום התשלום
- `currency` - מטבע (ברירת מחדל: ILS)
- `status` - סטטוס ('pending', 'completed', 'failed', 'refunded')
- `payment_method` - שיטת תשלום
- `created_at`, `updated_at` - תאריכי יצירה ועדכון

**מתי נשמר:**
- **אוטומטית** בכל יצירת הזמנה (`/book`)
- סטטוס ראשוני: `pending`

**איפה בקוד:**
- `src/api_server.py` - שורה 780: `save_transaction()`
- `src/db.py` - שורה 450: `save_transaction()`

**דוגמה:**
```python
# ב-/book endpoint
if booking_id:
    transaction_id = save_transaction(
        booking_id=booking_id,
        amount=total_price or 0.0,
        status="pending",
        payment_method=None
    )
```

---

### 6. **`audit_log`** - טבלת לוגים
**מה נשמר:**
- `id` (UUID) - מזהה ייחודי
- `table_name` - שם הטבלה (למשל: 'bookings', 'availability_search')
- `record_id` (UUID) - מזהה הרשומה
- `action` - פעולה ('INSERT', 'UPDATE', 'DELETE')
- `old_values` (JSONB) - ערכים ישנים (לעדכון/מחיקה)
- `new_values` (JSONB) - ערכים חדשים (ליצירה/עדכון)
- `user_id` (UUID) - מזהה משתמש (אופציונלי)
- `created_at` - תאריך יצירה

**מתי נשמר:**
- **אוטומטית** בכל חיפוש זמינות (`/availability`)
- **אוטומטית** בכל יצירת הזמנה (`/book`)

**איפה בקוד:**
- `src/api_server.py`:
  - שורה 430: `save_audit_log()` ב-`/availability`
  - שורה 789: `save_audit_log()` ב-`/book`
- `src/db.py` - שורה 334: `save_audit_log()`

**דוגמה:**
```python
# ב-/availability endpoint
save_audit_log(
    table_name="availability_search",
    record_id=str(uuid.uuid4()),
    action="INSERT",
    new_values={
        "check_in": request.check_in,
        "check_out": request.check_out,
        "adults": request.adults,
        "kids": request.kids,
        "features": request.features,
        "area": request.area
    }
)

# ב-/book endpoint
save_audit_log(
    table_name="bookings",
    record_id=booking_id,
    action="INSERT",
    new_values={
        "cabin_id": request.cabin_id,
        "customer_id": customer_id,
        "check_in": check_in_local.date().isoformat(),
        "check_out": check_out_local.date().isoformat(),
        "adults": request.adults,
        "kids": request.kids,
        "total_price": total_price,
        "status": "confirmed",
        "event_id": event_id,
        "event_link": event_link
    }
)
```

---

### 7. **`pricing_rules`** - טבלת כללי תמחור
**מה נשמר:**
- `id` (UUID) - מזהה ייחודי
- `cabin_id` (UUID) - קישור לצימר
- `rule_type` - סוג כלל ('weekend', 'holiday', 'season', 'discount')
- `start_date`, `end_date` - תאריכי תחילה וסיום
- `multiplier` - מכפיל מחיר
- `fixed_amount` - סכום קבוע
- `description` - תיאור
- `created_at` - תאריך יצירה

**מתי נשמר:**
- **לא נשמר אוטומטית** - צריך להוסיף ידנית
- מיועד לכללי תמחור מורכבים (עונות, חגים, וכו')

**איפה בקוד:**
- לא בשימוש פעיל כרגע
- מיועד לעתיד

---

### 8. **`notifications`** - טבלת הודעות
**מה נשמר:**
- `id` (UUID) - מזהה ייחודי
- `booking_id` (UUID) - קישור להזמנה
- `customer_id` (UUID) - קישור ללקוח
- `notification_type` - סוג הודעה ('confirmation', 'reminder', 'cancellation')
- `channel` - ערוץ ('email', 'sms', 'whatsapp', 'push')
- `status` - סטטוס ('pending', 'sent', 'failed')
- `sent_at` - תאריך שליחה
- `created_at` - תאריך יצירה

**מתי נשמר:**
- **לא נשמר אוטומטית** - צריך להוסיף ידנית
- מיועד למערכת הודעות עתידית

**איפה בקוד:**
- לא בשימוש פעיל כרגע
- מיועד לעתיד

---

## 📋 סיכום - מה נשמר אוטומטית?

### ✅ נשמר אוטומטית:

1. **`/availability`** (חיפוש זמינות):
   - ✅ `audit_log` - לוג של החיפוש

2. **`/quote`** (הצעת מחיר):
   - ⚠️ `quotes` - אופציונלי (לא נכשל אם נכשל)

3. **`/book`** (יצירת הזמנה):
   - ✅ `customers` - לקוח (או שימוש בקיים)
   - ✅ `bookings` - הזמנה
   - ✅ `transactions` - תשלום (סטטוס: pending)
   - ✅ `audit_log` - לוג של ההזמנה

### ❌ לא נשמר אוטומטית:

- `pricing_rules` - צריך להוסיף ידנית
- `notifications` - מיועד לעתיד

---

## 🔍 איפה לראות את הנתונים?

### דרך Admin Panel:
1. פתח `http://127.0.0.1:8000/tools/features_picker.html`
2. לחץ על "Admin Panel"
3. לך ל-"Bookings" - רואה כל ההזמנות
4. לך ל-"Audit Log" - רואה כל הלוגים
5. לך ל-"Statistics" - רואה סטטיסטיקות

### דרך API:
- `GET /admin/bookings` - רשימת הזמנות
- `GET /admin/bookings/{id}` - הזמנה ספציפית
- `GET /admin/audit` - רשימת לוגים

### דרך Python Script:
```bash
python database/show_all_data.py
```

---

## 📍 מיקום מסד הנתונים

**הגדרות חיבור:**
- קובץ: `.env`
- משתנים:
  ```
  DB_HOST=localhost
  DB_PORT=5432
  DB_NAME=zimmerbot_db
  DB_USER=postgres
  DB_PASSWORD=zimmerbot
  ```

**מיקום פיזי:**
- PostgreSQL שומר את הנתונים בתיקייה שלו (תלוי בהתקנה)
- Windows: בדרך כלל `C:\Program Files\PostgreSQL\{version}\data`
- Linux: בדרך כלל `/var/lib/postgresql/{version}/main`

---

## ✅ בדיקה - האם הכל נשמר?

### בדיקה מהירה:
```bash
# 1. בדוק חיבור ל-DB
python -c "from src.db import get_db_connection; conn = get_db_connection(); print('✓ Connected')"

# 2. הצג את כל הנתונים
python database/show_all_data.py

# 3. בדוק דרך API
curl http://127.0.0.1:8000/admin/bookings
```

### בדיקה מפורטת:
1. צור הזמנה דרך `features_picker.html`
2. פתח Admin Panel → Bookings
3. ודא שההזמנה מופיעה
4. פתח Admin Panel → Audit Log
5. ודא שיש לוג של החיפוש וההזמנה

---

## 🎯 סיכום

**כן, הכל נשמר ב-Database!**

- ✅ צימרים → `cabins`
- ✅ לקוחות → `customers`
- ✅ הזמנות → `bookings`
- ✅ תשלומים → `transactions`
- ✅ הצעות מחיר → `quotes` (אופציונלי)
- ✅ לוגים → `audit_log`

כל זה נשמר **אוטומטית** ב-PostgreSQL Database!


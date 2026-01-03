# איך לבדוק את ה-API ב-Swagger UI

## גישה ל-Swagger UI

1. פתח בדפדפן: `http://127.0.0.1:8000/docs`
2. תראה את כל ה-endpoints עם תיעוד מלא

---

## בדיקות שלב שלב

### 1. GET /health - בדיקת בריאות

**איך לבדוק:**
1. לחץ על `GET /health`
2. לחץ על "Try it out"
3. לחץ על "Execute"
4. בדוק את התגובה - אמור להיות `200 OK` עם `"status": "healthy"`

**תגובה צפויה:**
```json
{
  "token_file": "data/token_api.json",
  "required_scopes": [...],
  "creds_scopes": [...],
  "calendar_service_ready": true,
  "cabins_loaded": 3,
  "status": "healthy"
}
```

---

### 2. GET /cabins - רשימת צימרים

**איך לבדוק:**
1. לחץ על `GET /cabins`
2. לחץ על "Try it out"
3. לחץ על "Execute"
4. בדוק את התגובה - אמור להיות `200 OK` עם רשימת 3 צימרים

**תגובה צפויה:**
```json
[
  {
    "cabin_id": "...",
    "name": "הצימר של יולי",
    "area": "גליל מערבי",
    "max_adults": 2,
    "max_kids": 2,
    "features": "jacuzzi,pool,accessible,bbq,pet_friendly",
    "base_price_night": 600.0,
    "weekend_price": 900.0,
    "calendar_id": "..."
  },
  ...
]
```

---

### 3. POST /availability - בדיקת זמינות

**איך לבדוק:**
1. לחץ על `POST /availability`
2. לחץ על "Try it out"
3. מלא את הפרמטרים:
   ```json
   {
     "check_in": "2026-02-15 15:00",
     "check_out": "2026-02-17 11:00",
     "adults": 2,
     "kids": null,
     "area": null,
     "features": null
   }
   ```
4. לחץ על "Execute"
5. בדוק את התגובה - אמור להיות `200 OK` עם רשימת צימרים זמינים

**תגובה צפויה:**
```json
[
  {
    "cabin_id": "...",
    "name": "הצימר של יולי",
    "area": "גליל מערבי",
    "nights": 2,
    "regular_nights": 1,
    "weekend_nights": 1,
    "total_price": 1500.0,
    "max_adults": 2,
    "max_kids": 2,
    "features": "jacuzzi,pool,accessible,bbq,pet_friendly"
  }
]
```

**אם יש שגיאה 500:**
- בדוק את ה-calendar_id של הצימרים ב-DB
- ודא שה-calendar_id תקין וקיים ב-Google Calendar

---

### 4. POST /quote - הצעת מחיר מפורטת

**איך לבדוק:**
1. לחץ על `POST /quote`
2. לחץ על "Try it out"
3. מלא את הפרמטרים:
   ```json
   {
     "cabin_id": "ZB01",
     "check_in": "2026-02-15 15:00",
     "check_out": "2026-02-17 11:00",
     "adults": 2,
     "kids": null,
     "addons": [
       {
         "name": "מסאג' לחדר",
         "price": 200
       },
       {
         "name": "ארוחת שף",
         "price": 300
       }
     ]
   }
   ```
4. לחץ על "Execute"
5. בדוק את התגובה - אמור להיות `200 OK` עם breakdown מפורט

**תגובה צפויה:**
```json
{
  "cabin_id": "ZB01",
  "cabin_name": "הצימר של יולי",
  "check_in": "2026-02-15 15:00",
  "check_out": "2026-02-17 11:00",
  "nights": 2,
  "regular_nights": 1,
  "weekend_nights": 1,
  "holiday_nights": 0,
  "high_season_nights": 0,
  "base_total": 1500.0,
  "weekend_surcharge": 300.0,
  "holiday_surcharge": 0.0,
  "high_season_surcharge": 0.0,
  "addons_total": 500.0,
  "addons": [...],
  "subtotal": 2000.0,
  "discount": {
    "percent": 0.0,
    "amount": 0.0,
    "reason": null
  },
  "total": 2000.0,
  "breakdown": [
    {
      "date": "2026-02-15",
      "is_weekend": true,
      "is_holiday": false,
      "is_high_season": false,
      "price": 900.0
    },
    {
      "date": "2026-02-16",
      "is_weekend": false,
      "is_holiday": false,
      "is_high_season": false,
      "price": 600.0
    }
  ]
}
```

---

### 5. POST /book - יצירת הזמנה

**⚠️ אזהרה:** זה יוצר הזמנה אמיתית ב-DB וביומן!

**איך לבדוק:**
1. לחץ על `POST /book`
2. לחץ על "Try it out"
3. מלא את הפרמטרים:
   ```json
   {
     "cabin_id": "ZB01",
     "check_in": "2026-02-20 15:00",
     "check_out": "2026-02-22 11:00",
     "customer_name": "ישראל ישראלי",
     "customer_email": "test@example.com",
     "customer_phone": "050-1234567",
     "adults": 2,
     "kids": null,
     "addons": [
       {
         "name": "מסאג' לחדר",
         "price": 200
       }
     ]
   }
   ```
4. לחץ על "Execute"
5. בדוק את התגובה - אמור להיות `200 OK` עם פרטי ההזמנה

**תגובה צפויה:**
```json
{
  "success": true,
  "cabin_id": "ZB01",
  "event_id": "...",
  "event_link": "https://calendar.google.com/...",
  "message": "Booking created successfully",
  "booking_id": "...",
  "total_price": 1700.0
}
```

---

### 6. GET /admin/bookings - רשימת הזמנות

**איך לבדוק:**
1. לחץ על `GET /admin/bookings`
2. לחץ על "Try it out"
3. (אופציונלי) מלא פרמטרים:
   - `status`: "confirmed" / "hold" / "cancelled" (אופציונלי)
   - `limit`: 100 (ברירת מחדל)
   - `offset`: 0 (ברירת מחדל)
4. לחץ על "Execute"
5. בדוק את התגובה - אמור להיות `200 OK` עם רשימת הזמנות

**תגובה צפויה:**
```json
[
  {
    "booking_id": "...",
    "cabin_id": "...",
    "cabin_name": "הצימר של יולי",
    "customer_name": "ישראל ישראלי",
    "customer_email": "test@example.com",
    "check_in": "2026-02-20",
    "check_out": "2026-02-22",
    "adults": 2,
    "kids": null,
    "status": "confirmed",
    "total_price": 1700.0,
    "event_id": "...",
    "event_link": "...",
    "created_at": "2026-01-03T...",
    "updated_at": "2026-01-03T..."
  }
]
```

---

### 7. GET /admin/bookings/{booking_id} - הזמנה ספציפית

**איך לבדוק:**
1. לחץ על `GET /admin/bookings/{booking_id}`
2. לחץ על "Try it out"
3. מלא את `booking_id` (UUID מהזמנה קודמת)
4. לחץ על "Execute"
5. בדוק את התגובה - אמור להיות `200 OK` עם פרטי ההזמנה המלאים

---

### 8. GET /admin/audit - לוגים

**איך לבדוק:**
1. לחץ על `GET /admin/audit`
2. לחץ על "Try it out"
3. (אופציונלי) מלא פרמטרים:
   - `table_name`: "bookings" / "availability_search" (אופציונלי)
   - `action`: "INSERT" / "UPDATE" / "DELETE" (אופציונלי)
   - `limit`: 100 (ברירת מחדל)
   - `offset`: 0 (ברירת מחדל)
4. לחץ על "Execute"
5. בדוק את התגובה - אמור להיות `200 OK` עם רשימת לוגים

**תגובה צפויה:**
```json
[
  {
    "audit_id": "...",
    "table_name": "availability_search",
    "record_id": "...",
    "action": "INSERT",
    "old_values": null,
    "new_values": {
      "check_in": "2026-02-15 15:00",
      "check_out": "2026-02-17 11:00",
      "adults": 2,
      "results_count": 1
    },
    "user_id": null,
    "created_at": "2026-01-03T..."
  }
]
```

---

## טיפים לבדיקה

1. **תאריכים:** השתמש בתאריכים עתידיים (לפחות שבועיים מהיום)
2. **cabin_id:** השתמש ב-`ZB01`, `ZB02`, או `ZB03` (או UUID מהתגובה של `/cabins`)
3. **תוספות:** תוספות זמינות:
   - `{"name": "מסאג' לחדר", "price": 200}`
   - `{"name": "ארוחת שף", "price": 300}`
   - `{"name": "טיול בבוקר", "price": 150}`
4. **Features:** השתמש ב-features מהצימרים, למשל: `"jacuzzi,pool,bbq"`

---

## פתרון בעיות

### שגיאת 500 ב-POST /availability
- **סיבה:** calendar_id לא תקין או לא קיים
- **פתרון:** בדוק את ה-calendar_id ב-DB או ב-Google Sheets

### שגיאת 404 ב-calendar
- **סיבה:** ה-calendar_id לא קיים ב-Google Calendar
- **פתרון:** ודא שה-calendar_id תקין וקיים

### שגיאת 500 ב-/admin/bookings או /admin/audit
- **סיבה:** עמודות חסרות בטבלאות
- **פתרון:** הרץ את ה-migration או צור את הטבלאות מחדש

---

## סדר מומלץ לבדיקה

1. ✅ GET /health
2. ✅ GET /cabins
3. ✅ POST /availability
4. ✅ POST /quote
5. ⚠️ POST /book (רק אם אתה רוצה ליצור הזמנה אמיתית)
6. ✅ GET /admin/bookings
7. ✅ GET /admin/audit


# 🔗 מדריך אינטגרציה: חיבור לאתר צימרים אמיתי

## 📋 סקירה כללית

המערכת הנוכחית עובדת עם:
- **Google Sheets** - לקריאת נתוני צימרים
- **Google Calendar** - לבדיקת זמינות ויצירת הזמנות
- **FastAPI** - שרת API מקומי

## 🌐 איך לחבר לאתר צימרים אמיתי?

### אפשרות 1: החלפת Google Sheets ב-Database

**מה צריך לעשות:**
1. העבר את כל נתוני הצימרים מ-Google Sheets ל-PostgreSQL
2. עדכן את `src/main.py` לקרוא מ-DB במקום Sheets
3. שמור את `calendar_id` של כל צימר ב-DB

**קוד לדוגמה:**
```python
# במקום read_cabins_from_sheet()
def read_cabins_from_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            id as cabin_id,
            name,
            area,
            max_adults,
            max_kids,
            features,
            base_price_night,
            weekend_price,
            calendar_id
        FROM cabins
    """)
    # Convert to dict format
    return [dict(row) for row in cursor.fetchall()]
```

### אפשרות 2: API Gateway

**מה צריך לעשות:**
1. צור API Gateway שמחבר בין האתר שלך ל-FastAPI
2. האתר שלך שולח בקשות ל-Gateway
3. ה-Gateway ממיר ומעביר ל-FastAPI

**דוגמה:**
```
Website → API Gateway → FastAPI → Google Calendar/DB
```

### אפשרות 3: Embedding

**מה צריך לעשות:**
1. שמור את `features_picker.html` בשרת שלך
2. Embed אותו באתר שלך עם iframe או כחלק מהדף
3. עדכן את `API_BASE` ב-JavaScript לכתובת השרת שלך

**דוגמה:**
```html
<!-- באתר שלך -->
<iframe src="https://your-server.com/tools/features_picker.html" 
        width="100%" 
        height="800px">
</iframe>
```

## 💾 איפה נכנס ה-DB? מה נשמר?

### מה נשמר כרגע:

**❌ כלום!** - המערכת הנוכחית **לא שומרת כלום ב-DB**.

### מה צריך לשמור:

#### 1. **טבלת `cabins`** (צימרים)
```sql
- id (UUID)
- name (שם הצימר)
- area (אזור)
- max_adults, max_kids
- features (JSONB)
- base_price_night, weekend_price
- calendar_id (מ-Google Calendar)
```

#### 2. **טבלת `bookings`** (הזמנות)
```sql
- id (UUID)
- cabin_id (FK)
- customer_id (FK)
- check_in, check_out
- total_price
- status (pending/confirmed/cancelled)
- created_at, updated_at
```

#### 3. **טבלת `customers`** (לקוחות)
```sql
- id (UUID)
- name
- phone
- email
- created_at
```

#### 4. **טבלת `transactions`** (תשלומים)
```sql
- id (UUID)
- booking_id (FK)
- amount
- payment_method
- status
- created_at
```

#### 5. **טבלת `pricing_rules`** (חוקי תמחור)
```sql
- id (UUID)
- rule_type (discount/surcharge)
- min_nights
- percent
- start_date, end_date
```

### מה צריך לעדכן בקוד:

#### 1. **`src/main.py`** - קריאת צימרים
```python
# במקום:
cabins = read_cabins_from_sheet(creds)

# שנה ל:
cabins = read_cabins_from_db()
```

#### 2. **`src/api_server.py`** - שמירת הזמנות
```python
@app.post("/book")
async def book_cabin(request: BookingRequest):
    # ... בדיקת זמינות ...
    
    # שמור ב-DB
    booking_id = save_booking_to_db(
        cabin_id=request.cabin_id,
        customer=request.customer,
        check_in=check_in_local,
        check_out=check_out_local,
        total_price=quote["total"]
    )
    
    # צור אירוע ב-Calendar
    create_calendar_event(...)
    
    return BookingResponse(...)
```

#### 3. **`src/pricing.py`** - קריאת חוקי תמחור
```python
def __init__(self):
    # במקום hardcoded rules:
    # self.discounts = [...]
    
    # קרא מ-DB:
    self.discounts = load_discounts_from_db()
    self.pricing_rules = load_pricing_rules_from_db()
```

## 🔄 זרימת נתונים מלאה:

```
1. לקוח בוחר תאריכים
   ↓
2. Frontend → POST /availability
   ↓
3. Backend → קורא צימרים מ-DB
   ↓
4. Backend → בודק זמינות ב-Google Calendar
   ↓
5. Backend → מחזיר רשימת צימרים זמינים
   ↓
6. לקוח בוחר צימר → POST /quote
   ↓
7. Backend → קורא חוקי תמחור מ-DB
   ↓
8. Backend → מחשב מחיר מפורט
   ↓
9. Backend → מחזיר quote
   ↓
10. לקוח לוחץ "צור הזמנה" → POST /book
    ↓
11. Backend → שומר הזמנה ב-DB
    ↓
12. Backend → יוצר אירוע ב-Google Calendar
    ↓
13. Backend → מחזיר אישור
```

## 📝 שלבים לביצוע:

### שלב 1: העברת נתונים ל-DB
```bash
# 1. ייבא צימרים מ-Google Sheets ל-DB
python scripts/import_cabins_from_sheets.py

# 2. ודא ש-calendar_id נשמר
```

### שלב 2: עדכון קוד קריאה
```python
# src/main.py
def get_service():
    # ... existing code ...
    if _cabins is None:
        _cabins = read_cabins_from_db()  # במקום read_cabins_from_sheet
    return _service, _cabins
```

### שלב 3: הוספת שמירת הזמנות
```python
# src/api_server.py
@app.post("/book")
async def book_cabin(request: BookingRequest):
    # ... existing validation ...
    
    # שמור ב-DB
    booking = save_booking_to_db(...)
    
    # ... existing calendar creation ...
    
    return BookingResponse(booking_id=booking.id, ...)
```

### שלב 4: חיבור לאתר
```html
<!-- באתר שלך -->
<script>
  const API_BASE = "https://your-api-server.com";
  // השתמש ב-features_picker.html או צור UI משלך
</script>
```

## 🎯 המלצות:

1. **התחל עם DB** - העבר את כל הנתונים ל-PostgreSQL
2. **שמור כל הזמנה** - גם אם זה רק ב-Calendar, שמור ב-DB
3. **שמור היסטוריה** - כל שינוי במחיר, ביטול, וכו'
4. **Backup** - גבה את ה-DB באופן קבוע
5. **Monitoring** - הוסף לוגים לכל פעולה חשובה

## ❓ שאלות נפוצות:

**Q: האם אני יכול להשתמש רק ב-Google Calendar?**  
A: כן, אבל לא מומלץ. DB נותן לך:
- היסטוריה מלאה
- דוחות וניתוחים
- גיבויים
- חיפושים מתקדמים

**Q: איך אני מחבר את זה לאתר WordPress?**  
A: צור plugin שמקרא ל-API שלך, או embed את `features_picker.html`

**Q: האם אני צריך לשמור גם ב-Calendar וגם ב-DB?**  
A: כן! Calendar = זמינות בזמן אמת, DB = היסטוריה וניהול


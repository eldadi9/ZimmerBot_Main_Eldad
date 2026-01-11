# 📋 תהליך הזמנה מלא - תכנית עבודה מפורטת וסטטוס

> 📅 **תאריך:** ינואר 2026  
> 🎯 **מטרה:** בניית תהליך הזמנה מלא ומסודר עם כל השלבים

---

## 📊 סטטוס נוכחי

### ✅ הושלם (40%):
- ✅ שיפור Agent Logic - שלב ראשון
- ✅ שיפור API Server - שלב ראשון  
- ✅ תיקון לוגיקת booking_flow - context restoration
- ✅ תיקון שמירת booking_flow state ב-metadata

### ⚠️ בתהליך (10%):
- ⚠️ שיפור create_calendar_event() - מצב "מתנה"

### ❌ לא התחיל (50%):
- ❌ Endpoint `/agent/booking/customer-details`
- ❌ טופס פרטי לקוח ב-Frontend
- ❌ טופס תשלום ב-Frontend
- ❌ עדכון אירוע ביומן - הזמנה אמיתית

---

## 🔍 איפה לבדוק?

**מיקום בדיקה:** `tools/features_picker.html` - כפתור "💬 Agent Chat"

**תהליך בדיקה:**
1. פתח את `tools/features_picker.html` בדפדפן (http://127.0.0.1:8000/tools/features_picker.html)
2. לחץ על כפתור "💬 Agent Chat"
3. נסה את התרחיש הבא:
   ```
   משתמש: "מה הזמינות ב-15-17 במרץ?"
   → Agent: מציג זמינות + "האם תרצה להמשיך להזמנה?"
   
   משתמש: "כן"
   → Agent: מציג הצעת מחיר מפורטת + "האם תרצה להזמין?"
   
   משתמש: "כן"
   → Agent: "מעולה! בואו נתחיל בהזמנה. אני צריך כמה פרטים ממך..."
   → Frontend: צריך להציג טופס פרטי לקוח (עדיין לא מומש)
   ```

**בדיקות לוגיקה:**
- ✅ `booking_flow` state נשמר ב-conversation metadata
- ✅ `booking_flow` state משוחזר מה-metadata של הודעה קודמת
- ✅ מעבר `availability_confirmed` → `quote_confirmed` → `customer_details_needed`
- ⚠️ טופס פרטי לקוח עדיין לא מומש (צריך לבנות)

**בדיקת Response:**
- בדוק ב-`Response Details` שהשדות הבאים קיימים:
  - `booking_flow` - מצב תהליך הזמנה
  - `show_customer_form` - האם להציג טופס (true/false)

---

## 🔄 תהליך הזמנה - סקירה כללית

```
1. בדיקת זמינות תאריכים → אשר כן/לא
2. אם כן → מעבר אוטומטי להצעת מחיר
3. לאחר הצעת מחיר, אם הלקוח רוצה להזמין → טופס מילוי פרטי לקוח
4. אחרי מילוי פרטים → יצירת HOLD ל-15 דקות (עם הודעת HOLD)
5. יצירת הזמנה ביומן במצב "מתנה" עד לאישור תשלום
6. מעבר לחלון תשלומים
7. לאחר תשלום → אישור → יצירת הזמנה אמיתית ביומן
```

---

## ✅ מה בוצע עד כה

### 1. תיקון לוגיקת booking_flow ✅

#### מה בוצע:
- ✅ תיקון שמירת `booking_flow` state ב-conversation metadata
- ✅ תיקון שחזור `booking_flow` state מה-metadata של הודעה קודמת
- ✅ תיקון הלוגיקה כך שטיפול ב-booking_flow יתבצע רק אחרי שה-tool_results מוגדר

#### קבצים ששונו:
- `src/api_server.py` - שיפור `/agent/chat` endpoint (שורות 1900-1931, 2608-2681)

---

### 2. שיפור Agent Logic ✅

#### מה בוצע:
- ✅ שיפור `src/agent.py` - `detect_intent`: הכרת "כן" בהקשר booking flow
- ✅ שיפור `src/agent.py` - `generate_response`: booking_flow state management
- ✅ הוספת `booking_flow` state ב-availability response

#### קבצים ששונו:
- `src/agent.py` - שיפורי detect_intent ו-generate_response

---

### 3. שיפור API Server ✅

#### מה בוצע:
- ✅ הוספת `booking_flow` ו-`show_customer_form` ל-`ChatResponse`
- ✅ שיפור `/agent/chat` endpoint - טיפול ב-booking_flow states
- ✅ שיפור Tool 2 (Quote) - הוספת booking_flow state update

#### קבצים ששונו:
- `src/api_server.py` - שיפורי `/agent/chat` endpoint

---

## 🚀 תכנית יישום - שלבים הבאים

### שלב 2: יצירת Endpoint `/agent/booking/customer-details` ❌

1. יצירת Pydantic models: `CustomerDetailsRequest`, `CustomerDetailsResponse`
2. יצירת endpoint `POST /agent/booking/customer-details`
3. שמירת פרטי לקוח ב-DB
4. יצירת HOLD ל-15 דקות
5. יצירת אירוע ביומן במצב "מתנה"
6. החזרת hold_id, event_id, expires_at
7. עדכון booking_flow state ל-`customer_details_provided`

**קבצים:**
- `src/api_server.py` - endpoint חדש
- `src/db.py` - פונקציות לשמירת פרטי לקוח (אם נדרש)

---

### שלב 3: טופס פרטי לקוח ב-Frontend ❌

1. יצירת טופס HTML ב-`tools/features_picker.html`
2. JavaScript לשליחת טופס ל-`/agent/booking/customer-details`
3. הצגת טופס אוטומטית כש-`show_customer_form == true`
4. עדכון UI אחרי שליחת טופס

**קבצים:**
- `tools/features_picker.html` - הוספת טופס + JavaScript

---

### שלב 4: שיפור `create_calendar_event()` - מצב "מתנה" ⚠️

1. שיפור `create_calendar_event()` לתמיכה במצב "מתנה"
2. פרמטר חדש: `status='pending'` או `is_pending=True`
3. סיכום אירוע: "🔒 HOLD | {customer_name}"
4. תיאור אירוע: כולל כל הפרטים + "מצב: מתנה עד תשלום"

**קבצים:**
- `src/main.py` - שיפור `create_calendar_event()`
- `src/api_server.py` - שימוש ב-`create_calendar_event()` עם status='pending'

---

### שלב 5: טופס תשלום ב-Frontend ❌

1. יצירת טופס תשלום ב-`tools/features_picker.html`
2. JavaScript לשליחת תשלום
3. בשלב ראשון: אפשר לכתוב סתם מספר (לא תשלום אמיתי)
4. Endpoint `POST /agent/booking/payment` (או שימוש ב-`/book` הקיים)

**קבצים:**
- `tools/features_picker.html` - הוספת טופס תשלום
- `src/api_server.py` - endpoint תשלום

---

### שלב 6: עדכון אירוע ביומן - הזמנה אמיתית ⚠️

1. יצירת פונקציה `update_calendar_event()` ב-`src/main.py`
2. אחרי אישור תשלום → עדכון אירוע למצב "הזמנה מאושרת"
3. עדכון DB: `UPDATE bookings SET status='confirmed' WHERE booking_id=...`
4. הודעת אישור למשתמש

**קבצים:**
- `src/main.py` - פונקציה `update_calendar_event()` (חדש)
- `src/api_server.py` - endpoint `/agent/booking/payment-confirm`
- `src/db.py` - `update_booking_status()` (אם לא קיים)

---

## 📝 הערות חשובות

### State Management
- `booking_flow` states: `availability_confirmed` → `quote_confirmed` → `customer_details_needed` → `customer_details_provided` → `payment_required` → `payment_confirmed`
- צריך לשמור state ב-conversation metadata
- צריך לשחזר state מה-metadata של הודעה קודמת

### Error Handling
- אם HOLD פג תוקף → לשאול אם רוצה לנסות שוב
- אם תשלום נכשל → לשאול אם רוצה לנסות שוב
- אם אירוע ביומן נכשל → להודיע אבל לשמור HOLD

---

**סיכום:** תיקנתי את הבעיות בלוגיקת booking_flow ושחזור context. עכשיו צריך לבנות את הטופסים וה-endpoints החדשים.

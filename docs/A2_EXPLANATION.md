# 📝 הסבר מפורט - שלב A2: יצירת endpoint `/agent/chat`

**תאריך:** 2026-01-06  
**מטרה:** יצירת endpoint בסיסי ל-Agent Chat עם שמירה ב-DB

---

## 🎯 מה נעשה בשלב A2?

### 1. פונקציות DB לשמירת שיחות (ב-`src/db.py`)

נוספו 4 פונקציות חדשות:

#### `create_conversation()`
**מה זה עושה:**
- יוצר שיחה חדשה ב-DB
- שומר: customer_id, channel (web/whatsapp/voice/sms), status, metadata
- מחזיר: conversation_id (UUID)

**דוגמה:**
```python
conversation_id = create_conversation(
    customer_id="123e4567-e89b-12d3-a456-426614174000",
    channel="web",
    status="active",
    metadata={"context": {"check_in": "2026-03-15"}}
)
```

#### `save_message()`
**מה זה עושה:**
- שומר הודעה בשיחה
- שומר: conversation_id, role (user/assistant/system), content, metadata
- יוצר audit log אוטומטית
- מחזיר: message_id (UUID)

**דוגמה:**
```python
message_id = save_message(
    conversation_id="123e4567-...",
    role="user",
    content="שלום, אני מחפש צימר",
    metadata={"intent": "search"}
)
```

#### `get_conversation()`
**מה זה עושה:**
- מביא שיחה עם כל ההודעות שלה
- מחזיר: dict עם פרטי השיחה + רשימת הודעות

#### `update_conversation_status()`
**מה זה עושה:**
- מעדכן סטטוס שיחה (active/closed/escalated)
- יוצר audit log

---

### 2. Pydantic Models (ב-`src/api_server.py`)

נוצרו 3 models חדשים:

#### `ChatRequest` - קלט מהמשתמש
```python
{
    "message": "שלום, אני מחפש צימר",      # חובה
    "customer_id": "uuid-optional",        # אופציונלי
    "phone": "050-1234567",                # אופציונלי
    "channel": "web",                      # ברירת מחדל: "web"
    "context": {                           # אופציונלי
        "check_in": "2026-03-15",
        "check_out": "2026-03-17",
        "guests": 2,
        "cabin_id": "ZB01"
    }
}
```

#### `ChatResponse` - פלט מהשרת
```python
{
    "answer": "שלום! אשמח לעזור...",      # תשובת ה-Agent
    "actions_suggested": ["availability"], # פעולות מוצעות
    "confidence": 0.7,                     # רמת ביטחון (0.0-1.0)
    "conversation_id": "uuid-here"         # מזהה השיחה
}
```

#### `ChatContext` - הקשר השיחה
```python
{
    "check_in": "2026-03-15",    # תאריך הגעה
    "check_out": "2026-03-17",   # תאריך יציאה
    "guests": 2,                 # מספר אורחים
    "cabin_id": "ZB01"           # מזהה צימר
}
```

---

### 3. Endpoint `/agent/chat` (ב-`src/api_server.py`)

**מה ה-endpoint עושה:**

1. **מקבל הודעה מהמשתמש**
   - בודק שהערוץ תקין (web/whatsapp/voice/sms)
   - מחפש/יוצר customer לפי phone (אם נתון)

2. **יוצר/מביא שיחה**
   - יוצר שיחה חדשה ב-DB
   - שומר metadata (context, phone)

3. **שומר הודעת user**
   - שומר את ההודעה של המשתמש ב-DB
   - יוצר audit log

4. **מייצר תשובה (placeholder)**
   - זיהוי כוונות בסיסי (keyword-based):
     - "זמינות" → `actions: ["availability"]`
     - "מחיר" → `actions: ["quote"]`
     - "הזמנה" → `actions: ["hold", "book"]`
   - מחזיר תשובה בסיסית

5. **שומר תשובת assistant**
   - שומר את התשובה ב-DB
   - יוצר audit log

6. **מחזיר תגובה**
   - answer, actions_suggested, confidence, conversation_id

---

## 🔍 איך לבדוק את מה שנעשה?

### דרך 1: Swagger UI (הכי קל)

1. **הפעל את השרת:**
   ```bash
   run_api.bat
   ```
   או:
   ```bash
   venv\Scripts\python.exe -m uvicorn src.api_server:app --reload --port 8000
   ```

2. **פתח בדפדפן:**
   ```
   http://127.0.0.1:8000/docs
   ```

3. **מצא את `POST /agent/chat`:**
   - לחץ עליו כדי להרחיב
   - לחץ "Try it out"

4. **הזן בקשה:**
   ```json
   {
     "message": "שלום, אני מחפש צימר",
     "channel": "web"
   }
   ```

5. **לחץ "Execute"**

6. **ראה את התגובה:**
   ```json
   {
     "answer": "שלום! תודה על פנייתך...",
     "actions_suggested": [],
     "confidence": 0.5,
     "conversation_id": "uuid-here"
   }
   ```

---

### דרך 2: Python Script

**הרץ את הסקריפט:**
```bash
venv\Scripts\python.exe database\test_agent_chat.py
```

**מה הסקריפט עושה:**
1. שולח הודעה פשוטה
2. שולח הודעה עם context
3. בודק audit logs

---

### דרך 3: בדיקה ישירה ב-DB

**בדוק שהשיחות נשמרו:**

```sql
-- ראה את כל השיחות
SELECT 
    id::text as conversation_id,
    customer_id::text as customer_id,
    channel,
    status,
    created_at
FROM conversations
ORDER BY created_at DESC
LIMIT 10;

-- ראה את כל ההודעות
SELECT 
    m.id::text as message_id,
    m.conversation_id::text as conversation_id,
    m.role,
    LEFT(m.content, 50) as content_preview,
    m.created_at
FROM messages m
ORDER BY m.created_at DESC
LIMIT 20;

-- ראה שיחה ספציפית עם כל ההודעות
SELECT 
    c.id::text as conversation_id,
    c.channel,
    c.status,
    m.role,
    m.content,
    m.created_at
FROM conversations c
LEFT JOIN messages m ON c.id = m.conversation_id
WHERE c.id = 'YOUR_CONVERSATION_ID_HERE'
ORDER BY m.created_at ASC;
```

---

### דרך 4: בדיקת Audit Logs

**ב-Swagger UI:**
```
GET /admin/audit?table_name=messages&limit=10
```

**או ב-Python:**
```python
import requests
response = requests.get("http://127.0.0.1:8000/admin/audit?table_name=messages&limit=10")
print(response.json())
```

---

## 📊 מה קורה מאחורי הקלעים?

### זרימת עבודה מלאה:

```
1. משתמש שולח: "שלום, אני מחפש צימר"
   ↓
2. API מקבל: POST /agent/chat
   ↓
3. יוצר שיחה ב-DB:
   INSERT INTO conversations (...)
   → conversation_id = "abc-123"
   ↓
4. שומר הודעת user:
   INSERT INTO messages (conversation_id, role='user', content='...')
   → message_id = "msg-1"
   ↓
5. יוצר audit log:
   INSERT INTO audit_log (table_name='messages', record_id='msg-1', action='INSERT')
   ↓
6. מזהה כוונה (keyword-based):
   "מחפש" → actions: []
   ↓
7. מייצר תשובה:
   answer = "שלום! תודה על פנייתך..."
   ↓
8. שומר תשובת assistant:
   INSERT INTO messages (conversation_id, role='assistant', content='...')
   → message_id = "msg-2"
   ↓
9. יוצר audit log:
   INSERT INTO audit_log (table_name='messages', record_id='msg-2', action='INSERT')
   ↓
10. מחזיר תגובה:
    {
      "answer": "...",
      "conversation_id": "abc-123",
      ...
    }
```

---

## ✅ מה עובד עכשיו?

### ✅ עובד:
- יצירת שיחה חדשה
- שמירת הודעת user
- שמירת הודעת assistant
- Audit log לכל הודעה
- זיהוי כוונות בסיסי (keyword-based)
- תמיכה ב-context (תאריכים, אורחים, צימר)
- יצירת customer אוטומטית לפי phone

### ⏳ Placeholder (יבוצע ב-A3):
- זיהוי כוונות מתקדם (כרגע רק keyword-based)
- חיבור לכלים (availability/quote/hold) - עדיין לא קוראים ל-API
- תגובות חכמות - עדיין תשובות בסיסיות

---

## 🧪 דוגמאות לבדיקה

### דוגמה 1: הודעה פשוטה
```json
POST /agent/chat
{
  "message": "שלום",
  "channel": "web"
}
```

**תגובה צפויה:**
```json
{
  "answer": "שלום! תודה על פנייתך. אני כאן כדי לעזור לך למצוא צימר מתאים.",
  "actions_suggested": [],
  "confidence": 0.5,
  "conversation_id": "uuid-here"
}
```

### דוגמה 2: שאילתת זמינות
```json
POST /agent/chat
{
  "message": "מה הזמינות בתאריכים 15-17 במרץ?",
  "channel": "web",
  "context": {
    "check_in": "2026-03-15",
    "check_out": "2026-03-17"
  }
}
```

**תגובה צפויה:**
```json
{
  "answer": "אשמח לעזור לך לבדוק זמינות. איזה תאריכים אתה מחפש?",
  "actions_suggested": ["availability"],
  "confidence": 0.7,
  "conversation_id": "uuid-here"
}
```

### דוגמה 3: שאילתת מחיר
```json
POST /agent/chat
{
  "message": "כמה עולה צימר ZB01?",
  "channel": "web",
  "context": {
    "cabin_id": "ZB01",
    "check_in": "2026-03-15",
    "check_out": "2026-03-17",
    "guests": 2
  }
}
```

**תגובה צפויה:**
```json
{
  "answer": "אשמח לעזור לך לקבל הצעת מחיר. איזה צימר מעניין אותך ובאילו תאריכים?",
  "actions_suggested": ["quote"],
  "confidence": 0.7,
  "conversation_id": "uuid-here"
}
```

---

## 📁 קבצים שנוצרו/עודכנו

1. **`src/db.py`** - נוספו 4 פונקציות:
   - `create_conversation()`
   - `save_message()`
   - `get_conversation()`
   - `update_conversation_status()`

2. **`src/api_server.py`** - נוספו:
   - Pydantic models: `ChatRequest`, `ChatResponse`, `ChatContext`
   - Endpoint: `POST /agent/chat`
   - עדכון root endpoint

3. **`database/test_agent_chat.py`** - סקריפט בדיקה

4. **`BACKLOG.md`** - עודכן עם סטטוס A2

---

## 🎯 מה הלאה? (שלב A3)

בשלב A3 נוסיף:
- Agent class חכם יותר
- חיבור לכלים קיימים (availability, quote, hold)
- 3 תרחישים מקצה לקצה

---

**נקודת עצירה - הסבר הושלם** ✅


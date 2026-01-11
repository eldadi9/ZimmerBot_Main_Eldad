# 📋 ZimmerBot Backlog
### עבודה מסודרת, שלב אחרי שלב, בלי להתפזר

> 📚 **קישור לתיעוד המלא:** [README.md](./README.md) | [README_FULL.md](./docs/README_FULL.md)

---

## 🎯 מצב נוכחי (אמת טכנית)

### ✅ Stage 1-4 - קיימים ועובדים
| שלב | תיאור | סטטוס |
|-----|--------|--------|
| **Stage 1** | DB Schema ובדיקות | 🟢 Done |
| **Stage 2** | זמינות והזמנה ליומן | 🟢 Done |
| **Stage 3** | `/quote` עם PricingEngine + breakdown | 🟢 Done |
| **Stage 4** | Hold מלא (API + Calendar + DB + Redis fallback) | 🟢 Done |

### ⏳ חסר (השלבים הבאים)
- ✅ **Agent Chat (A1-A4.1)** - הושלם במלואם: DB, Endpoint, Tool Routing, Knowledge (Business Facts + FAQ), שיפור זמינות, מיקום/מפות, תהליך הזמנה מלא. עקרונות הסוכן החכם מוגדרים וממומשים
- ✅ **סנכרון דו-כיווני** - הושלם במלואם: Calendar ↔ DB, Sheets ↔ DB, סנכרון אוטומטי (APScheduler), כפתורי סנכרון ידניים, עריכת הזמנות עם העברת אירועים
- 🟡 Host Console (B1-B2) - השלב הבא! 🎯 (יש UI בסיסי, צריך להשלים Admin API מלא)
- 🟡 תשלומים (חלקי - דמו עובד, חסר החזר כספי)
- 🟡 הודעות ותזכורות (חלקי - הודעה אחת עובדת, חסר תזמון אוטומטי)
- 🔴 אוטומציות n8n (לא התחיל - אין קבצים בקוד)
- 🔴 Agent קולי (לא התחיל - אין קבצים בקוד)

---

## 🚀 שלב A: Agent טקסט (הכי חשוב!)

### A1. 💾 DB לשיחות (חדש)

#### **משימה 1:** יצירת טבלאות לשיחות
```sql
טבלאות נדרשות:
├── conversations      # שיחות
├── messages          # הודעות בשיחה
├── faq               # שאלות מאושרות
└── escalations       # דורש בעלים
```

**תנאי סיום:**
- [x] קובץ migration SQL נוצר (`database/migration_agent_tables.sql`)
- [x] בדיקה שמכניסים שיחה והודעות ב-DB (`database/check_agent_tables.py`)
- [x] כל הבדיקות עברו (5/5)

---

#### **משימה 2:** Audit לכל הודעה
**תנאי סיום:**
- [x] יש רישום פעולה (audit log) לכל message שנשמר

---

### A2. 🤖 Endpoint Agent

#### **משימה 3:** יצירת `POST /agent/chat`

**קלט:**
```json
{
  "message": "string",
  "customer_id": "string (optional)",
  "phone": "string (optional)",
  "channel": "web|whatsapp|voice",
  "context": {
    "check_in": "YYYY-MM-DD (optional)",
    "check_out": "YYYY-MM-DD (optional)",
    "guests": "int (optional)",
    "cabin_id": "string (optional)"
  }
}
```

**פלט:**
```json
{
  "answer": "string",
  "actions_suggested": ["availability", "quote", "hold", "book"],
  "confidence": 0.95,
  "conversation_id": "uuid"
}
```

**תנאי סיום:**
- [x] עובד ב-Swagger UI (`POST /agent/chat`)
- [x] שומר שיחה ב-DB (conversations + messages)
- [x] Audit log לכל הודעה
- [x] Pydantic models (ChatRequest, ChatResponse)

---

#### **משימה 4:** Agent Tool Routing (שרת בלבד)

**לוגיקה:**
- אם צריך זמינות → קורא `check_availability()`
- אם צריך מחיר → קורא `calculate_quote()`
- אם צריך hold → קורא `create_hold()`
- אם צריך הזמנה → קורא `create_booking()`

**תנאי סיום:**
- [x] לפחות **3 תרחישים** עובדים מקצה לקצה
  1. שאילתת זמינות ✅
  2. קבלת הצעת מחיר ✅
  3. יצירת Hold ✅
- [x] Agent class נוצר (`src/agent.py`)
- [x] חיבור לכלים קיימים (availability, quote, hold)

---

### A4. 📚 Knowledge בסיסי

**✅ סטטוס: הושלם** - כל המשימות הושלמו:
- ✅ זמינות: אם שואלים "מה הזמינות" בלי תאריכים, הסוכן שואל "מתי?"
- ✅ זמינות צימר מסוים: אם שואלים "בדוק לי זמינות בצימר של יולי", מציג רשימה/טבלה מסודרת של תאריכים פנויים (60 יום קדימה)
- ✅ קיבוץ תאריכים רצופים: תאריכים רצופים מוצגים כטווח (למשל: "15.03.2026 - 20.03.2026 (6 ימים)")
- ✅ סיכום זמינות: "X תאריכים פנויים מתוך Y ימים"

#### **משימה 5:** קובץ/טבלת Business Facts

**נתונים נדרשים:**
```yaml
Business Facts:
  - שעות צ'ק אין: "15:00"
  - שעות צ'ק אאוט: "11:00"
  - מדיניות ביטול: "24 שעות מראש"
  - כתובת: "רחוב X, יישוב Y"
  - חניה: "כן, חניה פרטית"
  - חיות מחמד: "לא מותרות"
  - כשרות: "לא"
  - WiFi: "כן, חינם"
```

**תנאי סיום:**
- [x] טבלת `business_facts` נוצרה ב-DB
- [x] פונקציות קריאה/כתיבה ב-`src/db.py`
- [x] Agent עונה מתוך facts **בלי להמציא מידע**
- [x] Endpoint `GET /admin/business-facts` ו-`POST /admin/business-facts`

---

#### **משימה 6:** FAQ מאושר בלבד

**תהליך:**
1. Agent קודם מחפש FAQ מאושר
2. אם אין FAQ → עונה ומסמן כ**"מוצע"** (pending approval)
3. בעל הצימר מאשר/דוחה תשובות מוצעות

**תנאי סיום:**
- [x] Agent מחפש FAQ מאושר לפני תשובה
- [x] Agent מסמן תשובות כ-"מוצע" אם אין FAQ
- [x] Endpoint `GET /admin/faq/pending` - רשימת FAQs ממתינים
- [x] Endpoint `POST /admin/faq/approve` - אישור/דחייה של FAQ
- [x] Agent לא משתמש בתשובות לא מאושרות

---

### A4.1. 🔍 שיפור זמינות (Availability Improvements)

#### **משימה 7:** זמינות בלי תאריכים

**תרחישים:**
1. **שאלה בלי תאריכים**: "מה הזמינות?" / "מה זמין?" → Agent שואל "מתי?"
2. **שאלה עם צימר בלי תאריכים**: "בדוק לי זמינות בצימר של יולי" → Agent בודק חודש הקרוב ומציג רשימה/טבלה מסודרת של תאריכים פנויים

**לוגיקה:**
- אם `availability` action אבל אין `check_in`/`check_out` → לשאול "מתי?"
- אם יש `cabin_id` אבל אין תאריכים → לבדוק זמינות לחודש הקרוב (או 60 יום) ולהציג רשימה מסודרת
- אם יש תאריכים → לבדוק זמינות תקינה ולהציג תוצאות

**תצוגת תוצאות:**
- רשימה/טבלה מסודרת של תאריכים פנויים
- קיבוץ תאריכים רצופים (למשל: "15.03.2026 - 20.03.2026" במקום 6 שורות)
- סיכום: "X תאריכים פנויים מתוך Y ימים"
- תאריכים תפוסים (אם רלוונטי)

**תנאי סיום:**
- [x] Agent שואל "מתי?" אם אין תאריכים ✅
- [x] Agent מציג רשימה מסודרת של תאריכים פנויים אם יש `cabin_id` בלי תאריכים ✅
- [x] קיבוץ תאריכים רצופים מוצג נכון ✅
- [x] סיכום ברור של זמינות ✅

**✅ סטטוס:** הושלם במלואם - כל המשימות הושלמו:
- ✅ Agent שואל "מתי?" אם אין תאריכים
- ✅ Agent מציג רשימה מסודרת של תאריכים פנויים אם יש `cabin_id` בלי תאריכים
- ✅ קיבוץ תאריכים רצופים מוצג נכון
- ✅ סיכום ברור של זמינות

---

## 🔄 שלב A5: סנכרון דו-כיווני (הושלם)

### ✅ **משימה 8:** סנכרון Calendar ↔ DB

**תנאי סיום:**
- [x] Calendar → DB: מזהה שינויים ביומנים (שם, מייל, טלפון, תאריכים, צימר) ומעדכן את ה-DB
- [x] DB → Calendar: מעדכן אירועים ב-Google Calendar עם שינויים מה-DB
- [x] Endpoint `POST /admin/sync/calendar-to-db` עם `days_back` ו-`days_forward`
- [x] Endpoint `POST /admin/sync/db-to-calendar` עם `booking_id` אופציונלי
- [x] עדכון `cabin_id` ב-DB כשמזיזים אירוע ליומן אחר

---

### ✅ **משימה 9:** סנכרון Sheets ↔ DB

**תנאי סיום:**
- [x] Sheets → DB: מעתיק צימרים מ-Google Sheets ל-DB (צימרים חדשים, עדכונים)
- [x] DB → Sheets: מעתיק צימרים מה-DB ל-Google Sheets
- [x] Endpoint `POST /admin/sync/sheets-to-db`
- [x] Endpoint `POST /admin/sync/db-to-sheets`
- [x] השוואה חכמה: מעדכן רק שדות שהשתנו

---

### ✅ **משימה 10:** סנכרון אוטומטי

**תנאי סיום:**
- [x] Background scheduler (APScheduler) רץ כל 5 דקות
- [x] סנכרון אוטומטי: Calendar → DB ו-Sheets → DB
- [x] אפשר להפעיל/לכבות דרך UI
- [x] Endpoint `GET /admin/sync/auto-status` - סטטוס סנכרון אוטומטי
- [x] Endpoint `POST /admin/sync/auto-toggle` - הפעלה/כיבוי
- [x] UI מלא: Sync tab ב-Admin Panel עם ניהול סנכרון אוטומטי
- [x] יומן סנכרון עם לוגים מפורטים

---

### ✅ **משימה 11:** עריכת הזמנות

**תנאי סיום:**
- [x] עריכה מלאה של כל פרטי הזמנה (לקוח, צימר, תאריכים, מחיר, סטטוס)
- [x] Endpoint `PUT /admin/bookings/{booking_id}`
- [x] העברת אירועים אוטומטית בין יומנים כשמשנים צימר
- [x] עדכון אוטומטי של `event_id` ו-`event_link` ב-DB
- [x] UI מלא: Booking Edit modal ב-Admin Panel

---

## 🖥️ שלב B: Host Console (שליטה מלאה)

### B1. 🔌 Admin API

| משימה | Endpoint | תיאור |
|-------|----------|--------|
| **7** | `GET /admin/conversations` | רשימת שיחות |
| **8** | `GET /admin/conversations/{id}` | פרטי שיחה אחת |
| **9** | `POST /admin/send-reply` | שליחת תשובה ידנית |
| **10** | `POST /admin/faq` | יצירה/אישור FAQ |
| **11** | `GET /admin/analytics` | סטטיסטיקות |

**תנאי סיום:**
- [ ] הכל עובד ב-**Swagger UI**
- [ ] הכל מחובר ל-**DB**

---

### B2. 🎨 Lovable חיבור בפועל

#### **משימה 12:** Host Inbox UI
- מחובר ל-`GET /admin/conversations`
- מציג רשימת שיחות עם:
  - לקוח
  - זמן אחרון
  - סטטוס (ממתין, נענה, נסגר)

---

#### **משימה 13:** חלון שיחה
- מחובר ל-`GET /admin/conversations/{id}`
- מציג:
  - היסטוריית שיחה
  - תשובה מוצעת של Agent
  - אפשרות עריכה

---

#### **משימה 14:** כפתורים פעולה
```
┌─────────────────────────┐
│ 📤 שלח                  │
│ ✏️ ערוך ושלח            │
│ ⭐ שמור כ-FAQ           │
│ 🚨 דורש בעלים          │
└─────────────────────────┘
```

**תנאי סיום:**
- [ ] בעל צימר יכול לנהל שיחות **מקצה לקצה** מה-UI

---

## 💬 שלב C: Guest Portal (זרימה מלאה)

#### **משימה 15:** Guest Chat UI
- מחובר ל-`POST /agent/chat`
- ממשק צ'אט responsive
- שליחה והצגת תשובות בזמן אמת

---

#### **משימה 16:** תרחיש Full Flow
```mermaid
graph LR
    A[אורח שואל זמינות] --> B[Agent מציג אופציות]
    B --> C[אורח מבקש מחיר]
    C --> D[Agent מחזיר quote]
    D --> E[אורח יוצר Hold]
    E --> F[אורח מבצע הזמנה]
    F --> G[✅ הזמנה מאושרת]
```

**תנאי סיום:**
- [ ] עובד מול **API אמיתי**, לא דמו
- [ ] כל השלבים עובדים ברצף

---

## 💳 שלב D: תשלומים (Stage 5)

| משימה | תיאור | משך משוער |
|-------|--------|-----------|
| **17** | בחירת ספק (Stripe או ישראלי) | 1 יום |
| **18** | יצירת Payment Intent/Invoice | 2 ימים |
| **19** | Webhook מאומת | 1 יום |
| **20** | עדכון DB: transactions + booking status | 1 יום |
| **21** | Convert HOLD → CONFIRMED רק אחרי תשלום | 1 יום |

**תנאי סיום:**
- [x] תשלום בדמו עובד
- [x] הזמנה נסגרת **רק לאחר webhook תקין**
- [x] Rollback אוטומטי אם תשלום נכשל

---

## 📨 שלב E: הודעות ותזכורות (Stage 6)

#### **משימה 22:** תבניות הודעה

```yaml
תבניות נדרשות:
  1. אישור הזמנה:
     - שם לקוח
     - תאריכים
     - סכום
     - קישור לפרטים
  
  2. תזכורת 3 ימים לפני:
     - הנחיות הגעה
     - צק אין
     - איש קשר
  
  3. יום ההגעה:
     - קוד כניסה (אם רלוונטי)
     - מספר טלפון חירום
  
  4. אחרי יציאה:
     - תודה
     - בקשה לחוות דעת
     - קוד הנחה להזמנה הבאה
```

---

#### **משימה 23:** שליחה בערוץ ראשון
- אימייל **או** WhatsApp (לפי העדפת לקוח)
- Fallback: אם אחד נכשל, נסה את השני

---

#### **משימה 24:** רישום notifications ב-DB
```sql
notifications:
  - conversation_id
  - type (confirmation, reminder, followup)
  - channel (email, whatsapp, sms)
  - status (sent, failed, opened)
  - sent_at
```

**תנאי סיום:**
- [x] תשתית הודעות קיימת (`src/email_service.py` + SMTP)
- [x] `send_booking_confirmation()` - קיים
- [x] `send_payment_receipt()` - קיים
- [x] `send_reminder()` - קיים
- [x] סקריפט `database/send_reminders.py` - קיים
- [ ] ⚠️ **צריך לבדוק:** האם SMTP מוגדר ב-.env? האם הודעות נשלחות בפועל?
- [ ] טבלת `notifications` ב-DB - צריך לבדוק אם קיימת

---

## 🔄 שלב F: n8n אוטומציות (במקביל אחרי Host)

| משימה | אוטומציה | טריגר |
|-------|-----------|--------|
| **25** | סיכום יומי לבעל צימר | 08:00 בוקר |
| **26** | התראה על שיחה שלא נענתה | X דקות ללא מענה |
| **27** | יצירת משימה לחריגים | זיהוי בעיה |

**תנאי סיום:**
- [ ] **2 אוטומציות פעילות** ומדווחות
- [ ] לוגים ב-n8n
- [ ] התראות מגיעות בפועל

> ⚠️ **הערה:** שלב זה לא התחיל. אין קבצי n8n או workflows בקוד.

---

## 🎙️ שלב G: Agent קולי (Stage 8)

```mermaid
graph LR
    A[📞 Voice Inbound] --> B[🎤 תמלול Speech-to-Text]
    B --> C[🤖 POST /agent/chat]
    C --> D[💬 קבלת תשובה]
    D --> E[🔊 TTS]
    E --> F[📞 השמעה ללקוח]
```

| משימה | תיאור | כלים |
|-------|--------|------|
| **28** | Voice inbound → תמלול | Vapi / Bland.ai / Deepgram |
| **29** | POST /agent/chat | קיים |
| **30** | תשובה → TTS | ElevenLabs / Google TTS |

**תנאי סיום:**
- [ ] **שיחה קולית אחת מלאה** עובדת
- [ ] תמלול מדויק (>90%)
- [ ] TTS טבעי ומובן

> ⚠️ **הערה:** שלב זה לא התחיל. אין קבצי voice/TTS או אינטגרציה עם Vapi/Bland.ai בקוד.

---

## 📂 קבצים חשובים שכבר קיימים

### Backend
```
src/
├── api_server.py         # FastAPI routes
├── main.py               # Entry point
├── pricing.py            # לוגיקת תמחור
├── hold.py               # ניהול holds
├── db.py                 # חיבורים ל-DB
└── features_utils.py     # כלים משותפים
```

### Database
```
database/
├── check_stage1.py       # בדיקת Stage 1
├── check_stage2.py       # בדיקת Stage 2
├── check_stage3.py       # בדיקת Stage 3
└── check_stage4.py       # בדיקת Stage 4
```

### Tools & Docs
```
tools/
└── features_picker.html  # בחירת תכונות

docs/
├── PROJECT_STATUS.md     # סטטוס הפרויקט
└── README_FULL.md        # תיעוד מלא
```

---

## 🎯 סדר עבודה יומי מומלץ

1. **תמיד קודם Endpoint ואז UI**
   - Backend קודם → Frontend אחר כך
   - לא להתחיל UI לפני ש-API עובד

2. **לא עוברים סעיף בלי אישור**
   - סיימת משימה? ✅ סמן
   - בדוק תנאי סיום
   - עבור למשימה הבאה רק אחרי אישור

3. **כל שיחה נשמרת מהיום הראשון**
   - Audit trail מלא
   - לא מוחקים היסטוריה
   - שמירה ב-DB + logs

---

## 📊 טבלת סטטוס כללית

| שלב | תיאור | סטטוס | אחוז השלמה |
|-----|--------|--------|------------|
| **Stage 1** | DB Schema | 🟢 Done | 100% |
| **Stage 2** | זמינות והזמנה | 🟢 Done | 100% |
| **Stage 3** | תמחור | 🟢 Done | 100% |
| **Stage 4** | Hold | 🟢 Done | 100% |
| **Stage 5** | תשלומים | 🟢 Done | 100% |
| **Stage 6** | הודעות | 🟡 Partial | 80% (חסר תזמון אוטומטי) |
| **Stage 7** | Agent Chat (A1-A4.1) | 🟢 Done | 100% |
| **Stage 7.5** | סנכרון דו-כיווני | 🟢 Done | 100% |
| **Stage 8** | Host Console | 🟡 Partial | 20% (יש UI בסיסי) |
| **Stage 9** | n8n | 🔴 Not started | 0% |
| **Stage 10** | Voice | 🔴 Not started | 0% |

**סה"כ התקדמות: 78% (7.8 מתוך 10 שלבים)**

---

<div align="center">

**📌 עדכון אחרון:** 11 ינואר 2026  
**🎯 משימה נוכחית:** השלמת שלב 6 (הודעות - תזמון אוטומטי) או שלב B - Host Console (B1: Admin API)

### 🆕 מה הושלם לאחרונה (ינואר 2026):

#### ✅ סנכרון דו-כיווני מלא
- **סנכרון אוטומטי**: Calendar → DB ו-Sheets → DB רץ כל 5 דקות ברקע (APScheduler)
- **כפתורי סנכרון ידניים**: 4 כיווני סנכרון עם לוגים מפורטים
- **עריכת הזמנות**: עריכה מלאה עם העברת אירועים אוטומטית בין יומנים
- **UI מלא**: Sync tab ב-Admin Panel עם ניהול סנכרון אוטומטי

#### ✅ Agent Chat (A1-A4.1) - הושלם במלואם
- **A1**: DB לשיחות (conversations, messages, faq, escalations)
- **A2**: Agent Endpoint (`POST /agent/chat`) עם context management
- **A3**: Tool Routing (availability, quote, hold, book)
- **A4**: Knowledge Base (Business Facts + FAQ מאושר)
- **A4.1**: שיפור זמינות (שאילתת "מתי?", רשימה מסודרת, קיבוץ תאריכים)
- **תמיכה נוספת**: מיקום/מפות, תמונות, תהליך הזמנה מלא

**קבצים שנוספו/שונו:**
- `src/sync_calendar.py`, `src/sync_sheets.py` - פונקציות סנכרון
- `src/api_server.py` - Auto-sync scheduler, sync endpoints, booking edit endpoint
- `tools/features_picker.html` - Sync tab, Auto-sync UI, Booking Edit modal
- `docs/AUTO_SYNC_EXPLANATION.md`, `docs/AUTO_SYNC_SUMMARY.md` - תיעוד
- `requirements.txt` - הוספת `apscheduler==3.10.4`

[⬆️ חזרה למעלה](#-zimmerbot-backlog)

</div>

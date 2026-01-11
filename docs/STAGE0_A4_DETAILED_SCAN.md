# 📋 דוח סריקה מפורט - שלב 0 (A4)
## אמת טכנית: מה קיים בפועל בקוד סביב A4

> 📅 **תאריך:** ינואר 2026  
> 🎯 **מטרה:** בדיקה מקיפה של A4 (Business Facts + FAQ) ואיתור בעיית השמירה והמענה

---

## 🔍 א. סריקת מבנה - A4

### מבנה תיקיות - A4:

```
ZimmerBot_Main_Eldad/
├── src/
│   ├── api_server.py          # ✅ כולל /agent/chat + Admin endpoints
│   ├── db.py                  # ✅ כולל Business Facts + FAQ functions
│   └── agent.py               # ✅ כולל generate_response
├── database/
│   ├── migration_a4_business_facts.sql  # ✅ מיגרציה ל-Business Facts
│   ├── migration_agent_tables.sql       # ✅ מיגרציה ל-FAQ
│   ├── test_a4_business_facts.py        # ✅ בדיקות A4
│   ├── test_agent_chat.py               # ✅ בדיקות Agent Chat
│   └── init_static_questions.py         # ✅ אתחול Facts + FAQs
├── tools/
│   └── features_picker.html   # ✅ כולל Admin Panel + FAQ & Facts
└── docs/
    ├── A4_STATUS_UPDATE.md
    ├── A4_COMPLETION_REPORT.md
    ├── A4_FAQ_EXPLANATION.md
    ├── A4_FAQ_DYNAMIC_VS_STATIC.md
    └── A4_BUSINESS_FACTS_EXPLANATION.md
```

---

## 🔌 ב. FastAPI Endpoints - A4

### Endpoints קיימים:

| Endpoint | Method | סטטוס | הערות |
|----------|--------|-------|-------|
| `/agent/chat` | POST | ✅ | קיים, כולל A4 logic |
| `/admin/faq/pending` | GET | ✅ | רשימת FAQs ממתינים |
| `/admin/faq/approve` | POST | ✅ | אישור/דחייה FAQ |
| `/admin/faq/all` | GET | ✅ | כל ה-FAQs |
| `/admin/faq/{id}` | PUT | ✅ | עדכון FAQ |
| `/admin/faq/{id}` | DELETE | ✅ | מחיקת FAQ |
| `/admin/business-facts` | GET | ✅ | רשימת Business Facts |
| `/admin/business-facts` | POST | ✅ | יצירת/עדכון Fact |
| `/admin/business-facts/{key}` | DELETE | ✅ | מחיקת Fact |

**סה"כ:** 8 endpoints פעילים

---

## 💾 ג. DB Schema - A4

### טבלאות קיימות (ממיגרציות):

| טבלה | קובץ מיגרציה | שדות עיקריים | סטטוס |
|------|---------------|---------------|-------|
| `business_facts` | `migration_a4_business_facts.sql` | fact_key, fact_value, category, is_active | ✅ |
| `faq` | `migration_agent_tables.sql` | question, answer, approved, suggested_answer, suggested_at | ✅ |
| `conversations` | `migration_agent_tables.sql` | id, customer_id, channel, status, metadata | ✅ |
| `messages` | `migration_agent_tables.sql` | id, conversation_id, role, content, metadata | ✅ |

### שדות FAQ (מה קיים):

```sql
faq:
  - id (UUID PRIMARY KEY)
  - question (TEXT NOT NULL)
  - answer (TEXT NOT NULL)
  - approved (BOOLEAN DEFAULT FALSE)  ✅
  - suggested_by (UUID REFERENCES customers)  ✅
  - approved_by (UUID)  ✅
  - approved_at (TIMESTAMP)  ✅
  - usage_count (INT DEFAULT 0)  ✅
  - suggested_answer (TEXT)  ✅ (מ-migration_a4_business_facts.sql)
  - suggested_at (TIMESTAMP)  ✅ (מ-migration_a4_business_facts.sql)
  - created_at (TIMESTAMP)  ✅
  - updated_at (TIMESTAMP)  ✅
```

**הערה חשובה:** שדות `suggested_answer` ו-`suggested_at` נוספו ב-`migration_a4_business_facts.sql`, לא ב-`migration_agent_tables.sql`.

---

## 🔍 ד. זרימת /agent/chat - A4 (מה קיים בקוד)

### זרימה בפועל (משורה 1975 ב-`src/api_server.py`):

```
1. שמירת הודעת משתמש (שורות 1918-1925) ✅
   - save_message() עם role='user'
   
2. בדיקת FAQ מאושר (שורה 1980) ✅
   - get_approved_faq(request.message)
   - חיפוש לפי LOWER(question) LIKE LOWER(%{message}%)
   
3. בדיקת FAQ דינמי vs סטטי (שורות 1986-2021) ✅
   - אם FAQ מכיל מילות מפתח דינמיות (list_cabins, availability)
   - אז לא משתמשים ב-FAQ, עוברים ל-intent detection רגיל
   - אחרת משתמשים ב-FAQ ישירות
   
4. אם אין FAQ → בדיקת Business Facts (שורות 2031-2052) ✅
   - חיפוש לפי keywords (check_in_time, check_out_time, וכו')
   - get_business_fact(fact_key)
   - אם נמצא → answer = fact_value
   
5. אם אין FAQ ואין Facts → Intent Detection רגיל (שורות 2024-2029) ✅
   
6. קריאה לכלים (availability, quote, hold, cabin_info) (שורות 2054-2350) ✅
   
7. יצירת תשובה (שורות 2475-2510) ✅
   - agent.generate_response() אם לא FAQ/Fact
   
8. שמירת תשובת Agent (שורות 2512-2540) ✅
   - save_message() עם role='assistant'
   
9. הצעת FAQ אם אין FAQ (שורות 2490-2502) ⚠️
   - אם Agent יצר תשובה (לא FAQ/Fact) → suggest_faq()
   - אבל: רק אם answer לא ריק ולא FAQ/Fact
```

**בעיה אפשרית #1:** הצעת FAQ (שורה 2490) - האם זה נקרא בכל המקרים הנכונים?

**בעיה אפשרית #2:** חיפוש FAQ (שורה 1980) - האם החיפוש `LIKE` מספיק? האם יש normalização?

**בעיה אפשרית #3:** שמירת FAQ (שורה 1140 ב-`src/db.py`) - האם יש `conn.commit()`?

---

## 🐛 ה. איתור בעיות פוטנציאליות - שמירה ומענה

### בעיה #1: הצעת FAQ לא נקראת תמיד

**מיקום:** `src/api_server.py`, שורה 2490

```python
# A4: If Agent generated an answer and no FAQ was found, suggest it as FAQ
if not faq_match and answer and intent not in ['faq', 'business_fact']:
    # Suggest this answer as FAQ for Host approval
    suggested_faq_id = suggest_faq(
        question=request.message,
        answer=answer,
        customer_id=customer_id
    )
```

**בעיה פוטנציאלית:**
- אם `intent == 'faq'` או `intent == 'business_fact'`, FAQ לא מוצע
- זה נכון לוגית, אבל צריך לוודא ש-FAQ/Fact אכן נמצאו

**תיקון נדרש:** ✅ נראה נכון - FAQ לא מוצע אם כבר נמצא FAQ/Fact

---

### בעיה #2: שמירת FAQ - האם יש commit?

**מיקום:** `src/db.py`, שורה 1131-1160

```python
def suggest_faq(question: str, answer: str, customer_id: Optional[str] = None) -> Optional[str]:
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO faq (question, answer, approved, suggested_by, suggested_answer, suggested_at)
                VALUES (%s, %s, FALSE, %s, %s, CURRENT_TIMESTAMP)
                RETURNING id
            """, (question, answer, customer_id, answer))
            faq_id = cursor.fetchone()[0]
            
            # Save audit log
            try:
                save_audit_log(...)
            except Exception as audit_error:
                print(f"Warning: Could not save audit log: {audit_error}")
            
            return str(faq_id)
```

**בעיה פוטנציאלית:**
- `with get_db_connection()` אמור לעשות `commit()` אוטומטית (context manager)
- אבל צריך לבדוק אם `get_db_connection()` באמת עושה commit

**בדיקה:** קרא את `get_db_connection()` context manager:

```python
@contextmanager
def get_db_connection():
    conn = None
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        yield conn
        conn.commit()  # ✅ יש commit!
    except Exception as e:
        if conn:
            conn.rollback()
        raise e
    finally:
        if conn:
            conn.close()
```

**מסקנה:** ✅ יש `commit()` אוטומטית

---

### בעיה #3: עדכון FAQ - האם יש commit?

**מיקום:** `src/db.py`, שורה 1163-1230

```python
def approve_faq(faq_id: str, approved_by: Optional[str] = None, question: Optional[str] = None, answer: Optional[str] = None) -> bool:
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            # ... UPDATE faq ...
            conn.commit()  # ✅ יש commit מפורש!
            return True
```

**מסקנה:** ✅ יש `commit()` מפורש ב-`approve_faq`

**מיקום:** `src/db.py`, `update_faq()` (צריך לבדוק)

---

### בעיה #4: חיפוש FAQ - האם החיפוש מספיק טוב?

**מיקום:** `src/db.py`, שורה 1098-1128

```python
def get_approved_faq(question: str) -> Optional[Dict[str, Any]]:
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            # Search for FAQ where question is similar (case-insensitive)
            cursor.execute("""
                SELECT id, question, answer, usage_count
                FROM faq
                WHERE approved = TRUE 
                AND LOWER(question) LIKE LOWER(%s)
                ORDER BY usage_count DESC
                LIMIT 1
            """, (f"%{question}%",))
```

**בעיות פוטנציאליות:**
1. חיפוש `LIKE` פשוט - לא מנרמל (סימני פיסוק, רווחים כפולים, וכו')
2. חיפוש לפי כל השאלה - אם המשתמש שואל "מה שעות הצק אין?" והשאלה ב-FAQ היא "שעות הצק אין", זה לא ימצא
3. לא משתמש ב-similarity/text search מתקדם

**דוגמה לבעיה:**
- FAQ ב-DB: `"מה שעות הצק אין?"`
- שאלת משתמש: `"שעות הצק אין"`
- `LIKE '%שעות הצק אין%'` לא ימצא `"מה שעות הצק אין?"`

**תיקון נדרש:** נרמול טוב יותר - הסרת סימני פיסוק, רווחים כפולים, מילות שאלה

---

### בעיה #5: Business Facts - חיפוש לפי keywords קשיח

**מיקום:** `src/api_server.py`, שורות 2033-2052

```python
business_facts_keywords = {
    'check_in_time': ['שעת צק אין', 'צק אין', 'check in', 'שעה להגעה'],
    'check_out_time': ['שעת צק אאוט', 'צק אאוט', 'check out', 'שעה לעזיבה'],
    ...
}

# Check if message is asking about a business fact
for fact_key, keywords in business_facts_keywords.items():
    if any(kw in message_lower for kw in keywords):
        fact_value = get_business_fact(fact_key)
        if fact_value:
            answer = fact_value
            ...
```

**בעיות פוטנציאליות:**
1. חיפוש `if any(kw in message_lower for kw in keywords)` - מאוד בסיסי
2. אם המשתמש שואל "מה השעה להגעה?" והמילה "צק אין" לא מופיעה, זה לא ימצא
3. לא מחפש ב-FAQ לפני Business Facts (אבל זה נכון לפי A4 - FAQ קודם)

**תיקון נדרש:** שיפור keywords או מעבר לחיפוש semantický

---

## 📊 ו. בדיקות בפועל - מה צריך לבדוק

### בדיקה 1: DB Schema
- [ ] האם טבלת `business_facts` קיימת?
- [ ] האם טבלת `faq` קיימת עם כל השדות?
- [ ] האם יש נתונים ב-`business_facts`?
- [ ] האם יש FAQs מאושרים?

### בדיקה 2: שמירה
- [ ] האם `suggest_faq()` שומרת ל-DB?
- [ ] האם `approve_faq()` מעדכן ב-DB?
- [ ] האם `update_faq()` מעדכן ב-DB?

### בדיקה 3: שליפה
- [ ] האם `get_approved_faq()` מוצא FAQ מאושר?
- [ ] האם `get_business_fact()` מוצא Fact?
- [ ] האם חיפוש FAQ עובד עם וריאציות שונות של השאלה?

### בדיקה 4: זרימה
- [ ] האם `/agent/chat` מחפש FAQ לפני Facts?
- [ ] האם `/agent/chat` מציע FAQ אם לא נמצא?
- [ ] האם התשובות נשמרות ל-`messages`?

---

## 🔍 ז. זיהוי Root Cause - בעיית השמירה והמענה

### בעיה אפשרית #1: חיפוש FAQ לא מדויק

**Root Cause:**
- `get_approved_faq()` משתמש ב-`LIKE '%{question}%'`
- לא מנהל רווחים כפולים, סימני פיסוק, מילות שאלה
- לא מנרמל טקסט עברית (ניקוד, טעמים)

**דוגמה:**
- FAQ: `"מה שעות הצק אין?"`
- שאלה: `"שעות הצק אין"`
- תוצאה: לא נמצא ❌

**תיקון נדרש:** נרמול טוב יותר - הסרת סימני פיסוק, מילות שאלה, רווחים

---

### בעיה אפשרית #2: Business Facts keywords לא מקיפות

**Root Cause:**
- חיפוש לפי keywords קשיח - רק מילות מפתח ספציפיות
- אם המשתמש שואל בצורה שונה, זה לא ימצא

**דוגמה:**
- Fact: `check_in_time = "15:00"`
- שאלה: `"מתי אפשר להגיע?"`
- תוצאה: לא נמצא ❌ (כי "הגעה" לא ברשימת keywords)

**תיקון נדרש:** הוספת keywords או שיפור החיפוש

---

### בעיה אפשרית #3: FAQ לא מוצע אם יש Business Fact

**Root Cause:**
- אם נמצא Business Fact, התשובה נקבעת (שורה 2048)
- אבל FAQ לא מוצע אחר כך (כי יש `answer`)
- זה נכון לוגית, אבל יכול להיות ש-FAQ עדיף על Fact

**תיקון נדרש:** ✅ זה נכון - FAQ קודם ל-Fact (שורה 1975)

---

### בעיה אפשרית #4: שמירה לא עובדת (לא commit)

**Root Cause:**
- בדקתי - יש `commit()` ב-context manager ✅
- אבל צריך לוודא שלא יש exception לפני commit

**תיקון נדרש:** בדיקה שכל exceptions מטופלים נכון

---

## 📋 ח. רשימת פערים - A4

### פערים זוהו:

1. **חיפוש FAQ לא מדויק:**
   - בעיה: `LIKE` פשוט לא מספיק
   - תיקון: נרמול טוב יותר (הסרת פיסוק, מילות שאלה, רווחים)

2. **Business Facts keywords לא מקיפות:**
   - בעיה: רק keywords ספציפיים
   - תיקון: הוספת keywords או שיפור החיפוש

3. **לא נבדק בפועל:**
   - צריך לבדוק אם שמירה באמת עובדת
   - צריך לבדוק אם שליפה באמת עובדת
   - צריך לבדוק אם התשובות נכונות

---

## 🎯 ט. מה עובד ומה לא

### ✅ מה עובד (מהקוד):

1. **DB Schema** - ✅ טבלאות קיימות
2. **Functions** - ✅ כל הפונקציות קיימות (get_approved_faq, get_business_fact, suggest_faq, approve_faq)
3. **Endpoints** - ✅ כל ה-endpoints קיימים
4. **Logic Flow** - ✅ FAQ קודם ל-Fact, Facts קודם ל-intent רגיל
5. **Context Manager** - ✅ יש commit() אוטומטית

### 🟡 מה חלקי (צריך לבדוק):

1. **חיפוש FAQ** - 🟡 חיפוש בסיסי, לא מנרמל
2. **Business Facts keywords** - 🟡 רק keywords קשיחים
3. **שמירה בפועל** - 🟡 צריך לבדוק אם באמת נשמר

### ❌ מה לא נבדק:

1. **שמירה בפועל** - ❌ לא נבדק אם suggest_faq באמת שומרת
2. **שליפה בפועל** - ❌ לא נבדק אם get_approved_faq באמת מוצא
3. **תשובות נכונות** - ❌ לא נבדק אם התשובות מהן Facts/FAQ נכונות

---

## 🔄 י. הצלבה למסמכים

### BACKLOG.md vs קוד:

| דרישה | BACKLOG | קוד | תואם? |
|-------|---------|-----|-------|
| טבלת business_facts | ✅ | ✅ קיימת | ✅ |
| Agent עונה מתוך facts | ✅ | ✅ קיים | ✅ |
| FAQ מאושר בלבד | ✅ | ✅ קיים | ✅ |
| Agent מסמן כ-"מוצע" | ✅ | ✅ קיים | ✅ |
| Endpoint /admin/faq/pending | ✅ | ✅ קיים | ✅ |
| Endpoint /admin/faq/approve | ✅ | ✅ קיים | ✅ |
| Agent לא משתמש בלא מאושר | ✅ | ✅ קיים (approved=TRUE) | ✅ |

**מסקנה:** ✅ הקוד תואם ל-BACKLOG

---

## ⚠️ יא. פערים ובעיות - סיכום

### פערים קריטיים:

1. **חיפוש FAQ לא מדויק:**
   - בעיה: `LIKE '%{question}%'` לא מנרמל
   - דוגמה: `"מה שעות הצק אין?"` לא ימצא `"שעות הצק אין"`
   - תיקון: נרמול - הסרת סימני פיסוק, מילות שאלה, רווחים כפולים

2. **Business Facts keywords לא מקיפות:**
   - בעיה: רק keywords קשיחים
   - דוגמה: `"מתי אפשר להגיע?"` לא ימצא `check_in_time`
   - תיקון: הוספת keywords או שיפור החיפוש

3. **לא נבדק בפועל:**
   - צריך להריץ בדיקות בפועל
   - צריך לבדוק אם שמירה עובדת
   - צריך לבדוק אם שליפה עובדת

---

## 🎯 יב. תכנית עבודה - A4

### עדיפות 1: בדיקות בפועל
- [ ] בדיקת DB - האם טבלאות קיימות עם נתונים?
- [ ] בדיקת שמירה - האם suggest_faq באמת שומרת?
- [ ] בדיקת שליפה - האם get_approved_faq באמת מוצא?
- [ ] בדיקת Swagger - 6 תרחישים

### עדיפות 2: תיקון חיפוש FAQ
- [ ] נרמול טוב יותר ב-get_approved_faq()
- [ ] הסרת סימני פיסוק, מילות שאלה, רווחים כפולים
- [ ] בדיקת edge cases

### עדיפות 3: שיפור Business Facts
- [ ] הוספת keywords
- [ ] או שיפור החיפוש (semantic)

### עדיפות 4: בדיקות רגרסיה
- [ ] בדיקת availability/quote/hold/book לא נשברו

---

<div align="center">

**📅 תאריך:** ינואר 2026  
**✅ מה קיים:** DB Schema, Functions, Endpoints, Logic  
**🟡 מה חלקי:** חיפוש FAQ (לא מנרמל), Business Facts keywords (לא מקיפות)  
**❌ מה לא נבדק:** שמירה בפועל, שליפה בפועל  
**🎯 השלב הבא:** בדיקות בפועל + תיקון חיפוש FAQ

</div>

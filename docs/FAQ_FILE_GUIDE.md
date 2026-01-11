# 📄 מדריך לקובץ Question & Answers.txt

**תאריך יצירה:** 11 ינואר 2026

## 📋 סקירה כללית

הקובץ `Question & Answers.txt` הוא **קובץ טקסט פשוט** שמכיל שאלות ותשובות עבור הסוכן החכם.

**חשוב:**
- ✅ הקובץ כבר קיים בפרויקט (לא צריך ליצור)
- ✅ אפשר להוסיף אליו שאלות חדשות
- ✅ הסקריפט `database/import_faqs_from_file.py` קורא מהקובץ ומייבא ל-DB
- ✅ המידע **נשמר ב-DB** בטבלאות `faq` ו-`business_facts`

---

## 📊 איפה המידע נשמר ב-DB?

### 1. FAQs → טבלת `faq`

**טבלה:** `faq`

**שדות:**
- `id` (UUID) - מזהה ייחודי
- `question` (TEXT) - השאלה
- `answer` (TEXT) - התשובה
- `approved` (BOOLEAN) - האם מאושר (רק FAQs מאושרים משמשים את הסוכן)
- `suggested_by` (UUID) - מי הציע (אם רלוונטי)
- `approved_by` (UUID) - מי אישר (Host/Admin)
- `approved_at` (TIMESTAMP) - מתי אושר
- `usage_count` (INTEGER) - כמה פעמים השתמשו ב-FAQ זה
- `created_at` (TIMESTAMP) - מתי נוצר
- `updated_at` (TIMESTAMP) - מתי עודכן

**איך לבדוק:**
```sql
-- כל ה-FAQs
SELECT id, question, approved, usage_count FROM faq ORDER BY created_at DESC;

-- FAQs מאושרים בלבד
SELECT question, answer FROM faq WHERE approved = TRUE;

-- FAQs ממתינים לאישור
SELECT question, answer FROM faq WHERE approved = FALSE;
```

### 2. Business Facts → טבלת `business_facts`

**טבלה:** `business_facts`

**שדות:**
- `id` (UUID) - מזהה ייחודי
- `fact_key` (VARCHAR) - מפתח ייחודי (לדוגמה: "check_in_time", "reception_hours")
- `fact_value` (TEXT) - הערך (לדוגמה: "15:00", "א' עד ה' בין השעות: 08:00 – 17:00")
- `category` (VARCHAR) - קטגוריה (לדוגמה: "hours", "policies", "amenities")
- `description` (TEXT) - תיאור (אופציונלי)
- `is_active` (BOOLEAN) - האם פעיל
- `created_at` (TIMESTAMP) - מתי נוצר
- `updated_at` (TIMESTAMP) - מתי עודכן

**איך לבדוק:**
```sql
-- כל ה-Business Facts
SELECT fact_key, fact_value, category FROM business_facts WHERE is_active = TRUE;

-- Business Facts בקטגוריה מסוימת
SELECT fact_key, fact_value FROM business_facts WHERE category = 'hours' AND is_active = TRUE;
```

---

## ✏️ איך להוסיף שאלות לקובץ?

### שיטה 1: הוספה ידנית לקובץ

**לשאלות ותשובות פשוטות (FAQs):**

פתח את הקובץ `Question & Answers.txt` והוסף בסוף החלק הראשון (לפני "---"):

```
11. השאלה החדשה שלך?
תשובה: התשובה החדשה שלך כאן.

12. שאלה נוספת?
תשובה: תשובה נוספת.
```

**לשאלות מורכבות יותר (FAQs מובנים):**

הוסף בחלק השני (אחרי "---"):

```
ID: FAQ-000150
Category: 1) תהליך הזמנה ותיאום
Subcategory: זמינות ותאריכים
Question: השאלה החדשה שלך?
OwnerAnswer: [בעל הצימר להשלים]
SuggestedAnswer: התשובה המוצעת כאן
Tags: [תג1, תג2]
Status: pending_approval
```

**ל-Business Facts:**

הוסף מידע סטטי (שעות, מדיניות, וכו'):

```
שעות פעילות חדשות
משרד הקבלה עובד בימים א'-ה' בין השעות: 09:00 – 18:00
```

הסקריפט יזהה וייביא אוטומטית.

### שיטה 2: הוספה דרך Admin Panel (מומלץ)

**דרך Admin Panel (`tools/features_picker.html`):**

1. פתח `tools/features_picker.html`
2. Admin Panel → FAQ & Facts
3. לחץ על "הוסף FAQ חדש"
4. מלא שאלה ותשובה
5. שמור

**יתרונות:**
- ✅ נשמר ישירות ב-DB (אין צורך בייבוא)
- ✅ אפשר לאשר/לדחות מיד
- ✅ נוח יותר לשימוש

---

## 🔄 תהליך העבודה המומלץ

### אופציה 1: עריכה בקובץ + ייבוא

1. **ערוך את הקובץ** `Question & Answers.txt`
2. **הוסף שאלות/תשובות** בפורמט הנכון
3. **הרץ את הסקריפט:**
   ```bash
   database\run_import_faqs.bat
   ```
4. **בדוק ב-Admin Panel** שהשאלות יובאו

### אופציה 2: הוספה ישירה דרך Admin Panel (מומלץ)

1. פתח `tools/features_picker.html`
2. Admin Panel → FAQ & Facts
3. הוסף FAQ חדש או Business Fact חדש
4. שמור ואשר

**יתרונות:**
- ✅ אין צורך בייבוא
- ✅ נשמר מיד ב-DB
- ✅ נוח יותר לשימוש
- ✅ אפשר לערוך/למחוק מיד

---

## 📝 מבנה הקובץ הנוכחי

הקובץ `Question & Answers.txt` מכיל:

### חלק 1: שאלות ותשובות בסיסיות (שורות 1-61)

```
1. מהי ההתחייבות למחיר הטוב ביותר?
תשובה: אנחנו מתחייבים למחיר הנמוך ביותר...

2. האם ניתנת הנחה נוספת...
תשובה: בחלק מהמתחמים...
```

**10 שאלות** + מידע על גילאים ושעות פעילות

### חלק 2: בנק שאלות ותשובות מורחב (אחרי "---")

```
ID: FAQ-000001
Category: 1) תהליך הזמנה ותיאום
Subcategory: זמינות ותאריכים
Question: איך אני בודק זמינות...
...
```

**158 שאלות** עם פורמט מובנה

---

## ✅ מה נשמר ב-DB?

### FAQs:

**מקור:** קובץ `Question & Answers.txt`
**טבלה:** `faq`
**כמה:** 158 FAQs (לפי הבדיקה האחרונה)

**סטטוס:**
- FAQs מאושרים (`approved = TRUE`) → משמשים את הסוכן
- FAQs ממתינים (`approved = FALSE`) → דורשים אישור דרך Admin Panel

### Business Facts:

**מקור:** קובץ `Question & Answers.txt`
**טבלה:** `business_facts`
**כמה:** 6 Business Facts (לפי הבדיקה האחרונה)

**דוגמאות:**
- `pricing_by_age` - תמחור לפי גיל
- `reception_hours` - שעות פעילות משרד הקבלה
- `check_in_hours` - שעות קבלת חדרים
- `check_out_hours` - שעות פינוי חדרים
- `meals_available` - ארוחות זמינות
- `kosher_status` - כשרות

---

## 🔍 איך לבדוק מה נשמר?

### דרך SQL:

```sql
-- בדוק FAQs
SELECT COUNT(*) as total_faqs FROM faq;
SELECT COUNT(*) as approved_faqs FROM faq WHERE approved = TRUE;
SELECT COUNT(*) as pending_faqs FROM faq WHERE approved = FALSE;

-- בדוק Business Facts
SELECT COUNT(*) as total_facts FROM business_facts WHERE is_active = TRUE;
SELECT fact_key, fact_value FROM business_facts WHERE is_active = TRUE;
```

### דרך Admin Panel:

1. פתח `tools/features_picker.html`
2. Admin Panel → FAQ & Facts
3. **FAQs:**
   - **"FAQ & Facts"** → רשימת FAQs ממתינים לאישור
   - **"All FAQs"** → כל ה-FAQs (מאושרים וממתינים)
4. **Business Facts:**
   - **"FAQ & Facts"** → רשימת Business Facts

---

## 🎯 המלצות

### מתי להשתמש בקובץ `Question & Answers.txt`?

✅ **כשאתה רוצה:**
- להוסיף הרבה שאלות בבת אחת
- לנהל את כל השאלות בקובץ טקסט אחד
- לעבוד עם עורך טקסט
- לשתף את הקובץ עם אחרים

### מתי להשתמש ב-Admin Panel?

✅ **כשאתה רוצה:**
- להוסיף שאלה אחת או שתיים
- לאשר/לדחות FAQs ממתינים
- לערוך/למחוק FAQs קיימים
- לנהל Business Facts
- לעבוד מהדפדפן

---

## 📋 סיכום

### הקובץ:

- ✅ **קיים:** `Question & Answers.txt` (בתיקיית הבסיס של הפרויקט)
- ✅ **ניתן לעריכה:** אפשר להוסיף שאלות חדשות
- ✅ **נשמר ב-DB:** הסקריפט מייבא מהקובץ ל-DB

### הטבלאות ב-DB:

1. **`faq`** - כל השאלות והתשובות (FAQs)
   - FAQs מאושרים → משמשים את הסוכן
   - FAQs ממתינים → דורשים אישור

2. **`business_facts`** - עובדות עסקיות סטטיות
   - שעות, מדיניות, תכונות
   - משמשות את הסוכן ישירות

### תהליך עבודה:

1. **ערוך את הקובץ** (או השתמש ב-Admin Panel)
2. **הרץ את הסקריפט** (`database\run_import_faqs.bat`)
3. **בדוק ב-Admin Panel** שהשאלות יובאו
4. **אשר FAQs ממתינים** (אם צריך)

---

**קובץ זה הוא כלי עזר לייבוא המוני. לשאלות בודדות, מומלץ להשתמש ב-Admin Panel!**

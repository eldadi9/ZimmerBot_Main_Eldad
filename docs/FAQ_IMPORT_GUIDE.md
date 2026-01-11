# 📚 מדריך לייבוא FAQs ו-Business Facts

**תאריך יצירה:** 11 ינואר 2026

## 📋 סקירה כללית

סקריפט `database/import_faqs_from_file.py` מיועד לייבא FAQs ו-Business Facts מקובץ `Question & Answers.txt` ל-DB.

## 📄 מבנה הקובץ

הקובץ `Question & Answers.txt` מכיל שני חלקים:

### חלק 1: שאלות ותשובות בסיסיות (שורות 1-61)

**פורמט:**
```
1. מהי ההתחייבות למחיר הטוב ביותר?
תשובה: אנחנו מתחייבים למחיר הנמוך ביותר...

2. האם ניתנת הנחה נוספת...
תשובה: בחלק מהמתחמים...
```

**מה קורה:**
- שאלות 1-10 → יובאו כ-**FAQs מאושרים** (`approved=True`)
- מידע על גילאים → יובא כ-**Business Fact** (`pricing_by_age`)
- שעות פעילות → יובא כ-**Business Facts** (`reception_hours`, `check_in_hours`, `check_out_hours`)
- ארוחות וכשרות → יובא כ-**Business Facts** (`meals_available`, `kosher_status`)

### חלק 2: בנק שאלות ותשובות מורחב (אחרי "---")

**פורמט:**
```
ID: FAQ-000001
Category: 1) תהליך הזמנה ותיאום
Subcategory: זמינות ותאריכים
Question: איך אני בודק זמינות...
OwnerAnswer: [בעל הצימר להשלים]
SuggestedAnswer: בדרך כלל אפשר לבדוק זמינות...
Tags: [זמינות, תאריכים, תיאום]
Status: pending_approval
```

**מה קורה:**
- אם יש `OwnerAnswer` (ולא "[בעל הצימר להשלים]") → יובא כ-**FAQ מאושר**
- אחרת, אם יש `SuggestedAnswer` → יובא כ-**FAQ ממתין לאישור** (`approved=False`)

## 🚀 איך להשתמש

### 1. בדיקה ראשונית (Dry Run)

```bash
cd database
python import_faqs_from_file.py --dry-run
```

זה יציג מה ייובא **בלי לשמור ב-DB**.

### 2. ייבוא אמיתי

**Windows:**
```bash
database\run_import_faqs.bat
```

**או ישירות:**
```bash
cd database
python import_faqs_from_file.py
```

## 📊 מה הסקריפט עושה

### שלב 1: קריאה וניתוח הקובץ
- קורא את הקובץ `Question & Answers.txt`
- מזהה שאלות ותשובות (חלק 1)
- מזהה FAQs מובנים (חלק 2)
- מזהה Business Facts

### שלב 2: ייבוא FAQs
- **FAQs חדשים**: יוצרים כמאושרים או כממתינים (תלוי בתשובה)
- **FAQs קיימים**: מדלג או מעדכן (אם צריך)
- **בדיקת כפילות**: בודק לפי שאלה (case-insensitive)

### שלב 3: ייבוא Business Facts
- **Facts חדשים**: יוצרים
- **Facts קיימים**: מעדכנים

### שלב 4: סיכום
- מציג סטטיסטיקות (יובאו, עודכנו, שגיאות)
- מציג רשימת שגיאות (אם יש)

## 📈 תוצאות צפויות

**דוגמה לתוצאה:**
```
============================================================
📊 סיכום ייבוא
============================================================

FAQs:
  ✅ יובאו: 168
  ✓ אושרו: 10
  ⏳ ממתינים לאישור: 158
  ❌ שגיאות: 0

Business Facts:
  ✅ יובאו: 6
  🔄 עודכנו: 0
  ❌ שגיאות: 0

✅ הייבוא הושלם בהצלחה!
```

## ⚠️ חשוב לדעת

### FAQs מאושרים vs ממתינים

1. **FAQs מאושרים** (`approved=True`):
   - שאלות 1-10 מהחלק הראשון (תשובות מלאות)
   - FAQs מהחלק השני עם `OwnerAnswer` מלא

2. **FAQs ממתינים** (`approved=False`):
   - FAQs מהחלק השני עם `OwnerAnswer: [בעל הצימר להשלים]`
   - דורשים אישור דרך Admin Panel

### Business Facts

כל Business Fact יוצר/מעדכן עם:
- `key`: מפתח ייחודי (לדוגמה: `reception_hours`)
- `value`: הערך (לדוגמה: "א' עד ה' בין השעות: 08:00 – 17:00")
- `category`: קטגוריה (לדוגמה: `hours`, `policies`, `amenities`)
- `description`: תיאור (לדוגמה: "שעות פעילות משרד הקבלה")

## 🔍 בדיקה אחרי ייבוא

### בדיקת FAQs ב-DB:
```sql
-- כל ה-FAQs
SELECT COUNT(*) FROM faq;

-- FAQs מאושרים
SELECT COUNT(*) FROM faq WHERE approved = TRUE;

-- FAQs ממתינים
SELECT COUNT(*) FROM faq WHERE approved = FALSE;
```

### בדיקת Business Facts:
```sql
-- כל ה-Business Facts
SELECT * FROM business_facts WHERE is_active = TRUE;
```

### דרך Admin Panel:
1. פתח `tools/features_picker.html`
2. Admin Panel → FAQ & Facts
3. תראה את כל ה-FAQs (מאושרים וממתינים)
4. תראה את כל ה-Business Facts

## 🛠️ פתרון בעיות

### בעיה: "קובץ לא נמצא"
**פתרון:**
- ודא שהקובץ `Question & Answers.txt` נמצא בתיקיית הבסיס של הפרויקט
- בדוק את הנתיב בקוד

### בעיה: "שגיאות ייבוא"
**פתרון:**
- בדוק את הקונסול לראות אילו FAQs/Business Facts נכשלו
- ודא שהקובץ בפורמט הנכון
- בדוק ש-DB עובד (הרץ `database\run_check_stage1.bat`)

### בעיה: "FAQs כפולים"
**פתרון:**
- הסקריפט בודק כפילות לפי שאלה (case-insensitive)
- FAQs קיימים לא יווצרו שוב
- אם צריך לעדכן FAQ קיים, עשה זאת דרך Admin Panel

## 📝 קבצים קשורים

- `database/import_faqs_from_file.py` - הסקריפט הראשי
- `database/run_import_faqs.bat` - הרצה מהירה (Windows)
- `src/db.py` - פונקציות DB (suggest_faq, approve_faq, set_business_fact)
- `Question & Answers.txt` - קובץ המקור

## 🎯 סיכום

הסקריפט מאפשר ייבוא מהיר ומסודר של FAQs ו-Business Facts מהקובץ `Question & Answers.txt` ל-DB. זה חוסך זמן ומאפשר לסוכן להשתמש בתשובות מאושרות.

**זכור:**
- FAQs ממתינים דורשים אישור דרך Admin Panel
- Business Facts מתעדכנים אוטומטית אם כבר קיימים
- תמיד הרץ `--dry-run` קודם כדי לראות מה יקרה

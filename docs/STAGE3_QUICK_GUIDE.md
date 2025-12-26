# 🚀 מדריך מהיר: שלב 3 - מנוע תמחור

## 📋 מה זה שלב 3?

**הוספנו מנוע תמחור מתקדם** שמחשב מחירים עם:
- ✅ סופ"ש (תוספת 30% או מחיר נפרד)
- ✅ חגים (תוספת 50%)
- ✅ עונה גבוהה (תוספת 20% בקיץ)
- ✅ הנחות לפי משך שהות (4 לילות = 5%, שבוע = 10%, חודש = 15%)
- ✅ תוספות (ארוחת בוקר, צ'ק אין מוקדם, וכו')

## 🎯 מה השתנה?

### ✅ מה **לא** השתנה (נשאר כמו שהיה):
- `compute_price_for_stay` - הפונקציה המקורית עדיין עובדת
- `/availability` endpoint - עדיין מחזיר רשימת צימרים זמינים
- כל הקוד הקיים - לא נגענו בו!

### 🆕 מה **נוסף**:
- `src/pricing.py` - מנוע תמחור חדש
- `/quote` endpoint - מחזיר מחיר מפורט עם breakdown

## 🧪 מה הבדיקות בודקות?

הרץ:
```bash
database\run_check_stage3.bat
```

**6 בדיקות:**
1. ✅ מחיר בסיסי (2 לילות = 1,000₪)
2. ✅ תמחור סופ"ש (2 לילות סופ"ש = 1,300₪)
3. ✅ תמחור חגים (לילה אחד בחג = 750₪)
4. ✅ הנחות (7 לילות = הנחה 10%)
5. ✅ תוספות (2 לילות + תוספות = 1,200₪)
6. ⏳ עונה גבוהה (לילה אחד בקיץ = 600₪)

## 🔧 איך להשתמש?

### **דרך 1: Swagger UI (הכי קל!) ⭐**

1. הפעל את השרת:
   ```bash
   python -m uvicorn src.api_server:app --reload
   ```

2. פתח בדפדפן:
   ```
   http://127.0.0.1:8000/docs
   ```

3. מצא את `/quote` → לחץ "Try it out" → מלא פרטים → "Execute"

### **דרך 2: Python Script (מוכן!)**

```bash
python tools/test_quote.py
```

### **דרך 3: PowerShell**

```powershell
$body = @{
    cabin_id = "cabin-1"
    check_in = "2026-02-14 15:00"
    check_out = "2026-02-16 11:00"
    adults = 2
    kids = 0
    addons = @(
        @{name = "ארוחת בוקר"; price = 100}
    )
} | ConvertTo-Json -Depth 3

Invoke-RestMethod -Uri "http://127.0.0.1:8000/quote" -Method POST -Body $body -ContentType "application/json" | ConvertTo-Json -Depth 10
```

## 📊 מה רואים בתגובה?

```json
{
  "cabin_id": "cabin-1",
  "nights": 2,
  "regular_nights": 2,
  "weekend_nights": 0,
  "holiday_nights": 0,
  "high_season_nights": 0,
  "base_total": 1000.0,
  "weekend_surcharge": 0.0,
  "holiday_surcharge": 0.0,
  "high_season_surcharge": 0.0,
  "addons_total": 100.0,
  "subtotal": 1100.0,
  "discount": {
    "percent": 0.0,
    "amount": 0.0,
    "reason": null
  },
  "total": 1100.0,
  "breakdown": [
    {"date": "2026-02-14", "price": 500.0},
    {"date": "2026-02-15", "price": 500.0}
  ]
}
```

## 🔗 מתי להשתמש במה?

### `/availability` - כשצריך:
- רשימת צימרים זמינים
- מחיר בסיסי מהיר
- חיפוש עם פילטרים

### `/quote` - כשצריך:
- מחיר מפורט לצימר ספציפי
- breakdown מלא (סופ"ש, חגים, עונות, הנחות)
- להציג ללקוח מחיר מדויק

## ❓ שאלות נפוצות

**Q: האם זה משנה את הקוד הקיים?**  
A: לא! הכל נוסף, שום דבר לא נמחק.

**Q: איך אני יודע איזה endpoint להשתמש?**  
A: `/availability` לחיפוש, `/quote` למחיר מפורט.

**Q: מה אם הבדיקות נכשלות?**  
A: בדוק שהשרת רץ ושהתאריכים נכונים (לא חגים/סופ"ש אם לא צפוי).

## 📚 עוד מידע

להסבר מפורט, ראה: `docs/stage3_pricing_explanation.md`


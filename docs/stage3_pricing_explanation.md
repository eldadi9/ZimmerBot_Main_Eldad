# 📘 הסבר מפורט: שלב 3 - מנוע תמחור

## 🎯 מה נוסף בשלב 3?

### 1. קובץ חדש: `src/pricing.py`

**מה יש בו:**
- `PricingEngine` - מנוע תמחור מתקדם
- תמיכה בעונות, חגים, סופ"ש, הנחות, תוספות
- Breakdown מפורט לכל יום

**מה זה לא עושה:**
- ❌ לא משנה את `compute_price_for_stay` הקיים
- ❌ לא משנה את `/availability` endpoint
- ✅ רק מוסיף יכולות חדשות

### 2. API Endpoint חדש: `/quote`

**מה הוא עושה:**
- מחזיר הצעת מחיר מפורטת עם breakdown מלא
- כולל: מחיר בסיסי, תוספות סופ"ש, תוספות חגים, תוספות עונה, הנחות, תוספות

**איך זה שונה מ-`/availability`?**
- `/availability` - מחזיר רשימת צימרים זמינים עם מחיר בסיסי
- `/quote` - מחזיר מחיר מפורט עם breakdown מלא לצימר ספציפי

---

## 🧪 מה הבדיקות בודקות?

### בדיקה 1: מחיר בסיסי ✅
**מה בודקים:**
- 2 לילות רגילים (ראשון-שלישי)
- מחיר: 2 × 500₪ = 1,000₪

**למה זה חשוב:**
- מוודא שהמנוע מחשב נכון מחיר בסיסי

### בדיקה 2: תמחור סופ"ש ✅
**מה בודקים:**
- 2 לילות סופ"ש (שישי-ראשון)
- מחיר: 2 × 650₪ = 1,300₪

**למה זה חשוב:**
- מוודא שסופ"ש מתומחר נכון

### בדיקה 3: תמחור חגים ✅
**מה בודקים:**
- לילה אחד ביום העצמאות (חג)
- מחיר: 500₪ + 50% = 750₪

**למה זה חשוב:**
- מוודא שחגים מתומחרים נכון (+50%)

### בדיקה 4: הנחות לפי משך שהות ✅
**מה בודקים:**
- 7 לילות (5 רגילים + 2 סופ"ש)
- מחיר בסיס: 3,800₪
- הנחה 10%: 380₪
- סה"כ: 3,420₪

**למה זה חשוב:**
- מוודא שהנחות מחושבות נכון לפי משך שהות

### בדיקה 5: תוספות ✅
**מה בודקים:**
- 2 לילות + 2 תוספות (200₪)
- מחיר: 1,000₪ + 200₪ = 1,200₪

**למה זה חשוב:**
- מוודא שתוספות מתווספות נכון

### בדיקה 6: עונה גבוהה (קיץ) ⏳
**מה בודקים:**
- לילה אחד באוגוסט (עונה גבוהה)
- מחיר: 500₪ + 20% = 600₪

**למה זה חשוב:**
- מוודא שעונה גבוהה מתומחרת נכון (+20%)

---

## 🔧 איך להשתמש?

### דרך 1: Swagger UI (הכי קל!)

1. הפעל את השרת:
   ```bash
   python -m uvicorn src.api_server:app --reload
   ```

2. פתח בדפדפן:
   ```
   http://127.0.0.1:8000/docs
   ```

3. מצא את `/quote` endpoint
4. לחץ על "Try it out"
5. מלא את הפרטים:
   ```json
   {
     "cabin_id": "cabin-1",
     "check_in": "2026-02-14 15:00",
     "check_out": "2026-02-16 11:00",
     "adults": 2,
     "kids": 0,
     "addons": [
       {"name": "ארוחת בוקר", "price": 100}
     ]
   }
   ```
6. לחץ "Execute"
7. תראה את התוצאה עם breakdown מלא!

### דרך 2: PowerShell (Windows) - **מומלץ!**

```powershell
# הפעל את השרת קודם (בטרמינל אחר)
# python -m uvicorn src.api_server:app --reload

# ואז הרץ:
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

**או עם curl (אם מותקן):**
```powershell
curl -X POST http://127.0.0.1:8000/quote `
  -H "Content-Type: application/json" `
  -d '{\"cabin_id\": \"cabin-1\", \"check_in\": \"2026-02-14 15:00\", \"check_out\": \"2026-02-16 11:00\", \"adults\": 2, \"kids\": 0, \"addons\": [{\"name\": \"ארוחת בוקר\", \"price\": 100}]}'
```

**⚠️ בעיה עם curl ב-Windows:**
- Windows PowerShell לא תמיד תומך ב-curl טוב
- עדיף להשתמש ב-PowerShell `Invoke-RestMethod` או ב-Swagger UI

### דרך 3: Python Script - **הכי פשוט!**

**יש לך כבר קובץ מוכן:** `tools/test_quote.py`

פשוט הרץ:
```bash
python tools/test_quote.py
```

**או צור בעצמך:**
```python
import requests
import json

response = requests.post(
    "http://127.0.0.1:8000/quote",
    json={
        "cabin_id": "cabin-1",
        "check_in": "2026-02-14 15:00",
        "check_out": "2026-02-16 11:00",
        "adults": 2,
        "kids": 0,
        "addons": [
            {"name": "ארוחת בוקר", "price": 100}
        ]
    }
)

print(json.dumps(response.json(), ensure_ascii=False, indent=2))
```

---

## 📊 מה רואים בתגובה?

### דוגמה לתגובה:

```json
{
  "cabin_id": "cabin-1",
  "cabin_name": "הצימר של אמי",
  "check_in": "2026-02-14 15:00",
  "check_out": "2026-02-16 11:00",
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
  "addons": [
    {"name": "ארוחת בוקר", "price": 100.0}
  ],
  "subtotal": 1100.0,
  "discount": {
    "percent": 0.0,
    "amount": 0.0,
    "reason": null
  },
  "total": 1100.0,
  "breakdown": [
    {
      "date": "2026-02-14",
      "is_weekend": false,
      "is_holiday": false,
      "is_high_season": false,
      "price": 500.0
    },
    {
      "date": "2026-02-15",
      "is_weekend": false,
      "is_holiday": false,
      "is_high_season": false,
      "price": 500.0
    }
  ]
}
```

### מה כל שדה אומר?

| שדה | הסבר |
|-----|------|
| `nights` | מספר לילות כולל |
| `regular_nights` | לילות רגילים |
| `weekend_nights` | לילות סופ"ש |
| `holiday_nights` | לילות חג |
| `high_season_nights` | לילות עונה גבוהה |
| `base_total` | מחיר בסיסי (ללא תוספות) |
| `weekend_surcharge` | תוספת סופ"ש |
| `holiday_surcharge` | תוספת חגים |
| `high_season_surcharge` | תוספת עונה גבוהה |
| `addons_total` | סה"כ תוספות |
| `addons` | רשימת תוספות |
| `subtotal` | סכום ביניים (לפני הנחות) |
| `discount` | הנחה (אחוז, סכום, סיבה) |
| `total` | סה"כ סופי |
| `breakdown` | breakdown מפורט לכל יום |

---

## 🔗 איך זה משתלב עם הקיים?

### מה נשאר כמו שהיה:

✅ **`compute_price_for_stay`** - הפונקציה המקורית עדיין עובדת  
✅ **`/availability`** - endpoint קיים, משתמש בפונקציה המקורית  
✅ **כל הקוד הקיים** - לא נגענו בו!

### מה נוסף:

🆕 **`PricingEngine`** - מנוע תמחור חדש  
🆕 **`/quote`** - endpoint חדש להצעת מחיר מפורטת  
🆕 **תמיכה בעונות, חגים, הנחות, תוספות**

### מתי להשתמש במה?

**`/availability`** - כשצריך:
- רשימת צימרים זמינים
- מחיר בסיסי מהיר
- חיפוש עם פילטרים

**`/quote`** - כשצריך:
- מחיר מפורט לצימר ספציפי
- breakdown מלא
- לראות תוספות, הנחות, עונות
- להציג ללקוח מחיר מדויק

---

## 🎯 סיכום

**מה עשינו:**
1. ✅ יצרנו מנוע תמחור מתקדם (לא משנה את הקיים!)
2. ✅ הוספנו endpoint `/quote` חדש
3. ✅ יצרנו בדיקות אוטומטיות
4. ✅ הכל עובד ביחד - הקיים + החדש

**מה הלאה:**
- שלב 4: מנגנון Hold (נעילה זמנית)
- שלב 5: תשלומים

**איך לבדוק שהכל עובד:**
```bash
# הרץ את הבדיקות
database\run_check_stage3.bat

# הפעל את השרת
python -m uvicorn src.api_server:app --reload

# פתח Swagger
# http://127.0.0.1:8000/docs
```


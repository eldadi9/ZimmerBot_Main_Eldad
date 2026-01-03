# מדריך: Cabin ID ותמונות

## 1. Cabin ID - ZB01, ZB02, ZB03

### מה השתנה?
- **לפני:** הזמנות היו לפי UUID (למשל: `c5b7e7bd-2790-514a-97ef-6803e71579b2`)
- **עכשיו:** הזמנות לפי שם פשוט (למשל: `ZB01`, `ZB02`, `ZB03`)

### איך זה עובד?
1. **ב-DB:** נוסף שדה `cabin_id_string` שמכיל את ה-ID המקורי (ZB01, ZB02, ZB03)
2. **ב-API:** כל ה-endpoints מחזירים `cabin_id_string` במקום UUID
3. **חיפוש:** אפשר לחפש לפי:
   - `cabin_id_string` (ZB01, ZB02, ZB03) - **מומלץ!**
   - `cabin_id` (UUID)
   - `name` (שם הצימר)
   - `calendar_id` (Google Calendar ID)

### דוגמאות שימוש:

#### POST /quote
```json
{
  "cabin_id": "ZB01",
  "check_in": "2026-02-15 15:00",
  "check_out": "2026-02-17 11:00",
  "adults": 2,
  "kids": null
}
```

#### POST /book
```json
{
  "cabin_id": "ZB03",
  "check_in": "2026-02-20 15:00",
  "check_out": "2026-02-22 11:00",
  "customer": "ישראל ישראלי",
  "email": "test@example.com",
  "phone": "050-1234567",
  "adults": 2,
  "kids": null
}
```

---

## 2. תמונות - Google Drive vs מקומי

### מה השתנה?
- **תמיכה בתמונות מקומיות:** התמונות מהתיקייה `zimmers_pic` נטענות אוטומטית
- **עדיפות:** תמונות מקומיות > קישורי Google Drive

### מבנה התיקייה:
```
zimmers_pic/
├── ZB01/
│   └── hero-cabin.jpg
├── ZB02/
│   ├── cabin-galilee.jpg
│   ├── cabin-interior.jpg
│   └── cabin-jerusalem.jpg
└── ZB03/
    ├── cabin-negev.jpg
    └── hero-cabin.jpg
```

### איך זה עובד?
1. **ב-import:** הקוד בודק אם יש תיקייה `zimmers_pic/{cabin_id}/` (למשל `zimmers_pic/ZB01/`)
2. **אם יש תמונות מקומיות:** הן נטענות אוטומטית ל-`images_urls`
3. **אם אין תמונות מקומיות:** משתמשים בקישורי Google Drive מ-Sheets

### פורמט תמונות נתמך:
- `.jpg`
- `.jpeg`
- `.png`

### גישה לתמונות:
התמונות נגישות דרך:
```
http://127.0.0.1:8000/zimmers_pic/ZB01/hero-cabin.jpg
http://127.0.0.1:8000/zimmers_pic/ZB02/cabin-galilee.jpg
http://127.0.0.1:8000/zimmers_pic/ZB03/cabin-negev.jpg
```

### המלצות:
- ✅ **תמונות מקומיות** - מהירות יותר, לא תלויות ב-Google Drive
- ⚠️ **קישורי Google Drive** - עובדים אבל איטיים יותר, תלויים באינטרנט

---

## 3. איך לעדכן?

### שלב 1: הוסף עמודת cabin_id_string ל-DB
```bash
python -c "from src.db import get_db_connection; conn = get_db_connection().__enter__(); cursor = conn.cursor(); cursor.execute('ALTER TABLE cabins ADD COLUMN IF NOT EXISTS cabin_id_string VARCHAR(20)'); cursor.execute('CREATE INDEX IF NOT EXISTS idx_cabins_cabin_id_string ON cabins(cabin_id_string)'); conn.commit(); conn.__exit__(None, None, None)"
```

או הרץ:
```sql
ALTER TABLE cabins ADD COLUMN IF NOT EXISTS cabin_id_string VARCHAR(20);
CREATE INDEX IF NOT EXISTS idx_cabins_cabin_id_string ON cabins(cabin_id_string);
```

### שלב 2: ייבא מחדש את הצימרים
```bash
python database/import_cabins_to_db.py
```

זה יעדכן את כל הצימרים עם:
- `cabin_id_string` (ZB01, ZB02, ZB03)
- תמונות מקומיות (אם קיימות)

### שלב 3: בדוק שהכל עובד
```bash
# בדוק שהצימרים מופיעים עם cabin_id_string
curl http://127.0.0.1:8000/cabins

# בדוק הזמנה לפי ZB01
curl -X POST http://127.0.0.1:8000/quote \
  -H "Content-Type: application/json" \
  -d '{"cabin_id": "ZB01", "check_in": "2026-02-15 15:00", "check_out": "2026-02-17 11:00", "adults": 2}'
```

---

## 4. סיכום

### מה עובד עכשיו:
✅ הזמנות לפי ZB01, ZB02, ZB03 (לא UUID)  
✅ תמונות מקומיות מהתיקייה `zimmers_pic/`  
✅ תמיכה בקישורי Google Drive (fallback)  
✅ חיפוש גמיש (cabin_id_string, UUID, name, calendar_id)  

### מה צריך לעשות:
1. ✅ הוסף עמודת `cabin_id_string` ל-DB
2. ✅ ייבא מחדש את הצימרים
3. ✅ בדוק שהכל עובד

---

## 5. שאלות נפוצות

**Q: מה אם יש לי תמונות גם ב-Google Drive וגם מקומיות?**  
A: התמונות המקומיות יופיעו, קישורי Google Drive יוזנחו.

**Q: מה אם אין לי תמונות מקומיות?**  
A: הקוד ישתמש בקישורי Google Drive מ-Sheets.

**Q: איך אני מוסיף תמונות חדשות?**  
A: פשוט הוסף את התמונות לתיקייה `zimmers_pic/{cabin_id}/` והרץ `import_cabins_to_db.py` מחדש.

**Q: האם אני יכול להשתמש גם ב-UUID וגם ב-ZB01?**  
A: כן! הקוד תומך בשניהם, אבל מומלץ להשתמש ב-ZB01 כי זה יותר פשוט.

---

**🎯 טיפ:** תמיד השתמש ב-`cabin_id_string` (ZB01, ZB02, ZB03) להזמנות - זה יותר פשוט וידידותי למשתמש!


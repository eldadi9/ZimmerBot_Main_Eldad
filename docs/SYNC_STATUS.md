# 🔄 סטטוס סנכרון אוטומטי - מדריך בדיקה

**תאריך עדכון:** 11 ינואר 2026

## ✅ האם הסנכרון האוטומטי עובד?

### איך לבדוק:

1. **הפעל את השרת:**
   ```bash
   python -m uvicorn src.api_server:app --reload
   ```

2. **בדוק הודעת Startup:**
   ```
   ✅ Auto-sync scheduler started (interval: 5 minutes)
   🔄 Auto-sync will run every 5 minutes
   📅 Calendar → DB: Detects changes in calendar events and updates DB
   📊 Sheets → DB: Detects changes in Google Sheets and updates DB
   ```

3. **אם לא רואה הודעה זו:**
   - בדוק ש-APScheduler מותקן: `pip install apscheduler==3.10.4`
   - בדוק את הקונסול לשגיאות

4. **בדוק בטרמינל כל 5 דקות:**
   ```
   ============================================================
   🔄 Starting automatic sync (Calendar → DB, Sheets → DB)
   ============================================================
   ✅ Calendar → DB: X imported, Y updated, Z errors
   ✅ Sheets → DB: X imported, Y updated, Z errors
   ============================================================
   ```

5. **בדוק דרך UI:**
   - פתח `tools/features_picker.html`
   - Admin Panel → Sync
   - תראה סטטוס: "🟢 פעיל" או "🔴 מושבת"
   - תראה זמן סנכרון הבא

6. **בדוק דרך API:**
   ```bash
   curl http://127.0.0.1:8000/admin/sync/auto-status
   ```
   
   תוצאה צפויה:
   ```json
   {
     "enabled": true,
     "interval_minutes": 5,
     "next_run_time": "2026-01-11T02:05:00",
     "scheduler_running": true
   }
   ```

## 🔧 פתרון בעיות

### בעיה: "APScheduler not installed"
**פתרון:**
```bash
pip install apscheduler==3.10.4
```

### בעיה: Scheduler לא מתחיל
**פתרון:**
- בדוק את הקונסול לשגיאות
- ודא ש-`requirements.txt` כולל `apscheduler==3.10.4`
- הרץ מחדש את השרת

### בעיה: סנכרון לא רץ
**פתרון:**
- בדוק ש-`auto_sync_enabled = True`
- בדוק דרך UI: Admin Panel → Sync → כפתור "הפעל סנכרון אוטומטי"
- בדוק את הקונסול לראות אם יש שגיאות בפעולת הסנכרון

### בעיה: שגיאות בסנכרון
**פתרון:**
- בדוק את יומן הסנכרון ב-UI (Sync tab → יומן סנכרון אחרון)
- בדוק את הקונסול של השרת לשגיאות מפורטות
- ודא שיש הרשאות נכונות ל-Google Calendar/Sheets API

## 📊 מה הסנכרון האוטומטי עושה?

### Calendar → DB (כל 5 דקות):
1. קורא את כל האירועים מכל יומני הצימרים
2. משווה עם ההזמנות ב-DB
3. אם יש שינוי (שם, מייל, טלפון, תאריכים, צימר) → מעדכן את ה-DB
4. אם יש אירוע חדש ביומן → יוצר הזמנה חדשה ב-DB
5. אם אירוע הועבר ליומן אחר → מעדכן את `cabin_id` ב-DB

### Sheets → DB (כל 5 דקות):
1. קורא את כל הצימרים מ-Google Sheets
2. משווה עם הצימרים ב-DB
3. אם יש שינוי (שם, אזור, מחירים, תכונות, תמונות, כתובת) → מעדכן את ה-DB
4. אם יש צימר חדש ב-Sheets → יוצר צימר חדש ב-DB

## ⚙️ הגדרות

### שינוי תקופת סנכרון:
```bash
# ב-.env או משתנה סביבה
AUTO_SYNC_INTERVAL_MINUTES=10  # כל 10 דקות במקום 5
```

### הפעלה/כיבוי:
- דרך UI: Admin Panel → Sync → כפתור "עצור/הפעל סנכרון אוטומטי"
- דרך API: `POST /admin/sync/auto-toggle`

## 📝 לוגים

כל פעולת סנכרון נרשמת ב:
- **קונסול השרת**: הודעות מפורטות עם מספר הועתקו/עודכנו/שגיאות
- **יומן סנכרון ב-UI**: Admin Panel → Sync → יומן סנכרון אחרון
- **שגיאות מפורטות**: במידה ויש שגיאות, הן מוצגות ב-UI ובקונסול

## 🎯 סיכום

**סטטוס נוכחי:** ✅ **עובד** (אם APScheduler מותקן והשרת רץ)

**קבצים רלוונטיים:**
- `src/api_server.py` - Auto-sync scheduler (שורות 3840-4000)
- `src/sync_calendar.py` - Calendar ↔ DB sync
- `src/sync_sheets.py` - Sheets ↔ DB sync
- `tools/features_picker.html` - Sync UI
- `requirements.txt` - APScheduler dependency

**תיעוד נוסף:**
- `docs/AUTO_SYNC_EXPLANATION.md` - למה כפתורי הסנכרון שימושיים
- `docs/AUTO_SYNC_SUMMARY.md` - סיכום יישום סנכרון אוטומטי

"""
בדיקה מלאה של התהליך מההתחלה עד הסוף:
1. קריאה מ-Google Sheets
2. ייבוא ל-DB
3. קריאה מ-DB
4. בדיקת זמינות
5. יצירת Hold
6. המרת Hold להזמנה
"""
import sys
import os
from pathlib import Path
from datetime import datetime, timedelta

# Fix encoding for PowerShell
if sys.platform == "win32":
    os.environ["PYTHONIOENCODING"] = "utf-8"
    try:
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))

print("=" * 80)
print("בדיקה מלאה של התהליך - מההתחלה עד הסוף")
print("=" * 80)

# שלב 1: קריאה מ-Google Sheets
print("\n" + "=" * 80)
print("שלב 1: קריאה מ-Google Sheets")
print("=" * 80)
try:
    from src.main import get_credentials_api, read_cabins_from_sheet
    
    creds = get_credentials_api()
    cabins_from_sheets = read_cabins_from_sheet(creds)
    
    print(f"✓ נמצאו {len(cabins_from_sheets)} צימרים ב-Google Sheets:")
    for cabin in cabins_from_sheets:
        cabin_id = cabin.get("cabin_id") or cabin.get("id", "N/A")
        name = cabin.get("name", "N/A")
        calendar_id = cabin.get("calendar_id") or cabin.get("calendarId", "N/A")
        print(f"  - {name} (ID: {cabin_id}, Calendar: {calendar_id[:50]}...)")
        
        # בדיקה מיוחדת לצימר של מורן
        if "מורן" in name or "מורני" in name:
            print(f"    ⚠️  נמצא הצימר של מורן!")
            print(f"       cabin_id: {cabin_id}")
            print(f"       name: {name}")
            print(f"       calendar_id: {calendar_id}")
except Exception as e:
    print(f"✗ שגיאה בקריאה מ-Google Sheets: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# שלב 2: בדיקת מה יש ב-DB לפני
print("\n" + "=" * 80)
print("שלב 2: בדיקת מה יש ב-DB לפני ייבוא")
print("=" * 80)
try:
    from src.db import get_db_connection, read_cabins_from_db
    from psycopg2.extras import RealDictCursor
    
    with get_db_connection() as conn:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT id::text, name, calendar_id FROM cabins ORDER BY name")
        existing_cabins = cursor.fetchall()
        
        print(f"✓ נמצאו {len(existing_cabins)} צימרים ב-DB:")
        for cabin in existing_cabins:
            print(f"  - {cabin['name']} (ID: {cabin['id']}, Calendar: {cabin.get('calendar_id', 'N/A')[:50]}...)")
            
            # בדיקה מיוחדת לצימר של מורן
            if "מורן" in cabin['name'] or "מורני" in cabin['name']:
                print(f"    ⚠️  נמצא הצימר של מורן ב-DB!")
except Exception as e:
    print(f"✗ שגיאה בקריאה מ-DB: {e}")
    import traceback
    traceback.print_exc()

# שלב 3: ייבוא ל-DB
print("\n" + "=" * 80)
print("שלב 3: ייבוא ל-DB")
print("=" * 80)
try:
    import subprocess
    result = subprocess.run(
        [sys.executable, "database/import_cabins_to_db.py"],
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='replace'
    )
    print(result.stdout)
    if result.stderr:
        print("STDERR:", result.stderr)
except Exception as e:
    print(f"✗ שגיאה בייבוא: {e}")
    import traceback
    traceback.print_exc()

# שלב 4: בדיקת מה יש ב-DB אחרי
print("\n" + "=" * 80)
print("שלב 4: בדיקת מה יש ב-DB אחרי ייבוא")
print("=" * 80)
try:
    cabins_from_db = read_cabins_from_db()
    
    print(f"✓ נמצאו {len(cabins_from_db)} צימרים ב-DB:")
    for cabin in cabins_from_db:
        cabin_id = cabin.get("cabin_id", "N/A")
        name = cabin.get("name", "N/A")
        calendar_id = cabin.get("calendar_id", "N/A")
        print(f"  - {name} (ID: {cabin_id}, Calendar: {calendar_id[:50] if calendar_id != 'N/A' else 'N/A'}...)")
        
        # בדיקה מיוחדת לצימר של מורן
        if "מורן" in name or "מורני" in name:
            print(f"    ⚠️  נמצא הצימר של מורן ב-DB!")
except Exception as e:
    print(f"✗ שגיאה בקריאה מ-DB: {e}")
    import traceback
    traceback.print_exc()

# שלב 5: בדיקת זמינות
print("\n" + "=" * 80)
print("שלב 5: בדיקת זמינות")
print("=" * 80)
try:
    from src.main import build_calendar_service, find_available_cabins, to_utc, parse_datetime_local
    
    service = build_calendar_service(creds)
    check_in = datetime.now() + timedelta(days=7)
    check_out = check_in + timedelta(days=2)
    check_in_utc = to_utc(check_in)
    check_out_utc = to_utc(check_out)
    
    available = find_available_cabins(
        service=service,
        cabins=cabins_from_db,
        check_in_utc=check_in_utc,
        check_out_utc=check_out_utc,
        adults=2,
        kids=None,
        area=None,
        wanted_features=None,
        verbose=False
    )
    
    print(f"✓ נמצאו {len(available)} צימרים זמינים:")
    for cabin in available:
        name = cabin.get("name", "N/A")
        print(f"  - {name}")
        
        # בדיקה מיוחדת לצימר של מורן
        if "מורן" in name or "מורני" in name:
            print(f"    ⚠️  הצימר של מורן זמין!")
    
    # בדיקה למה הצימר של מורן לא מופיע
    print(f"\n🔍 בדיקת כל הצימרים (זמינים ולא זמינים):")
    for cabin in cabins_from_db:
        name = cabin.get("name", "N/A")
        cabin_id = cabin.get("cabin_id", "N/A")
        calendar_id = cabin.get("calendar_id", "N/A")
        
        is_available = any(c.get("cabin_id") == cabin_id for c in available)
        status = "✓ זמין" if is_available else "✗ לא זמין"
        
        print(f"  {status}: {name} (ID: {cabin_id[:20]}...)")
        
        if "מורן" in name or "מורני" in name:
            print(f"    ⚠️  פרטי הצימר של מורן:")
            print(f"       cabin_id: {cabin_id}")
            print(f"       calendar_id: {calendar_id[:80]}...")
            
            # בדיקה אם יש בעיה עם calendar_id
            if not calendar_id or calendar_id == "N/A":
                print(f"       ⚠️  בעיה: אין calendar_id!")
            
            # נסה לבדוק זמינות רק לצימר הזה
            try:
                cabin_available = find_available_cabins(
                    service=service,
                    cabins=[cabin],
                    check_in_utc=check_in_utc,
                    check_out_utc=check_out_utc,
                    adults=2,
                    kids=None,
                    area=None,
                    wanted_features=None,
                    verbose=True
                )
                if cabin_available:
                    print(f"       ✓ הצימר זמין בבדיקה נפרדת!")
                else:
                    print(f"       ✗ הצימר לא זמין בבדיקה נפרדת")
            except Exception as e:
                print(f"       ✗ שגיאה בבדיקת זמינות: {e}")
except Exception as e:
    print(f"✗ שגיאה בבדיקת זמינות: {e}")
    import traceback
    traceback.print_exc()

# שלב 6: בדיקת Hold (אם Redis זמין)
print("\n" + "=" * 80)
print("שלב 6: בדיקת Hold Mechanism")
print("=" * 80)
try:
    from src.hold import get_hold_manager
    
    hold_manager = get_hold_manager()
    if hold_manager._is_available():
        print("✓ Redis זמין - ניתן לבדוק Hold")
        
        # נסה ליצור Hold על אחד הצימרים
        if cabins_from_db:
            test_cabin = cabins_from_db[0]
            cabin_id = test_cabin.get("cabin_id")
            name = test_cabin.get("name", "Unknown")
            
            hold_id = hold_manager.create_hold(
                cabin_id=cabin_id,
                check_in=check_in.isoformat(),
                check_out=check_out.isoformat(),
                expires_in_seconds=300
            )
            
            if hold_id:
                print(f"✓ Hold נוצר בהצלחה: {hold_id} עבור {name}")
                
                # בדיקה אם Hold קיים
                hold_data = hold_manager.get_hold(hold_id)
                if hold_data:
                    print(f"✓ Hold מאומת: {hold_data}")
                else:
                    print("✗ Hold לא נמצא")
            else:
                print("✗ לא ניתן ליצור Hold")
    else:
        print("⚠ Redis לא זמין - Hold לא נבדק")
except Exception as e:
    print(f"✗ שגיאה בבדיקת Hold: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 80)
print("סיום בדיקה")
print("=" * 80)


"""
סקריפט לתיקון calendar_id ב-DB
מעדכן calendar_id מה-Sheets ל-DB
"""
import sys
import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))
load_dotenv(BASE_DIR / ".env")

from src.main import get_credentials_api, read_cabins_from_sheet
from src.db import get_db_connection

def fix_calendar_ids():
    """עדכן calendar_id מה-Sheets ל-DB"""
    print("=" * 60)
    print("תיקון calendar_id ב-DB")
    print("=" * 60)
    print()
    
    try:
        # קרא צימרים מה-Sheets
        creds = get_credentials_api()
        cabins_from_sheets = read_cabins_from_sheet(creds)
        print(f"✓ נטענו {len(cabins_from_sheets)} צימרים מ-Google Sheets")
        
        # קרא צימרים מה-DB
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id::text, name, calendar_id FROM cabins")
            cabins_from_db = cursor.fetchall()
            print(f"✓ נמצאו {len(cabins_from_db)} צימרים ב-DB")
            print()
            
            # התאם בין Sheets ל-DB לפי שם
            updated = 0
            for sheet_cabin in cabins_from_sheets:
                sheet_name = sheet_cabin.get("name")
                sheet_calendar_id = sheet_cabin.get("calendar_id") or sheet_cabin.get("calendarId")
                sheet_cabin_id = sheet_cabin.get("cabin_id")
                
                if not sheet_calendar_id:
                    print(f"⚠ צימר '{sheet_name}' (ID: {sheet_cabin_id}) - אין calendar_id ב-Sheets")
                    continue
                
                # מצא את הצימר ב-DB לפי שם
                for db_cabin in cabins_from_db:
                    db_id, db_name, db_calendar_id = db_cabin
                    if db_name == sheet_name:
                        if db_calendar_id != sheet_calendar_id:
                            # עדכן את calendar_id
                            cursor.execute("""
                                UPDATE cabins 
                                SET calendar_id = %s 
                                WHERE id = %s::uuid
                            """, (sheet_calendar_id, db_id))
                            print(f"✓ עודכן: {sheet_name}")
                            print(f"  DB calendar_id ישן: {db_calendar_id}")
                            print(f"  DB calendar_id חדש: {sheet_calendar_id}")
                            updated += 1
                        else:
                            print(f"✓ תקין: {sheet_name} (calendar_id כבר נכון)")
                        break
                else:
                    print(f"⚠ צימר '{sheet_name}' לא נמצא ב-DB")
            
            conn.commit()
            print()
            print(f"✓ סה\"כ עודכנו {updated} צימרים")
            
    except Exception as e:
        print(f"✗ שגיאה: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(fix_calendar_ids())


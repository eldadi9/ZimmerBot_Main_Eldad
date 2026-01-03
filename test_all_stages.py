#!/usr/bin/env python3
"""
בדיקה מקיפה של כל השלבים 1-4
"""
import sys
import requests
from datetime import datetime, timedelta

API_BASE = "http://127.0.0.1:8000"

def print_header(title):
    print("\n" + "="*60)
    print(f"  {title}")
    print("="*60)

def print_result(success, message):
    symbol = "✅" if success else "❌"
    print(f"{symbol} {message}")

def test_stage1():
    """בדיקת שלב 1: Database Schema"""
    print_header("שלב 1: Database Schema")
    
    results = []
    
    # 1. בדיקת חיבור ל-DB
    try:
        from src.db import get_db_connection
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            results.append((True, "חיבור ל-DB עובד"))
    except Exception as e:
        results.append((False, f"חיבור ל-DB נכשל: {e}"))
    
    # 2. בדיקת טבלאות
    try:
        from src.db import get_db_connection
        from psycopg2.extras import RealDictCursor
        with get_db_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_type = 'BASE TABLE'
                ORDER BY table_name
            """)
            tables = [row['table_name'] for row in cursor.fetchall()]
            required_tables = ['cabins', 'customers', 'bookings', 'transactions', 'audit_log']
            missing = [t for t in required_tables if t not in tables]
            if not missing:
                results.append((True, f"כל הטבלאות קיימות: {', '.join(required_tables)}"))
            else:
                results.append((False, f"טבלאות חסרות: {', '.join(missing)}"))
    except Exception as e:
        results.append((False, f"בדיקת טבלאות נכשלה: {e}"))
    
    # 3. בדיקת קריאת cabins מ-DB
    try:
        from src.db import read_cabins_from_db
        cabins = read_cabins_from_db()
        if cabins:
            results.append((True, f"קריאת cabins מ-DB עובדת ({len(cabins)} צימרים)"))
            # בדוק שיש cabin_id_string
            with_cabin_id_string = [c for c in cabins if c.get('cabin_id_string')]
            if with_cabin_id_string:
                results.append((True, f"צימרים עם cabin_id_string: {len(with_cabin_id_string)}"))
            else:
                results.append((False, "אין צימרים עם cabin_id_string"))
        else:
            results.append((False, "אין צימרים ב-DB"))
    except Exception as e:
        results.append((False, f"קריאת cabins נכשלה: {e}"))
    
    # 4. בדיקת API /cabins
    try:
        r = requests.get(f"{API_BASE}/cabins", timeout=5)
        if r.status_code == 200:
            data = r.json()
            if data and len(data) > 0:
                # בדוק אם cabin_id הוא ZB01, ZB02 וכו' (לא UUID)
                first_cabin = data[0]
                cabin_id = first_cabin.get('cabin_id', '')
                if len(cabin_id) < 10 and not '-' in cabin_id:
                    results.append((True, f"API /cabins מחזיר cabin_id_string (ZB01, ZB02): {cabin_id}"))
                else:
                    results.append((False, f"API /cabins מחזיר UUID במקום cabin_id_string: {cabin_id[:20]}..."))
            else:
                results.append((False, "API /cabins מחזיר רשימה ריקה"))
        else:
            results.append((False, f"API /cabins מחזיר קוד שגיאה: {r.status_code}"))
    except Exception as e:
        results.append((False, f"בדיקת API /cabins נכשלה: {e}"))
    
    for success, message in results:
        print_result(success, message)
    
    return all(r[0] for r in results)

def test_stage2():
    """בדיקת שלב 2: Calendar Integration"""
    print_header("שלב 2: Calendar Integration")
    
    results = []
    
    # 1. בדיקת חיבור ל-Google Calendar
    try:
        from src.api_server import get_service
        service, cabins = get_service()
        if service:
            results.append((True, "חיבור ל-Google Calendar עובד"))
        else:
            results.append((False, "חיבור ל-Google Calendar נכשל"))
    except Exception as e:
        results.append((False, f"חיבור ל-Google Calendar נכשל: {e}"))
    
    # 2. בדיקת קריאת cabins
    try:
        from src.api_server import get_service
        service, cabins = get_service()
        if cabins and len(cabins) > 0:
            results.append((True, f"קריאת cabins עובדת ({len(cabins)} צימרים)"))
            # בדוק שיש calendar_id
            with_calendar = [c for c in cabins if c.get('calendar_id') or c.get('calendarId')]
            if with_calendar:
                results.append((True, f"צימרים עם calendar_id: {len(with_calendar)}"))
            else:
                results.append((False, "אין צימרים עם calendar_id"))
        else:
            results.append((False, "אין צימרים"))
    except Exception as e:
        results.append((False, f"קריאת cabins נכשלה: {e}"))
    
    # 3. בדיקת API /availability
    try:
        check_in = (datetime.now() + timedelta(days=10)).strftime("%Y-%m-%d 15:00")
        check_out = (datetime.now() + timedelta(days=12)).strftime("%Y-%m-%d 11:00")
        
        r = requests.post(
            f"{API_BASE}/availability",
            json={
                "check_in": check_in,
                "check_out": check_out,
                "adults": 2,
                "kids": 0
            },
            timeout=10
        )
        if r.status_code == 200:
            data = r.json()
            if isinstance(data, list):
                results.append((True, f"API /availability עובד ({len(data)} צימרים זמינים)"))
            else:
                results.append((False, f"API /availability מחזיר פורמט לא תקין: {type(data)}"))
        else:
            results.append((False, f"API /availability מחזיר קוד שגיאה: {r.status_code}"))
    except Exception as e:
        results.append((False, f"בדיקת API /availability נכשלה: {e}"))
    
    for success, message in results:
        print_result(success, message)
    
    return all(r[0] for r in results)

def test_stage3():
    """בדיקת שלב 3: Pricing Engine"""
    print_header("שלב 3: Pricing Engine")
    
    results = []
    
    # 1. בדיקת API /quote
    try:
        check_in = (datetime.now() + timedelta(days=10)).strftime("%Y-%m-%d 15:00")
        check_out = (datetime.now() + timedelta(days=12)).strftime("%Y-%m-%d 11:00")
        
        # קודם צריך לקבל cabin_id
        cabins_r = requests.get(f"{API_BASE}/cabins", timeout=5)
        if cabins_r.status_code == 200:
            cabins = cabins_r.json()
            if cabins:
                cabin_id = cabins[0].get('cabin_id')
                
                r = requests.post(
                    f"{API_BASE}/quote",
                    json={
                        "cabin_id": cabin_id,
                        "check_in": check_in,
                        "check_out": check_out,
                        "adults": 2,
                        "kids": 0
                    },
                    timeout=10
                )
                if r.status_code == 200:
                    quote = r.json()
                    if 'total' in quote or 'total_price' in quote:
                        total = quote.get('total') or quote.get('total_price', 0)
                        results.append((True, f"API /quote עובד (מחיר: ₪{total})"))
                        
                        # בדוק שיש breakdown
                        if 'base_price' in quote or 'nights' in quote:
                            results.append((True, "API /quote מחזיר breakdown מלא"))
                        else:
                            results.append((False, "API /quote לא מחזיר breakdown"))
                    else:
                        results.append((False, "API /quote לא מחזיר total"))
                else:
                    error_text = r.text[:100] if r.text else ""
                    results.append((False, f"API /quote מחזיר קוד שגיאה {r.status_code}: {error_text}"))
            else:
                results.append((False, "אין צימרים לבדיקה"))
        else:
            results.append((False, f"לא הצלחתי לקבל cabins: {cabins_r.status_code}"))
    except Exception as e:
        results.append((False, f"בדיקת API /quote נכשלה: {e}"))
    
    # 2. בדיקת Pricing Engine ישירות
    try:
        from src.pricing import PricingEngine
        engine = PricingEngine()
        results.append((True, "PricingEngine נוצר בהצלחה"))
    except Exception as e:
        results.append((False, f"יצירת PricingEngine נכשלה: {e}"))
    
    for success, message in results:
        print_result(success, message)
    
    return all(r[0] for r in results)

def test_stage4():
    """בדיקת שלב 4: Hold Mechanism"""
    print_header("שלב 4: Hold Mechanism")
    
    results = []
    
    # 1. בדיקת HoldManager
    try:
        from src.hold import get_hold_manager
        hold_manager = get_hold_manager()
        results.append((True, "HoldManager נוצר בהצלחה"))
        
        # בדוק אם Redis זמין
        if hold_manager._is_available():
            results.append((True, "Redis זמין - Hold מוגן"))
        else:
            results.append((True, "Redis לא זמין - Hold ב-memory (עובד גם ככה)"))
    except Exception as e:
        results.append((False, f"יצירת HoldManager נכשלה: {e}"))
    
    # 2. בדיקת API /admin/holds
    try:
        r = requests.get(f"{API_BASE}/admin/holds", timeout=5)
        if r.status_code == 200:
            data = r.json()
            if 'holds' in data and 'count' in data:
                results.append((True, f"API /admin/holds עובד ({data['count']} Holds פעילים)"))
            else:
                results.append((False, "API /admin/holds מחזיר פורמט לא תקין"))
        else:
            results.append((False, f"API /admin/holds מחזיר קוד שגיאה: {r.status_code}"))
    except Exception as e:
        results.append((False, f"בדיקת API /admin/holds נכשלה: {e}"))
    
    # 3. בדיקת Audit Log
    try:
        r = requests.get(f"{API_BASE}/admin/audit", timeout=5)
        if r.status_code == 200:
            data = r.json()
            if isinstance(data, list):
                results.append((True, f"API /admin/audit עובד ({len(data)} רשומות)"))
            else:
                results.append((False, f"API /admin/audit מחזיר פורמט לא תקין: {type(data)}"))
        else:
            results.append((False, f"API /admin/audit מחזיר קוד שגיאה: {r.status_code}"))
    except Exception as e:
        results.append((False, f"בדיקת API /admin/audit נכשלה: {e}"))
    
    for success, message in results:
        print_result(success, message)
    
    return all(r[0] for r in results)

if __name__ == "__main__":
    print("\n" + "="*60)
    print("  בדיקה מקיפה של כל השלבים")
    print("="*60)
    
    # בדוק שהשרת רץ
    try:
        r = requests.get(f"{API_BASE}/health", timeout=5)
        if r.status_code != 200:
            print("❌ השרת לא רץ או לא מגיב")
            sys.exit(1)
    except:
        print("❌ השרת לא רץ. הפעל: python -m uvicorn src.api_server:app --reload")
        sys.exit(1)
    
    stage1_ok = test_stage1()
    stage2_ok = test_stage2()
    stage3_ok = test_stage3()
    stage4_ok = test_stage4()
    
    print_header("סיכום")
    print_result(stage1_ok, "שלב 1: Database Schema")
    print_result(stage2_ok, "שלב 2: Calendar Integration")
    print_result(stage3_ok, "שלב 3: Pricing Engine")
    print_result(stage4_ok, "שלב 4: Hold Mechanism")
    
    if all([stage1_ok, stage2_ok, stage3_ok, stage4_ok]):
        print("\n🎉 כל השלבים עובדים!")
    else:
        print("\n⚠️ יש בעיות בכמה שלבים - ראה למעלה")


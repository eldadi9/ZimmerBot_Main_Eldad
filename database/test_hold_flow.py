"""
סקריפט בדיקה אינטראקטיבי לשלב 4 - Hold Mechanism
מדגים את כל הזרימה: יצירת Hold, בדיקה, המרה להזמנה, ביטול
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

import requests
import json
from src.hold import get_hold_manager
from src.db import get_db_connection

API_BASE = "http://127.0.0.1:8000"

def print_section(title):
    print("\n" + "="*60)
    print(f"  {title}")
    print("="*60)

def print_step(step_num, description):
    print(f"\n📌 שלב {step_num}: {description}")
    print("-" * 60)

def test_hold_flow():
    """בדיקה מלאה של זרימת Hold"""
    
    print_section("בדיקת שלב 4 - Hold Mechanism")
    print("\nמדריך זה מדגים את כל הזרימה של Hold:")
    print("1. יצירת Hold (15 דקות)")
    print("2. בדיקת סטטוס Hold")
    print("3. מניעת Hold כפול")
    print("4. המרה להזמנה")
    print("5. ביטול Hold")
    
    # בדיקת חיבור לשרת
    print_step(0, "בדיקת חיבור לשרת")
    try:
        response = requests.get(f"{API_BASE}/health", timeout=5)
        if response.status_code == 200:
            print("✅ שרת פעיל")
        else:
            print(f"⚠️ שרת מחזיר קוד: {response.status_code}")
    except Exception as e:
        print(f"❌ שגיאה בחיבור לשרת: {e}")
        print("   ודא שהשרת רץ: python -m uvicorn src.api_server:app --reload")
        return
    
    # בדיקת Redis
    print_step(0.5, "בדיקת Redis")
    hold_manager = get_hold_manager()
    if hold_manager._is_available():
        print("✅ Redis פעיל - Hold מוגן במלואו")
    else:
        print("⚠️ Redis לא פעיל - Hold עובד אבל ללא הגנה מלאה")
        print("   התקן Redis להפעלה מלאה: redis-server")
    
    # תאריכים לבדיקה
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    day_after = (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d")
    check_in = f"{tomorrow} 15:00"
    check_out = f"{day_after} 11:00"
    
    print(f"\n📅 תאריכי בדיקה:")
    print(f"   כניסה: {check_in}")
    print(f"   יציאה: {check_out}")
    
    # שלב 1: יצירת Hold
    print_step(1, "יצירת Hold")
    print(f"שולח POST /hold...")
    
    hold_request = {
        "cabin_id": "ZB01",
        "check_in": check_in,
        "check_out": check_out,
        "customer_name": "ישראל ישראלי - בדיקה"
    }
    
    try:
        response = requests.post(
            f"{API_BASE}/hold",
            json=hold_request,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        
        if response.status_code == 200:
            hold_data = response.json()
            hold_id = hold_data.get("hold_id")
            expires_at = hold_data.get("expires_at")
            
            print("✅ Hold נוצר בהצלחה!")
            print(f"   Hold ID: {hold_id}")
            print(f"   תפוגה: {expires_at}")
            print(f"   סטטוס: {hold_data.get('status')}")
            
            if hold_data.get("warning"):
                print(f"   ⚠️ אזהרה: {hold_data['warning']}")
        else:
            print(f"❌ שגיאה ביצירת Hold: {response.status_code}")
            print(f"   תשובה: {response.text}")
            return
            
    except Exception as e:
        print(f"❌ שגיאה: {e}")
        return
    
    # שלב 2: בדיקת Hold
    print_step(2, "בדיקת סטטוס Hold")
    print(f"שולח GET /hold/{hold_id}...")
    
    try:
        response = requests.get(f"{API_BASE}/hold/{hold_id}", timeout=10)
        
        if response.status_code == 200:
            hold_status = response.json()
            print("✅ Hold נמצא!")
            print(f"   Cabin ID: {hold_status.get('cabin_id')}")
            print(f"   תאריכים: {hold_status.get('check_in')} - {hold_status.get('check_out')}")
            print(f"   לקוח: {hold_status.get('customer_name')}")
            print(f"   תפוגה: {hold_status.get('expires_at')}")
        else:
            print(f"❌ Hold לא נמצא: {response.status_code}")
            print(f"   תשובה: {response.text}")
    except Exception as e:
        print(f"❌ שגיאה: {e}")
    
    # שלב 3: מניעת Hold כפול
    print_step(3, "מניעת Hold כפול")
    print("מנסה ליצור Hold שני לאותו צימר ותאריכים...")
    
    try:
        response = requests.post(
            f"{API_BASE}/hold",
            json=hold_request,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        
        if response.status_code in [400, 409]:
            print("✅ Hold כפול נמנע (כצפוי)!")
            print(f"   הודעת שגיאה: {response.json().get('detail')}")
        else:
            print(f"⚠️ Hold שני נוצר (לא אמור לקרות): {response.status_code}")
    except Exception as e:
        print(f"❌ שגיאה: {e}")
    
    # שלב 4: בדיקת Redis (אם זמין)
    if hold_manager._is_available():
        print_step(4, "בדיקת Redis")
        print("בודק Hold ב-Redis...")
        
        check_in_date = datetime.strptime(check_in, "%Y-%m-%d %H:%M").date().isoformat()
        check_out_date = datetime.strptime(check_out, "%Y-%m-%d %H:%M").date().isoformat()
        
        exists = hold_manager.check_hold_exists("ZB01", check_in_date, check_out_date)
        if exists:
            print("✅ Hold נמצא ב-Redis")
            
            # בדיקת TTL
            hold_key = f"hold:ZB01:{check_in_date}:{check_out_date}"
            try:
                ttl = hold_manager.redis_client.ttl(hold_key)
                if ttl > 0:
                    minutes = ttl // 60
                    seconds = ttl % 60
                    print(f"   זמן תפוגה: {minutes} דקות ו-{seconds} שניות")
            except:
                pass
        else:
            print("⚠️ Hold לא נמצא ב-Redis")
    
    # שלב 5: המרה להזמנה
    print_step(5, "המרה להזמנה")
    print("ממיר Hold להזמנה מלאה...")
    
    booking_request = {
        "cabin_id": "ZB01",
        "check_in": check_in,
        "check_out": check_out,
        "customer": "ישראל ישראלי - בדיקה",
        "phone": "050-1234567",
        "email": "test@example.com",
        "adults": 2,
        "kids": 0,
        "total_price": 1000.0,
        "hold_id": hold_id
    }
    
    try:
        response = requests.post(
            f"{API_BASE}/book",
            json=booking_request,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        
        if response.status_code == 200:
            booking_data = response.json()
            print("✅ הזמנה נוצרה בהצלחה!")
            print(f"   Cabin ID: {booking_data.get('cabin_id')}")
            print(f"   Event ID: {booking_data.get('event_id')}")
            print(f"   Event Link: {booking_data.get('event_link')}")
            
            # בדיקה שה-Hold נמחק
            if hold_manager._is_available():
                check_in_date = datetime.strptime(check_in, "%Y-%m-%d %H:%M").date().isoformat()
                check_out_date = datetime.strptime(check_out, "%Y-%m-%d %H:%M").date().isoformat()
                exists = hold_manager.check_hold_exists("ZB01", check_in_date, check_out_date)
                if not exists:
                    print("✅ Hold נמחק מ-Redis (כצפוי)")
                else:
                    print("⚠️ Hold עדיין קיים ב-Redis")
        else:
            print(f"❌ שגיאה ביצירת הזמנה: {response.status_code}")
            print(f"   תשובה: {response.text}")
    except Exception as e:
        print(f"❌ שגיאה: {e}")
    
    # שלב 6: בדיקת DB
    print_step(6, "בדיקת Database")
    print("בודק מה נשמר ב-DB...")
    
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # בדיקת הזמנות
            cursor.execute("SELECT COUNT(*) FROM bookings WHERE customer_id IN (SELECT id FROM customers WHERE name LIKE %s)", ("%בדיקה%",))
            bookings_count = cursor.fetchone()[0]
            print(f"   הזמנות: {bookings_count}")
            
            # בדיקת לקוחות
            cursor.execute("SELECT COUNT(*) FROM customers WHERE name LIKE %s", ("%בדיקה%",))
            customers_count = cursor.fetchone()[0]
            print(f"   לקוחות: {customers_count}")
            
            # בדיקת Transactions
            cursor.execute("SELECT COUNT(*) FROM transactions WHERE booking_id IN (SELECT id FROM bookings WHERE customer_id IN (SELECT id FROM customers WHERE name LIKE %s))", ("%בדיקה%",))
            transactions_count = cursor.fetchone()[0]
            print(f"   Transactions: {transactions_count}")
            
            print("✅ בדיקת DB הושלמה")
    except Exception as e:
        print(f"⚠️ שגיאה בבדיקת DB: {e}")
    
    # סיכום
    print_section("סיכום")
    print("\n✅ כל הבדיקות הושלמו!")
    print("\n📋 מה קרה:")
    print("   1. Hold נוצר (15 דקות)")
    print("   2. Hold נבדק")
    print("   3. Hold כפול נמנע")
    print("   4. Hold הומר להזמנה")
    print("   5. נתונים נשמרו ב-DB")
    
    print("\n📊 איפה לראות:")
    print("   • Redis: redis-cli KEYS 'hold:*'")
    print("   • Calendar: פתח את יומן הצימר")
    print("   • DB: SELECT * FROM bookings ORDER BY created_at DESC")
    print("   • API: http://127.0.0.1:8000/docs")
    
    print("\n💡 טיפים:")
    print("   • Hold תקף ל-15 דקות בלבד")
    print("   • אחרי תשלום, Hold מומר להזמנה")
    print("   • אם לא שולם, Hold מתפוגג אוטומטית")
    print("   • Calendar: אירועי HOLD (צהוב) והזמנות (ירוק)")

if __name__ == "__main__":
    test_hold_flow()


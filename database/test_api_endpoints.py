"""
סקריפט בדיקה לכל ה-API endpoints
בודק שלב שלב שכל endpoint מחזיר נתונים תקינים
"""
import sys
import json
import requests
from datetime import datetime, timedelta
from typing import Dict, Any

API_BASE = "http://127.0.0.1:8000"

class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    END = "\033[0m"
    BOLD = "\033[1m"

def print_header(text: str):
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.END}\n")

def print_success(text: str):
    print(f"{Colors.GREEN}✓ {text}{Colors.END}")

def print_error(text: str):
    print(f"{Colors.RED}✗ {text}{Colors.END}")

def print_warning(text: str):
    print(f"{Colors.YELLOW}⚠ {text}{Colors.END}")

def print_info(text: str):
    print(f"{Colors.BLUE}ℹ {text}{Colors.END}")

def test_server_running():
    """בדיקה 1: האם השרת רץ?"""
    print_header("בדיקה 1: האם השרת רץ?")
    
    try:
        response = requests.get(f"{API_BASE}/health", timeout=5)
        if response.status_code == 200:
            print_success(f"השרת רץ! תגובה: {response.json()}")
            return True
        else:
            print_error(f"השרת הגיב עם קוד שגיאה: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print_error("לא ניתן להתחבר לשרת. ודא שהשרת רץ על פורט 8000")
        print_warning("הרץ: run_api.bat או: python -m uvicorn src.api_server:app --reload --port 8000")
        return False
    except Exception as e:
        print_error(f"שגיאה: {e}")
        return False

def test_get_health():
    """בדיקה 2: GET /health"""
    print_header("בדיקה 2: GET /health - בדיקת בריאות")
    
    try:
        response = requests.get(f"{API_BASE}/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print_success(f"תגובה: {json.dumps(data, ensure_ascii=False, indent=2)}")
            return True, data
        else:
            print_error(f"קוד שגיאה: {response.status_code}")
            return False, None
    except Exception as e:
        print_error(f"שגיאה: {e}")
        return False, None

def test_get_cabins():
    """בדיקה 3: GET /cabins"""
    print_header("בדיקה 3: GET /cabins - רשימת צימרים")
    
    try:
        response = requests.get(f"{API_BASE}/cabins", timeout=10)
        if response.status_code == 200:
            data = response.json()
            cabins = data if isinstance(data, list) else data.get('cabins', [])
            print_success(f"נמצאו {len(cabins)} צימרים")
            for i, cabin in enumerate(cabins[:3], 1):  # הצג רק 3 ראשונים
                cabin_id = cabin.get('cabin_id') or cabin.get('id', 'N/A')
                name = cabin.get('name', 'ללא שם')
                print_info(f"  {i}. {name} (ID: {cabin_id})")
            if len(cabins) > 3:
                print_info(f"  ... ועוד {len(cabins) - 3} צימרים")
            return True, cabins
        else:
            print_error(f"קוד שגיאה: {response.status_code}")
            print_error(f"תגובה: {response.text[:200]}")
            return False, None
    except Exception as e:
        print_error(f"שגיאה: {e}")
        return False, None

def test_post_availability():
    """בדיקה 4: POST /availability"""
    print_header("בדיקה 4: POST /availability - בדיקת זמינות")
    
    # תאריכים לבדיקה - שבועיים מהיום
    check_in = (datetime.now() + timedelta(days=14)).strftime("%Y-%m-%d 15:00")
    check_out = (datetime.now() + timedelta(days=16)).strftime("%Y-%m-%d 11:00")
    
    payload = {
        "check_in": check_in,
        "check_out": check_out,
        "adults": 2,
        "kids": None,
        "area": None,
        "features": None
    }
    
    print_info(f"בודק זמינות: {check_in} → {check_out}")
    print_info(f"Payload: {json.dumps(payload, ensure_ascii=False, indent=2)}")
    
    try:
        response = requests.post(f"{API_BASE}/availability", json=payload, timeout=10)
        if response.status_code == 200:
            data = response.json()
            available = data.get('available', [])
            print_success(f"נמצאו {len(available)} צימרים זמינים")
            for i, cabin in enumerate(available[:3], 1):
                cabin_id = cabin.get('cabin_id') or cabin.get('id', 'N/A')
                name = cabin.get('name', 'ללא שם')
                price = cabin.get('total_price', 'N/A')
                print_info(f"  {i}. {name} (ID: {cabin_id}, מחיר: ₪{price})")
            return True, data
        else:
            print_error(f"קוד שגיאה: {response.status_code}")
            print_error(f"תגובה: {response.text[:300]}")
            return False, None
    except Exception as e:
        print_error(f"שגיאה: {e}")
        import traceback
        traceback.print_exc()
        return False, None

def test_post_quote(cabin_id: str = None):
    """בדיקה 5: POST /quote"""
    print_header("בדיקה 5: POST /quote - הצעת מחיר מפורטת")
    
    if not cabin_id:
        print_warning("לא סופק cabin_id, מנסה לקבל מהבדיקה הקודמת...")
        # נסה לקבל cabin_id מהבדיקה הקודמת
        success, data = test_post_availability()
        if success and data:
            available = data.get('available', [])
            if available:
                cabin_id = available[0].get('cabin_id') or available[0].get('id')
                print_info(f"משתמש ב-cabin_id: {cabin_id}")
            else:
                print_error("אין צימרים זמינים לבדיקה")
                return False, None
        else:
            print_error("לא ניתן לקבל cabin_id")
            return False, None
    
    check_in = (datetime.now() + timedelta(days=14)).strftime("%Y-%m-%d 15:00")
    check_out = (datetime.now() + timedelta(days=16)).strftime("%Y-%m-%d 11:00")
    
    payload = {
        "cabin_id": cabin_id,
        "check_in": check_in,
        "check_out": check_out,
        "adults": 2,
        "kids": None,
        "addons": [
            {"name": "מסאג' לחדר", "price": 200},
            {"name": "ארוחת שף", "price": 300}
        ]
    }
    
    print_info(f"מבקש הצעת מחיר עבור: {cabin_id}")
    print_info(f"תאריכים: {check_in} → {check_out}")
    print_info(f"תוספות: {len(payload['addons'])}")
    
    try:
        response = requests.post(f"{API_BASE}/quote", json=payload, timeout=10)
        if response.status_code == 200:
            data = response.json()
            print_success("הצעת מחיר התקבלה!")
            print_info(f"מחיר סופי: ₪{data.get('total', data.get('total_price', 'N/A'))}")
            print_info(f"מספר לילות: {data.get('nights', 'N/A')}")
            print_info(f"סה\"כ תוספות: ₪{data.get('addons_total', 0)}")
            print(f"\n{Colors.BLUE}פירוט מלא:{Colors.END}")
            print(json.dumps(data, ensure_ascii=False, indent=2))
            return True, data
        else:
            print_error(f"קוד שגיאה: {response.status_code}")
            print_error(f"תגובה: {response.text[:300]}")
            return False, None
    except Exception as e:
        print_error(f"שגיאה: {e}")
        import traceback
        traceback.print_exc()
        return False, None

def test_post_book(cabin_id: str = None):
    """בדיקה 6: POST /book"""
    print_header("בדיקה 6: POST /book - יצירת הזמנה")
    
    if not cabin_id:
        print_warning("לא סופק cabin_id, מנסה לקבל מהבדיקה הקודמת...")
        success, data = test_post_availability()
        if success and data:
            available = data.get('available', [])
            if available:
                cabin_id = available[0].get('cabin_id') or available[0].get('id')
            else:
                print_error("אין צימרים זמינים לבדיקה")
                return False, None
    
    check_in = (datetime.now() + timedelta(days=14)).strftime("%Y-%m-%d 15:00")
    check_out = (datetime.now() + timedelta(days=16)).strftime("%Y-%m-%d 11:00")
    
    payload = {
        "cabin_id": cabin_id,
        "check_in": check_in,
        "check_out": check_out,
        "customer_name": "לקוח בדיקה",
        "customer_email": "test@example.com",
        "customer_phone": "050-1234567",
        "adults": 2,
        "kids": None,
        "addons": [
            {"name": "מסאג' לחדר", "price": 200}
        ]
    }
    
    print_info(f"יוצר הזמנה עבור: {cabin_id}")
    print_warning("⚠ זה יוצר הזמנה אמיתית ב-DB וביומן!")
    
    try:
        response = requests.post(f"{API_BASE}/book", json=payload, timeout=15)
        if response.status_code == 200:
            data = response.json()
            print_success("הזמנה נוצרה בהצלחה!")
            print_info(f"Booking ID: {data.get('booking_id', 'N/A')}")
            print_info(f"Event ID: {data.get('event_id', 'N/A')}")
            print_info(f"Event Link: {data.get('event_link', 'N/A')}")
            print_info(f"מחיר סופי: ₪{data.get('total_price', 'N/A')}")
            print(f"\n{Colors.BLUE}פירוט מלא:{Colors.END}")
            print(json.dumps(data, ensure_ascii=False, indent=2))
            return True, data
        else:
            print_error(f"קוד שגיאה: {response.status_code}")
            print_error(f"תגובה: {response.text[:300]}")
            return False, None
    except Exception as e:
        print_error(f"שגיאה: {e}")
        import traceback
        traceback.print_exc()
        return False, None

def test_get_admin_bookings():
    """בדיקה 7: GET /admin/bookings"""
    print_header("בדיקה 7: GET /admin/bookings - רשימת הזמנות")
    
    try:
        response = requests.get(f"{API_BASE}/admin/bookings", timeout=10)
        if response.status_code == 200:
            data = response.json()
            bookings = data if isinstance(data, list) else data.get('bookings', [])
            print_success(f"נמצאו {len(bookings)} הזמנות")
            for i, booking in enumerate(bookings[:5], 1):  # הצג רק 5 ראשונות
                booking_id = booking.get('id', booking.get('booking_id', 'N/A'))
                customer = booking.get('customer_name', 'ללא שם')
                total = booking.get('total_price', 0)
                status = booking.get('status', 'N/A')
                print_info(f"  {i}. {customer} - ₪{total} ({status})")
            if len(bookings) > 5:
                print_info(f"  ... ועוד {len(bookings) - 5} הזמנות")
            return True, bookings
        else:
            print_error(f"קוד שגיאה: {response.status_code}")
            print_error(f"תגובה: {response.text[:300]}")
            return False, None
    except Exception as e:
        print_error(f"שגיאה: {e}")
        return False, None

def test_get_admin_audit():
    """בדיקה 8: GET /admin/audit"""
    print_header("בדיקה 8: GET /admin/audit - לוגים")
    
    try:
        response = requests.get(f"{API_BASE}/admin/audit", timeout=10)
        if response.status_code == 200:
            data = response.json()
            logs = data if isinstance(data, list) else data.get('audit_logs', [])
            print_success(f"נמצאו {len(logs)} לוגים")
            for i, log in enumerate(logs[:5], 1):  # הצג רק 5 ראשונים
                action = log.get('action', 'N/A')
                table = log.get('table_name', 'N/A')
                created = log.get('created_at', 'N/A')
                print_info(f"  {i}. {action} על {table} ({created})")
            if len(logs) > 5:
                print_info(f"  ... ועוד {len(logs) - 5} לוגים")
            return True, logs
        else:
            print_error(f"קוד שגיאה: {response.status_code}")
            print_error(f"תגובה: {response.text[:300]}")
            return False, None
    except Exception as e:
        print_error(f"שגיאה: {e}")
        return False, None

def main():
    print(f"\n{Colors.BOLD}{Colors.BLUE}")
    print("╔" + "=" * 58 + "╗")
    print("║" + " " * 10 + "בדיקת כל ה-API Endpoints" + " " * 20 + "║")
    print("╚" + "=" * 58 + "╝")
    print(Colors.END)
    
    results = {}
    cabin_id = None
    
    # בדיקה 1: האם השרת רץ?
    if not test_server_running():
        print_error("\nהשרת לא רץ! הרץ את השרת לפני המשך:")
        print_warning("  run_api.bat")
        print_warning("  או: python -m uvicorn src.api_server:app --reload --port 8000")
        return 1
    
    # בדיקה 2: GET /health
    results['health'], _ = test_get_health()
    
    # בדיקה 3: GET /cabins
    results['cabins'], cabins_data = test_get_cabins()
    if cabins_data and len(cabins_data) > 0:
        cabin_id = cabins_data[0].get('cabin_id') or cabins_data[0].get('id')
    
    # בדיקה 4: POST /availability
    results['availability'], _ = test_post_availability()
    
    # בדיקה 5: POST /quote
    results['quote'], _ = test_post_quote(cabin_id)
    
    # בדיקה 6: POST /book (אופציונלי - יוצר הזמנה אמיתית)
    print_warning("\n⚠ בדיקת POST /book תדלג - זה יוצר הזמנה אמיתית")
    print_warning("אם תרצה לבדוק, הרץ את הפונקציה ידנית")
    # results['book'], _ = test_post_book(cabin_id)
    results['book'] = None
    
    # בדיקה 7: GET /admin/bookings
    results['admin_bookings'], _ = test_get_admin_bookings()
    
    # בדיקה 8: GET /admin/audit
    results['admin_audit'], _ = test_get_admin_audit()
    
    # סיכום
    print_header("סיכום בדיקות")
    
    total = len([r for r in results.values() if r is not None])
    passed = sum(1 for r in results.values() if r is True)
    
    print(f"\n{Colors.BOLD}תוצאות:{Colors.END}")
    print(f"  ✓ GET /health: {'עבר' if results['health'] else 'נכשל'}")
    print(f"  ✓ GET /cabins: {'עבר' if results['cabins'] else 'נכשל'}")
    print(f"  ✓ POST /availability: {'עבר' if results['availability'] else 'נכשל'}")
    print(f"  ✓ POST /quote: {'עבר' if results['quote'] else 'נכשל'}")
    print(f"  ✓ POST /book: {'דילוג' if results['book'] is None else ('עבר' if results['book'] else 'נכשל')}")
    print(f"  ✓ GET /admin/bookings: {'עבר' if results['admin_bookings'] else 'נכשל'}")
    print(f"  ✓ GET /admin/audit: {'עבר' if results['admin_audit'] else 'נכשל'}")
    
    print(f"\n{Colors.BOLD}ציון כולל: {passed}/{total}{Colors.END}")
    
    if passed == total:
        print(f"\n{Colors.GREEN}{Colors.BOLD}🎉 כל הבדיקות עברו!{Colors.END}\n")
        return 0
    else:
        print(f"\n{Colors.RED}{Colors.BOLD}⚠ יש בעיות שצריך לתקן.{Colors.END}\n")
        return 1

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}בוטל על ידי המשתמש{Colors.END}")
        sys.exit(1)
    except Exception as e:
        print_error(f"שגיאה כללית: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


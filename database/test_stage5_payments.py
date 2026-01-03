#!/usr/bin/env python3
"""
בדיקת שלב 5: תשלומים (Payments)
מדריך מעשי לבדיקת תכונות התשלום
"""
import sys
import os
import requests
from decimal import Decimal
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

API_BASE = "http://127.0.0.1:8000"

def print_header(title):
    print("\n" + "="*60)
    print(f"  {title}")
    print("="*60)

def print_step(step_num, description):
    print(f"\n📋 שלב {step_num}: {description}")
    print("-" * 60)

def check_server():
    """בדיקת שהשרת רץ"""
    try:
        r = requests.get(f"{API_BASE}/health", timeout=5)
        if r.status_code == 200:
            print("✅ השרת רץ")
            return True
        else:
            print(f"❌ השרת מחזיר קוד שגיאה: {r.status_code}")
            return False
    except Exception as e:
        print(f"❌ השרת לא רץ: {e}")
        print("   הפעל: python -m uvicorn src.api_server:app --reload")
        return False

def check_stripe_config():
    """בדיקת הגדרת Stripe"""
    print_step(1, "בדיקת הגדרת Stripe")
    
    try:
        from src.payment import get_payment_manager
        payment_manager = get_payment_manager()
        
        if payment_manager.is_available():
            print("✅ Stripe מוגדר (STRIPE_SECRET_KEY קיים)")
            return True
        else:
            print("⚠️ Stripe לא מוגדר")
            print("\n📝 כדי להגדיר Stripe:")
            print("   1. היכנס ל-Stripe Dashboard: https://dashboard.stripe.com")
            print("   2. עבור ל-Developers > API keys")
            print("   3. העתק את ה-Secret key (sk_test_...)")
            print("   4. הוסף ל-.env:")
            print("      STRIPE_SECRET_KEY=sk_test_...")
            print("      STRIPE_WEBHOOK_SECRET=whsec_... (אחרי יצירת webhook)")
            print("\n   ⚠️ הערה: בלי Stripe, תשלומים לא יעבדו, אבל ההזמנות יעבדו")
            return False
    except Exception as e:
        print(f"❌ שגיאה בבדיקת Stripe: {e}")
        return False

def test_payment_intent_creation():
    """בדיקת יצירת Payment Intent"""
    print_step(2, "בדיקת יצירת Payment Intent")
    
    try:
        from src.payment import get_payment_manager
        payment_manager = get_payment_manager()
        
        if not payment_manager.is_available():
            print("⏭️ דילוג - Stripe לא מוגדר")
            return None
        
        # יצירת Payment Intent לבדיקה
        test_amount = Decimal("100.00")
        test_booking_id = "test-booking-123"
        
        print(f"   יוצר Payment Intent עבור {test_amount} ILS...")
        result = payment_manager.create_payment_intent(
            amount=test_amount,
            currency="ils",
            booking_id=test_booking_id,
            description="Test Payment Intent"
        )
        
        print(f"✅ Payment Intent נוצר בהצלחה!")
        print(f"   Payment Intent ID: {result['payment_intent_id']}")
        print(f"   Client Secret: {result['client_secret'][:20]}...")
        print(f"   Status: {result['status']}")
        print(f"   Amount: {result['amount'] / 100} ILS")
        
        return result
    except Exception as e:
        print(f"❌ שגיאה ביצירת Payment Intent: {e}")
        return None

def test_booking_with_payment():
    """בדיקת יצירת הזמנה עם תשלום"""
    print_step(3, "בדיקת יצירת הזמנה עם תשלום")
    
    # קודם, נצטרך cabin_id זמין
    try:
        print("   בודק צימרים זמינים...")
        cabins_r = requests.get(f"{API_BASE}/cabins", timeout=5)
        if cabins_r.status_code != 200:
            print(f"❌ לא הצלחתי לקבל צימרים: {cabins_r.status_code}")
            return None
        
        cabins = cabins_r.json()
        if not cabins:
            print("❌ אין צימרים זמינים")
            return None
        
        cabin = cabins[0]
        cabin_id = cabin.get('cabin_id')
        print(f"   משתמש בצימר: {cabin.get('name')} ({cabin_id})")
        
        # תאריכים - בעוד 10 ימים
        check_in = (datetime.now() + timedelta(days=10)).strftime("%Y-%m-%d 15:00")
        check_out = (datetime.now() + timedelta(days=12)).strftime("%Y-%m-%d 11:00")
        
        print(f"   יוצר הזמנה עם תשלום...")
        print(f"   Check-in: {check_in}")
        print(f"   Check-out: {check_out}")
        
        booking_data = {
            "cabin_id": cabin_id,
            "check_in": check_in,
            "check_out": check_out,
            "customer": "בדיקת תשלום",
            "email": "test@example.com",
            "phone": "050-1234567",
            "adults": 2,
            "kids": 0,
            "create_payment": True  # זה מה שמוסיף את התשלום!
        }
        
        r = requests.post(
            f"{API_BASE}/book",
            json=booking_data,
            timeout=10
        )
        
        if r.status_code == 200:
            booking = r.json()
            print(f"✅ הזמנה נוצרה בהצלחה!")
            print(f"   Booking ID: {booking.get('booking_id', 'N/A')}")
            print(f"   Event ID: {booking.get('event_id', 'N/A')[:20]}...")
            
            if booking.get('payment_intent_id'):
                print(f"   ✅ Payment Intent נוצר!")
                print(f"   Payment Intent ID: {booking.get('payment_intent_id')}")
                print(f"   Client Secret: {booking.get('client_secret', 'N/A')[:30]}...")
                print(f"\n   💡 כדי להשלים תשלום:")
                print(f"      1. השתמש ב-client_secret ב-Stripe Checkout")
                print(f"      2. או השתמש ב-Stripe.js עם client_secret")
                print(f"      3. אחרי תשלום, Stripe ישלח webhook ל-/webhooks/stripe")
            else:
                print(f"   ⚠️ Payment Intent לא נוצר (אולי Stripe לא מוגדר)")
            
            return booking
        else:
            print(f"❌ שגיאה ביצירת הזמנה: {r.status_code}")
            print(f"   Response: {r.text[:200]}")
            return None
            
    except Exception as e:
        print(f"❌ שגיאה: {e}")
        return None

def test_transactions_in_db():
    """בדיקת transactions ב-DB"""
    print_step(4, "בדיקת Transactions ב-DB")
    
    try:
        from src.db import get_db_connection
        from psycopg2.extras import RealDictCursor
        
        with get_db_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # בדוק אם טבלת transactions קיימת
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'transactions'
                )
            """)
            table_exists = cursor.fetchone()[0]
            
            if not table_exists:
                print("❌ טבלת transactions לא קיימת")
                return
            
            # קבל את כל ה-transactions
            cursor.execute("""
                SELECT 
                    t.id::text as transaction_id,
                    t.booking_id::text as booking_id,
                    t.payment_id,
                    t.amount,
                    t.currency,
                    t.status,
                    t.payment_method,
                    t.created_at,
                    b.cabin_id::text as cabin_id,
                    c.name as customer_name
                FROM transactions t
                LEFT JOIN bookings b ON t.booking_id = b.id
                LEFT JOIN customers c ON b.customer_id = c.id
                ORDER BY t.created_at DESC
                LIMIT 10
            """)
            
            transactions = cursor.fetchall()
            
            if transactions:
                print(f"✅ נמצאו {len(transactions)} transactions:")
                print()
                for i, txn in enumerate(transactions, 1):
                    print(f"   {i}. Transaction {txn['transaction_id'][:8]}...")
                    print(f"      Booking: {txn['booking_id'][:8] if txn['booking_id'] else 'N/A'}...")
                    print(f"      Payment ID: {txn['payment_id'] or 'N/A'}")
                    print(f"      Amount: {txn['amount']} {txn['currency'] or 'ILS'}")
                    print(f"      Status: {txn['status']}")
                    print(f"      Customer: {txn['customer_name'] or 'N/A'}")
                    print(f"      Created: {txn['created_at']}")
                    print()
            else:
                print("⚠️ אין transactions ב-DB עדיין")
                print("   זה תקין אם עדיין לא יצרת הזמנות עם תשלום")
                
    except Exception as e:
        print(f"❌ שגיאה בבדיקת DB: {e}")

def test_webhook_endpoint():
    """בדיקת Webhook endpoint"""
    print_step(5, "בדיקת Webhook Endpoint")
    
    print("   Webhook endpoint: POST /webhooks/stripe")
    print("   זה endpoint שמקבל webhooks מ-Stripe")
    print()
    print("   📝 כדי לבדוק webhook:")
    print("      1. היכנס ל-Stripe Dashboard")
    print("      2. עבור ל-Developers > Webhooks")
    print("      3. צור webhook חדש:")
    print("         URL: http://your-server.com/webhooks/stripe")
    print("         Events: payment_intent.succeeded, payment_intent.payment_failed")
    print("      4. העתק את ה-Webhook Secret ל-.env:")
    print("         STRIPE_WEBHOOK_SECRET=whsec_...")
    print()
    print("   💡 לבדיקה מקומית, השתמש ב-Stripe CLI:")
    print("      stripe listen --forward-to http://localhost:8000/webhooks/stripe")
    print()

def main():
    print_header("בדיקת שלב 5: תשלומים (Payments)")
    
    # בדיקת שרת
    if not check_server():
        return
    
    # בדיקת Stripe
    stripe_configured = check_stripe_config()
    
    # בדיקת Payment Intent
    if stripe_configured:
        test_payment_intent_creation()
    
    # בדיקת הזמנה עם תשלום
    test_booking_with_payment()
    
    # בדיקת Transactions ב-DB
    test_transactions_in_db()
    
    # הסבר על Webhook
    test_webhook_endpoint()
    
    print_header("סיכום")
    print("✅ בדיקת שלב 5 הושלמה!")
    print()
    print("📋 מה לבדוק:")
    print("   1. ✅ Payment Intent נוצר בהצלחה")
    print("   2. ✅ הזמנה עם תשלום נוצרת")
    print("   3. ✅ Transaction נשמר ב-DB")
    print("   4. ⏳ Webhook מתעדכן אחרי תשלום (דורש תשלום אמיתי)")
    print()
    print("💡 טיפים:")
    print("   - השתמש ב-Stripe Test Mode לבדיקות")
    print("   - בדוק את ה-transactions ב-DB דרך Admin Panel")
    print("   - השתמש ב-Stripe Dashboard לראות Payment Intents")

if __name__ == "__main__":
    main()


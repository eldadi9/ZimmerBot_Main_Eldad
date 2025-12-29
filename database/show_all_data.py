"""
Show all data from database
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
import json

# Fix encoding for Windows
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# Add parent directory to path
BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))
load_dotenv(BASE_DIR / ".env")

from src.db import get_db_connection
from psycopg2.extras import RealDictCursor


def show_all_data():
    """
    Display all data from database
    """
    print("=" * 60)
    print("Database Content Summary")
    print("=" * 60)
    
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # 1. Cabins
            print("\n1. CABINS:")
            print("-" * 60)
            cursor.execute("SELECT COUNT(*) as count FROM cabins")
            count = cursor.fetchone()["count"]
            print(f"   Total cabins: {count}")
            
            cursor.execute("""
                SELECT id::text, name, area, max_adults, max_kids, 
                       base_price_night, weekend_price, calendar_id
                FROM cabins
                ORDER BY name
            """)
            cabins = cursor.fetchall()
            for cabin in cabins:
                name = cabin['name'] or 'N/A'
                area = cabin['area'] or 'N/A'
                print(f"   - {name} (ID: {cabin['id'][:8]}...) | Area: {area} | "
                      f"Adults: {cabin['max_adults']} | Kids: {cabin['max_kids']} | "
                      f"Price: {cabin['base_price_night']} ILS")
            
            # 2. Customers
            print("\n2. CUSTOMERS:")
            print("-" * 60)
            cursor.execute("SELECT COUNT(*) as count FROM customers")
            count = cursor.fetchone()["count"]
            print(f"   Total customers: {count}")
            
            cursor.execute("""
                SELECT id::text, name, email, phone, created_at
                FROM customers
                ORDER BY created_at DESC
                LIMIT 10
            """)
            customers = cursor.fetchall()
            for customer in customers:
                print(f"   - {customer['name']} | Email: {customer['email']} | Phone: {customer['phone']}")
            
            # 3. Bookings
            print("\n3. BOOKINGS:")
            print("-" * 60)
            cursor.execute("SELECT COUNT(*) as count FROM bookings")
            count = cursor.fetchone()["count"]
            print(f"   Total bookings: {count}")
            
            cursor.execute("""
                SELECT 
                    b.id::text as booking_id,
                    c.name as cabin_name,
                    cust.name as customer_name,
                    b.check_in,
                    b.check_out,
                    b.status,
                    b.total_price,
                    b.event_id,
                    b.created_at
                FROM bookings b
                LEFT JOIN cabins c ON b.cabin_id = c.id
                LEFT JOIN customers cust ON b.customer_id = cust.id
                ORDER BY b.created_at DESC
                LIMIT 10
            """)
            bookings = cursor.fetchall()
            for booking in bookings:
                event_info = f" | Event ID: {booking['event_id'][:20]}..." if booking['event_id'] else " | No event"
                print(f"   - Booking {booking['booking_id'][:8]}... | {booking['cabin_name']} | "
                      f"{booking['customer_name']} | {booking['check_in']} to {booking['check_out']} | "
                      f"Status: {booking['status']} | Price: {booking['total_price']} ILS{event_info}")
            
            # 4. Transactions
            print("\n4. TRANSACTIONS:")
            print("-" * 60)
            cursor.execute("SELECT COUNT(*) as count FROM transactions")
            count = cursor.fetchone()["count"]
            print(f"   Total transactions: {count}")
            
            # Get all available columns from transactions table
            cursor.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'transactions'
            """)
            available_columns = [row['column_name'] for row in cursor.fetchall()]
            
            # Build SELECT query based on available columns
            select_fields = ['t.id::text as transaction_id', 't.booking_id::text as booking_id', 't.amount']
            if 'currency' in available_columns:
                select_fields.append('t.currency')
            else:
                select_fields.append("'ILS' as currency")
            select_fields.append('t.status')
            if 'payment_method' in available_columns:
                select_fields.append('t.payment_method')
            else:
                select_fields.append('NULL as payment_method')
            select_fields.append('t.created_at')
            
            query = f"""
                SELECT {', '.join(select_fields)}
                FROM transactions t
                ORDER BY t.created_at DESC
                LIMIT 10
            """
            cursor.execute(query)
            transactions = cursor.fetchall()
            for trans in transactions:
                print(f"   - Transaction {trans['transaction_id'][:8]}... | Booking: {trans['booking_id'][:8]}... | "
                      f"Amount: {trans['amount']} {trans['currency']} | Status: {trans['status']} | "
                      f"Method: {trans['payment_method'] or 'N/A'}")
            
            # 5. Quotes
            print("\n5. QUOTES:")
            print("-" * 60)
            cursor.execute("SELECT COUNT(*) as count FROM quotes")
            count = cursor.fetchone()["count"]
            print(f"   Total quotes: {count}")
            
            cursor.execute("""
                SELECT 
                    q.id::text as quote_id,
                    c.name as cabin_name,
                    q.check_in,
                    q.check_out,
                    q.total_price,
                    q.created_at
                FROM quotes q
                LEFT JOIN cabins c ON q.cabin_id = c.id
                ORDER BY q.created_at DESC
                LIMIT 10
            """)
            quotes = cursor.fetchall()
            for quote in quotes:
                print(f"   - Quote {quote['quote_id'][:8]}... | {quote['cabin_name']} | "
                      f"{quote['check_in']} to {quote['check_out']} | Price: {quote['total_price']} ILS")
            
            # 6. Audit Log
            print("\n6. AUDIT LOG:")
            print("-" * 60)
            cursor.execute("SELECT COUNT(*) as count FROM audit_log")
            count = cursor.fetchone()["count"]
            print(f"   Total audit log entries: {count}")
            
            # Check if audit_log table exists and has required columns
            cursor.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'audit_log'
            """)
            audit_columns = [row['column_name'] for row in cursor.fetchall()]
            
            if 'table_name' in audit_columns:
                cursor.execute("""
                    SELECT 
                        id::text as audit_id,
                        table_name,
                        record_id::text as record_id,
                        action,
                        created_at
                    FROM audit_log
                    ORDER BY created_at DESC
                    LIMIT 10
                """)
            else:
                # If table doesn't have expected columns, just show count
                cursor.execute("SELECT COUNT(*) as count FROM audit_log")
                count = cursor.fetchone()["count"]
                print(f"   Note: Audit log table exists but has different structure. Total entries: {count}")
                audit_logs = []
            audit_logs = cursor.fetchall()
            for log in audit_logs:
                print(f"   - {log['action']} on {log['table_name']} | Record: {log['record_id'][:8]}... | "
                      f"Time: {log['created_at']}")
            
            print("\n" + "=" * 60)
            print("Summary complete!")
            print("=" * 60)
            
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


if __name__ == "__main__":
    show_all_data()


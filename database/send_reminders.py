"""
Background task to send reminder emails 2 days before check-in
Run this script periodically (e.g., daily via cron or scheduled task)
"""
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add parent directory to path
BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))

from dotenv import load_dotenv
load_dotenv(BASE_DIR / ".env")

from src.db import get_db_connection
from src.email_service import get_email_service
from psycopg2.extras import RealDictCursor


def send_reminders():
    """
    Send reminder emails for bookings that are 2 days away from check-in
    """
    try:
        email_service = get_email_service()
        if not email_service.is_configured:
            print("Email service not configured. Skipping reminders.")
            return
        
        # Calculate target date (2 days from now)
        target_date = (datetime.now() + timedelta(days=2)).date()
        
        with get_db_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # Find bookings with check-in in 2 days that haven't been cancelled
            cursor.execute("""
                SELECT 
                    b.id::text as booking_id,
                    b.check_in,
                    c.name as cabin_name,
                    c.area as cabin_area,
                    cust.name as customer_name,
                    cust.email as customer_email,
                    c.address as cabin_address,
                    c.coordinates as cabin_coordinates
                FROM bookings b
                LEFT JOIN cabins c ON b.cabin_id = c.id
                LEFT JOIN customers cust ON b.customer_id = cust.id
                WHERE b.check_in = %s
                AND b.status != 'cancelled'
                AND cust.email IS NOT NULL
                AND cust.email != ''
            """, (target_date,))
            
            bookings = cursor.fetchall()
            
            sent_count = 0
            for booking in bookings:
                try:
                    check_in_str = booking["check_in"].strftime("%d/%m/%Y %H:%M") if isinstance(booking["check_in"], datetime) else str(booking["check_in"])
                    
                    email_service.send_reminder(
                        customer_email=booking["customer_email"],
                        customer_name=booking["customer_name"] or "לקוח",
                        booking_id=booking["booking_id"],
                        cabin_name=booking["cabin_name"] or "",
                        cabin_area=booking["cabin_area"] or "",
                        check_in=check_in_str,
                        cabin_address=booking.get("cabin_address"),
                        cabin_coordinates=booking.get("cabin_coordinates")
                    )
                    sent_count += 1
                    print(f"Sent reminder to {booking['customer_email']} for booking {booking['booking_id'][:8]}...")
                except Exception as e:
                    print(f"Error sending reminder to {booking.get('customer_email')}: {e}")
            
            print(f"Sent {sent_count} reminder emails for check-in date {target_date}")
            
    except Exception as e:
        print(f"Error in send_reminders: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    send_reminders()


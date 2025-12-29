"""
Import existing bookings from Google Calendar to PostgreSQL database
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime, timedelta
import re
import uuid

# Add parent directory to path
BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))
load_dotenv(BASE_DIR / ".env")

from src.main import get_credentials_api, build_calendar_service, list_calendar_events, ISRAEL_TZ
from src.db import get_db_connection, get_cabin_by_id, save_customer_to_db, save_booking_to_db
from psycopg2.extras import RealDictCursor


def parse_event_description(description: str) -> dict:
    """
    Parse event description to extract booking details
    Expected format:
    Cabin: ZB01
    Customer: John Doe
    Phone: 050-1234567
    Check-in: 2026-02-01T15:00:00
    Check-out: 2026-02-02T11:00:00
    Notes: Some notes
    """
    result = {
        "cabin_id": None,
        "customer_name": None,
        "phone": None,
        "email": None,
        "notes": None,
        "adults": None,
        "kids": None,
    }
    
    if not description:
        return result
    
    lines = description.split("\n")
    for line in lines:
        line = line.strip()
        if line.startswith("Cabin:"):
            result["cabin_id"] = line.replace("Cabin:", "").strip()
        elif line.startswith("Customer:"):
            result["customer_name"] = line.replace("Customer:", "").strip()
        elif line.startswith("Phone:"):
            result["phone"] = line.replace("Phone:", "").strip()
        elif line.startswith("Email:"):
            result["email"] = line.replace("Email:", "").strip()
        elif line.startswith("Notes:"):
            result["notes"] = line.replace("Notes:", "").strip()
        elif line.startswith("Adults:"):
            try:
                result["adults"] = int(line.replace("Adults:", "").strip())
            except:
                pass
        elif line.startswith("Kids:"):
            try:
                result["kids"] = int(line.replace("Kids:", "").strip())
            except:
                pass
    
    return result


def import_bookings_from_calendar(days_back: int = 365, days_forward: int = 365):
    """
    Import bookings from Google Calendar to database
    
    Args:
        days_back: How many days back to import (default: 365)
        days_forward: How many days forward to import (default: 365)
    """
    print("=" * 60)
    print("Importing Bookings from Google Calendar to Database")
    print("=" * 60)
    
    try:
        # Get credentials and service
        print("\n1. Connecting to Google Calendar...")
        creds = get_credentials_api()
        service = build_calendar_service(creds)
        print("   OK: Connected to Google Calendar")
        
        # Get all cabins from database
        print("\n2. Loading cabins from database...")
        with get_db_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute("""
                SELECT id::text, name, calendar_id
                FROM cabins
                WHERE calendar_id IS NOT NULL
            """)
            cabins = cursor.fetchall()
            print(f"   Found {len(cabins)} cabins with calendar IDs")
        
        if not cabins:
            print("   ERROR: No cabins found with calendar IDs!")
            return False
        
        # Date range
        now = datetime.now(ISRAEL_TZ)
        time_min = (now - timedelta(days=days_back)).isoformat()
        time_max = (now + timedelta(days=days_forward)).isoformat()
        
        imported = 0
        updated = 0
        errors = 0
        skipped = 0
        
        print(f"\n3. Importing events from {time_min[:10]} to {time_max[:10]}...")
        
        for cabin in cabins:
            cabin_id = cabin['id']
            cabin_name = cabin['name']
            calendar_id = cabin['calendar_id']
            
            print(f"\n   Processing cabin: {cabin_name} (Calendar: {calendar_id[:20]}...)")
            
            try:
                # Get all events from calendar
                events = list_calendar_events(service, calendar_id, time_min, time_max)
                print(f"      Found {len(events)} events")
                
                for event in events:
                    try:
                        # Skip cancelled events
                        if event.get('status') == 'cancelled':
                            skipped += 1
                            continue
                        
                        # Get event dates
                        start = event.get('start', {})
                        end = event.get('end', {})
                        
                        if 'dateTime' in start:
                            check_in_dt = datetime.fromisoformat(start['dateTime'].replace('Z', '+00:00'))
                            check_out_dt = datetime.fromisoformat(end['dateTime'].replace('Z', '+00:00'))
                        elif 'date' in start:
                            check_in_dt = datetime.fromisoformat(start['date'] + 'T00:00:00+02:00')
                            check_out_dt = datetime.fromisoformat(end['date'] + 'T00:00:00+02:00')
                        else:
                            skipped += 1
                            continue
                        
                        # Convert to Israel timezone
                        if check_in_dt.tzinfo is None:
                            check_in_dt = check_in_dt.replace(tzinfo=ISRAEL_TZ)
                        if check_out_dt.tzinfo is None:
                            check_out_dt = check_out_dt.replace(tzinfo=ISRAEL_TZ)
                        
                        check_in_date = check_in_dt.date().isoformat()
                        check_out_date = check_out_dt.date().isoformat()
                        
                        # Parse event description
                        description = event.get('description', '')
                        event_summary = event.get('summary', '')
                        parsed = parse_event_description(description)
                        
                        # Extract customer name from summary if not in description
                        if not parsed['customer_name'] and event_summary:
                            # Try to extract from summary like "הזמנה | John Doe"
                            if '|' in event_summary:
                                parsed['customer_name'] = event_summary.split('|')[-1].strip()
                            else:
                                parsed['customer_name'] = event_summary.replace('הזמנה', '').strip()
                        
                        if not parsed['customer_name']:
                            parsed['customer_name'] = 'Unknown Customer'
                        
                        # Check if booking already exists (by event_id)
                        event_id = event.get('id')
                        event_link = event.get('htmlLink')
                        
                        with get_db_connection() as conn:
                            cursor = conn.cursor()
                            
                            # Check if booking exists by event_id
                            cursor.execute("""
                                SELECT id::text FROM bookings 
                                WHERE event_id = %s
                            """, (event_id,))
                            existing = cursor.fetchone()
                            
                            if existing:
                                # Update existing booking
                                booking_id = existing[0]
                                cursor.execute("""
                                    UPDATE bookings SET
                                        check_in = %s::date,
                                        check_out = %s::date,
                                        event_link = %s,
                                        updated_at = CURRENT_TIMESTAMP
                                    WHERE id = %s::uuid
                                """, (check_in_date, check_out_date, event_link, booking_id))
                                updated += 1
                                print(f"      Updated booking {booking_id[:8]}... for {parsed['customer_name']}")
                            else:
                                # Create new booking
                                # Save customer
                                customer_id = save_customer_to_db(
                                    name=parsed['customer_name'],
                                    email=parsed['email'],
                                    phone=parsed['phone']
                                )
                                
                                # Save booking
                                booking_id = save_booking_to_db(
                                    cabin_id=cabin_id,
                                    customer_id=customer_id,
                                    check_in=check_in_date,
                                    check_out=check_out_date,
                                    adults=parsed['adults'],
                                    kids=parsed['kids'],
                                    total_price=None,  # We don't have price from calendar
                                    status='confirmed',
                                    event_id=event_id,
                                    event_link=event_link
                                )
                                
                                if booking_id:
                                    imported += 1
                                    print(f"      Imported booking {booking_id[:8]}... for {parsed['customer_name']}")
                                else:
                                    errors += 1
                                    print(f"      ERROR: Failed to save booking for {parsed['customer_name']}")
                    
                    except Exception as e:
                        errors += 1
                        print(f"      ERROR processing event {event.get('id', 'unknown')[:20]}...: {e}")
            
            except Exception as e:
                errors += 1
                print(f"   ERROR processing cabin {cabin_name}: {e}")
        
        print("\n" + "=" * 60)
        print("Import Summary:")
        print(f"  Imported: {imported}")
        print(f"  Updated: {updated}")
        print(f"  Skipped: {skipped}")
        print(f"  Errors: {errors}")
        print(f"  Total processed: {imported + updated + skipped + errors}")
        print("=" * 60)
        
        return errors == 0
        
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Import bookings from Google Calendar to database')
    parser.add_argument('--days-back', type=int, default=365, help='Days back to import (default: 365)')
    parser.add_argument('--days-forward', type=int, default=365, help='Days forward to import (default: 365)')
    
    args = parser.parse_args()
    
    success = import_bookings_from_calendar(args.days_back, args.days_forward)
    sys.exit(0 if success else 1)


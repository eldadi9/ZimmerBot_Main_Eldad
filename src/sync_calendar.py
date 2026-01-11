"""
Sync utilities for Google Calendar ↔ Database
"""
import os
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR / ".env")

from src.main import build_calendar_service, list_calendar_events, ISRAEL_TZ, parse_datetime_local
from src.api_server import get_credentials_api
from src.db import get_db_connection, save_customer_to_db, save_booking_to_db, DB_CONFIG
from psycopg2.extras import RealDictCursor


def sync_calendar_to_db(days_back: int = 30, days_forward: int = 365):
    """
    Sync bookings from Google Calendar to PostgreSQL database
    Detects changes in calendar events and updates DB accordingly
    
    Returns: (imported_count, updated_count, errors_count, error_list)
    """
    error_list = []  # Collect all errors for detailed reporting
    try:
        creds = get_credentials_api()
        service = build_calendar_service(creds)
        
        # Get all cabins with calendar IDs
        with get_db_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute("""
                SELECT id::text, name, calendar_id
                FROM cabins
                WHERE calendar_id IS NOT NULL
            """)
            cabins = cursor.fetchall()
        
        if not cabins:
            print("ℹ️ No cabins with calendar_id found in database")
            return (0, 0, 0, [])
        
        print(f"Found {len(cabins)} cabins with calendar_id to sync")
        
        # Date range
        now = datetime.now(ISRAEL_TZ)
        time_min = (now - timedelta(days=days_back)).isoformat()
        time_max = (now + timedelta(days=days_forward)).isoformat()
        
        imported = 0
        updated = 0
        errors = 0
        
        for cabin in cabins:
            try:
                # Handle cabin_id - can be UUID string or already a string
                cabin_id = cabin.get('id') or cabin.get('cabin_id')
                if not cabin_id:
                    print(f"⚠️ Warning: Cabin '{cabin.get('name', 'Unknown')}' has no id/cabin_id, skipping")
                    errors += 1
                    continue
                
                # Ensure cabin_id is a string (UUID from DB is already text via ::text)
                if isinstance(cabin_id, bytes):
                    cabin_id = cabin_id.decode('utf-8')
                cabin_id = str(cabin_id)
                
                calendar_id = cabin.get('calendar_id')
                
                if not calendar_id:
                    error_msg = f"Cabin '{cabin.get('name', 'Unknown')}' (id: {cabin_id[:8]}...) has no calendar_id"
                    print(f"⚠️ Warning: {error_msg}, skipping")
                    errors += 1
                    error_list.append({"type": "missing_calendar_id", "cabin": cabin.get('name', 'Unknown'), "error": error_msg})
                    continue
                
                # Get all events from calendar
                try:
                    events = list_calendar_events(service, calendar_id, time_min, time_max)
                except Exception as calendar_error:
                    error_msg = f"Error fetching events for cabin '{cabin.get('name', 'Unknown')}' (calendar_id: {calendar_id}): {str(calendar_error)}"
                    print(f"❌ {error_msg}")
                    import traceback
                    traceback.print_exc()
                    errors += 1
                    error_list.append({"type": "calendar_fetch_error", "cabin": cabin.get('name', 'Unknown'), "calendar_id": calendar_id, "error": str(calendar_error)})
                    continue
                
                if not events:
                    print(f"ℹ️ No events found for cabin {cabin.get('name', 'Unknown')} (calendar_id: {calendar_id})")
                    continue
                
                print(f"Processing {len(events)} events for cabin {cabin.get('name', 'Unknown')} (calendar_id: {calendar_id})")
                
                for event in events:
                    try:
                        # Skip cancelled events
                        if event.get('status') == 'cancelled':
                            continue
                        
                        # Get event dates with better error handling
                        start = event.get('start', {})
                        end = event.get('end', {})
                        
                        # Parse event dates with better error handling
                        check_in_dt = None
                        check_out_dt = None
                        
                        try:
                            if 'dateTime' in start:
                                check_in_dt = datetime.fromisoformat(start['dateTime'].replace('Z', '+00:00'))
                                check_out_dt = datetime.fromisoformat(end['dateTime'].replace('Z', '+00:00'))
                            elif 'date' in start:
                                check_in_dt = datetime.fromisoformat(start['date'] + 'T00:00:00+02:00')
                                check_out_dt = datetime.fromisoformat(end['date'] + 'T00:00:00+02:00')
                            else:
                                print(f"Warning: Event {event_id[:20] if event_id else 'unknown'}... has no valid start/end date, skipping")
                                continue
                        except Exception as date_parse_error:
                            event_id_temp = event.get('id', 'unknown')
                            error_msg = f"Error parsing dates for event {event_id_temp[:20] if len(event_id_temp) > 20 else event_id_temp}: {str(date_parse_error)}"
                            print(f"❌ {error_msg}")
                            errors += 1
                            error_list.append({"type": "date_parse_error", "cabin": cabin.get('name', 'Unknown'), "event_id": event_id_temp[:20] if len(event_id_temp) > 20 else event_id_temp, "error": str(date_parse_error)})
                            continue
                        
                        # Convert to Israel timezone
                        if check_in_dt.tzinfo is None:
                            check_in_dt = check_in_dt.replace(tzinfo=ISRAEL_TZ)
                        if check_out_dt.tzinfo is None:
                            check_out_dt = check_out_dt.replace(tzinfo=ISRAEL_TZ)
                        
                        check_in_date = check_in_dt.date().isoformat()
                        check_out_date = check_out_dt.date().isoformat()
                        
                        # Extract customer info from event
                        event_summary = event.get('summary', '')
                        description = event.get('description', '')
                        event_id = event.get('id')
                        event_link = event.get('htmlLink')
                        event_updated = event.get('updated', '')
                        attendees = event.get('attendees', [])
                        
                        # Parse customer name from summary (multiple formats)
                        customer_name = 'Unknown Customer'
                        if '|' in event_summary:
                            customer_name = event_summary.split('|')[-1].strip()
                        elif '-' in event_summary:
                            parts = event_summary.split('-')
                            if len(parts) > 1:
                                customer_name = parts[-1].strip()
                        elif event_summary:
                            customer_name = event_summary.replace('הזמנה', '').replace('הזמנה', '').strip()
                        
                        # Extract email from description or attendees
                        customer_email = None
                        customer_phone = None
                        
                        # Try to find email in description
                        if description:
                            import re
                            # Look for email pattern
                            email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
                            emails = re.findall(email_pattern, description)
                            if emails:
                                customer_email = emails[0]
                            
                            # Look for phone pattern (Israeli format)
                            phone_patterns = [
                                r'0\d{1,2}[-\s]?\d{7}',  # 050-1234567, 03-1234567
                                r'\+972[-\s]?\d{1,2}[-\s]?\d{7}',  # +972-50-1234567
                                r'\d{10}',  # 0501234567
                            ]
                            for pattern in phone_patterns:
                                phones = re.findall(pattern, description)
                                if phones:
                                    customer_phone = phones[0].replace('-', '').replace(' ', '').replace('+972', '0')
                                    break
                        
                        # Try to find email/phone in attendees
                        if not customer_email and attendees:
                            for attendee in attendees:
                                attendee_email = attendee.get('email')
                                if attendee_email and '@' in attendee_email:
                                    customer_email = attendee_email
                                    break
                        
                        # Validate event_id
                        if not event_id:
                            print(f"Warning: Event has no ID, skipping")
                            continue
                        
                        # Check if booking exists by event_id
                        with get_db_connection() as conn:
                            cursor = conn.cursor()
                            
                            # Check if updated_at column exists, otherwise use created_at
                            cursor.execute("""
                                SELECT column_name 
                                FROM information_schema.columns 
                                WHERE table_name = 'bookings' 
                                AND column_name = 'updated_at'
                            """)
                            has_updated_at = cursor.fetchone() is not None
                            
                            if has_updated_at:
                                cursor.execute("""
                                    SELECT id::text, updated_at, customer_id::text
                                    FROM bookings 
                                    WHERE event_id = %s
                                """, (event_id,))
                            else:
                                # Use created_at if updated_at doesn't exist
                                cursor.execute("""
                                    SELECT id::text, created_at, customer_id::text
                                    FROM bookings 
                                    WHERE event_id = %s
                                """, (event_id,))
                            existing = cursor.fetchone()
                            
                            if existing:
                                booking_id, db_updated_at, customer_id = existing
                                
                                # Always check for changes (not just timestamp comparison)
                                # Get current booking and customer data - also get cabin_id to check if it changed
                                cursor.execute("""
                                    SELECT check_in, check_out, event_link, cabin_id::text
                                    FROM bookings
                                    WHERE id = %s::uuid
                                """, (booking_id,))
                                booking_data = cursor.fetchone()
                                
                                if customer_id:
                                    cursor.execute("""
                                        SELECT name, email, phone
                                        FROM customers
                                        WHERE id = %s::uuid
                                    """, (customer_id,))
                                    customer_data = cursor.fetchone()
                                else:
                                    customer_data = None
                                
                                # Check for changes in booking - including cabin_id if event moved to different calendar
                                booking_changed = False
                                cabin_id_changed = False
                                if booking_data:
                                    db_check_in, db_check_out, db_event_link, db_cabin_id = booking_data
                                    # Check if dates or link changed
                                    if (db_check_in.isoformat() != check_in_date or 
                                        db_check_out.isoformat() != check_out_date or 
                                        db_event_link != event_link):
                                        booking_changed = True
                                    # Check if cabin_id changed (event moved to different calendar/cabin)
                                    # Normalize both to strings for comparison
                                    db_cabin_id_str = str(db_cabin_id) if db_cabin_id else None
                                    cabin_id_str = str(cabin_id) if cabin_id else None
                                    if db_cabin_id_str != cabin_id_str:
                                        cabin_id_changed = True
                                        booking_changed = True  # Mark as changed so we update it
                                        print(f"🔍 Detected cabin change: DB has {db_cabin_id_str[:8] if db_cabin_id_str else 'None'}, Calendar has {cabin_id_str[:8] if cabin_id_str else 'None'}")
                                
                                # Check for changes in customer
                                customer_changed = False
                                if customer_data:
                                    if (customer_data[0] != customer_name or 
                                        (customer_email and customer_data[1] != customer_email) or
                                        (customer_phone and customer_data[2] != customer_phone)):
                                        customer_changed = True
                                
                                # Update if there are changes
                                if booking_changed or customer_changed:
                                    try:
                                        # Update booking if changed
                                        if booking_changed:
                                            # Build UPDATE query dynamically based on what changed
                                            update_fields = []
                                            update_values = []
                                            
                                            if cabin_id_changed:
                                                update_fields.append("cabin_id = %s::uuid")
                                                update_values.append(cabin_id)
                                                print(f"📦 Cabin changed for booking {booking_id[:8]}...: {db_cabin_id[:8] if db_cabin_id else 'None'} → {cabin_id[:8]}")
                                            
                                            # Always update dates and link if booking changed
                                            update_fields.append("check_in = %s::date")
                                            update_values.append(check_in_date)
                                            update_fields.append("check_out = %s::date")
                                            update_values.append(check_out_date)
                                            update_fields.append("event_link = %s")
                                            update_values.append(event_link)
                                            
                                            if has_updated_at:
                                                update_fields.append("updated_at = CURRENT_TIMESTAMP")
                                            
                                            update_values.append(booking_id)
                                            
                                            update_query = f"""
                                                UPDATE bookings SET
                                                    {', '.join(update_fields)}
                                                WHERE id = %s::uuid
                                            """
                                            
                                            cursor.execute(update_query, tuple(update_values))
                                            
                                            change_summary = []
                                            if cabin_id_changed:
                                                change_summary.append("cabin_id")
                                            change_summary.append("dates/link")
                                            print(f"✅ Updated booking {booking_id[:8]}...: {', '.join(change_summary)}")
                                        
                                        # Update customer if changed
                                        if customer_changed and customer_id:
                                            update_fields = []
                                            update_values = []
                                            
                                            if customer_data[0] != customer_name:
                                                update_fields.append("name = %s")
                                                update_values.append(customer_name)
                                            
                                            if customer_email and customer_data[1] != customer_email:
                                                update_fields.append("email = %s")
                                                update_values.append(customer_email)
                                            
                                            if customer_phone and customer_data[2] != customer_phone:
                                                update_fields.append("phone = %s")
                                                update_values.append(customer_phone)
                                            
                                            if update_fields:
                                                update_values.append(customer_id)
                                                cursor.execute(f"""
                                                    UPDATE customers SET
                                                        {', '.join(update_fields)}
                                                    WHERE id = %s::uuid
                                                """, tuple(update_values))
                                                print(f"Updated customer {customer_id[:8]}...: {', '.join([f.replace(' = %s', '') for f in update_fields])}")
                                        
                                        conn.commit()
                                        updated += 1
                                    except Exception as e:
                                        errors += 1
                                        conn.rollback()
                                        error_msg = f"Error updating booking/customer for event {event_id[:20] if event_id else 'unknown'}...: {str(e)}"
                                        print(f"❌ {error_msg}")
                                        error_list.append({"type": "update_error", "cabin": cabin.get('name', 'Unknown'), "event_id": event_id[:20] if event_id else 'unknown', "error": str(e)})
                                        import traceback
                                        traceback.print_exc()
                            else:
                                # Create new booking - check if we already have this customer
                                # First try to find existing customer by email (most reliable)
                                existing_customer = None
                                if customer_email:
                                    cursor.execute("""
                                        SELECT id::text FROM customers 
                                        WHERE email = %s 
                                        LIMIT 1
                                    """, (customer_email,))
                                    existing_customer = cursor.fetchone()
                                
                                # If not found by email, try phone
                                if not existing_customer and customer_phone:
                                    cursor.execute("""
                                        SELECT id::text FROM customers 
                                        WHERE phone = %s 
                                        LIMIT 1
                                    """, (customer_phone,))
                                    existing_customer = cursor.fetchone()
                                
                                # If still not found, try name
                                if not existing_customer:
                                    cursor.execute("""
                                        SELECT id::text FROM customers 
                                        WHERE name = %s 
                                        LIMIT 1
                                    """, (customer_name,))
                                    existing_customer = cursor.fetchone()
                                
                                if existing_customer:
                                    customer_id = existing_customer[0]
                                    # Update existing customer with new info if available
                                    if customer_email or customer_phone:
                                        update_fields = []
                                        update_values = []
                                        if customer_email:
                                            update_fields.append("email = %s")
                                            update_values.append(customer_email)
                                        if customer_phone:
                                            update_fields.append("phone = %s")
                                            update_values.append(customer_phone)
                                        if update_fields:
                                            update_values.append(customer_id)
                                            cursor.execute(f"""
                                                UPDATE customers SET
                                                    {', '.join(update_fields)}
                                                WHERE id = %s::uuid
                                            """, tuple(update_values))
                                            print(f"Updated existing customer {customer_id[:8]}... with email/phone")
                                else:
                                    # Create new customer
                                    customer_id = save_customer_to_db(
                                        name=customer_name,
                                        email=customer_email,
                                        phone=customer_phone
                                    )
                                
                                if customer_id:
                                    # Create new booking
                                    booking_id = save_booking_to_db(
                                        cabin_id=cabin_id,
                                        customer_id=customer_id,
                                        check_in=check_in_date,
                                        check_out=check_out_date,
                                        adults=None,
                                        kids=None,
                                        total_price=None,
                                        status='confirmed',
                                        event_id=event_id,
                                        event_link=event_link
                                    )
                                    
                                    if booking_id:
                                        imported += 1
                                        print(f"✅ Imported new booking {booking_id[:8]}... for customer '{customer_name}' (event_id: {event_id[:20] if event_id and len(event_id) > 20 else (event_id or 'unknown')}...)")
                                    else:
                                        print(f"❌ Failed to create booking for customer '{customer_name}' (event_id: {event_id[:20] if event_id and len(event_id) > 20 else (event_id or 'unknown')}...)")
                                        errors += 1
                                else:
                                    error_msg = f"Failed to create/find customer '{customer_name}' for booking with event_id {event_id[:20] if event_id and len(event_id) > 20 else (event_id or 'unknown')}..."
                                    print(f"❌ {error_msg}")
                                    errors += 1
                                    error_list.append({"type": "customer_creation_error", "cabin": cabin.get('name', 'Unknown'), "customer_name": customer_name, "event_id": event_id[:20] if event_id and len(event_id) > 20 else (event_id or 'unknown'), "error": error_msg})
                    except Exception as e:
                        errors += 1
                        event_id_display = event.get('id', 'unknown')[:20] if event.get('id') and len(event.get('id', '')) > 20 else (event.get('id', 'unknown') or 'unknown')
                        cabin_name = cabin.get('name', 'Unknown')
                        error_msg = str(e)
                        print(f"❌ Error processing event {event_id_display}... for cabin '{cabin_name}': {error_msg}")
                        error_list.append({"type": "event_processing_error", "cabin": cabin_name, "event_id": event_id_display, "error": error_msg})
                        import traceback
                        traceback.print_exc()
            
            except Exception as e:
                errors += 1
                cabin_name = cabin.get('name', 'Unknown') if cabin else 'Unknown'
                error_msg = str(e)
                print(f"❌ Error processing cabin '{cabin_name}': {error_msg}")
                error_list.append({"type": "cabin_processing_error", "cabin": cabin_name, "error": error_msg})
                import traceback
                traceback.print_exc()
        
        print(f"\n✅ Sync Calendar → DB completed: {imported} imported, {updated} updated, {errors} errors")
        return (imported, updated, errors, error_list)
    
    except Exception as e:
        error_msg = str(e)
        print(f"❌ Critical error in sync_calendar_to_db: {error_msg}")
        error_list.append({"type": "critical_error", "error": error_msg})
        import traceback
        traceback.print_exc()
        return (0, 0, 1, error_list)


def update_calendar_event(
    service,
    event_id: str,
    calendar_id: str,
    summary: Optional[str] = None,
    description: Optional[str] = None,
    start_local: Optional[datetime] = None,
    end_local: Optional[datetime] = None
) -> Optional[Dict[str, Any]]:
    """
    Update an existing calendar event
    
    Args:
        service: Google Calendar API service
        event_id: ID of the event to update
        calendar_id: Calendar ID
        summary: New summary (optional)
        description: New description (optional)
        start_local: New start time (optional, timezone-aware)
        end_local: New end time (optional, timezone-aware)
    
    Returns:
        Updated event dict or None if error
    """
    try:
        # Get existing event
        event = service.events().get(calendarId=calendar_id, eventId=event_id).execute()
        
        # Update fields if provided
        if summary:
            event['summary'] = summary
        if description:
            event['description'] = description
        if start_local:
            if start_local.tzinfo is None:
                start_local = start_local.replace(tzinfo=ISRAEL_TZ)
            event['start'] = {
                'dateTime': start_local.isoformat(),
                'timeZone': 'Asia/Jerusalem'
            }
        if end_local:
            if end_local.tzinfo is None:
                end_local = end_local.replace(tzinfo=ISRAEL_TZ)
            event['end'] = {
                'dateTime': end_local.isoformat(),
                'timeZone': 'Asia/Jerusalem'
            }
        
        # Update event
        updated_event = service.events().update(
            calendarId=calendar_id,
            eventId=event_id,
            body=event
        ).execute()
        
        return updated_event
    
    except Exception as e:
        print(f"❌ Error updating calendar event {event_id[:20] if event_id and len(event_id) > 20 else (event_id or 'unknown')}: {e}")
        import traceback
        traceback.print_exc()
        return None

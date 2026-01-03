"""
Database connection and utilities
"""
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from typing import Optional, Dict, List, Any
from contextlib import contextmanager
from dotenv import load_dotenv
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR / ".env")

# Database connection parameters
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "5432")),
    "database": os.getenv("DB_NAME", "zimmerbot_db"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", "postgres"),
}


@contextmanager
def get_db_connection():
    """
    Context manager for database connections
    Returns a connection that will be closed automatically
    """
    conn = None
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        yield conn
        conn.commit()
    except Exception as e:
        if conn:
            conn.rollback()
        raise e
    finally:
        if conn:
            conn.close()


def read_cabins_from_db() -> List[Dict[str, Any]]:
    """
    Read all cabins from database
    Returns list of cabin dictionaries compatible with existing code
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            # Check if cabin_id_string column exists
            cursor.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'cabins' AND column_name = 'cabin_id_string'
            """)
            has_cabin_id_string = cursor.fetchone() is not None
            
            if has_cabin_id_string:
                cursor.execute("""
                    SELECT 
                        id::text as cabin_id,
                        name,
                        area,
                        max_adults,
                        max_kids,
                        features,
                        base_price_night,
                        weekend_price,
                        images_urls,
                        calendar_id,
                        COALESCE(cabin_id_string, id::text) as cabin_id_string
                    FROM cabins
                    ORDER BY name
                """)
            else:
                cursor.execute("""
                    SELECT 
                        id::text as cabin_id,
                        name,
                        area,
                        max_adults,
                        max_kids,
                        features,
                        base_price_night,
                        weekend_price,
                        images_urls,
                        calendar_id,
                        id::text as cabin_id_string
                    FROM cabins
                    ORDER BY name
                """)
            
            # Note: cabin_id from DB is now a UUID string
            # If you need the original cabin_id from Sheets, you might want to add a cabin_id_string field
            rows = cursor.fetchall()
            
            # Convert to list of dicts compatible with existing code
            cabins = []
            for row in rows:
                cabin = dict(row)
                # Ensure compatibility with existing code
                if cabin.get("features") and isinstance(cabin["features"], dict):
                    # If features is a dict with 'raw' key, extract it
                    if 'raw' in cabin["features"]:
                        cabin["features"] = cabin["features"]["raw"]
                    # Otherwise keep as dict (will be converted later in API)
                
                # Convert images_urls from PostgreSQL array to Python list
                if cabin.get("images_urls"):
                    if isinstance(cabin["images_urls"], str):
                        # If it's a string, try to parse as JSON or split by comma
                        import json
                        try:
                            cabin["images_urls"] = json.loads(cabin["images_urls"])
                        except:
                            # If not JSON, split by comma
                            cabin["images_urls"] = [img.strip() for img in cabin["images_urls"].split(",") if img.strip()]
                    elif not isinstance(cabin["images_urls"], list):
                        # If it's not a list, convert to list
                        cabin["images_urls"] = [cabin["images_urls"]] if cabin["images_urls"] else []
                else:
                    cabin["images_urls"] = []
                
                # Use cabin_id_string if available for easier booking (ZB01, ZB02, etc.)
                if cabin.get("cabin_id_string") and cabin["cabin_id_string"] != cabin.get("cabin_id"):
                    # Keep both - cabin_id (UUID) and cabin_id_string (ZB01, etc.)
                    # The API will use cabin_id_string for display and booking
                    pass
                
                cabins.append(cabin)
            
            return cabins
    except psycopg2.OperationalError as e:
        # If DB connection fails, return empty list (fallback to Sheets)
        print(f"Warning: Could not connect to database: {e}")
        return []
    except Exception as e:
        print(f"Error reading cabins from DB: {e}")
        return []


def save_customer_to_db(name: str, email: Optional[str] = None, phone: Optional[str] = None) -> Optional[str]:
    """
    Save or get existing customer from database
    Returns customer_id (UUID as string)
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Check if customer exists (by email or phone)
            if email:
                cursor.execute("""
                    SELECT id::text FROM customers 
                    WHERE email = %s
                """, (email,))
                row = cursor.fetchone()
                if row:
                    return row[0]
            
            if phone:
                cursor.execute("""
                    SELECT id::text FROM customers 
                    WHERE phone = %s
                """, (phone,))
                row = cursor.fetchone()
                if row:
                    return row[0]
            
            # Create new customer with UUID
            import uuid as uuid_lib
            customer_uuid = str(uuid_lib.uuid4())
            cursor.execute("""
                INSERT INTO customers (id, name, email, phone)
                VALUES (%s::uuid, %s, %s, %s)
                RETURNING id::text
            """, (customer_uuid, name, email, phone))
            customer_id = cursor.fetchone()[0]
            conn.commit()
            return customer_id
            
    except Exception as e:
        print(f"Error saving customer to DB: {e}")
        return None


def save_booking_to_db(
    cabin_id: str,
    customer_id: Optional[str],
    check_in: str,
    check_out: str,
    adults: Optional[int] = None,
    kids: Optional[int] = None,
    total_price: Optional[float] = None,
    status: str = "confirmed",
    event_id: Optional[str] = None,
    event_link: Optional[str] = None
) -> Optional[str]:
    """
    Save booking to database
    Returns booking_id (UUID as string)
    
    Note: cabin_id should be a UUID string (from DB) or a cabin_id from Sheets
    If it's from Sheets, we need to find the UUID in DB first
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Try to find cabin by cabin_id (could be UUID or original ID)
            # First, try as UUID
            try:
                import uuid as uuid_lib
                uuid_lib.UUID(cabin_id)  # Validate UUID format
                # It's a valid UUID, use it directly
                cabin_uuid = cabin_id
            except (ValueError, AttributeError):
                # Not a UUID, might be original cabin_id from Sheets
                # Try to find by calendar_id or name (we'll need to add a lookup)
                # For now, assume it's already a UUID from DB
                cabin_uuid = cabin_id
            
            # Convert customer_id to UUID if provided
            customer_uuid = None
            if customer_id:
                try:
                    import uuid as uuid_lib
                    uuid_lib.UUID(customer_id)  # Validate UUID format
                    customer_uuid = customer_id
                except (ValueError, AttributeError):
                    # Not a UUID, skip customer_id
                    customer_uuid = None
            
            # Generate UUID for booking
            import uuid as uuid_lib
            booking_uuid = str(uuid_lib.uuid4())
            
            cursor.execute("""
                INSERT INTO bookings (
                    id, cabin_id, customer_id, check_in, check_out,
                    adults, kids, total_price, status, event_id, event_link
                )
                VALUES (
                    %s::uuid, %s::uuid, %s::uuid, %s::date, %s::date,
                    %s, %s, %s, %s, %s, %s
                )
                RETURNING id::text
            """, (
                booking_uuid,
                cabin_uuid,
                customer_uuid,
                check_in,
                check_out,
                adults,
                kids,
                total_price,
                status,
                event_id,
                event_link
            ))
            
            booking_id = cursor.fetchone()[0]
            conn.commit()
            return booking_id
            
    except Exception as e:
        print(f"Error saving booking to DB: {e}")
        import traceback
        traceback.print_exc()
        return None


def get_cabin_by_id(cabin_id: str) -> Optional[Dict[str, Any]]:
    """
    Get cabin by ID from database
    cabin_id can be UUID string or original cabin_id from Sheets
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # Try as UUID first
            try:
                import uuid as uuid_lib
                uuid_lib.UUID(cabin_id)  # Validate UUID format
                # It's a valid UUID
                cursor.execute("""
                    SELECT 
                        id::text as cabin_id,
                        name,
                        area,
                        max_adults,
                        max_kids,
                        features,
                        base_price_night,
                        weekend_price,
                        images_urls,
                        calendar_id
                    FROM cabins
                    WHERE id = %s::uuid
                """, (cabin_id,))
            except (ValueError, AttributeError):
                # Not a UUID, try to find by calendar_id or name
                cursor.execute("""
                    SELECT 
                        id::text as cabin_id,
                        name,
                        area,
                        max_adults,
                        max_kids,
                        features,
                        base_price_night,
                        weekend_price,
                        images_urls,
                        calendar_id
                    FROM cabins
                    WHERE calendar_id = %s OR name = %s
                    LIMIT 1
                """, (cabin_id, cabin_id))
            
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None
            
    except Exception as e:
        print(f"Error getting cabin from DB: {e}")
        return None


def save_audit_log(
    table_name: str,
    record_id: str,
    action: str,
    old_values: Optional[Dict[str, Any]] = None,
    new_values: Optional[Dict[str, Any]] = None,
    user_id: Optional[str] = None
) -> Optional[str]:
    """
    Save audit log entry
    Returns audit_log_id (UUID as string)
    
    Supports both old schema (entity_type, entity_id, payload) and new schema (table_name, record_id, old_values, new_values)
    
    Note: record_id can be any string. If it's not a UUID, we'll generate a UUID
    and store the original record_id in new_values.
    """
    try:
        import json
        import uuid as uuid_lib
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Check which schema the table uses
            cursor.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'audit_log' 
                AND column_name IN ('table_name', 'entity_type')
            """)
            columns = [row[0] for row in cursor.fetchall()]
            
            if 'table_name' in columns:
                # New schema with table_name, record_id, old_values, new_values
                # Convert record_id to UUID if needed
                try:
                    record_uuid = str(uuid_lib.UUID(record_id))
                except (ValueError, AttributeError):
                    # Not a UUID, generate a new UUID for the audit log
                    # The original record_id will be stored in new_values
                    record_uuid = str(uuid_lib.uuid4())
                    # Add original record_id to new_values if not already there
                    if new_values:
                        new_values = dict(new_values)
                        new_values["original_record_id"] = record_id
                    else:
                        new_values = {"original_record_id": record_id}
                
                # Convert user_id to UUID if provided
                user_uuid = None
                if user_id:
                    try:
                        user_uuid = str(uuid_lib.UUID(user_id))
                    except (ValueError, AttributeError):
                        user_uuid = None
                
                cursor.execute("""
                    INSERT INTO audit_log (
                        table_name, record_id, action, old_values, new_values, user_id
                    )
                    VALUES (
                        %s, %s::uuid, %s, %s::jsonb, %s::jsonb, %s::uuid
                    )
                    RETURNING id::text
                """, (
                    table_name,
                    record_uuid,
                    action,
                    json.dumps(old_values) if old_values else None,
                    json.dumps(new_values) if new_values else None,
                    user_uuid
                ))
                
                audit_id = cursor.fetchone()[0]
                conn.commit()
                return audit_id
            elif 'entity_type' in columns:
                # Old schema with entity_type, entity_id, payload
                # Build payload JSON
                payload = {}
                if old_values:
                    payload["old_values"] = old_values
                if new_values:
                    payload["new_values"] = new_values
                if user_id:
                    payload["user_id"] = user_id
                
                cursor.execute("""
                    INSERT INTO audit_log (
                        entity_type, entity_id, action, payload
                    )
                    VALUES (
                        %s, %s, %s, %s::jsonb
                    )
                    RETURNING id::text
                """, (
                    table_name,
                    record_id,
                    action,
                    json.dumps(payload) if payload else None
                ))
                
                audit_id = cursor.fetchone()[0]
                conn.commit()
                return audit_id
            else:
                # Unknown schema - skip
                print("Warning: Unknown audit_log schema, skipping save")
                return None
            
    except Exception as e:
        print(f"Error saving audit log: {e}")
        return None


def save_transaction(
    booking_id: str,
    payment_id: Optional[str] = None,
    amount: float = 0.0,
    currency: str = "ILS",
    status: str = "pending",
    payment_method: Optional[str] = None
) -> Optional[str]:
    """
    Save transaction to database
    Returns transaction_id (UUID as string)
    """
    try:
        import uuid as uuid_lib
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Convert booking_id to UUID
            try:
                booking_uuid = str(uuid_lib.UUID(booking_id))
            except (ValueError, AttributeError):
                return None
            
            cursor.execute("""
                INSERT INTO transactions (
                    booking_id, payment_id, amount, currency, status, payment_method
                )
                VALUES (
                    %s::uuid, %s, %s, %s, %s, %s
                )
                RETURNING id::text
            """, (
                booking_uuid,
                payment_id,
                amount,
                currency,
                status,
                payment_method
            ))
            
            transaction_id = cursor.fetchone()[0]
            conn.commit()
            return transaction_id
            
    except Exception as e:
        print(f"Error saving transaction: {e}")
        return None


def save_quote(
    cabin_id: str,
    check_in: str,
    check_out: str,
    adults: Optional[int] = None,
    kids: Optional[int] = None,
    total_price: Optional[float] = None,
    quote_data: Optional[Dict[str, Any]] = None
) -> Optional[str]:
    """
    Save quote to database (optional)
    Returns quote_id (UUID as string)
    """
    try:
        import json
        import uuid as uuid_lib
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Try to find cabin by cabin_id
            try:
                cabin_uuid = str(uuid_lib.UUID(cabin_id))
            except (ValueError, AttributeError):
                # Not a UUID, try to find by calendar_id or name
                cursor.execute("""
                    SELECT id FROM cabins WHERE calendar_id = %s OR name = %s LIMIT 1
                """, (cabin_id, cabin_id))
                row = cursor.fetchone()
                if row:
                    cabin_uuid = str(row[0])
                else:
                    return None
            
            cursor.execute("""
                INSERT INTO quotes (
                    cabin_id, check_in, check_out, adults, kids, total_price, quote_data
                )
                VALUES (
                    %s::uuid, %s::date, %s::date, %s, %s, %s, %s::jsonb
                )
                RETURNING id::text
            """, (
                cabin_uuid,
                check_in,
                check_out,
                adults,
                kids,
                total_price,
                json.dumps(quote_data) if quote_data else None
            ))
            
            quote_id = cursor.fetchone()[0]
            conn.commit()
            return quote_id
            
    except Exception as e:
        print(f"Error saving quote: {e}")
        return None


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
                        cabin_id_string
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
                        WHERE id = %s::uuid
                    """, (cabin_id,))
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
                
                # Generate UUID for audit log entry
                audit_uuid = str(uuid_lib.uuid4())
                
                cursor.execute("""
                    INSERT INTO audit_log (
                        id, entity_type, entity_id, action, payload
                    )
                    VALUES (
                        %s::uuid, %s, %s, %s, %s::jsonb
                    )
                    RETURNING id::text
                """, (
                    audit_uuid,
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
            
            # Check which columns exist in transactions table
            cursor.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'transactions'
            """)
            columns = {row[0] for row in cursor.fetchall()}
            
            # Generate UUID for transaction id
            transaction_uuid = str(uuid_lib.uuid4())
            
            # Check if id column has default (UUID generation)
            cursor.execute("""
                SELECT column_default 
                FROM information_schema.columns 
                WHERE table_name = 'transactions' AND column_name = 'id'
            """)
            id_default = cursor.fetchone()
            has_uuid_default = id_default and id_default[0] and 'uuid_generate' in str(id_default[0])
            
            # Build query based on available columns
            if 'currency' in columns and 'payment_method' in columns:
                if has_uuid_default:
                    # Let database generate UUID
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
                else:
                    # Explicitly set UUID
                    cursor.execute("""
                        INSERT INTO transactions (
                            id, booking_id, payment_id, amount, currency, status, payment_method
                        )
                        VALUES (
                            %s::uuid, %s::uuid, %s, %s, %s, %s, %s
                        )
                        RETURNING id::text
                    """, (
                        transaction_uuid,
                        booking_uuid,
                        payment_id,
                        amount,
                        currency,
                        status,
                        payment_method
                    ))
            elif 'currency' in columns:
                if has_uuid_default:
                    cursor.execute("""
                        INSERT INTO transactions (
                            booking_id, payment_id, amount, currency, status
                        )
                        VALUES (
                            %s::uuid, %s, %s, %s, %s
                        )
                        RETURNING id::text
                    """, (
                        booking_uuid,
                        payment_id,
                        amount,
                        currency,
                        status
                    ))
                else:
                    cursor.execute("""
                        INSERT INTO transactions (
                            id, booking_id, payment_id, amount, currency, status
                        )
                        VALUES (
                            %s::uuid, %s::uuid, %s, %s, %s, %s
                        )
                        RETURNING id::text
                    """, (
                        transaction_uuid,
                        booking_uuid,
                        payment_id,
                        amount,
                        currency,
                        status
                    ))
            elif 'payment_method' in columns:
                if has_uuid_default:
                    cursor.execute("""
                        INSERT INTO transactions (
                            booking_id, payment_id, amount, status, payment_method
                        )
                        VALUES (
                            %s::uuid, %s, %s, %s, %s
                        )
                        RETURNING id::text
                    """, (
                        booking_uuid,
                        payment_id,
                        amount,
                        status,
                        payment_method
                    ))
                else:
                    cursor.execute("""
                        INSERT INTO transactions (
                            id, booking_id, payment_id, amount, status, payment_method
                        )
                        VALUES (
                            %s::uuid, %s::uuid, %s, %s, %s, %s
                        )
                        RETURNING id::text
                    """, (
                        transaction_uuid,
                        booking_uuid,
                        payment_id,
                        amount,
                        status,
                        payment_method
                    ))
            else:
                # Minimal schema - only required fields
                if has_uuid_default:
                    cursor.execute("""
                        INSERT INTO transactions (
                            booking_id, payment_id, amount, status
                        )
                        VALUES (
                            %s::uuid, %s, %s, %s
                        )
                        RETURNING id::text
                    """, (
                        booking_uuid,
                        payment_id,
                        amount,
                        status
                    ))
                else:
                    cursor.execute("""
                        INSERT INTO transactions (
                            id, booking_id, payment_id, amount, status
                        )
                        VALUES (
                            %s::uuid, %s::uuid, %s, %s, %s
                        )
                        RETURNING id::text
                    """, (
                        transaction_uuid,
                        booking_uuid,
                        payment_id,
                        amount,
                        status
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


def update_transaction_status(
    transaction_id: str,
    status: str,
    payment_method: Optional[str] = None
) -> bool:
    """
    Update transaction status
    
    Args:
        transaction_id: Transaction UUID
        status: New status (pending, completed, failed, refunded)
        payment_method: Payment method if available
    
    Returns:
        True if updated successfully
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Check which columns exist
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'transactions'
        """)
        columns = {row[0] for row in cursor.fetchall()}
        
        if 'payment_method' in columns and 'updated_at' in columns:
            cursor.execute("""
                UPDATE transactions
                SET status = %s, payment_method = %s, updated_at = NOW()
                WHERE id = %s::uuid
            """, (status, payment_method, transaction_id))
        elif 'payment_method' in columns:
            cursor.execute("""
                UPDATE transactions
                SET status = %s, payment_method = %s
                WHERE id = %s::uuid
            """, (status, payment_method, transaction_id))
        else:
            cursor.execute("""
                UPDATE transactions
                SET status = %s
                WHERE id = %s::uuid
            """, (status, transaction_id))
        
        conn.commit()
        return cursor.rowcount > 0


# ============================================
# Agent Chat - Conversations and Messages
# ============================================

def create_conversation(
    customer_id: Optional[str] = None,
    channel: str = "web",
    status: str = "active",
    metadata: Optional[Dict[str, Any]] = None
) -> Optional[str]:
    """
    Create a new conversation
    Returns conversation_id (UUID as string)
    """
    try:
        import json
        import uuid
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Convert customer_id to UUID if provided
            customer_uuid = None
            if customer_id:
                try:
                    customer_uuid = str(uuid.UUID(customer_id))
                except (ValueError, AttributeError):
                    # Not a valid UUID, try to find by email or phone
                    pass
            
            cursor.execute("""
                INSERT INTO conversations (customer_id, channel, status, metadata)
                VALUES (%s::uuid, %s, %s, %s::jsonb)
                RETURNING id::text
            """, (
                customer_uuid,
                channel,
                status,
                json.dumps(metadata) if metadata else None
            ))
            
            conversation_id = cursor.fetchone()[0]
            conn.commit()
            return conversation_id
            
    except Exception as e:
        print(f"Error creating conversation: {e}")
        import traceback
        traceback.print_exc()
        return None


def save_message(
    conversation_id: str,
    role: str,
    content: str,
    metadata: Optional[Dict[str, Any]] = None
) -> Optional[str]:
    """
    Save a message to a conversation
    Returns message_id (UUID as string)
    """
    try:
        import json
        import uuid
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Validate conversation_id
            try:
                conversation_uuid = str(uuid.UUID(conversation_id))
            except (ValueError, AttributeError):
                print(f"Invalid conversation_id: {conversation_id}")
                return None
            
            # Validate role
            if role not in ['user', 'assistant', 'system']:
                print(f"Invalid role: {role}. Must be 'user', 'assistant', or 'system'")
                return None
            
            cursor.execute("""
                INSERT INTO messages (conversation_id, role, content, metadata)
                VALUES (%s::uuid, %s, %s, %s::jsonb)
                RETURNING id::text
            """, (
                conversation_uuid,
                role,
                content,
                json.dumps(metadata) if metadata else None
            ))
            
            message_id = cursor.fetchone()[0]
            conn.commit()
            
            # Save audit log for message
            try:
                save_audit_log(
                    table_name="messages",
                    record_id=message_id,
                    action="INSERT",
                    new_values={
                        "conversation_id": conversation_id,
                        "role": role,
                        "content": content[:100] + "..." if len(content) > 100 else content,  # Truncate for audit
                        "metadata": metadata
                    }
                )
            except Exception as audit_error:
                print(f"Warning: Could not save audit log for message: {audit_error}")
            
            return message_id
            
    except Exception as e:
        print(f"Error saving message: {e}")
        import traceback
        traceback.print_exc()
        return None


def get_conversation(conversation_id: str) -> Optional[Dict[str, Any]]:
    """
    Get conversation by ID with all messages
    """
    try:
        import uuid
        
        with get_db_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            try:
                conversation_uuid = str(uuid.UUID(conversation_id))
            except (ValueError, AttributeError):
                return None
            
            # Get conversation
            cursor.execute("""
                SELECT 
                    id::text as id,
                    customer_id::text as customer_id,
                    channel,
                    status,
                    metadata,
                    created_at,
                    updated_at
                FROM conversations
                WHERE id = %s::uuid
            """, (conversation_uuid,))
            
            conversation = cursor.fetchone()
            if not conversation:
                return None
            
            # Get messages
            cursor.execute("""
                SELECT 
                    id::text as id,
                    role,
                    content,
                    metadata,
                    created_at
                FROM messages
                WHERE conversation_id = %s::uuid
                ORDER BY created_at ASC
            """, (conversation_uuid,))
            
            messages = [dict(row) for row in cursor.fetchall()]
            
            result = dict(conversation)
            result["messages"] = messages
            
            return result
            
    except Exception as e:
        print(f"Error getting conversation: {e}")
        return None


def update_conversation_status(
    conversation_id: str,
    status: str
) -> bool:
    """
    Update conversation status
    """
    try:
        import uuid
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            try:
                conversation_uuid = str(uuid.UUID(conversation_id))
            except (ValueError, AttributeError):
                return False
            
            if status not in ['active', 'closed', 'escalated']:
                return False
            
            cursor.execute("""
                UPDATE conversations
                SET status = %s, updated_at = NOW()
                WHERE id = %s::uuid
            """, (status, conversation_uuid))
            
            conn.commit()
            
            # Save audit log
            try:
                save_audit_log(
                    table_name="conversations",
                    record_id=conversation_id,
                    action="UPDATE",
                    new_values={"status": status}
                )
            except Exception as audit_error:
                print(f"Warning: Could not save audit log: {audit_error}")
            
            return cursor.rowcount > 0
            
    except Exception as e:
        print(f"Error updating conversation status: {e}")
        return False


# ============================================
# Business Facts Functions (A4)
# ============================================

def get_business_fact(fact_key: str) -> Optional[str]:
    """
    Get a business fact by key
    Returns the fact value or None if not found
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT fact_value 
                FROM business_facts 
                WHERE fact_key = %s AND is_active = TRUE
            """, (fact_key,))
            result = cursor.fetchone()
            return result[0] if result else None
    except Exception as e:
        print(f"Error getting business fact: {e}")
        return None


def get_all_business_facts(category: Optional[str] = None) -> Dict[str, Any]:
    """
    Get all active business facts
    Returns a dictionary of fact_key -> {'value': fact_value, 'category': category, 'description': description}
    For backward compatibility, also supports simple fact_key -> fact_value format
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            if category:
                cursor.execute("""
                    SELECT fact_key, fact_value, category, description
                    FROM business_facts 
                    WHERE is_active = TRUE AND category = %s
                """, (category,))
            else:
                cursor.execute("""
                    SELECT fact_key, fact_value, category, description
                    FROM business_facts 
                    WHERE is_active = TRUE
                """)
            results = cursor.fetchall()
            # Return as dict with value and metadata
            return {
                row[0]: {
                    'value': row[1],
                    'category': row[2],
                    'description': row[3]
                }
                for row in results
            }
    except Exception as e:
        print(f"Error getting business facts: {e}")
        return {}


def set_business_fact(fact_key: str, fact_value: str, category: Optional[str] = None, description: Optional[str] = None) -> bool:
    """
    Set or update a business fact
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO business_facts (fact_key, fact_value, category, description, is_active)
                VALUES (%s, %s, %s, %s, TRUE)
                ON CONFLICT (fact_key) 
                DO UPDATE SET 
                    fact_value = EXCLUDED.fact_value,
                    category = COALESCE(EXCLUDED.category, business_facts.category),
                    description = COALESCE(EXCLUDED.description, business_facts.description),
                    updated_at = CURRENT_TIMESTAMP
            """, (fact_key, fact_value, category, description))
            return True
    except Exception as e:
        print(f"Error setting business fact: {e}")
        return False


# ============================================
# FAQ Functions (A4)
# ============================================

def get_approved_faq(question: str) -> Optional[Dict[str, Any]]:
    """
    Search for an approved FAQ that matches the question
    Returns the FAQ dict or None if not found
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            # Search for FAQ where question is similar (case-insensitive)
            cursor.execute("""
                SELECT id, question, answer, usage_count
                FROM faq
                WHERE approved = TRUE 
                AND LOWER(question) LIKE LOWER(%s)
                ORDER BY usage_count DESC
                LIMIT 1
            """, (f"%{question}%",))
            result = cursor.fetchone()
            if result:
                # Increment usage count
                cursor.execute("""
                    UPDATE faq 
                    SET usage_count = usage_count + 1,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (result['id'],))
                return dict(result)
            return None
    except Exception as e:
        print(f"Error getting approved FAQ: {e}")
        return None


def suggest_faq(question: str, answer: str, customer_id: Optional[str] = None) -> Optional[str]:
    """
    Suggest a new FAQ (pending approval)
    Returns the FAQ ID or None if failed
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO faq (question, answer, approved, suggested_by, suggested_answer, suggested_at)
                VALUES (%s, %s, FALSE, %s, %s, CURRENT_TIMESTAMP)
                RETURNING id
            """, (question, answer, customer_id, answer))
            faq_id = cursor.fetchone()[0]
            
            # Save audit log
            try:
                save_audit_log(
                    table_name="faq",
                    record_id=str(faq_id),
                    action="INSERT",
                    new_values={"question": question, "answer": answer, "approved": False}
                )
            except Exception as audit_error:
                print(f"Warning: Could not save audit log: {audit_error}")
            
            return str(faq_id)
    except Exception as e:
        print(f"Error suggesting FAQ: {e}")
        return None


def approve_faq(faq_id: str, approved_by: Optional[str] = None, question: Optional[str] = None, answer: Optional[str] = None) -> bool:
    """
    Approve a FAQ (only Host can do this)
    Can optionally update question and answer during approval
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # First check if FAQ exists and is not already approved
            cursor.execute("""
                SELECT id, approved FROM faq WHERE id = %s
            """, (faq_id,))
            existing = cursor.fetchone()
            
            if not existing:
                print(f"FAQ {faq_id} not found")
                return False
            
            if existing[1]:  # Already approved
                print(f"FAQ {faq_id} is already approved")
                # Still allow updating question/answer if provided
                if question or answer:
                    cursor.execute("""
                        UPDATE faq 
                        SET question = COALESCE(%s, question),
                            answer = COALESCE(%s, answer),
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = %s
                    """, (question, answer, faq_id))
                    conn.commit()
                    return cursor.rowcount > 0
                return False
            
            # If question/answer provided, use them; otherwise use suggested_answer
            if question or answer:
                cursor.execute("""
                    UPDATE faq 
                    SET approved = TRUE,
                        approved_by = %s,
                        approved_at = CURRENT_TIMESTAMP,
                        question = COALESCE(%s, question),
                        answer = COALESCE(%s, COALESCE(suggested_answer, answer)),
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s AND approved = FALSE
                """, (approved_by, question, answer, faq_id))
            else:
                cursor.execute("""
                    UPDATE faq 
                    SET approved = TRUE,
                        approved_by = %s,
                        approved_at = CURRENT_TIMESTAMP,
                        answer = COALESCE(suggested_answer, answer),
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s AND approved = FALSE
                """, (approved_by, faq_id))
            
            conn.commit()
            
            # Save audit log
            try:
                save_audit_log(
                    table_name="faq",
                    record_id=faq_id,
                    action="UPDATE",
                    new_values={"approved": True, "approved_by": approved_by}
                )
            except Exception as audit_error:
                print(f"Warning: Could not save audit log: {audit_error}")
            
            return cursor.rowcount > 0
    except Exception as e:
        print(f"Error approving FAQ: {e}")
        import traceback
        traceback.print_exc()
        return False


def reject_faq(faq_id: str) -> bool:
    """
    Reject a suggested FAQ (delete it)
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM faq WHERE id = %s AND approved = FALSE", (faq_id,))
            return cursor.rowcount > 0
    except Exception as e:
        print(f"Error rejecting FAQ: {e}")
        return False


def get_pending_faqs() -> List[Dict[str, Any]]:
    """
    Get all pending (not approved) FAQs for Host review
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute("""
                SELECT id, question, answer, suggested_answer, suggested_at, created_at
                FROM faq
                WHERE approved = FALSE
                ORDER BY suggested_at DESC, created_at DESC
            """)
            return [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        print(f"Error getting pending FAQs: {e}")
        return []


def get_all_faqs(include_pending: bool = True) -> List[Dict[str, Any]]:
    """
    Get all FAQs (approved and optionally pending)
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            if include_pending:
                cursor.execute("""
                    SELECT id, question, answer, approved, approved_at, approved_by,
                           suggested_answer, suggested_at, usage_count, created_at, updated_at
                    FROM faq
                    ORDER BY approved DESC, approved_at DESC NULLS LAST, created_at DESC
                """)
            else:
                cursor.execute("""
                    SELECT id, question, answer, approved, approved_at, approved_by,
                           suggested_answer, suggested_at, usage_count, created_at, updated_at
                    FROM faq
                    WHERE approved = TRUE
                    ORDER BY approved_at DESC, created_at DESC
                """)
            return [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        print(f"Error getting all FAQs: {e}")
        return []


def update_faq(faq_id: str, question: Optional[str] = None, answer: Optional[str] = None) -> bool:
    """
    Update an existing FAQ (approved or pending)
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # First check if FAQ exists
            cursor.execute("SELECT id FROM faq WHERE id = %s", (faq_id,))
            if not cursor.fetchone():
                print(f"FAQ {faq_id} not found")
                return False
            
            updates = []
            params = []
            
            if question is not None:
                updates.append("question = %s")
                params.append(question)
            if answer is not None:
                updates.append("answer = %s")
                params.append(answer)
            
            if not updates:
                print("No updates provided")
                return False
            
            updates.append("updated_at = CURRENT_TIMESTAMP")
            params.append(faq_id)
            
            query = f"""
                UPDATE faq 
                SET {', '.join(updates)}
                WHERE id = %s
            """
            cursor.execute(query, params)
            conn.commit()
            
            # Save audit log
            try:
                save_audit_log(
                    table_name="faq",
                    record_id=faq_id,
                    action="UPDATE",
                    new_values={"question": question, "answer": answer}
                )
            except Exception as audit_error:
                print(f"Warning: Could not save audit log: {audit_error}")
            
            return cursor.rowcount > 0
    except Exception as e:
        print(f"Error updating FAQ: {e}")
        import traceback
        traceback.print_exc()
        return False


def delete_faq(faq_id: str) -> bool:
    """
    Delete a FAQ (approved or pending)
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM faq WHERE id = %s", (faq_id,))
            
            # Save audit log
            try:
                save_audit_log(
                    table_name="faq",
                    record_id=faq_id,
                    action="DELETE",
                    new_values={}
                )
            except Exception as audit_error:
                print(f"Warning: Could not save audit log: {audit_error}")
            
            return cursor.rowcount > 0
    except Exception as e:
        print(f"Error deleting FAQ: {e}")
        return False


def delete_business_fact(fact_key: str) -> bool:
    """
    Delete a business fact (or mark as inactive)
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            # Mark as inactive instead of deleting
            cursor.execute("""
                UPDATE business_facts 
                SET is_active = FALSE, updated_at = CURRENT_TIMESTAMP
                WHERE fact_key = %s
            """, (fact_key,))
            
            # Save audit log
            try:
                save_audit_log(
                    table_name="business_facts",
                    record_id=fact_key,
                    action="UPDATE",
                    new_values={"is_active": False}
                )
            except Exception as audit_error:
                print(f"Warning: Could not save audit log: {audit_error}")
            
            return cursor.rowcount > 0
    except Exception as e:
        print(f"Error deleting business fact: {e}")
        return False


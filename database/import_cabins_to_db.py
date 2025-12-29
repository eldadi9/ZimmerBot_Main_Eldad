"""
Import cabins from Google Sheets to PostgreSQL database
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add parent directory to path
BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))
load_dotenv(BASE_DIR / ".env")

from src.main import get_credentials_api, read_cabins_from_sheet
from src.db import get_db_connection


def import_cabins():
    """
    Import cabins from Google Sheets to PostgreSQL database
    """
    print("=" * 60)
    print("Importing cabins from Google Sheets to PostgreSQL")
    print("=" * 60)
    
    try:
        # Get credentials and read from Sheets
        print("\n1. Reading cabins from Google Sheets...")
        creds = get_credentials_api()
        cabins = read_cabins_from_sheet(creds)
        print(f"   Found {len(cabins)} cabins in Sheets")
        
        if not cabins:
            print("   ERROR: No cabins found in Sheets!")
            return False
        
        # Connect to database
        print("\n2. Connecting to database...")
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Check if updated_at column exists, add it if missing
            cursor.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'cabins' AND column_name = 'updated_at'
            """)
            has_updated_at = cursor.fetchone() is not None
            
            if not has_updated_at:
                print("   Adding missing 'updated_at' column to cabins table...")
                try:
                    cursor.execute("""
                        ALTER TABLE cabins 
                        ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    """)
                    conn.commit()
                    print("   ✓ Column 'updated_at' added successfully")
                except Exception as e:
                    print(f"   Warning: Could not add 'updated_at' column: {e}")
                    conn.rollback()
            
            imported = 0
            updated = 0
            errors = 0
            
            print("\n3. Importing cabins...")
            for cabin in cabins:
                try:
                    cabin_id_raw = cabin.get("cabin_id") or cabin.get("id")
                    name = cabin.get("name") or "Unknown"
                    area = cabin.get("area")
                    max_adults = cabin.get("max_adults")
                    max_kids = cabin.get("max_kids")
                    features = cabin.get("features")
                    base_price_night = cabin.get("base_price_night") or cabin.get("base_price")
                    weekend_price = cabin.get("weekend_price")
                    images_urls = cabin.get("images_urls") or cabin.get("images")
                    calendar_id = cabin.get("calendar_id") or cabin.get("calendarId")
                    
                    # Generate UUID from cabin_id if it's not already a UUID
                    # Use a deterministic UUID v5 based on cabin_id string
                    import uuid as uuid_lib
                    try:
                        # Try to parse as UUID first
                        cabin_id = str(uuid_lib.UUID(cabin_id_raw))
                    except (ValueError, AttributeError):
                        # If not a valid UUID, generate one deterministically
                        # Use UUID5 with a namespace to ensure same UUID for same cabin_id
                        namespace = uuid_lib.UUID('6ba7b810-9dad-11d1-80b4-00c04fd430c8')  # DNS namespace
                        cabin_id = str(uuid_lib.uuid5(namespace, str(cabin_id_raw)))
                    
                    # Convert features to JSONB if it's a string
                    if isinstance(features, str):
                        # Try to parse as JSON, otherwise store as string
                        import json
                        try:
                            features = json.loads(features)
                        except:
                            features = {"raw": features}
                    
                    # Convert images to array if it's a string
                    if isinstance(images_urls, str):
                        images_urls = [img.strip() for img in images_urls.split(",") if img.strip()]
                    elif not isinstance(images_urls, list):
                        images_urls = []
                    
                    # Check if cabin exists (by cabin_id string in a separate field, or by UUID)
                    # First, let's check if we need to add a cabin_id_string field or use name/calendar_id
                    # For now, we'll check by calendar_id if available, otherwise by name
                    if calendar_id:
                        cursor.execute("""
                            SELECT id FROM cabins WHERE calendar_id = %s
                        """, (calendar_id,))
                    else:
                        cursor.execute("""
                            SELECT id FROM cabins WHERE name = %s
                        """, (name,))
                    
                    exists = cursor.fetchone()
                    
                    if exists:
                        existing_id = exists[0]
                        # Update existing cabin (has_updated_at was checked at start)
                        if has_updated_at:
                            cursor.execute("""
                                UPDATE cabins SET
                                    name = %s,
                                    area = %s,
                                    max_adults = %s,
                                    max_kids = %s,
                                    features = %s::jsonb,
                                    base_price_night = %s,
                                    weekend_price = %s,
                                    images_urls = %s,
                                    calendar_id = %s,
                                    updated_at = CURRENT_TIMESTAMP
                                WHERE id = %s
                            """, (
                                name,
                                area,
                                max_adults,
                                max_kids,
                                json.dumps(features) if features else None,
                                base_price_night,
                                weekend_price,
                                images_urls,
                                calendar_id,
                                existing_id,
                            ))
                        else:
                            # Update without updated_at column
                            cursor.execute("""
                                UPDATE cabins SET
                                    name = %s,
                                    area = %s,
                                    max_adults = %s,
                                    max_kids = %s,
                                    features = %s::jsonb,
                                    base_price_night = %s,
                                    weekend_price = %s,
                                    images_urls = %s,
                                    calendar_id = %s
                                WHERE id = %s
                            """, (
                                name,
                                area,
                                max_adults,
                                max_kids,
                                json.dumps(features) if features else None,
                                base_price_night,
                                weekend_price,
                                images_urls,
                                calendar_id,
                                existing_id,
                            ))
                        updated += 1
                        print(f"   ✓ Updated: {name} (ID: {existing_id}, Original: {cabin_id_raw})")
                    else:
                        # Insert new cabin
                        cursor.execute("""
                            INSERT INTO cabins (
                                id, name, area, max_adults, max_kids,
                                features, base_price_night, weekend_price,
                                images_urls, calendar_id
                            )
                            VALUES (
                                %s::uuid, %s, %s, %s, %s,
                                %s::jsonb, %s, %s,
                                %s, %s
                            )
                        """, (
                            cabin_id,
                            name,
                            area,
                            max_adults,
                            max_kids,
                            json.dumps(features) if features else None,
                            base_price_night,
                            weekend_price,
                            images_urls,
                            calendar_id,
                        ))
                        imported += 1
                        print(f"   + Imported: {name} (ID: {cabin_id}, Original: {cabin_id_raw})")
                
                except Exception as e:
                    errors += 1
                    cabin_name = cabin.get("name", "Unknown")
                    print(f"   ✗ Error importing {cabin_name}: {e}")
            
            conn.commit()
            
            print("\n" + "=" * 60)
            print("Import Summary:")
            print(f"  Imported: {imported}")
            print(f"  Updated: {updated}")
            print(f"  Errors: {errors}")
            print(f"  Total: {len(cabins)}")
            print("=" * 60)
            
            return errors == 0
    
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = import_cabins()
    sys.exit(0 if success else 1)


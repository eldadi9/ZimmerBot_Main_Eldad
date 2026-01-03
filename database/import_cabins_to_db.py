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
            # Check if cabin_id_string column exists, add it if missing
            cursor.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'cabins' AND column_name = 'cabin_id_string'
            """)
            has_cabin_id_string = cursor.fetchone() is not None
            
            if not has_cabin_id_string:
                print("   Adding missing 'cabin_id_string' column to cabins table...")
                try:
                    cursor.execute("""
                        ALTER TABLE cabins 
                        ADD COLUMN cabin_id_string VARCHAR(20)
                    """)
                    cursor.execute("""
                        CREATE INDEX IF NOT EXISTS idx_cabins_cabin_id_string 
                        ON cabins(cabin_id_string)
                    """)
                    conn.commit()
                    print("   ✓ Column 'cabin_id_string' added successfully")
                except Exception as e:
                    print(f"   Warning: Could not add 'cabin_id_string' column: {e}")
                    conn.rollback()
            
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
                    
                    # Check if cabin exists (by UUID first, then by calendar_id, then by name)
                    # First check if UUID already exists
                    cursor.execute("""
                        SELECT id FROM cabins WHERE id = %s::uuid
                    """, (cabin_id,))
                    exists_by_uuid = cursor.fetchone()
                    
                    # Then check by calendar_id if available
                    exists_by_calendar = None
                    if calendar_id:
                        cursor.execute("""
                            SELECT id FROM cabins WHERE calendar_id = %s
                        """, (calendar_id,))
                        exists_by_calendar = cursor.fetchone()
                    
                    # Finally check by name
                    cursor.execute("""
                        SELECT id FROM cabins WHERE name = %s
                    """, (name,))
                    exists_by_name = cursor.fetchone()
                    
                    # Determine which ID to use
                    existing_id = None
                    if exists_by_uuid:
                        existing_id = exists_by_uuid[0]
                    elif exists_by_calendar:
                        existing_id = exists_by_calendar[0]
                    elif exists_by_name:
                        existing_id = exists_by_name[0]
                    
                    if existing_id:
                        # Use existing ID (might be different from generated UUID)
                        cabin_id = str(existing_id)
                    
                    # Handle images - check for local images in zimmers_pic folder
                    import os
                    from pathlib import Path
                    local_images = []
                    if cabin_id_raw and isinstance(cabin_id_raw, str) and len(cabin_id_raw) <= 20:
                        # Check if local images exist
                        pic_dir = BASE_DIR / "zimmers_pic" / cabin_id_raw
                        if pic_dir.exists() and pic_dir.is_dir():
                            for img_file in pic_dir.glob("*.jpg"):
                                local_images.append(f"/zimmers_pic/{cabin_id_raw}/{img_file.name}")
                            for img_file in pic_dir.glob("*.jpeg"):
                                local_images.append(f"/zimmers_pic/{cabin_id_raw}/{img_file.name}")
                            for img_file in pic_dir.glob("*.png"):
                                local_images.append(f"/zimmers_pic/{cabin_id_raw}/{img_file.name}")
                    
                    # Use local images if available, otherwise use images_urls from Sheets
                    final_images = local_images if local_images else images_urls
                    
                    if existing_id:
                        # Update existing cabin (has_updated_at was checked at start)
                        if has_updated_at:
                            if has_cabin_id_string:
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
                                        cabin_id_string = %s,
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
                                    final_images,
                                    calendar_id,
                                    cabin_id_raw if isinstance(cabin_id_raw, str) and len(cabin_id_raw) <= 20 else None,
                                    existing_id,
                                ))
                            else:
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
                                    final_images,
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


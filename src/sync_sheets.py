"""
Sync utilities for Google Sheets ↔ Database
"""
import os
import json
from pathlib import Path
from dotenv import load_dotenv
import gspread
from google.oauth2.credentials import Credentials

BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR / ".env")

from src.main import read_cabins_from_sheet
from src.api_server import get_credentials_api
from src.db import get_db_connection, read_cabins_from_db
from psycopg2.extras import RealDictCursor


def sync_sheets_to_db():
    """
    Sync cabins from Google Sheets to PostgreSQL database
    Detects changes by comparing values before updating
    Returns: (imported_count, updated_count, errors_count, error_list)
    """
    error_list = []  # Collect all errors for detailed reporting
    try:
        creds = get_credentials_api()
        cabins = read_cabins_from_sheet(creds)
        
        if not cabins:
            print("ℹ️ No cabins found in Google Sheets")
            return (0, 0, 0, [])
        
        print(f"Found {len(cabins)} cabins in Google Sheets to sync")
        
        with get_db_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            # Note: We'll commit after each successful operation to prevent cascade failures
            
            # Check if address columns exist
            cursor.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'cabins' 
                AND column_name IN ('cabin_id_string', 'street_name', 'city', 'postal_code')
            """)
            columns = [row['column_name'] for row in cursor.fetchall()]
            has_cabin_id_string = 'cabin_id_string' in columns
            has_street = 'street_name' in columns
            has_city = 'city' in columns
            has_postal = 'postal_code' in columns
            
            imported = 0
            updated = 0
            errors = 0
            
            for cabin in cabins:
                # Use a separate transaction for each cabin to prevent cascade failures
                try:
                    cabin_id_raw = cabin.get("cabin_id") or cabin.get("id") or cabin.get("Cabin ID")
                    name = cabin.get("name") or cabin.get("Name") or "Unknown"
                    area = cabin.get("area") or cabin.get("Area")
                    max_adults = cabin.get("max_adults") or cabin.get("Max Adults")
                    max_kids = cabin.get("max_kids") or cabin.get("Max Kids")
                    features = cabin.get("features") or cabin.get("Features")
                    base_price_night = cabin.get("base_price_night") or cabin.get("Base Price Night") or cabin.get("base_price") or cabin.get("Base Price")
                    weekend_price = cabin.get("weekend_price") or cabin.get("Weekend Price")
                    images_urls_raw = cabin.get("images_urls") or cabin.get("Images URLs") or cabin.get("images")
                    calendar_id = cabin.get("calendar_id") or cabin.get("Calendar ID") or cabin.get("calendarId")
                    
                    # Normalize images_urls to PostgreSQL TEXT[] array format
                    images_urls = None
                    if images_urls_raw:
                        if isinstance(images_urls_raw, list):
                            # Already a list, use as is
                            images_urls = images_urls_raw
                        elif isinstance(images_urls_raw, str):
                            # String - could be comma-separated or single URL
                            if ',' in images_urls_raw:
                                images_urls = [url.strip() for url in images_urls_raw.split(',') if url.strip()]
                            else:
                                # Single URL
                                images_urls = [images_urls_raw.strip()] if images_urls_raw.strip() else None
                        else:
                            # Try to convert to list
                            try:
                                images_urls = list(images_urls_raw) if images_urls_raw else None
                            except:
                                images_urls = None
                    
                    # Address fields (if exist in Sheets)
                    street_name = cabin.get("street_name") or cabin.get("Street name + number") or cabin.get("Street Name")
                    city = cabin.get("city") or cabin.get("City")
                    postal_code = cabin.get("postal_code") or cabin.get("Postal code") or cabin.get("Postal Code")
                    
                    # Normalize features to JSONB - use proper JSON format (json already imported at top)
                    if features:
                        if isinstance(features, str):
                            # Convert comma-separated string to JSON array
                            features_list = [f.strip() for f in features.split(',') if f.strip()]
                            features_json = json.dumps(features_list)  # Use json.dumps for proper JSON format
                        elif isinstance(features, (list, dict)):
                            features_json = json.dumps(features)  # Convert list/dict to JSON string
                        else:
                            # Try to convert to JSON
                            try:
                                features_json = json.dumps(str(features).split(',')) if str(features) else None
                            except:
                                features_json = None
                    else:
                        features_json = None
                    
                    # Check if cabin exists (by calendar_id, cabin_id_string, or name)
                    existing = None
                    if calendar_id:
                        cursor.execute("""
                            SELECT * FROM cabins WHERE calendar_id = %s
                        """, (calendar_id,))
                        existing = cursor.fetchone()
                    
                    if not existing and cabin_id_raw and has_cabin_id_string:
                        cursor.execute("""
                            SELECT * FROM cabins WHERE cabin_id_string = %s
                        """, (cabin_id_raw,))
                        existing = cursor.fetchone()
                    
                    if not existing:
                        cursor.execute("""
                            SELECT * FROM cabins WHERE name = %s
                        """, (name,))
                        existing = cursor.fetchone()
                    
                    if existing:
                        # Compare values to detect actual changes
                        changes = []
                        
                        if existing.get('name') != name:
                            changes.append(('name', name))
                        if existing.get('area') != area:
                            changes.append(('area', area))
                        if existing.get('max_adults') != max_adults:
                            changes.append(('max_adults', max_adults))
                        if existing.get('max_kids') != max_kids:
                            changes.append(('max_kids', max_kids))
                        if existing.get('base_price_night') != base_price_night:
                            changes.append(('base_price_night', base_price_night))
                        if existing.get('weekend_price') != weekend_price:
                            changes.append(('weekend_price', weekend_price))
                        if existing.get('calendar_id') != calendar_id:
                            changes.append(('calendar_id', calendar_id))
                        # Compare images_urls - handle both list and array formats from DB
                        existing_images = existing.get('images_urls')
                        # Normalize existing_images to list for comparison (DB returns as list/tuple)
                        if existing_images is not None:
                            if isinstance(existing_images, (tuple, set)):
                                existing_images = list(existing_images)
                            elif not isinstance(existing_images, list):
                                # If it's a string (shouldn't happen, but handle it)
                                existing_images = [str(existing_images)]
                        
                        # Compare normalized lists (both should be lists now)
                        if existing_images != images_urls:
                            changes.append(('images_urls', images_urls))
                        if existing.get('features') != features_json:
                            changes.append(('features', features_json))
                        
                        # Address fields (if exist)
                        if has_street and existing.get('street_name') != street_name:
                            changes.append(('street_name', street_name))
                        if has_city and existing.get('city') != city:
                            changes.append(('city', city))
                        if has_postal and existing.get('postal_code') != postal_code:
                            changes.append(('postal_code', postal_code))
                        
                        # Only update if there are actual changes
                        if changes:
                            # Build UPDATE query dynamically
                            set_clauses = []
                            values = []
                            for field, value in changes:
                                if field == 'features':
                                    set_clauses.append(f"{field} = %s::jsonb")
                                    values.append(value)
                                elif field == 'images_urls':
                                    # images_urls is TEXT[] array - psycopg2 handles Python lists as arrays
                                    # Ensure it's a list (should already be normalized above)
                                    if value is None:
                                        # For NULL, use explicit NULL without parameter
                                        set_clauses.append(f"{field} = NULL")
                                        # Don't append to values - NULL is handled in SQL
                                    else:
                                        # Ensure it's a list
                                        if not isinstance(value, list):
                                            value = [str(value)]
                                        set_clauses.append(f"{field} = %s::text[]")
                                        values.append(value)
                                else:
                                    set_clauses.append(f"{field} = %s")
                                    values.append(value)
                            
                            set_clauses.append("updated_at = CURRENT_TIMESTAMP")
                            values.append(existing['id'])
                            
                            update_query = f"""
                                UPDATE cabins SET
                                    {', '.join(set_clauses)}
                                WHERE id = %s
                            """
                            
                            cursor.execute(update_query, tuple(values))
                            updated += 1
                            print(f"✅ Updated cabin '{name}': {len(changes)} fields changed")
                            conn.commit()  # Commit after each successful update
                        # else: no changes detected, skip update
                    else:
                        # Insert new
                        import uuid as uuid_lib
                        cabin_id = str(uuid_lib.uuid4())
                        
                        # Build INSERT query dynamically based on available columns
                        # Build lists excluding NULL values to avoid issues
                        columns_to_insert = []
                        values_to_insert = []
                        placeholders = []
                        
                        # Always include these fields
                        columns_to_insert.extend(['id', 'name', 'area', 'max_adults', 'max_kids', 'base_price_night', 'weekend_price'])
                        values_to_insert.extend([cabin_id, name, area, max_adults, max_kids, base_price_night, weekend_price])
                        placeholders.extend(['%s'] * 7)
                        
                        # Handle features (JSONB) - always include
                        # Note: 'columns' is already a list of column name strings (from line 48), not dicts
                        columns_to_insert.append('features')
                        values_to_insert.append(features_json)
                        placeholders.append('%s::jsonb')
                        
                        # Handle images_urls (TEXT[]) - only include if not None
                        # Note: 'columns' is already a list of column name strings, not dicts
                        if 'images_urls' in columns:
                            if images_urls is not None:
                                # Ensure it's a list
                                if not isinstance(images_urls, list):
                                    images_urls = [str(images_urls)]
                                columns_to_insert.append('images_urls')
                                values_to_insert.append(images_urls)
                                placeholders.append('%s::text[]')
                        
                        # Handle calendar_id
                        if calendar_id:
                            columns_to_insert.append('calendar_id')
                            values_to_insert.append(calendar_id)
                            placeholders.append('%s')
                        
                        # Handle optional fields
                        if has_cabin_id_string and cabin_id_raw:
                            columns_to_insert.append('cabin_id_string')
                            values_to_insert.append(cabin_id_raw)
                            placeholders.append('%s')
                        
                        if has_street and street_name:
                            columns_to_insert.append('street_name')
                            values_to_insert.append(street_name)
                            placeholders.append('%s')
                        if has_city and city:
                            columns_to_insert.append('city')
                            values_to_insert.append(city)
                            placeholders.append('%s')
                        if has_postal and postal_code:
                            columns_to_insert.append('postal_code')
                            values_to_insert.append(postal_code)
                            placeholders.append('%s')
                        
                        insert_query = f"""
                            INSERT INTO cabins ({', '.join(columns_to_insert)})
                            VALUES ({', '.join(placeholders)})
                        """
                        
                        cursor.execute(insert_query, tuple(values_to_insert))
                        conn.commit()  # Commit after each successful insert
                        imported += 1
                        print(f"✅ Imported new cabin '{name}' (ID: {cabin_id_raw or 'N/A'})")
                except Exception as e:
                    errors += 1
                    cabin_name = cabin.get('name') or cabin.get('Name') or 'Unknown'
                    error_msg = str(e)
                    print(f"❌ Error syncing cabin '{cabin_name}': {error_msg}")
                    error_list.append({"type": "cabin_sync_error", "cabin": cabin_name, "error": error_msg})
                    # Rollback the transaction for this cabin
                    try:
                        conn.rollback()
                    except:
                        pass
                    import traceback
                    traceback.print_exc()
                    # Continue with next cabin instead of failing completely
                    continue
            
            # No need for final commit - each successful operation already committed
            # Only commit here if there were no operations at all (shouldn't happen)
            print(f"\n✅ Sync Sheets → DB completed: {imported} imported, {updated} updated, {errors} errors")
            return (imported, updated, errors, error_list)
    
    except Exception as e:
        error_msg = str(e)
        print(f"❌ Critical error in sync_sheets_to_db: {error_msg}")
        error_list.append({"type": "critical_error", "error": error_msg})
        import traceback
        traceback.print_exc()
        return (0, 0, 1, error_list)


def sync_db_to_sheets():
    """
    Sync cabins from PostgreSQL database to Google Sheets
    Returns: (updated_count, errors_count)
    """
    try:
        creds = get_credentials_api()
        cabins_db = read_cabins_from_db()
        
        if not cabins_db:
            print("ℹ️ No cabins found in database to sync")
            return (0, 0)
        
        print(f"Found {len(cabins_db)} cabins in database to sync to Sheets")
        
        # Get Google Sheets
        sheet_id = os.getenv("SHEET_ID")
        sheet_name = os.getenv("SHEET_NAME")
        worksheet_name = os.getenv("WORKSHEET_NAME", "Sheet1")
        
        if not sheet_id and not sheet_name:
            raise ValueError("Missing SHEET_ID or SHEET_NAME in .env")
        
        gc = gspread.authorize(creds)
        
        if sheet_id:
            sh = gc.open_by_key(sheet_id.strip())
        else:
            sh = gc.open(sheet_name.strip())
        
        ws = sh.worksheet(worksheet_name)
        
        # Get all records to find existing rows
        all_records = ws.get_all_records()
        
        updated = 0
        errors = 0
        
        for cabin in cabins_db:
            try:
                cabin_id_string = cabin.get('cabin_id_string') or cabin.get('cabin_id', '')
                name = cabin.get('name', '')
                calendar_id = cabin.get('calendar_id', '')
                
                # Find row by cabin_id_string or calendar_id
                row_index = None
                for idx, record in enumerate(all_records, start=2):  # Start from row 2 (skip header)
                    if (record.get('cabin_id') == cabin_id_string or 
                        record.get('calendar_id') == calendar_id or
                        record.get('name') == name):
                        row_index = idx
                        break
                
                if row_index:
                    # Update existing row
                    ws.update_cell(row_index, 1, cabin.get('name', ''))
                    ws.update_cell(row_index, 2, cabin.get('area', ''))
                    ws.update_cell(row_index, 3, cabin.get('max_adults', ''))
                    ws.update_cell(row_index, 4, cabin.get('max_kids', ''))
                    ws.update_cell(row_index, 5, cabin.get('base_price_night', ''))
                    ws.update_cell(row_index, 6, cabin.get('weekend_price', ''))
                    ws.update_cell(row_index, 7, calendar_id)
                    updated += 1
                else:
                    # Append new row
                    ws.append_row([
                        cabin.get('name', ''),
                        cabin.get('area', ''),
                        cabin.get('max_adults', ''),
                        cabin.get('max_kids', ''),
                        cabin.get('base_price_night', ''),
                        cabin.get('weekend_price', ''),
                        calendar_id
                    ])
                    updated += 1
            except Exception as e:
                errors += 1
                cabin_name = cabin.get('name', 'Unknown')
                print(f"❌ Error syncing cabin '{cabin_name}' to Sheets: {e}")
                import traceback
                traceback.print_exc()
                # Continue with next cabin instead of failing completely
                continue
        
        print(f"\n✅ Sync DB → Sheets completed: {updated} rows updated, {errors} errors")
        return (updated, errors)
    
    except Exception as e:
        error_msg = str(e)
        print(f"❌ Critical error in sync_db_to_sheets: {error_msg}")
        import traceback
        traceback.print_exc()
        return (0, 1)

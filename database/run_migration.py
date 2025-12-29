"""
Run migration to add event_id and event_link to bookings table
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add parent directory to path
BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))
load_dotenv(BASE_DIR / ".env")

from src.db import get_db_connection


def run_migration():
    """
    Run migration to add event_id and event_link columns to bookings table
    and create quotes table
    """
    print("=" * 60)
    print("Running Migration: Add event_id and event_link to bookings")
    print("=" * 60)
    
    migration_sql = """
    -- Add event_id and event_link to bookings
    ALTER TABLE bookings 
    ADD COLUMN IF NOT EXISTS event_id VARCHAR(255),
    ADD COLUMN IF NOT EXISTS event_link TEXT;

    -- Create quotes table if it doesn't exist
    CREATE TABLE IF NOT EXISTS quotes (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        cabin_id UUID REFERENCES cabins(id) ON DELETE CASCADE,
        check_in DATE NOT NULL,
        check_out DATE NOT NULL,
        adults INT,
        kids INT,
        total_price DECIMAL(10,2),
        quote_data JSONB,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- Add index for quotes
    CREATE INDEX IF NOT EXISTS idx_quotes_cabin_id ON quotes(cabin_id);
    CREATE INDEX IF NOT EXISTS idx_quotes_dates ON quotes(check_in, check_out);
    CREATE INDEX IF NOT EXISTS idx_quotes_created_at ON quotes(created_at);
    """
    
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Execute migration SQL
            print("\n1. Adding event_id and event_link to bookings table...")
            cursor.execute("""
                ALTER TABLE bookings 
                ADD COLUMN IF NOT EXISTS event_id VARCHAR(255),
                ADD COLUMN IF NOT EXISTS event_link TEXT
            """)
            print("   OK: Columns added successfully")
            
            print("\n2. Creating quotes table...")
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS quotes (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    cabin_id UUID REFERENCES cabins(id) ON DELETE CASCADE,
                    check_in DATE NOT NULL,
                    check_out DATE NOT NULL,
                    adults INT,
                    kids INT,
                    total_price DECIMAL(10,2),
                    quote_data JSONB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            print("   OK: Quotes table created")
            
            print("\n3. Creating indexes...")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_quotes_cabin_id ON quotes(cabin_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_quotes_dates ON quotes(check_in, check_out)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_quotes_created_at ON quotes(created_at)")
            print("   OK: Indexes created")
            
            conn.commit()
            
            print("\n" + "=" * 60)
            print("Migration completed successfully!")
            print("=" * 60)
            return True
            
    except Exception as e:
        print(f"\nERROR: Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_migration()
    sys.exit(0 if success else 1)


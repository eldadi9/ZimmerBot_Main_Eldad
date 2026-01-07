"""
Run migration for A4: Business Facts
"""
import sys
from pathlib import Path

# Add parent directory to path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from src.db import get_db_connection

def run_migration():
    """Run the A4 migration SQL file"""
    migration_file = Path(__file__).parent / "migration_a4_business_facts.sql"
    
    if not migration_file.exists():
        print(f"Error: Migration file not found: {migration_file}")
        return False
    
    print("=" * 60)
    print("Running Migration: A4 Business Facts")
    print("=" * 60)
    
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Read and execute SQL
            with open(migration_file, 'r', encoding='utf-8') as f:
                sql = f.read()
            
            cursor.execute(sql)
            conn.commit()
            
            print("OK: Migration completed successfully!")
            return True
            
    except Exception as e:
        print(f"ERROR: Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = run_migration()
    sys.exit(0 if success else 1)


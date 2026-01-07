"""
Run migration to create Agent Chat tables
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
    Run migration to create Agent Chat tables:
    - conversations
    - messages
    - faq
    - escalations
    """
    print("=" * 60)
    print("Running Migration: Agent Chat Tables")
    print("=" * 60)
    
    migration_file = Path(__file__).parent / "migration_agent_tables.sql"
    
    if not migration_file.exists():
        print(f"ERROR: Migration file not found: {migration_file}")
        return False
    
    try:
        with open(migration_file, 'r', encoding='utf-8') as f:
            migration_sql = f.read()
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            print("\n1. Creating conversations table...")
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    customer_id UUID REFERENCES customers(id) ON DELETE SET NULL,
                    channel VARCHAR(20) NOT NULL CHECK (channel IN ('web', 'whatsapp', 'voice', 'sms')),
                    status VARCHAR(20) NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'closed', 'escalated')),
                    metadata JSONB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            print("   OK: conversations table created")
            
            print("\n2. Creating messages table...")
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
                    role VARCHAR(20) NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
                    content TEXT NOT NULL,
                    metadata JSONB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            print("   OK: messages table created")
            
            print("\n3. Creating faq table...")
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS faq (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    question TEXT NOT NULL,
                    answer TEXT NOT NULL,
                    approved BOOLEAN NOT NULL DEFAULT FALSE,
                    suggested_by UUID REFERENCES customers(id) ON DELETE SET NULL,
                    approved_by UUID,
                    approved_at TIMESTAMP,
                    usage_count INT DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            print("   OK: faq table created")
            
            print("\n4. Creating escalations table...")
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS escalations (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
                    reason TEXT NOT NULL,
                    status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'in_progress', 'resolved', 'closed')),
                    assigned_to UUID,
                    resolution_notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    resolved_at TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            print("   OK: escalations table created")
            
            print("\n5. Creating indexes...")
            # Indexes for conversations
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_conversations_customer_id ON conversations(customer_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_conversations_channel ON conversations(channel)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_conversations_status ON conversations(status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_conversations_created_at ON conversations(created_at)")
            
            # Indexes for messages
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_conversation_id ON messages(conversation_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_role ON messages(role)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_created_at ON messages(created_at)")
            
            # Indexes for faq
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_faq_approved ON faq(approved)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_faq_usage_count ON faq(usage_count)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_faq_created_at ON faq(created_at)")
            
            # Indexes for escalations
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_escalations_conversation_id ON escalations(conversation_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_escalations_status ON escalations(status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_escalations_created_at ON escalations(created_at)")
            print("   OK: Indexes created")
            
            print("\n6. Creating triggers...")
            # Check if update_updated_at_column function exists
            cursor.execute("""
                SELECT EXISTS (
                    SELECT 1 FROM pg_proc 
                    WHERE proname = 'update_updated_at_column'
                )
            """)
            function_exists = cursor.fetchone()[0]
            
            if not function_exists:
                cursor.execute("""
                    CREATE OR REPLACE FUNCTION update_updated_at_column()
                    RETURNS TRIGGER AS $$
                    BEGIN
                        NEW.updated_at = CURRENT_TIMESTAMP;
                        RETURN NEW;
                    END;
                    $$ language 'plpgsql';
                """)
                print("   OK: update_updated_at_column function created")
            
            # Create triggers
            cursor.execute("""
                DROP TRIGGER IF EXISTS update_conversations_updated_at ON conversations;
                CREATE TRIGGER update_conversations_updated_at BEFORE UPDATE ON conversations
                    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
            """)
            cursor.execute("""
                DROP TRIGGER IF EXISTS update_faq_updated_at ON faq;
                CREATE TRIGGER update_faq_updated_at BEFORE UPDATE ON faq
                    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
            """)
            cursor.execute("""
                DROP TRIGGER IF EXISTS update_escalations_updated_at ON escalations;
                CREATE TRIGGER update_escalations_updated_at BEFORE UPDATE ON escalations
                    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
            """)
            print("   OK: Triggers created")
            
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


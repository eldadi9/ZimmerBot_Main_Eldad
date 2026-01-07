"""
סקריפט בדיקה לשלב A1: טבלאות Agent Chat
בודק את כל הנקודות מה-Definition of Done
"""

import psycopg2
from psycopg2.extras import RealDictCursor
import sys
from typing import Dict, List, Tuple
import os
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5432"),
    "database": os.getenv("DB_NAME", "zimmerbot_db"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", "postgres"),
}

REQUIRED_TABLES = [
    "conversations",
    "messages",
    "faq",
    "escalations",
]

REQUIRED_FOREIGN_KEYS = [
    ("conversations", "customer_id", "customers", "id"),
    ("messages", "conversation_id", "conversations", "id"),
    ("faq", "suggested_by", "customers", "id"),
    ("escalations", "conversation_id", "conversations", "id"),
]

REQUIRED_INDEXES = [
    ("conversations", "customer_id"),
    ("conversations", "channel"),
    ("conversations", "status"),
    ("conversations", "created_at"),
    ("messages", "conversation_id"),
    ("messages", "role"),
    ("messages", "created_at"),
    ("faq", "approved"),
    ("faq", "usage_count"),
    ("faq", "created_at"),
    ("escalations", "conversation_id"),
    ("escalations", "status"),
    ("escalations", "created_at"),
]

REQUIRED_CONSTRAINTS = [
    ("conversations", "channel"),
    ("conversations", "status"),
    ("messages", "role"),
    ("escalations", "status"),
]


class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    END = "\033[0m"
    BOLD = "\033[1m"


def print_header(text: str):
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.END}\n")


def print_success(text: str):
    print(f"{Colors.GREEN}✓ {text}{Colors.END}")


def print_error(text: str):
    print(f"{Colors.RED}✗ {text}{Colors.END}")


def print_warning(text: str):
    print(f"{Colors.YELLOW}⚠ {text}{Colors.END}")


def connect_db():
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        conn.autocommit = True
        return conn
    except psycopg2.OperationalError as e:
        print_error(f"לא ניתן להתחבר למסד הנתונים: {e}")
        print_warning("ודא ש-PostgreSQL פועל והפרטים ב-.env נכונים")
        sys.exit(1)


def check_tables_exist(conn) -> Tuple[bool, List[str]]:
    print_header("1. בדיקת קיום טבלאות Agent Chat")

    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
          AND table_type = 'BASE TABLE'
        """
    )

    existing_tables = [row[0] for row in cursor.fetchall()]
    missing_tables = [t for t in REQUIRED_TABLES if t not in existing_tables]
    all_exist = len(missing_tables) == 0

    for table in REQUIRED_TABLES:
        if table in existing_tables:
            print_success(f"טבלה '{table}' קיימת")
        else:
            print_error(f"טבלה '{table}' חסרה")

    cursor.close()
    return all_exist, missing_tables


def check_foreign_keys(conn) -> Tuple[bool, List[str]]:
    print_header("2. בדיקת Foreign Keys (קשרים)")

    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute(
        """
        SELECT
            tc.table_name,
            kcu.column_name,
            ccu.table_name AS foreign_table_name,
            ccu.column_name AS foreign_column_name
        FROM information_schema.table_constraints AS tc
        JOIN information_schema.key_column_usage AS kcu
          ON tc.constraint_name = kcu.constraint_name
         AND tc.table_schema = kcu.table_schema
        JOIN information_schema.constraint_column_usage AS ccu
          ON ccu.constraint_name = tc.constraint_name
         AND ccu.constraint_schema = tc.table_schema
        WHERE tc.constraint_type = 'FOREIGN KEY'
          AND tc.table_schema = 'public'
        """
    )

    existing_fks = cursor.fetchall()
    existing_fk_dict = {
        (fk["table_name"], fk["column_name"]): (
            fk["foreign_table_name"],
            fk["foreign_column_name"],
        )
        for fk in existing_fks
    }

    missing_fks = []
    all_exist = True

    for table, column, ref_table, ref_column in REQUIRED_FOREIGN_KEYS:
        key = (table, column)
        if key in existing_fk_dict:
            expected_ref = (ref_table, ref_column)
            actual_ref = existing_fk_dict[key]
            if actual_ref == expected_ref:
                print_success(f"FK: {table}.{column} → {ref_table}.{ref_column}")
            else:
                print_error(
                    f"FK שגוי: {table}.{column} → {actual_ref[0]}.{actual_ref[1]} (צפוי: {ref_table}.{ref_column})"
                )
                all_exist = False
        else:
            print_error(f"FK חסר: {table}.{column} → {ref_table}.{ref_column}")
            missing_fks.append(f"{table}.{column}")
            all_exist = False

    cursor.close()
    return all_exist, missing_fks


def check_indexes(conn) -> Tuple[bool, List[str]]:
    print_header("3. בדיקת Indexes על שדות חיפוש")

    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT tablename, indexname, indexdef
        FROM pg_indexes
        WHERE schemaname = 'public'
        ORDER BY tablename, indexname
        """
    )

    all_indexes = cursor.fetchall()
    index_dict = {}
    for table, index_name, index_def in all_indexes:
        if table not in index_dict:
            index_dict[table] = []
        index_dict[table].append((index_name, index_def.lower()))

    missing_indexes = []
    all_exist = True

    for table, column in REQUIRED_INDEXES:
        found = False
        if table in index_dict:
            for index_name, index_def in index_dict[table]:
                if column.lower() in index_def:
                    print_success(f"Index: {table}.{column} ({index_name})")
                    found = True
                    break

        if not found:
            print_error(f"Index חסר: {table}.{column}")
            missing_indexes.append(f"{table}.{column}")
            all_exist = False

    cursor.close()
    return all_exist, missing_indexes


def check_constraints(conn) -> Tuple[bool, List[str]]:
    print_header("4. בדיקת Constraints (CHECK constraints)")

    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute(
        """
        SELECT
            tc.table_name,
            tc.constraint_name,
            cc.check_clause
        FROM information_schema.table_constraints tc
        JOIN information_schema.check_constraints cc
            ON tc.constraint_name = cc.constraint_name
           AND tc.constraint_schema = cc.constraint_schema
        WHERE tc.table_schema = 'public'
          AND tc.constraint_type = 'CHECK'
        ORDER BY tc.table_name, tc.constraint_name
        """
    )

    constraints = cursor.fetchall()
    # Build a map of table -> column -> constraint_name
    constraint_map = {}
    for c in constraints:
        table = c["table_name"]
        check_clause = c["check_clause"].lower()
        if table not in constraint_map:
            constraint_map[table] = {}
        
        # Try to identify which column this constraint is for
        if 'channel' in check_clause:
            constraint_map[table]['channel'] = c["constraint_name"]
        elif 'status' in check_clause:
            constraint_map[table]['status'] = c["constraint_name"]
        elif 'role' in check_clause:
            constraint_map[table]['role'] = c["constraint_name"]

    missing_constraints = []
    all_exist = True

    # Check required constraints
    required_map = {
        ('conversations', 'channel'): 'channel',
        ('conversations', 'status'): 'status',
        ('messages', 'role'): 'role',
        ('escalations', 'status'): 'status',
    }

    for (table, column), key in required_map.items():
        if table in constraint_map and key in constraint_map[table]:
            constraint_name = constraint_map[table][key]
            print_success(f"Constraint: {table}.{column} ({constraint_name})")
        else:
            print_error(f"Constraint חסר: {table}.{column}")
            missing_constraints.append(f"{table}.{column}")
            all_exist = False

    cursor.close()
    return all_exist, missing_constraints


def test_insert_and_select() -> bool:
    print_header("5. בדיקת הכנסה ושליפה של נתוני דמה")

    conn = None
    cursor = None

    try:
        conn = psycopg2.connect(**DB_CONFIG)
        conn.autocommit = False
        cursor = conn.cursor()

        # בדיקה 1: יצירת customer (אם לא קיים)
        cursor.execute(
            """
            SELECT id FROM customers WHERE email = 'agent_test@example.com'
            """
        )
        result = cursor.fetchone()
        if result:
            customer_id = result[0]
            print_success(f"משתמש ב-customer קיים: {customer_id}")
        else:
            # לקוח לא קיים, ניצור אותו
            cursor.execute(
                """
                INSERT INTO customers (id, name, email, phone)
                VALUES (gen_random_uuid(), 'לקוח בדיקה Agent', 'agent_test@example.com', '050-9999999')
                RETURNING id
                """
            )
            customer_id = cursor.fetchone()[0]
            print_success(f"הוכנס customer: {customer_id}")

        # בדיקה 2: יצירת conversation
        cursor.execute(
            """
            INSERT INTO conversations (id, customer_id, channel, status, metadata)
            VALUES (gen_random_uuid(), %s, 'web', 'active', '{"test": true}'::jsonb)
            RETURNING id
            """,
            (customer_id,),
        )
        conversation_id = cursor.fetchone()[0]
        print_success(f"הוכנס conversation: {conversation_id}")

        # בדיקה 3: יצירת messages
        cursor.execute(
            """
            INSERT INTO messages (id, conversation_id, role, content, metadata)
            VALUES 
                (gen_random_uuid(), %s, 'user', 'שלום, אני מחפש צימר', '{"intent": "search"}'::jsonb),
                (gen_random_uuid(), %s, 'assistant', 'שלום! אשמח לעזור לך למצוא צימר', '{"confidence": 0.95}'::jsonb)
            RETURNING id
            """,
            (conversation_id, conversation_id),
        )
        message_ids = [row[0] for row in cursor.fetchall()]
        print_success(f"הוכנסו {len(message_ids)} messages")

        # בדיקה 4: יצירת FAQ (לא מאושר)
        cursor.execute(
            """
            INSERT INTO faq (id, question, answer, approved, suggested_by)
            VALUES (gen_random_uuid(), 'מה שעות צ''ק אין?', 'שעות צ''ק אין הן 15:00', FALSE, %s)
            RETURNING id
            """,
            (customer_id,),
        )
        faq_id = cursor.fetchone()[0]
        print_success(f"הוכנס FAQ (לא מאושר): {faq_id}")

        # בדיקה 5: יצירת escalation
        cursor.execute(
            """
            INSERT INTO escalations (id, conversation_id, reason, status)
            VALUES (gen_random_uuid(), %s, 'לקוח מבקש לדבר עם בעלים', 'pending')
            RETURNING id
            """,
            (conversation_id,),
        )
        escalation_id = cursor.fetchone()[0]
        print_success(f"הוכנס escalation: {escalation_id}")

        # בדיקה 6: שליפה - conversation עם messages
        cursor.execute(
            """
            SELECT 
                c.id as conv_id,
                c.channel,
                c.status,
                COUNT(m.id) as message_count
            FROM conversations c
            LEFT JOIN messages m ON c.id = m.conversation_id
            WHERE c.id = %s
            GROUP BY c.id, c.channel, c.status
            """,
            (conversation_id,),
        )
        result = cursor.fetchone()
        if result:
            print_success(
                f"שליפה הצליחה: conversation {result[0]} ({result[1]}, {result[2]}) עם {result[3]} הודעות"
            )
        else:
            print_error("שליפה נכשלה")
            conn.rollback()
            return False

        # בדיקה 7: JSONB metadata
        cursor.execute(
            """
            SELECT metadata
            FROM conversations
            WHERE id = %s
            """,
            (conversation_id,),
        )
        metadata = cursor.fetchone()[0]
        print_success(f"JSONB metadata עובד: {metadata}")

        # בדיקה 8: עדכון FAQ לאישור
        cursor.execute(
            """
            UPDATE faq
            SET approved = TRUE, approved_at = CURRENT_TIMESTAMP
            WHERE id = %s
            RETURNING approved, approved_at
            """,
            (faq_id,),
        )
        approved_result = cursor.fetchone()
        if approved_result and approved_result[0]:
            print_success(f"עדכון FAQ לאישור הצליח: {approved_result[1]}")

        conn.rollback()
        print_success("Rollback בוצע - נתוני בדיקה לא נשמרו")
        return True

    except Exception as e:
        print_error(f"שגיאה בבדיקת הכנסה/שליפה: {e}")
        import traceback

        traceback.print_exc()
        try:
            if conn:
                conn.rollback()
        except Exception:
            pass
        return False

    finally:
        try:
            if cursor:
                cursor.close()
        except Exception:
            pass
        try:
            if conn:
                conn.close()
        except Exception:
            pass


def print_summary(results: Dict):
    print_header("סיכום בדיקות")

    total_checks = 5
    passed_checks = sum(1 for v in results.values() if v)

    print(f"\n{Colors.BOLD}תוצאות:{Colors.END}")
    print(f"  ✓ טבלאות: {'עבר' if results['tables'] else 'נכשל'}")
    print(f"  ✓ Foreign Keys: {'עבר' if results['foreign_keys'] else 'נכשל'}")
    print(f"  ✓ Indexes: {'עבר' if results['indexes'] else 'נכשל'}")
    print(f"  ✓ Constraints: {'עבר' if results['constraints'] else 'נכשל'}")
    print(f"  ✓ הכנסה/שליפה: {'עבר' if results['insert_select'] else 'נכשל'}")

    print(f"\n{Colors.BOLD}ציון כולל: {passed_checks}/{total_checks}{Colors.END}")

    if passed_checks == total_checks:
        print(
            f"\n{Colors.GREEN}{Colors.BOLD}כל הבדיקות עברו. שלב A1 מוכן.{Colors.END}\n"
        )
        return True

    print(
        f"\n{Colors.RED}{Colors.BOLD}יש בעיות שצריך לתקן לפני המעבר לשלב הבא.{Colors.END}\n"
    )
    return False


def main():
    # Set UTF-8 encoding for Windows console
    import sys
    if sys.platform == 'win32':
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    
    print(f"\n{Colors.BOLD}{Colors.BLUE}")
    print("=" * 60)
    print("בדיקת שלב A1: טבלאות Agent Chat")
    print("=" * 60)
    print(Colors.END)

    conn = connect_db()
    results = {}

    try:
        results["tables"], _ = check_tables_exist(conn)
        results["foreign_keys"], _ = check_foreign_keys(conn)
        results["indexes"], _ = check_indexes(conn)
        results["constraints"], _ = check_constraints(conn)
        results["insert_select"] = test_insert_and_select()

        all_passed = print_summary(results)
        return 0 if all_passed else 1

    except Exception as e:
        print_error(f"שגיאה כללית: {e}")
        import traceback

        traceback.print_exc()
        return 1

    finally:
        try:
            conn.close()
        except Exception:
            pass


if __name__ == "__main__":
    sys.exit(main())


"""
סקריפט בדיקה לשלב 1: מודל נתונים (Database Schema)
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
    "cabins",
    "customers",
    "bookings",
    "pricing_rules",
    "transactions",
    "notifications",
    "audit_log",
]

REQUIRED_FOREIGN_KEYS = [
    ("bookings", "cabin_id", "cabins", "id"),
    ("bookings", "customer_id", "customers", "id"),
    ("pricing_rules", "cabin_id", "cabins", "id"),
    ("transactions", "booking_id", "bookings", "id"),
    ("notifications", "booking_id", "bookings", "id"),
    ("notifications", "customer_id", "customers", "id"),
]

REQUIRED_INDEXES = [
    ("cabins", "calendar_id"),
    ("bookings", "cabin_id"),
    ("bookings", "customer_id"),
    ("bookings", "check_in"),
    ("bookings", "check_out"),
    ("bookings", "status"),
    ("customers", "email"),
    ("transactions", "booking_id"),
    ("transactions", "payment_id"),
]

REQUIRED_CONSTRAINTS = [
    ("bookings", "check_dates"),
    ("bookings", "status"),
    ("transactions", "status"),
    ("notifications", "channel"),
    ("notifications", "status"),
    ("audit_log", "action"),
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
        # חשוב: כל הבדיקות הרגילות רצות בלי לפתוח טרנזקציות
        conn.autocommit = True
        return conn
    except psycopg2.OperationalError as e:
        print_error(f"לא ניתן להתחבר למסד הנתונים: {e}")
        print_warning("ודא ש-PostgreSQL פועל והפרטים ב-.env נכונים")
        sys.exit(1)


def check_tables_exist(conn) -> Tuple[bool, List[str]]:
    print_header("1. בדיקת קיום טבלאות")

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
    print_header("4. בדיקת Constraints")

    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute(
        """
        SELECT
            tc.table_name,
            tc.constraint_name,
            tc.constraint_type,
            cc.check_clause
        FROM information_schema.table_constraints tc
        LEFT JOIN information_schema.check_constraints cc
            ON tc.constraint_name = cc.constraint_name
           AND tc.constraint_schema = cc.constraint_schema
        WHERE tc.table_schema = 'public'
          AND tc.constraint_type IN ('CHECK', 'UNIQUE', 'PRIMARY KEY')
        ORDER BY tc.table_name, tc.constraint_name
        """
    )

    constraints = cursor.fetchall()
    constraint_dict = {}
    for c in constraints:
        table = c["table_name"]
        if table not in constraint_dict:
            constraint_dict[table] = []
        constraint_dict[table].append(c["constraint_name"])

    missing_constraints = []
    all_exist = True

    for table, constraint_name in REQUIRED_CONSTRAINTS:
        if table in constraint_dict and constraint_name in constraint_dict[table]:
            print_success(f"Constraint: {table}.{constraint_name}")
        else:
            print_error(f"Constraint חסר: {table}.{constraint_name}")
            missing_constraints.append(f"{table}.{constraint_name}")
            all_exist = False

    cursor.close()
    return all_exist, missing_constraints


def test_insert_and_select() -> bool:
    print_header("5. בדיקת הכנסה ושליפה של נתוני דמה")

    # חיבור נפרד כדי לא להשפיע על הטרנזקציה/מצב session של שאר הבדיקות
    conn = None
    cursor = None

    try:
        conn = psycopg2.connect(**DB_CONFIG)
        conn.autocommit = False
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO customers (id, name, email, phone)
            VALUES (gen_random_uuid(), 'לקוח בדיקה', 'test@example.com', '050-1234567')
            RETURNING id
            """
        )
        customer_id = cursor.fetchone()[0]
        print_success(f"הוכנס customer: {customer_id}")

        cursor.execute(
            """
            INSERT INTO cabins (id, name, area, max_adults, max_kids, base_price_night, weekend_price, calendar_id)
            VALUES (gen_random_uuid(), 'צימר בדיקה', 'גליל', 2, 2, 500.00, 650.00, 'cal_test')
            RETURNING id
            """
        )
        cabin_id = cursor.fetchone()[0]
        print_success(f"הוכנס cabin: {cabin_id}")

        cursor.execute(
            """
            INSERT INTO bookings (id, cabin_id, customer_id, check_in, check_out, adults, kids, status, total_price)
            VALUES (gen_random_uuid(), %s, %s, '2025-02-01', '2025-02-03', 2, 0, 'hold', 1000.00)
            RETURNING id
            """,
            (cabin_id, customer_id),
        )
        booking_id = cursor.fetchone()[0]
        print_success(f"הוכנס booking: {booking_id}")

        cursor.execute(
            """
            SELECT b.id, c.name as customer_name, cab.name as cabin_name, b.status
            FROM bookings b
            JOIN customers c ON b.customer_id = c.id
            JOIN cabins cab ON b.cabin_id = cab.id
            WHERE b.id = %s
            """,
            (booking_id,),
        )

        result = cursor.fetchone()
        if not result:
            print_error("שליפה נכשלה")
            conn.rollback()
            return False

        print_success(f"שליפה הצליחה: {result[1]} הזמין {result[2]} (סטטוס: {result[3]})")

        cursor.execute(
            """
            UPDATE cabins
            SET features = '{"jacuzzi": true, "pool": true, "breakfast": false}'::jsonb
            WHERE id = %s
            RETURNING features
            """,
            (cabin_id,),
        )
        features = cursor.fetchone()[0]
        print_success(f"JSONB עובד: {features}")

        cursor.execute(
            """
            UPDATE cabins
            SET images_urls = ARRAY['https://example.com/img1.jpg', 'https://example.com/img2.jpg']
            WHERE id = %s
            RETURNING images_urls
            """,
            (cabin_id,),
        )
        images = cursor.fetchone()[0]
        print_success(f"Array עובד: {images}")

        conn.rollback()
        print_success("Rollback בוצע - נתוני בדיקה לא נשמרו")
        return True

    except Exception as e:
        print_error(f"שגיאה בבדיקת הכנסה/שליפה: {e}")
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
        print(f"\n{Colors.GREEN}{Colors.BOLD}כל הבדיקות עברו. שלב 1 מוכן.{Colors.END}\n")
        return True

    print(f"\n{Colors.RED}{Colors.BOLD}יש בעיות שצריך לתקן לפני המעבר לשלב הבא.{Colors.END}\n")
    return False


def main():
    print(f"\n{Colors.BOLD}{Colors.BLUE}")
    print("╔" + "=" * 58 + "╗")
    print("║" + " " * 10 + "בדיקת שלב 1: מודל נתונים" + " " * 20 + "║")
    print("╚" + "=" * 58 + "╝")
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

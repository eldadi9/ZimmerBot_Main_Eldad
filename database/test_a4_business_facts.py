"""
בדיקת שלב A4: Business Facts ו-FAQ
"""
import sys
import io
from pathlib import Path

# Add parent directory to path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

# Set UTF-8 encoding for Windows console
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from src.db import (
    get_db_connection,
    get_business_fact,
    get_all_business_facts,
    set_business_fact,
    get_approved_faq,
    suggest_faq,
    approve_faq,
    get_pending_faqs,
    reject_faq
)
from psycopg2.extras import RealDictCursor

def test_business_facts():
    """בדיקת Business Facts"""
    print("=" * 60)
    print("בדיקת Business Facts")
    print("=" * 60)
    
    # Test 1: Get a fact
    print("\n1. בדיקת קבלת fact:")
    check_in = get_business_fact('check_in_time')
    print(f"   check_in_time: {check_in}")
    assert check_in == "15:00", f"Expected '15:00', got '{check_in}'"
    print("   ✓ עבר")
    
    # Test 2: Get all facts
    print("\n2. בדיקת קבלת כל ה-facts:")
    all_facts = get_all_business_facts()
    print(f"   נמצאו {len(all_facts)} facts")
    assert len(all_facts) >= 7, f"Expected at least 7 facts, got {len(all_facts)}"
    print("   ✓ עבר")
    
    # Test 3: Set a new fact
    print("\n3. בדיקת הגדרת fact חדש:")
    success = set_business_fact('test_fact', 'test_value', 'test', 'Test fact')
    assert success, "Failed to set business fact"
    test_value = get_business_fact('test_fact')
    assert test_value == 'test_value', f"Expected 'test_value', got '{test_value}'"
    print("   ✓ עבר")
    
    # Test 4: Update existing fact
    print("\n4. בדיקת עדכון fact קיים:")
    success = set_business_fact('test_fact', 'updated_value', 'test', 'Updated test fact')
    assert success, "Failed to update business fact"
    updated_value = get_business_fact('test_fact')
    assert updated_value == 'updated_value', f"Expected 'updated_value', got '{updated_value}'"
    print("   ✓ עבר")
    
    # Cleanup
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM business_facts WHERE fact_key = 'test_fact'")
        conn.commit()
    
    print("\n✅ כל בדיקות Business Facts עברו!")


def test_faq():
    """בדיקת FAQ"""
    print("\n" + "=" * 60)
    print("בדיקת FAQ")
    print("=" * 60)
    
    # Test 1: Suggest a FAQ
    print("\n1. בדיקת הצעת FAQ:")
    faq_id = suggest_faq(
        question="מה שעות הצק אין?",
        answer="שעות הצק אין הן 15:00",
        customer_id=None
    )
    assert faq_id is not None, "Failed to suggest FAQ"
    print(f"   FAQ ID: {faq_id}")
    print("   ✓ עבר")
    
    # Test 2: Get pending FAQs
    print("\n2. בדיקת קבלת pending FAQs:")
    pending = get_pending_faqs()
    assert len(pending) > 0, "No pending FAQs found"
    print(f"   נמצאו {len(pending)} pending FAQs")
    print("   ✓ עבר")
    
    # Test 3: Try to get approved FAQ (should not find it yet)
    print("\n3. בדיקת חיפוש FAQ מאושר (עדיין לא מאושר):")
    approved = get_approved_faq("מה שעות הצק אין?")
    assert approved is None, "Should not find unapproved FAQ"
    print("   ✓ עבר - FAQ לא נמצא (כצפוי)")
    
    # Test 4: Approve FAQ
    print("\n4. בדיקת אישור FAQ:")
    success = approve_faq(faq_id, approved_by=None)
    assert success, "Failed to approve FAQ"
    print("   ✓ עבר")
    
    # Test 5: Get approved FAQ (should find it now)
    print("\n5. בדיקת חיפוש FAQ מאושר (אחרי אישור):")
    approved = get_approved_faq("מה שעות הצק אין?")
    assert approved is not None, "Should find approved FAQ"
    assert approved['answer'] == "שעות הצק אין הן 15:00", "Wrong answer"
    print(f"   נמצא FAQ: {approved['question']}")
    print(f"   תשובה: {approved['answer']}")
    print("   ✓ עבר")
    
    # Cleanup
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM faq WHERE id = %s", (faq_id,))
        conn.commit()
    
    print("\n✅ כל בדיקות FAQ עברו!")


def main():
    """הרצת כל הבדיקות"""
    print("=" * 60)
    print("בדיקת שלב A4: Business Facts ו-FAQ")
    print("=" * 60)
    
    try:
        test_business_facts()
        test_faq()
        
        print("\n" + "=" * 60)
        print("סיכום בדיקות")
        print("=" * 60)
        print("תוצאות:")
        print("✓ Business Facts: עבר")
        print("✓ FAQ: עבר")
        print("\nציון כולל: 2/2")
        print("כל הבדיקות עברו. שלב A4 מוכן.")
        
    except AssertionError as e:
        print(f"\n❌ בדיקה נכשלה: {e}")
        return False
    except Exception as e:
        print(f"\n❌ שגיאה: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)


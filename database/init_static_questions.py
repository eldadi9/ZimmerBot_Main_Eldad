"""
Initialize static questions as Business Facts or FAQs
This script adds the recommended static questions from A4_BUSINESS_FACTS_EXPLANATION.md
"""
import sys
import os
import io

# Fix Unicode encoding for Windows
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.db import set_business_fact, get_business_fact, suggest_faq, get_approved_faq
from src.db import get_db_connection
from psycopg2.extras import RealDictCursor

def init_static_questions():
    """Add static questions to Business Facts or FAQ"""
    
    # Static questions that should be Business Facts (already exist, but we'll verify)
    business_facts = {
        'check_in_time': {'value': '15:00', 'category': 'hours', 'description': 'שעת צ\'ק אין'},
        'check_out_time': {'value': '11:00', 'category': 'hours', 'description': 'שעת צ\'ק אאוט'},
        'cancellation_policy': {'value': '24 שעות מראש', 'category': 'policies', 'description': 'מדיניות ביטול'},
        'parking': {'value': 'כן, חניה פרטית', 'category': 'amenities', 'description': 'חניה'},
        'pets_allowed': {'value': 'לא מותרות', 'category': 'policies', 'description': 'חיות מחמד'},
        'kosher': {'value': 'לא', 'category': 'policies', 'description': 'כשרות'},
        'wifi': {'value': 'כן, חינם', 'category': 'amenities', 'description': 'WiFi'},
    }
    
    # Additional Business Facts for FAQ questions
    additional_facts = {
        'breakfast_included': {'value': 'לא כלול (אלא אם צוין אחרת)', 'category': 'amenities', 'description': 'ארוחת בוקר'},
        'towels_provided': {'value': 'כן, מסופק', 'category': 'amenities', 'description': 'מגבות'},
        'kitchen_equipped': {'value': 'כן, מטבח מאובזר עם כלים, מקרר, מיקרוגל', 'category': 'kitchen', 'description': 'מטבח'},
    }
    
    print("=" * 60)
    print("Initializing Static Questions")
    print("=" * 60)
    
    # Update/Add Business Facts
    print("\n1. Updating Business Facts...")
    all_facts = {**business_facts, **additional_facts}
    for fact_key, fact_data in all_facts.items():
        existing = get_business_fact(fact_key)
        if existing:
            print(f"  [OK] {fact_key} already exists: {existing}")
        else:
            success = set_business_fact(
                fact_key=fact_key,
                fact_value=fact_data['value'],
                category=fact_data['category'],
                description=fact_data['description']
            )
            if success:
                print(f"  [OK] Added {fact_key}: {fact_data['value']}")
            else:
                print(f"  [FAIL] Failed to add {fact_key}")
    
    # Add FAQ suggestions for questions that need custom answers
    print("\n2. Adding FAQ suggestions...")
    faq_questions = [
        {
            'question': 'איך לבטל הזמנה?',
            'answer': 'ניתן לבטל עד 24 שעות לפני התאריך. לאחר מכן, הביטול כפוף למדיניות הביטול.'
        },
        {
            'question': 'מה כלול במחיר?',
            'answer': 'כלול: WiFi, חניה, מים חמים, מגבות. לא כלול: ארוחות (אלא אם צוין אחרת).'
        },
        {
            'question': 'איך מגיעים?',
            'answer': 'כתובת: [כתובת הצימר]. ניתן להגיע ברכב או בתחבורה ציבורית. פרטים נוספים יישלחו לאחר ההזמנה.'
        },
        {
            'question': 'מה צריך להביא?',
            'answer': 'מומלץ להביא: סבון, שמפו (אם יש העדפה אישית). כל השאר מסופק: מגבות, מים חמים, WiFi.'
        },
    ]
    
    for faq in faq_questions:
        # Check if already exists
        existing = get_approved_faq(faq['question'])
        if existing:
            print(f"  [OK] FAQ already exists: {faq['question']}")
        else:
            # Suggest as FAQ
            faq_id = suggest_faq(
                question=faq['question'],
                answer=faq['answer'],
                customer_id=None
            )
            if faq_id:
                print(f"  [OK] Suggested FAQ: {faq['question']}")
            else:
                print(f"  [FAIL] Failed to suggest FAQ: {faq['question']}")
    
    print("\n" + "=" * 60)
    print("Initialization complete!")
    print("=" * 60)
    print("\nNext steps:")
    print("1. Go to Admin Panel → FAQ & Facts")
    print("2. Review and approve the suggested FAQs")
    print("3. Edit Business Facts if needed")

if __name__ == '__main__':
    init_static_questions()


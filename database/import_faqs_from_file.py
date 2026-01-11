"""
סקריפט לייבוא FAQs ו-Business Facts מקובץ "Question & Answers.txt"
"""
import sys
import os
import re
from pathlib import Path
from typing import List, Dict, Any, Optional
import uuid

# Add parent directory to path
BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))

# Configure stdout for Hebrew
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from src.db import get_db_connection, suggest_faq, approve_faq, set_business_fact
from psycopg2.extras import RealDictCursor


def parse_qna_file(file_path: str) -> Dict[str, Any]:
    """
    קורא ומנתח את קובץ השאלות והתשובות
    מחזיר: {'faqs': [...], 'business_facts': [...]}
    """
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"קובץ לא נמצא: {file_path}")
    
    content = file_path.read_text(encoding='utf-8')
    
    result = {
        'faqs': [],
        'business_facts': []
    }
    
    # חלק 1: שאלות ותשובות בסיסיות (לפני "---")
    # חילוץ שאלות 1-10
    part1_match = re.search(r'^שאלות ותשובות להזמנות אונליין(.*?)---', content, re.DOTALL)
    if part1_match:
        part1_content = part1_match.group(1)
        lines = part1_content.split('\n')
        
        current_question = None
        current_answer = []
        in_answer = False
        
        for line in lines:
            original_line = line
            line = line.strip()
            
            if not line:
                # שורה ריקה - סיום תשובה
                if current_question and current_answer:
                    answer = ' '.join(current_answer).strip()
                    if answer and answer != 'תשובה:':
                        result['faqs'].append({
                            'question': current_question,
                            'answer': answer,
                            'approved': True,
                            'source': 'Question & Answers.txt (part 1 - basic Q&A)'
                        })
                    current_question = None
                    current_answer = []
                    in_answer = False
                continue
            
            # זיהוי שאלה חדשה (מספר + שאלה)
            match = re.match(r'^(\d+)\.?\s+(.+)', line)
            if match:
                # שמור שאלה קודמת אם יש
                if current_question and current_answer:
                    answer = ' '.join(current_answer).strip()
                    if answer and answer != 'תשובה:' and not answer.startswith('תשובה'):
                        result['faqs'].append({
                            'question': current_question,
                            'answer': answer,
                            'approved': True,
                            'source': 'Question & Answers.txt (part 1 - basic Q&A)'
                        })
                
                current_question = match.group(2).strip()
                current_answer = []
                in_answer = False
                continue
            
            # זיהוי "תשובה:" - התחלת תשובה
            if 'תשובה' in line and ':' in line:
                in_answer = True
                # הסר את "תשובה:"
                answer_text = re.sub(r'^תשובה\s*:?\s*', '', line).strip()
                if answer_text:
                    current_answer.append(answer_text)
                continue
            
            # אם אנחנו בתוך תשובה, הוסף את השורה
            if in_answer or current_answer:
                current_answer.append(line)
            elif current_question:
                # אם יש שאלה אבל אין "תשובה:" - אולי התשובה מתחילה מיד
                current_answer.append(line)
                in_answer = True
        
        # הוסף את השאלה האחרונה אם יש
        if current_question and current_answer:
            answer = ' '.join(current_answer).strip()
            if answer and answer != 'תשובה:' and not answer.startswith('תשובה'):
                result['faqs'].append({
                    'question': current_question,
                    'answer': answer,
                    'approved': True,
                    'source': 'Question & Answers.txt (part 1 - basic Q&A)'
                })
    
    # חילוץ מידע על גילאים (Business Fact)
    age_match = re.search(r'מאיזה גיל משלמים\?*\s*\n(.+?)(?=\n\n|\n#|$)', content, re.DOTALL)
    if age_match:
        age_text = age_match.group(1).strip()
        # נסה לחלץ פרטים
        age_lines = [l.strip() for l in age_text.split('\n') if l.strip() and not l.strip().startswith('*')]
        if age_lines:
            age_value = '\n'.join(age_lines)
            result['business_facts'].append({
                'key': 'pricing_by_age',
                'value': age_value,
                'category': 'pricing',
                'description': 'תמחור לפי גיל'
            })
    
    # חילוץ שעות פעילות (Business Facts)
    # שעות משרד קבלה
    reception_match = re.search(r'מהן שעות הפעילות של משרד הקבלה\?*\s*\n(.+?)(?=\n\n|\nקבלת חדרים|$)', content, re.DOTALL)
    if reception_match:
        reception_text = reception_match.group(1).strip()
        result['business_facts'].append({
            'key': 'reception_hours',
            'value': reception_text,
            'category': 'hours',
            'description': 'שעות פעילות משרד הקבלה'
        })
    
    # קבלת חדרים
    checkin_match = re.search(r'קבלת חדרים\s*\n(.+?)(?=\n\n|\nפינוי חדרים|$)', content, re.DOTALL)
    if checkin_match:
        checkin_text = checkin_match.group(1).strip()
        result['business_facts'].append({
            'key': 'check_in_hours',
            'value': checkin_text,
            'category': 'hours',
            'description': 'שעות קבלת חדרים'
        })
    
    # פינוי חדרים
    checkout_match = re.search(r'פינוי חדרים\s*\n(.+?)(?=\n\n|\nהאם יש ארוחות|$)', content, re.DOTALL)
    if checkout_match:
        checkout_text = checkout_match.group(1).strip()
        result['business_facts'].append({
            'key': 'check_out_hours',
            'value': checkout_text,
            'category': 'hours',
            'description': 'שעות פינוי חדרים'
        })
    
    # ארוחות
    meals_match = re.search(r'האם יש ארוחות\?*\s*\n(.+?)(?=\n\n|\nכשרות:|$)', content, re.DOTALL)
    if meals_match:
        meals_text = meals_match.group(1).strip()
        result['business_facts'].append({
            'key': 'meals_available',
            'value': meals_text,
            'category': 'amenities',
            'description': 'ארוחות זמינות'
        })
    
    # כשרות
    kosher_match = re.search(r'כשרות:\s*(.+?)(?=\n\n|\n---|$)', content, re.DOTALL)
    if kosher_match:
        kosher_text = kosher_match.group(1).strip()
        result['business_facts'].append({
            'key': 'kosher_status',
            'value': kosher_text,
            'category': 'policies',
            'description': 'כשרות'
        })
    
    # חלק 2: בנק שאלות ותשובות מורחב (אחרי "---")
    # חיפוש אחר חלק בנק שאלות
    expanded_section = re.search(r'# בנק שאלות ותשובות.*?\n(.*)', content, re.DOTALL)
    if expanded_section:
        expanded_content = expanded_section.group(1)
        
        # חילוץ FAQs עם פורמט מובנה
        faq_blocks = re.split(r'\nID:\s*FAQ-', expanded_content)
        
        for block in faq_blocks[1:]:  # דלג על חלק ראשון ריק
            faq_data = {}
            lines = block.split('\n')
            
            # חילוץ ID
            id_match = re.match(r'(\d+)', lines[0]) if lines else None
            if not id_match:
                continue
            
            # חילוץ שאר השדות
            for line in lines[1:]:
                line = line.strip()
                if not line:
                    continue
                
                if line.startswith('Category:'):
                    faq_data['category'] = line.replace('Category:', '').strip()
                elif line.startswith('Subcategory:'):
                    faq_data['subcategory'] = line.replace('Subcategory:', '').strip()
                elif line.startswith('Question:'):
                    faq_data['question'] = line.replace('Question:', '').strip()
                elif line.startswith('OwnerAnswer:'):
                    faq_data['owner_answer'] = line.replace('OwnerAnswer:', '').strip()
                elif line.startswith('SuggestedAnswer:'):
                    faq_data['suggested_answer'] = line.replace('SuggestedAnswer:', '').strip()
                elif line.startswith('Tags:'):
                    tags_text = line.replace('Tags:', '').strip()
                    faq_data['tags'] = tags_text
                elif line.startswith('Status:'):
                    faq_data['status'] = line.replace('Status:', '').strip()
            
            # הוסף FAQ רק אם יש שאלה
            if 'question' in faq_data:
                # השתמש ב-OwnerAnswer אם קיים ואינו "[בעל הצימר להשלים]"
                if faq_data.get('owner_answer') and faq_data['owner_answer'] not in ['[בעל הצימר להשלים]', '']:
                    answer = faq_data['owner_answer']
                    approved = True
                elif faq_data.get('suggested_answer'):
                    answer = faq_data['suggested_answer']
                    approved = False  # pending approval
                else:
                    continue  # אין תשובה
                
                result['faqs'].append({
                    'question': faq_data['question'],
                    'answer': answer,
                    'approved': approved,
                    'category': faq_data.get('category'),
                    'subcategory': faq_data.get('subcategory'),
                    'tags': faq_data.get('tags'),
                    'source': 'Question & Answers.txt (expanded FAQ bank)'
                })
    
    return result


def import_faqs_to_db(faqs: List[Dict[str, Any]], dry_run: bool = False) -> Dict[str, Any]:
    """
    מייבא FAQs ל-DB
    """
    stats = {
        'imported': 0,
        'approved': 0,
        'pending': 0,
        'errors': 0,
        'errors_list': []
    }
    
    if dry_run:
        print("🔍 DRY RUN - לא נשמר ב-DB")
        print(f"📊 נמצאו {len(faqs)} FAQs לייבוא")
        return stats
    
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            for faq in faqs:
                try:
                    question = faq['question']
                    answer = faq['answer']
                    approved = faq.get('approved', False)
                    
                    # בדוק אם FAQ כבר קיים (לפי שאלה)
                    cursor.execute("""
                        SELECT id, approved FROM faq 
                        WHERE LOWER(question) = LOWER(%s)
                    """, (question,))
                    existing = cursor.fetchone()
                    
                    if existing:
                        # FAQ כבר קיים - עדכן אם צריך
                        existing_id = existing['id']
                        existing_approved = existing['approved']
                        
                        if not existing_approved and approved:
                            # עדכן לאישור
                            success, message = approve_faq(str(existing_id), question=question, answer=answer)
                            if success:
                                stats['approved'] += 1
                                print(f"  ✓ עודכן לאישור: {question[:50]}...")
                            else:
                                stats['errors'] += 1
                                stats['errors_list'].append(f"שגיאה באישור FAQ: {question[:50]}... - {message}")
                        else:
                            print(f"  ⊙ כבר קיים (נדלג): {question[:50]}...")
                        continue
                    
                    # יוצר FAQ חדש
                    if approved:
                        # יוצר ישירות כמאושר
                        faq_id = suggest_faq(question, answer)
                        if faq_id:
                            success, message = approve_faq(faq_id, question=question, answer=answer)
                            if success:
                                stats['imported'] += 1
                                stats['approved'] += 1
                                print(f"  ✅ יובא ואושר: {question[:50]}...")
                            else:
                                stats['errors'] += 1
                                stats['errors_list'].append(f"שגיאה באישור: {question[:50]}... - {message}")
                        else:
                            stats['errors'] += 1
                            stats['errors_list'].append(f"שגיאה ביצירת FAQ: {question[:50]}...")
                    else:
                        # יוצר כממתין לאישור
                        faq_id = suggest_faq(question, answer)
                        if faq_id:
                            stats['imported'] += 1
                            stats['pending'] += 1
                            print(f"  ⏳ יובא כממתין לאישור: {question[:50]}...")
                        else:
                            stats['errors'] += 1
                            stats['errors_list'].append(f"שגיאה ביצירת FAQ: {question[:50]}...")
                    
                except Exception as e:
                    stats['errors'] += 1
                    error_msg = f"שגיאה ב-FAQ: {faq.get('question', 'Unknown')[:50]}... - {str(e)}"
                    stats['errors_list'].append(error_msg)
                    print(f"  ❌ {error_msg}")
    
    except Exception as e:
        print(f"❌ שגיאה כללית בייבוא FAQs: {e}")
        import traceback
        traceback.print_exc()
    
    return stats


def import_business_facts_to_db(facts: List[Dict[str, Any]], dry_run: bool = False) -> Dict[str, Any]:
    """
    מייבא Business Facts ל-DB
    """
    stats = {
        'imported': 0,
        'updated': 0,
        'errors': 0,
        'errors_list': []
    }
    
    if dry_run:
        print("🔍 DRY RUN - לא נשמר ב-DB")
        print(f"📊 נמצאו {len(facts)} Business Facts לייבוא")
        return stats
    
    for fact in facts:
        try:
            key = fact['key']
            value = fact['value']
            category = fact.get('category', 'general')
            description = fact.get('description', '')
            
            # set_business_fact יוצר או מעדכן
            success = set_business_fact(key, value, category, description)
            
            if success:
                # בדוק אם זה חדש או עדכון
                with get_db_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT created_at, updated_at FROM business_facts 
                        WHERE fact_key = %s
                    """, (key,))
                    existing = cursor.fetchone()
                    
                    if existing:
                        # בדוק אם זה עדכון או חדש (לפי created_at == updated_at)
                        if existing[0] == existing[1]:
                            stats['imported'] += 1
                            print(f"  ✅ יובא: {key} = {value[:50]}...")
                        else:
                            stats['updated'] += 1
                            print(f"  🔄 עודכן: {key} = {value[:50]}...")
                    else:
                        stats['imported'] += 1
                        print(f"  ✅ יובא: {key} = {value[:50]}...")
            else:
                stats['errors'] += 1
                error_msg = f"שגיאה ב-Business Fact: {key}"
                stats['errors_list'].append(error_msg)
                print(f"  ❌ {error_msg}")
                
        except Exception as e:
            stats['errors'] += 1
            error_msg = f"שגיאה ב-Business Fact: {fact.get('key', 'Unknown')} - {str(e)}"
            stats['errors_list'].append(error_msg)
            print(f"  ❌ {error_msg}")
    
    return stats


def main():
    """
    פונקציה ראשית לייבוא
    """
    print("=" * 60)
    print("ייבוא FAQs ו-Business Facts מקובץ Question & Answers.txt")
    print("=" * 60)
    
    # נתיב לקובץ
    file_path = BASE_DIR / "Question & Answers.txt"
    
    if not file_path.exists():
        print(f"❌ קובץ לא נמצא: {file_path}")
        return
    
    # אפשרות dry-run
    dry_run = '--dry-run' in sys.argv or '-d' in sys.argv
    
    try:
        # 1. קריאה וניתוח הקובץ
        print(f"\n📖 קורא קובץ: {file_path}")
        data = parse_qna_file(str(file_path))
        
        print(f"\n📊 סיכום ניתוח:")
        print(f"   FAQs: {len(data['faqs'])}")
        print(f"   Business Facts: {len(data['business_facts'])}")
        
        # 2. ייבוא FAQs
        print(f"\n{'=' * 60}")
        print(f"📝 ייבוא FAQs ({len(data['faqs'])} items)")
        print("=" * 60)
        faq_stats = import_faqs_to_db(data['faqs'], dry_run=dry_run)
        
        # 3. ייבוא Business Facts
        print(f"\n{'=' * 60}")
        print(f"📋 ייבוא Business Facts ({len(data['business_facts'])} items)")
        print("=" * 60)
        facts_stats = import_business_facts_to_db(data['business_facts'], dry_run=dry_run)
        
        # 4. סיכום
        print(f"\n{'=' * 60}")
        print("📊 סיכום ייבוא")
        print("=" * 60)
        
        print(f"\nFAQs:")
        print(f"  ✅ יובאו: {faq_stats['imported']}")
        print(f"  ✓ אושרו: {faq_stats['approved']}")
        print(f"  ⏳ ממתינים לאישור: {faq_stats['pending']}")
        print(f"  ❌ שגיאות: {faq_stats['errors']}")
        
        if faq_stats['errors_list']:
            print(f"\n  שגיאות FAQs:")
            for error in faq_stats['errors_list'][:10]:  # הצג 10 ראשונות
                print(f"    - {error}")
        
        print(f"\nBusiness Facts:")
        print(f"  ✅ יובאו: {facts_stats['imported']}")
        print(f"  🔄 עודכנו: {facts_stats['updated']}")
        print(f"  ❌ שגיאות: {facts_stats['errors']}")
        
        if facts_stats['errors_list']:
            print(f"\n  שגיאות Business Facts:")
            for error in facts_stats['errors_list'][:10]:
                print(f"    - {error}")
        
        if dry_run:
            print(f"\n⚠️  זה היה DRY RUN - לא נשמר ב-DB")
            print(f"   להרצה אמיתית, הסר את הארגומנט --dry-run")
        else:
            print(f"\n✅ הייבוא הושלם בהצלחה!")
        
    except Exception as e:
        print(f"\n❌ שגיאה כללית: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()

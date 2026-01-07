"""
בדיקת שלב A3: Tool Routing - 3 תרחישים מקצה לקצה
"""
import requests
import json
import sys
import io

# Set UTF-8 encoding for Windows console
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

def print_header(text):
    print("\n" + "=" * 60)
    print(text)
    print("=" * 60 + "\n")

def test_scenario_1_availability():
    """תרחיש 1: שאילתת זמינות"""
    print_header("תרחיש 1: שאילתת זמינות")
    
    url = "http://127.0.0.1:8000/agent/chat"
    
    # תאריכים עתידיים (לפחות שבוע קדימה)
    from datetime import datetime, timedelta
    check_in = (datetime.now() + timedelta(days=10)).strftime("%Y-%m-%d")
    check_out = (datetime.now() + timedelta(days=12)).strftime("%Y-%m-%d")
    
    data = {
        "message": "מה הזמינות בתאריכים 15-17 במרץ?",
        "channel": "web",
        "context": {
            "check_in": check_in,
            "check_out": check_out,
            "guests": 2
        }
    }
    
    print(f"📤 שולח: {data['message']}")
    print(f"📅 תאריכים: {check_in} → {check_out}")
    
    try:
        response = requests.post(url, json=data)
        response.raise_for_status()
        result = response.json()
        
        print(f"✅ תגובה התקבלה:")
        print(f"   Conversation ID: {result.get('conversation_id')}")
        print(f"   Answer: {result.get('answer')}")
        print(f"   Actions: {result.get('actions_suggested')}")
        print(f"   Confidence: {result.get('confidence')}")
        
        # בדוק אם יש תוצאות זמינות
        if 'availability' in result.get('actions_suggested', []):
            print(f"   ✓ זיהוי כוונה: availability")
            return True
        else:
            print(f"   ⚠️  לא זיהה availability")
            return False
            
    except requests.exceptions.ConnectionError:
        print("❌ שגיאה: לא ניתן להתחבר לשרת")
        print("   ודא שהשרת רץ: run_api.bat")
        return False
    except Exception as e:
        print(f"❌ שגיאה: {e}")
        return False


def test_scenario_2_quote():
    """תרחיש 2: קבלת הצעת מחיר"""
    print_header("תרחיש 2: קבלת הצעת מחיר")
    
    url = "http://127.0.0.1:8000/agent/chat"
    
    # תאריכים עתידיים
    from datetime import datetime, timedelta
    check_in = (datetime.now() + timedelta(days=10)).strftime("%Y-%m-%d")
    check_out = (datetime.now() + timedelta(days=12)).strftime("%Y-%m-%d")
    
    data = {
        "message": "כמה עולה צימר ZB01 בתאריכים 15-17 במרץ?",
        "channel": "web",
        "context": {
            "cabin_id": "ZB01",
            "check_in": check_in,
            "check_out": check_out,
            "guests": 2
        }
    }
    
    print(f"📤 שולח: {data['message']}")
    print(f"🏠 צימר: ZB01")
    print(f"📅 תאריכים: {check_in} → {check_out}")
    
    try:
        response = requests.post(url, json=data)
        response.raise_for_status()
        result = response.json()
        
        print(f"✅ תגובה התקבלה:")
        print(f"   Conversation ID: {result.get('conversation_id')}")
        print(f"   Answer: {result.get('answer')}")
        print(f"   Actions: {result.get('actions_suggested')}")
        print(f"   Confidence: {result.get('confidence')}")
        
        # בדוק אם יש תוצאות quote
        if 'quote' in result.get('actions_suggested', []):
            print(f"   ✓ זיהוי כוונה: quote")
            return True
        else:
            print(f"   ⚠️  לא זיהה quote")
            return False
            
    except Exception as e:
        print(f"❌ שגיאה: {e}")
        return False


def test_scenario_3_hold():
    """תרחיש 3: יצירת Hold"""
    print_header("תרחיש 3: יצירת Hold")
    
    url = "http://127.0.0.1:8000/agent/chat"
    
    # תאריכים עתידיים
    from datetime import datetime, timedelta
    check_in = (datetime.now() + timedelta(days=10)).strftime("%Y-%m-%d")
    check_out = (datetime.now() + timedelta(days=12)).strftime("%Y-%m-%d")
    
    data = {
        "message": "אני רוצה לשריין את צימר ZB01 בתאריכים 15-17 במרץ",
        "channel": "web",
        "context": {
            "cabin_id": "ZB01",
            "check_in": check_in,
            "check_out": check_out,
            "guests": 2
        }
    }
    
    print(f"📤 שולח: {data['message']}")
    print(f"🏠 צימר: ZB01")
    print(f"📅 תאריכים: {check_in} → {check_out}")
    
    try:
        response = requests.post(url, json=data)
        response.raise_for_status()
        result = response.json()
        
        print(f"✅ תגובה התקבלה:")
        print(f"   Conversation ID: {result.get('conversation_id')}")
        print(f"   Answer: {result.get('answer')}")
        print(f"   Actions: {result.get('actions_suggested')}")
        print(f"   Confidence: {result.get('confidence')}")
        
        # בדוק אם יש תוצאות hold
        if 'hold' in result.get('actions_suggested', []):
            print(f"   ✓ זיהוי כוונה: hold")
            return True
        else:
            print(f"   ⚠️  לא זיהה hold")
            return False
            
    except Exception as e:
        print(f"❌ שגיאה: {e}")
        return False


def main():
    print("\n" + "=" * 60)
    print("בדיקת שלב A3: Tool Routing - 3 תרחישים מקצה לקצה")
    print("=" * 60)
    
    results = []
    
    # תרחיש 1: זמינות
    results.append(("תרחיש 1: זמינות", test_scenario_1_availability()))
    
    # תרחיש 2: מחיר
    results.append(("תרחיש 2: מחיר", test_scenario_2_quote()))
    
    # תרחיש 3: Hold
    results.append(("תרחיש 3: Hold", test_scenario_3_hold()))
    
    # סיכום
    print_header("סיכום בדיקות")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ עבר" if result else "❌ נכשל"
        print(f"  {status} - {name}")
    
    print(f"\nציון: {passed}/{total}")
    
    if passed == total:
        print("\n✅ כל התרחישים עברו בהצלחה!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} תרחישים נכשלו")
        return 1


if __name__ == "__main__":
    sys.exit(main())


"""
בדיקה פשוטה ל-endpoint /agent/chat
"""
import requests
import json
import sys
import io

# Set UTF-8 encoding for Windows console
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

def test_agent_chat():
    """בדיקת endpoint /agent/chat"""
    
    url = "http://127.0.0.1:8000/agent/chat"
    
    # בדיקה 1: הודעה פשוטה
    print("=" * 60)
    print("בדיקה 1: הודעה פשוטה")
    print("=" * 60)
    
    data1 = {
        "message": "שלום, אני מחפש צימר",
        "channel": "web"
    }
    
    try:
        response = requests.post(url, json=data1)
        response.raise_for_status()
        result = response.json()
        
        print(f"✅ תגובה התקבלה:")
        print(f"   Conversation ID: {result.get('conversation_id')}")
        print(f"   Answer: {result.get('answer')}")
        print(f"   Actions: {result.get('actions_suggested')}")
        print(f"   Confidence: {result.get('confidence')}")
        print()
        
        conversation_id = result.get('conversation_id')
        
    except requests.exceptions.ConnectionError:
        print("❌ שגיאה: לא ניתן להתחבר לשרת")
        print("   ודא שהשרת רץ: run_api.bat")
        return False
    except requests.exceptions.HTTPError as e:
        print(f"❌ שגיאת HTTP: {e}")
        if hasattr(e.response, 'text'):
            print(f"   פרטים: {e.response.text}")
        return False
    except Exception as e:
        print(f"❌ שגיאה: {e}")
        return False
    
    # בדיקה 2: הודעה עם context
    print("=" * 60)
    print("בדיקה 2: הודעה עם context")
    print("=" * 60)
    
    data2 = {
        "message": "מה המחיר לצימר ZB01 בתאריכים 15-17 במרץ?",
        "channel": "web",
        "context": {
            "check_in": "2026-03-15",
            "check_out": "2026-03-17",
            "guests": 2,
            "cabin_id": "ZB01"
        }
    }
    
    try:
        response = requests.post(url, json=data2)
        response.raise_for_status()
        result = response.json()
        
        print(f"✅ תגובה התקבלה:")
        print(f"   Conversation ID: {result.get('conversation_id')}")
        print(f"   Answer: {result.get('answer')}")
        print(f"   Actions: {result.get('actions_suggested')}")
        print(f"   Confidence: {result.get('confidence')}")
        print()
        
    except Exception as e:
        print(f"❌ שגיאה: {e}")
        return False
    
    # בדיקה 3: בדיקת שיחה ב-DB
    if conversation_id:
        print("=" * 60)
        print("בדיקה 3: בדיקת שיחה ב-DB")
        print("=" * 60)
        
        admin_url = f"http://127.0.0.1:8000/admin/audit?table_name=messages&limit=5"
        
        try:
            response = requests.get(admin_url)
            response.raise_for_status()
            audit_logs = response.json()
            
            print(f"✅ נמצאו {len(audit_logs)} רשומות audit ל-messages")
            for log in audit_logs[:3]:
                print(f"   - {log.get('action')} on {log.get('table_name')} at {log.get('created_at')}")
            print()
            
        except Exception as e:
            print(f"⚠️  לא ניתן לבדוק audit logs: {e}")
    
    print("=" * 60)
    print("✅ כל הבדיקות הושלמו!")
    print("=" * 60)
    return True

if __name__ == "__main__":
    test_agent_chat()


"""
דוגמה לשימוש ב-/quote endpoint
"""
import requests
import json

# הפעל את השרת קודם:
# python -m uvicorn src.api_server:app --reload

def test_quote():
    """שולח בקשה ל-/quote endpoint"""
    
    url = "http://127.0.0.1:8000/quote"
    
    data = {
        "cabin_id": "cabin-1",
        "check_in": "2026-02-14 15:00",
        "check_out": "2026-02-16 11:00",
        "adults": 2,
        "kids": 0,
        "addons": [
            {"name": "ארוחת בוקר", "price": 100}
        ]
    }
    
    print("📤 שולח בקשה ל-/quote...")
    print(f"URL: {url}")
    print(f"Data: {json.dumps(data, ensure_ascii=False, indent=2)}")
    print()
    
    try:
        response = requests.post(url, json=data)
        response.raise_for_status()
        
        result = response.json()
        
        print("✅ תגובה התקבלה:")
        print("=" * 60)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        print("=" * 60)
        
        # הדפס breakdown מפורט
        print("\n📊 Breakdown מפורט:")
        print("-" * 60)
        print(f"צימר: {result.get('cabin_name', 'N/A')}")
        print(f"תאריכים: {result.get('check_in')} → {result.get('check_out')}")
        print(f"מספר לילות: {result.get('nights')}")
        print()
        print(f"לילות רגילים: {result.get('regular_nights')}")
        print(f"לילות סופ\"ש: {result.get('weekend_nights')}")
        print(f"לילות חג: {result.get('holiday_nights')}")
        print(f"לילות עונה גבוהה: {result.get('high_season_nights')}")
        print()
        print(f"מחיר בסיס: {result.get('base_total')}₪")
        print(f"תוספת סופ\"ש: {result.get('weekend_surcharge')}₪")
        print(f"תוספת חגים: {result.get('holiday_surcharge')}₪")
        print(f"תוספת עונה: {result.get('high_season_surcharge')}₪")
        print(f"תוספות: {result.get('addons_total')}₪")
        print(f"סה\"כ ביניים: {result.get('subtotal')}₪")
        
        discount = result.get('discount', {})
        if discount.get('amount', 0) > 0:
            print(f"הנחה ({discount.get('percent', 0)}%): -{discount.get('amount', 0)}₪")
            print(f"סיבה: {discount.get('reason', 'N/A')}")
        
        print(f"סה\"כ סופי: {result.get('total_price')}₪")
        print("-" * 60)
        
    except requests.exceptions.ConnectionError:
        print("❌ שגיאה: לא ניתן להתחבר לשרת")
        print("   ודא שהשרת רץ: python -m uvicorn src.api_server:app --reload")
    except requests.exceptions.HTTPError as e:
        print(f"❌ שגיאת HTTP: {e}")
        if hasattr(e.response, 'text'):
            print(f"   פרטים: {e.response.text}")
    except Exception as e:
        print(f"❌ שגיאה: {e}")

if __name__ == "__main__":
    test_quote()


"""
Stage 3: Pricing Engine Tests
Tests that the pricing engine calculates prices correctly with all features
"""
import sys
import os
from pathlib import Path
from datetime import datetime, date, timedelta

# תיקון encoding ל-PowerShell
if sys.platform == "win32":
    # הגדר environment variable
    os.environ["PYTHONIOENCODING"] = "utf-8"
    try:
        # נסה לתקן את encoding של stdout/stderr
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        elif hasattr(sys.stdout, 'buffer'):
            # Python 3 - נסה דרך אחרת
            import io
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace", line_buffering=True)
    except Exception:
        # אם נכשל, נמשיך בלי תיקון
        pass

# הוסף את src ל-path
BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))

from src.pricing import PricingEngine

def test_basic_pricing():
    """Test 1: Basic pricing"""
    print("Check 1: Basic pricing...")
    
    engine = PricingEngine()
    cabin = {
        "base_price_night": 500.0,
        "weekend_price": 650.0
    }
    
    check_in = datetime(2026, 2, 1, 15, 0)  # ראשון
    check_out = datetime(2026, 2, 3, 11, 0)  # שלישי (2 לילות)
    
    result = engine.calculate_price_breakdown(cabin, check_in, check_out)
    
    assert result["nights"] == 2, f"Expected 2 nights, got {result['nights']}"
    assert result["regular_nights"] == 2, f"Expected 2 regular nights, got {result['regular_nights']}"
    assert result["weekend_nights"] == 0, f"Expected 0 weekend nights, got {result['weekend_nights']}"
    assert result["total"] == 1000.0, f"Expected 1000, got {result['total']}"
    
    print("PASS: Check 1 passed - Basic pricing correct")


def test_weekend_pricing():
    """Test 2: Weekend pricing"""
    print("\nCheck 2: Weekend pricing...")
    
    engine = PricingEngine()
    cabin = {
        "base_price_night": 500.0,
        "weekend_price": 650.0
    }
    
    check_in = datetime(2026, 2, 6, 15, 0)  # שישי
    check_out = datetime(2026, 2, 8, 11, 0)  # ראשון (2 לילות - שישי ושבת)
    
    result = engine.calculate_price_breakdown(cabin, check_in, check_out)
    
    assert result["nights"] == 2, f"Expected 2 nights, got {result['nights']}"
    assert result["weekend_nights"] == 2, f"Expected 2 weekend nights, got {result['weekend_nights']}"
    assert result["total"] == 1300.0, f"Expected 1300 (2x650), got {result['total']}"
    
    print("PASS: Check 2 passed - Weekend pricing correct")


def test_holiday_pricing():
    """Test 3: Holiday pricing"""
    print("\nCheck 3: Holiday pricing...")
    
    engine = PricingEngine()
    cabin = {
        "base_price_night": 500.0,
        "weekend_price": 650.0
    }
    
    # יום העצמאות 2026 - 14 במאי (חמישי)
    check_in = datetime(2026, 5, 14, 15, 0)
    check_out = datetime(2026, 5, 15, 11, 0)  # לילה אחד
    
    result = engine.calculate_price_breakdown(cabin, check_in, check_out)
    
    assert result["nights"] == 1, f"Expected 1 night, got {result['nights']}"
    assert result["holiday_nights"] == 1, f"Expected 1 holiday night, got {result['holiday_nights']}"
    # חג: 500 + 50% = 750
    assert result["total"] == 750.0, f"Expected 750 (500 + 50%), got {result['total']}"
    
    print("PASS: Check 3 passed - Holiday pricing correct")


def test_discounts():
    """Test 4: Discounts by stay duration"""
    print("\nCheck 4: Discounts by stay duration...")
    
    engine = PricingEngine()
    cabin = {
        "base_price_night": 500.0,
        "weekend_price": 650.0
    }
    
    # שבוע (7 לילות) - מתחיל ביום ראשון, נגמר ביום ראשון
    # ראשון-חמישי (5 לילות רגילים) + שישי-שבת (2 לילות סופ"ש)
    check_in = datetime(2026, 2, 1, 15, 0)  # ראשון
    check_out = datetime(2026, 2, 8, 11, 0)  # ראשון הבא
    
    result = engine.calculate_price_breakdown(cabin, check_in, check_out)
    
    assert result["nights"] == 7, f"Expected 7 nights, got {result['nights']}"
    
    # חישוב נכון: 5 לילות רגילים × 500 + 2 לילות סופ"ש × 650 = 2500 + 1300 = 3800
    # הנחה 10% על 3800 = 380, סה"כ 3420
    expected_base = (5 * 500) + (2 * 650)  # 2500 + 1300 = 3800
    expected_discount = expected_base * 0.1  # 380
    expected_total = expected_base - expected_discount  # 3420
    
    assert result["regular_nights"] == 5, f"Expected 5 regular nights, got {result['regular_nights']}"
    assert result["weekend_nights"] == 2, f"Expected 2 weekend nights, got {result['weekend_nights']}"
    assert result["base_total"] == expected_base, f"Expected {expected_base} base, got {result['base_total']}"
    assert result["discount"]["percent"] == 10.0, f"Expected 10% discount, got {result['discount']['percent']}%"
    assert abs(result["discount"]["amount"] - expected_discount) < 0.01, f"Expected {expected_discount} discount, got {result['discount']['amount']}"
    assert abs(result["total"] - expected_total) < 0.01, f"Expected {expected_total} total, got {result['total']}"
    
    print("PASS: Check 4 passed - Discounts correct")


def test_addons():
    """Test 5: Addons"""
    print("\nCheck 5: Addons...")
    
    engine = PricingEngine()
    cabin = {
        "base_price_night": 500.0,
        "weekend_price": 650.0
    }
    
    check_in = datetime(2026, 2, 1, 15, 0)
    check_out = datetime(2026, 2, 3, 11, 0)  # 2 לילות
    
    addons = [
        {"name": "ארוחת בוקר", "price": 100.0},  # 2 אנשים × 50
        {"name": "צ'ק אין מוקדם", "price": 100.0}
    ]
    
    result = engine.calculate_price_breakdown(cabin, check_in, check_out, addons=addons)
    
    assert result["nights"] == 2, f"Expected 2 nights, got {result['nights']}"
    assert result["base_total"] == 1000.0, f"Expected 1000 base, got {result['base_total']}"
    assert result["addons_total"] == 200.0, f"Expected 200 addons, got {result['addons_total']}"
    assert result["total"] == 1200.0, f"Expected 1200 total, got {result['total']}"
    assert len(result["addons"]) == 2, f"Expected 2 addons, got {len(result['addons'])}"
    
    print("PASS: Check 5 passed - Addons correct")


def test_high_season():
    """Test 6: High season (summer)"""
    print("\nCheck 6: High season (summer)...")
    
    engine = PricingEngine()
    cabin = {
        "base_price_night": 500.0,
        "weekend_price": 650.0
    }
    
    # אוגוסט (עונה גבוהה) - יום שני (לא חג, לא סופ"ש)
    # 2 באוגוסט 2026 = יום שני
    check_in = datetime(2026, 8, 2, 15, 0)  # שני
    check_out = datetime(2026, 8, 3, 11, 0)  # שלישי (לילה אחד)
    
    result = engine.calculate_price_breakdown(cabin, check_in, check_out)
    
    assert result["nights"] == 1, f"Expected 1 night, got {result['nights']}"
    assert result["high_season_nights"] == 1, f"Expected 1 high season night, got {result['high_season_nights']}"
    assert result["regular_nights"] == 1, f"Expected 1 regular night, got {result['regular_nights']}"
    # עונה גבוהה: 500 + 20% = 600
    assert abs(result["total"] - 600.0) < 0.01, f"Expected 600 (500 + 20%), got {result['total']}"
    
    print("PASS: Check 6 passed - High season correct")


def main():
    """Run all tests"""
    print("=" * 60)
    print("Stage 3: Pricing Engine Tests")
    print("=" * 60)
    print()
    
    try:
        test_basic_pricing()
        test_weekend_pricing()
        test_holiday_pricing()
        test_discounts()
        test_addons()
        test_high_season()
        
        print()
        print("=" * 60)
        print("SUCCESS: All tests passed! Stage 3 ready.")
        print("=" * 60)
        return 0
        
    except AssertionError as e:
        print()
        print(f"FAIL: Test error: {e}")
        print()
        return 1
    except Exception as e:
        print()
        print(f"ERROR: Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())


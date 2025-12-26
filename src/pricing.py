"""
מנוע תמחור מתקדם לצימרים
מרחיב את compute_price_for_stay עם יכולות נוספות:
- עונות וחגים
- הנחות לפי משך שהות
- תוספות
- breakdown מפורט
"""
from datetime import datetime, date, timedelta
from typing import Optional, Dict, List, Any
from decimal import Decimal, ROUND_HALF_UP


def get_israel_tzinfo():
    """מחזיר timezone של ישראל"""
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo("Asia/Jerusalem")
    except Exception:
        from datetime import timezone
        return timezone(timedelta(hours=2))


ISRAEL_TZ = get_israel_tzinfo()


class PricingEngine:
    """
    מנוע תמחור מתקדם עם תמיכה בעונות, חגים, הנחות ותוספות
    """
    
    def __init__(self):
        # חגים ישראליים (ניתן להרחיב)
        self.holidays_2026 = {
            date(2026, 4, 22),  # פסח
            date(2026, 4, 23),
            date(2026, 4, 24),
            date(2026, 4, 28),
            date(2026, 4, 29),
            date(2026, 5, 14),  # יום העצמאות
            date(2026, 6, 11),  # שבועות
            date(2026, 9, 15),  # ראש השנה
            date(2026, 9, 16),
            date(2026, 9, 24),  # יום כיפור
            date(2026, 9, 29),  # סוכות
            date(2026, 9, 30),
            date(2026, 10, 1),
            date(2026, 10, 6),
            date(2026, 10, 7),
        }
        
        # עונות (ניתן להרחיב)
        self.high_season_months = [7, 8]  # יולי-אוגוסט (קיץ)
        self.holiday_season_months = [4, 9, 10]  # פסח, חגי תשרי
    
    def is_weekend(self, d: date) -> bool:
        """בודק אם זה סופ"ש (שישי או שבת)"""
        return d.weekday() in (4, 5)  # Fri, Sat
    
    def is_holiday(self, d: date) -> bool:
        """בודק אם זה חג"""
        return d in self.holidays_2026
    
    def is_high_season(self, d: date) -> bool:
        """בודק אם זה עונה גבוהה (קיץ)"""
        return d.month in self.high_season_months
    
    def is_holiday_season(self, d: date) -> bool:
        """בודק אם זה עונת חגים"""
        return d.month in self.holiday_season_months
    
    def calculate_nights(self, check_in: date, check_out: date) -> int:
        """מחשב מספר לילות"""
        nights = (check_out - check_in).days
        return max(0, nights)
    
    def calculate_discount(self, nights: int, base_total: float) -> Dict[str, Any]:
        """
        מחשב הנחות לפי משך שהות
        """
        discount_percent = 0.0
        discount_amount = 0.0
        discount_reason = None
        
        if nights >= 30:  # חודש
            discount_percent = 15.0
            discount_reason = "הנחת שהות ארוכה (חודש)"
        elif nights >= 14:  # שבועיים
            discount_percent = 12.0
            discount_reason = "הנחת שהות ארוכה (שבועיים)"
        elif nights >= 7:  # שבוע
            discount_percent = 10.0
            discount_reason = "הנחת שהות ארוכה (שבוע)"
        elif nights >= 4:  # 4+ לילות
            discount_percent = 5.0
            discount_reason = "הנחת שהות ארוכה (4+ לילות)"
        
        if discount_percent > 0:
            discount_amount = base_total * (discount_percent / 100.0)
            discount_amount = round(discount_amount, 2)
        
        return {
            "percent": discount_percent,
            "amount": discount_amount,
            "reason": discount_reason
        }
    
    def calculate_price_breakdown(
        self,
        cabin: Dict[str, Any],
        check_in: datetime,
        check_out: datetime,
        addons: Optional[List[Dict[str, Any]]] = None,
        apply_discounts: bool = True
    ) -> Dict[str, Any]:
        """
        מחשב מחיר מפורט עם breakdown מלא
        
        Args:
            cabin: מידע על הצימר (מ-Google Sheets או DB)
            check_in: תאריך ושעת כניסה
            check_out: תאריך ושעת יציאה
            addons: רשימת תוספות (אופציונלי)
            apply_discounts: האם להחיל הנחות (ברירת מחדל: True)
        
        Returns:
            dict עם breakdown מפורט של המחיר
        """
        # המרה ל-date אם צריך
        if isinstance(check_in, datetime):
            check_in_date = check_in.date()
        else:
            check_in_date = check_in
        
        if isinstance(check_out, datetime):
            check_out_date = check_out.date()
        else:
            check_out_date = check_out
        
        # מחיר בסיסי
        base_price_night = float(cabin.get("base_price_night") or 0)
        weekend_price_night = float(cabin.get("weekend_price") or base_price_night)
        
        # חישוב מספר לילות
        nights = self.calculate_nights(check_in_date, check_out_date)
        
        if nights == 0:
            return {
                "nights": 0,
                "regular_nights": 0,
                "weekend_nights": 0,
                "holiday_nights": 0,
                "high_season_nights": 0,
                "base_total": 0.0,
                "weekend_surcharge": 0.0,
                "holiday_surcharge": 0.0,
                "high_season_surcharge": 0.0,
                "addons_total": 0.0,
                "subtotal": 0.0,
                "discount": {
                    "percent": 0.0,
                    "amount": 0.0,
                    "reason": None
                },
                "total": 0.0,
                "breakdown": []
            }
        
        # חישוב מחיר לפי יום
        regular_nights = 0
        weekend_nights = 0
        holiday_nights = 0
        high_season_nights = 0
        
        base_total = 0.0
        weekend_surcharge = 0.0
        holiday_surcharge = 0.0
        high_season_surcharge = 0.0
        
        breakdown = []
        
        for i in range(nights):
            d = check_in_date + timedelta(days=i)
            wd = d.weekday()
            is_weekend = self.is_weekend(d)
            is_holiday = self.is_holiday(d)
            is_high_season = self.is_high_season(d)
            is_holiday_season = self.is_holiday_season(d)
            
            # מחיר בסיסי ליום
            day_price = base_price_night
            
            # תוספת סופ"ש
            if is_weekend:
                weekend_nights += 1
                if weekend_price_night > base_price_night:
                    surcharge = weekend_price_night - base_price_night
                    weekend_surcharge += surcharge
                    day_price = weekend_price_night
            else:
                regular_nights += 1
            
            # תוספת חג (50% על המחיר הבסיסי)
            if is_holiday:
                holiday_nights += 1
                holiday_surcharge_amount = base_price_night * 0.5
                holiday_surcharge += holiday_surcharge_amount
                day_price += holiday_surcharge_amount
            
            # תוספת עונה גבוהה (20% על המחיר הבסיסי)
            if is_high_season and not is_holiday:
                high_season_nights += 1
                high_season_surcharge_amount = base_price_night * 0.2
                high_season_surcharge += high_season_surcharge_amount
                day_price += high_season_surcharge_amount
            
            # תוספת עונת חגים (30% על המחיר הבסיסי)
            elif is_holiday_season and not is_holiday and not is_high_season:
                high_season_surcharge_amount = base_price_night * 0.3
                high_season_surcharge += high_season_surcharge_amount
                day_price += high_season_surcharge_amount
            
            base_total += day_price
            
            # breakdown ליום
            breakdown.append({
                "date": d.isoformat(),
                "is_weekend": is_weekend,
                "is_holiday": is_holiday,
                "is_high_season": is_high_season,
                "price": round(day_price, 2)
            })
        
        # חישוב תוספות
        addons_total = 0.0
        addons_list = []
        
        if addons:
            for addon in addons:
                addon_price = float(addon.get("price", 0))
                addon_name = addon.get("name", "תוספת")
                addons_total += addon_price
                addons_list.append({
                    "name": addon_name,
                    "price": addon_price
                })
        
        # סכום ביניים
        subtotal = base_total + addons_total
        
        # הנחות
        discount_info = {
            "percent": 0.0,
            "amount": 0.0,
            "reason": None
        }
        
        if apply_discounts:
            discount_info = self.calculate_discount(nights, subtotal)
        
        # סה"כ סופי
        total = subtotal - discount_info["amount"]
        total = round(total, 2)
        
        return {
            "nights": nights,
            "regular_nights": regular_nights,
            "weekend_nights": weekend_nights,
            "holiday_nights": holiday_nights,
            "high_season_nights": high_season_nights,
            "base_total": round(base_total, 2),
            "weekend_surcharge": round(weekend_surcharge, 2),
            "holiday_surcharge": round(holiday_surcharge, 2),
            "high_season_surcharge": round(high_season_surcharge, 2),
            "addons_total": round(addons_total, 2),
            "addons": addons_list,
            "subtotal": round(subtotal, 2),
            "discount": discount_info,
            "total": total,
            "breakdown": breakdown
        }


# שמירה על תאימות לאחור - wrapper לפונקציה הקיימת
def compute_price_for_stay_enhanced(
    cabin: dict,
    check_in_local: datetime,
    check_out_local: datetime,
    addons: Optional[List[Dict[str, Any]]] = None
) -> dict:
    """
    גרסה משופרת של compute_price_for_stay עם תמיכה בתוספות
    שומרת על תאימות לאחור עם הפונקציה המקורית
    """
    engine = PricingEngine()
    result = engine.calculate_price_breakdown(
        cabin=cabin,
        check_in=check_in_local,
        check_out=check_out_local,
        addons=addons,
        apply_discounts=True
    )
    
    # החזר בפורמט תואם לפונקציה המקורית + שדות נוספים
    return {
        "nights": result["nights"],
        "regular": result["regular_nights"],
        "weekend": result["weekend_nights"],
        "total": result["total"],
        # שדות נוספים
        "holiday_nights": result["holiday_nights"],
        "high_season_nights": result["high_season_nights"],
        "base_total": result["base_total"],
        "weekend_surcharge": result["weekend_surcharge"],
        "holiday_surcharge": result["holiday_surcharge"],
        "high_season_surcharge": result["high_season_surcharge"],
        "addons_total": result["addons_total"],
        "addons": result["addons"],
        "subtotal": result["subtotal"],
        "discount": result["discount"],
        "breakdown": result["breakdown"]
    }


"""
סקריפט בדיקה לשלב 2: חיבור ליומן וזמינות
בודק את כל הנקודות מה-Definition of Done
מתאים לקוד הקיים שמשתמש ב-Google Sheets
"""

import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import Tuple, List
from dotenv import load_dotenv

# הוסף את src ל-path
BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))

load_dotenv(BASE_DIR / ".env")

try:
    from src.main import (
        get_credentials_api,
        build_calendar_service,
        read_cabins_from_sheet,
        list_calendar_events,
        create_calendar_event,
        is_cabin_available,
        parse_datetime_local,
        to_utc,
        ISRAEL_TZ,
    )
except ImportError as e:
    print(f"❌ שגיאה בייבוא: {e}")
    print("ודא שאתה מריץ את הסקריפט מתיקיית הפרויקט")
    sys.exit(1)


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


def check_calendar_connection() -> Tuple[bool, any]:
    """בדוק חיבור ל-Google Calendar API"""
    print_header("1. בדיקת חיבור ל-Google Calendar API")

    try:
        creds = get_credentials_api()
        print_success("Credentials נטענו בהצלחה")

        service = build_calendar_service(creds)
        print_success("Calendar Service נוצר בהצלחה")

        # בדוק חיבור על ידי קריאה ל-calendar list
        calendar_list = service.calendarList().list().execute()
        print_success(f"חיבור ל-API עובד - נמצאו {len(calendar_list.get('items', []))} יומנים")

        return True, service, creds

    except FileNotFoundError as e:
        print_error(f"קובץ credentials.json לא נמצא: {e}")
        print_warning("ודא שיש קובץ credentials.json ב-data/ או בשורש הפרויקט")
        return False, None, None
    except Exception as e:
        print_error(f"שגיאה בחיבור ל-API: {e}")
        import traceback

        traceback.print_exc()
        return False, None, None


def check_cabins_have_calendars(service, creds) -> Tuple[bool, List[dict]]:
    """בדוק אם לכל צימר יש calendar_id (מ-Google Sheets)"""
    print_header("2. בדיקת יומנים לכל צימר (מ-Google Sheets)")

    try:
        cabins = read_cabins_from_sheet(creds)
        print_success(f"נטענו {len(cabins)} צימרים מ-Google Sheets")

        if len(cabins) == 0:
            print_warning("לא נמצאו צימרים ב-Google Sheets")
            print_warning("הוסף צימרים ל-Google Sheets לפני המשך")
            return False, []

        cabins_with_calendar = []
        cabins_without_calendar = []

        for cabin in cabins:
            cabin_id = cabin.get("cabin_id", "UNKNOWN")
            cabin_name = cabin.get("name", "ללא שם")
            calendar_id = cabin.get("calendar_id") or cabin.get("calendarId")

            if calendar_id:
                cabins_with_calendar.append(cabin)
                print_success(f"צימר '{cabin_name}' (id: {cabin_id}) - יש calendar_id: {calendar_id}")
            else:
                cabins_without_calendar.append(cabin)
                print_error(f"צימר '{cabin_name}' (id: {cabin_id}) - חסר calendar_id")

        if cabins_without_calendar:
            print_warning(f"נמצאו {len(cabins_without_calendar)} צימרים ללא calendar_id")
            return False, cabins_with_calendar

        print_success(f"כל {len(cabins)} הצימרים יש להם calendar_id")
        return True, cabins_with_calendar

    except ValueError as e:
        print_error(f"שגיאה בקריאת צימרים: {e}")
        print_warning("ודא ש-SHEET_NAME מוגדר ב-.env")
        return False, []
    except Exception as e:
        print_error(f"שגיאה בקריאת צימרים: {e}")
        import traceback

        traceback.print_exc()
        return False, []


def check_availability_query(service, cabins_with_calendar: List[dict]) -> bool:
    """בדוק אם שאילתת זמינות מחזירה תוצאות נכונות"""
    print_header("3. בדיקת שאילתת זמינות")

    if not cabins_with_calendar:
        print_warning("אין צימרים עם calendar_id לבדיקה")
        return False

    # בחר צימר ראשון לבדיקה
    test_cabin = cabins_with_calendar[0]
    calendar_id = test_cabin.get("calendar_id") or test_cabin.get("calendarId")
    cabin_name = test_cabin.get("name", "ללא שם")

    try:
        # תאריכים לבדיקה - שבועיים מהיום
        check_in = datetime.now() + timedelta(days=14)
        check_out = check_in + timedelta(days=2)

        check_in_local = parse_datetime_local(check_in.strftime("%Y-%m-%d"))
        check_out_local = parse_datetime_local(check_out.strftime("%Y-%m-%d"))

        check_in_utc = to_utc(check_in_local)
        check_out_utc = to_utc(check_out_local)

        is_available, conflicts = is_cabin_available(
            service, calendar_id, check_in_utc, check_out_utc
        )

        print_success(
            f"שאילתת זמינות עובדת - צימר '{cabin_name}' "
            f"({'זמין' if is_available else 'תפוס'}) בתאריכים {check_in.date()} - {check_out.date()}"
        )

        if conflicts:
            print_warning(f"נמצאו {len(conflicts)} התנגשויות")

        return True

    except Exception as e:
        print_error(f"שגיאה בבדיקת זמינות: {e}")
        import traceback

        traceback.print_exc()
        return False


def check_create_event(service, cabins_with_calendar: List[dict]) -> Tuple[bool, str, str]:
    """בדוק אם הוספת אירוע עובדת"""
    print_header("4. בדיקת הוספת אירוע ליומן")

    if not cabins_with_calendar:
        print_warning("אין צימרים עם calendar_id לבדיקה")
        return False, None, None

    test_cabin = cabins_with_calendar[0]
    calendar_id = test_cabin.get("calendar_id") or test_cabin.get("calendarId")
    cabin_name = test_cabin.get("name", "ללא שם")

    try:
        # תאריכים לבדיקה - שבועיים מהיום
        check_in = datetime.now() + timedelta(days=15)
        check_out = check_in + timedelta(days=1)

        # המר ל-timezone-aware
        check_in_local = check_in.replace(tzinfo=ISRAEL_TZ)
        check_out_local = check_out.replace(tzinfo=ISRAEL_TZ)

        event = create_calendar_event(
            service=service,
            calendar_id=calendar_id,
            summary="בדיקת מערכת - אירוע זמני",
            start_local=check_in_local,
            end_local=check_out_local,
            description="אירוע זה נוצר לבדיקה ויימחק מיד",
        )

        event_id = event.get("id")
        print_success(f"אירוע נוצר בהצלחה - ID: {event_id} (צימר: {cabin_name})")

        return True, event_id, calendar_id

    except Exception as e:
        print_error(f"שגיאה ביצירת אירוע: {e}")
        import traceback

        traceback.print_exc()
        return False, None, None


def check_delete_event(service, calendar_id: str, event_id: str) -> bool:
    """בדוק אם מחיקת אירוע עובדת"""
    print_header("5. בדיקת מחיקת אירוע")

    if not event_id:
        print_warning("אין event_id לבדיקה")
        return False

    try:
        service.events().delete(calendarId=calendar_id, eventId=event_id).execute()
        print_success(f"אירוע {event_id} נמחק בהצלחה")

        return True

    except Exception as e:
        print_error(f"שגיאה במחיקת אירוע: {e}")
        import traceback

        traceback.print_exc()
        return False


def print_summary(results: dict):
    """הדפס סיכום"""
    print_header("סיכום בדיקות")

    total_checks = 5
    passed_checks = sum(1 for v in results.values() if v)

    print(f"\n{Colors.BOLD}תוצאות:{Colors.END}")
    print(f"  ✓ חיבור API: {'עבר' if results['api_connection'] else 'נכשל'}")
    print(f"  ✓ יומנים לכל צימר: {'עבר' if results['cabins_calendars'] else 'נכשל'}")
    print(f"  ✓ שאילתת זמינות: {'עבר' if results['availability_query'] else 'נכשל'}")
    print(f"  ✓ הוספת אירוע: {'עבר' if results['create_event'] else 'נכשל'}")
    print(f"  ✓ מחיקת אירוע: {'עבר' if results['delete_event'] else 'נכשל'}")

    print(f"\n{Colors.BOLD}ציון כולל: {passed_checks}/{total_checks}{Colors.END}")

    if passed_checks == total_checks:
        print(f"\n{Colors.GREEN}{Colors.BOLD}🎉 כל הבדיקות עברו! שלב 2 מוכן.{Colors.END}\n")
        return True

    print(f"\n{Colors.RED}{Colors.BOLD}⚠ יש בעיות שצריך לתקן לפני המעבר לשלב הבא.{Colors.END}\n")
    return False


def main():
    """פונקציה ראשית"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}")
    print("╔" + "=" * 58 + "╗")
    print("║" + " " * 10 + "בדיקת שלב 2: חיבור ליומן וזמינות" + " " * 10 + "║")
    print("╚" + "=" * 58 + "╝")
    print(Colors.END)

    results = {}
    service = None
    creds = None
    cabins_with_calendar = []
    event_id = None
    test_calendar_id = None

    try:
        # 1. בדוק חיבור ל-Google Calendar API
        results["api_connection"], service, creds = check_calendar_connection()
        if not results["api_connection"]:
            print_error("לא ניתן להמשיך ללא חיבור ל-API")
            return 1

        # 2. בדוק יומנים לכל צימר (מ-Google Sheets)
        results["cabins_calendars"], cabins_with_calendar = check_cabins_have_calendars(
            service, creds
        )

        # 3. בדוק שאילתת זמינות
        if cabins_with_calendar:
            results["availability_query"] = check_availability_query(
                service, cabins_with_calendar
            )
        else:
            print_warning("דילוג על בדיקת זמינות - אין צימרים עם calendar_id")
            results["availability_query"] = False

        # 4. בדוק הוספת אירוע
        if cabins_with_calendar:
            results["create_event"], event_id, test_calendar_id = check_create_event(
                service, cabins_with_calendar
            )
        else:
            print_warning("דילוג על בדיקת הוספת אירוע - אין צימרים עם calendar_id")
            results["create_event"] = False

        # 5. בדוק מחיקת אירוע
        if event_id and test_calendar_id:
            results["delete_event"] = check_delete_event(service, test_calendar_id, event_id)
        else:
            print_warning("דילוג על בדיקת מחיקת אירוע - אין event_id לבדיקה")
            results["delete_event"] = False

        # סיכום
        all_passed = print_summary(results)

        return 0 if all_passed else 1

    except Exception as e:
        print_error(f"שגיאה כללית: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())


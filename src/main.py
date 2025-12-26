import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
import gspread

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


def configure_utf8_console() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    try:
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


configure_utf8_console()

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
TOKEN_PATH = DATA_DIR / "token.json"
CREDS_PATH = DATA_DIR / "credentials.json"

# חשוב:
# החלפנו calendar.readonly ל calendar.events כדי לאפשר יצירת הזמנה (insert event)
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/calendar.events",
]


def get_israel_tzinfo():
    """
    מנסה להשתמש ב ZoneInfo("Asia/Jerusalem").
    אם במחשב אין tzdata (כמו אצלך ב Python 3.13), נופלים ל UTC+02:00 קבוע.
    הערה: UTC+02:00 קבוע לא יודע DST אוטומטי. לפרויקט שלך זה עדיין יעבוד טוב אם אתה מזין שעות ישראל.
    """
    try:
        from zoneinfo import ZoneInfo  # py3.9+
        return ZoneInfo("Asia/Jerusalem")
    except Exception:
        return timezone(timedelta(hours=2))


ISRAEL_TZ = get_israel_tzinfo()


def get_credentials():
    import os
    from pathlib import Path
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request

    BASE_DIR = Path(__file__).resolve().parents[1]
    data_dir = BASE_DIR / "data"
    data_dir.mkdir(exist_ok=True)

    # Scopes for: read Google Sheets + read/write Google Calendar
    SCOPES = [
        "https://www.googleapis.com/auth/spreadsheets.readonly",
        "https://www.googleapis.com/auth/calendar",
    ]

    token_path = data_dir / "token.json"
    creds_path = data_dir / "credentials.json"

    # fallback if credentials.json is in project root
    if not creds_path.exists():
        alt = BASE_DIR / "credentials.json"
        if alt.exists():
            creds_path = alt

    if not creds_path.exists():
        raise FileNotFoundError(
            "Missing credentials.json. Put it in data/credentials.json or in project root."
        )

    creds = None

    if token_path.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
        except Exception:
            creds = None

    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except Exception:
            creds = None

    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file(str(creds_path), SCOPES)
        creds = flow.run_local_server(port=0)
        token_path.write_text(creds.to_json(), encoding="utf-8")

    return creds




def read_cabins_from_sheet(creds: Credentials) -> list[dict]:
    load_dotenv(BASE_DIR / ".env")
    sheet_name = os.getenv("SHEET_NAME")
    worksheet_name = os.getenv("WORKSHEET_NAME", "Sheet1")

    if not sheet_name:
        raise ValueError("Missing SHEET_NAME in .env")

    gc = gspread.authorize(creds)
    sh = gc.open(sheet_name)
    ws = sh.worksheet(worksheet_name)
    return ws.get_all_records()


def build_calendar_service(creds: Credentials):
    return build("calendar", "v3", credentials=creds)


def list_calendar_events(
    service,
    calendar_id: str,
    time_min_iso: str,
    time_max_iso: str,
) -> list[dict]:
    result = (
        service.events()
        .list(
            calendarId=calendar_id,
            timeMin=time_min_iso,
            timeMax=time_max_iso,
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )
    return result.get("items", [])


def create_calendar_event(
    service,
    calendar_id: str,
    summary: str,
    start_local: datetime,
    end_local: datetime,
    description: str = "",
) -> dict:
    """
    יוצר אירוע ביומן.
    start_local/end_local חייבים להיות timezone-aware (שעון ישראל).
    """
    if start_local.tzinfo is None:
        start_local = start_local.replace(tzinfo=ISRAEL_TZ)
    if end_local.tzinfo is None:
        end_local = end_local.replace(tzinfo=ISRAEL_TZ)

    body = {
        "summary": summary,
        "description": description or "",
        "start": {
            "dateTime": start_local.isoformat(),
            "timeZone": "Asia/Jerusalem",
        },
        "end": {
            "dateTime": end_local.isoformat(),
            "timeZone": "Asia/Jerusalem",
        },
    }

    created = service.events().insert(calendarId=calendar_id, body=body).execute()
    return created


def _to_rfc3339_z(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    dt_utc = dt.astimezone(timezone.utc)
    return dt_utc.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_event_dt(value: str) -> datetime:
    # dateTime: 2025-12-21T15:00:00+02:00
    # date: 2025-12-21 (all day)
    if "T" in value:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    return datetime.fromisoformat(value).replace(tzinfo=timezone.utc)


def _event_interval_utc(e: dict) -> tuple[datetime, datetime]:
    start_raw = e.get("start", {}).get("dateTime") or e.get("start", {}).get("date")
    end_raw = e.get("end", {}).get("dateTime") or e.get("end", {}).get("date")

    if not start_raw or not end_raw:
        now = datetime.now(timezone.utc)
        return now, now

    return _parse_event_dt(start_raw), _parse_event_dt(end_raw)


def _intervals_overlap(a_start: datetime, a_end: datetime, b_start: datetime, b_end: datetime) -> bool:
    return a_start < b_end and b_start < a_end


def is_cabin_available(
    service,
    calendar_id: str,
    desired_start_utc: datetime,
    desired_end_utc: datetime,
) -> tuple[bool, list[dict]]:
    time_min = _to_rfc3339_z(desired_start_utc)
    time_max = _to_rfc3339_z(desired_end_utc)

    events = list_calendar_events(service, calendar_id, time_min, time_max)

    conflicts: list[dict] = []
    for e in events:
        e_start, e_end = _event_interval_utc(e)
        if _intervals_overlap(desired_start_utc, desired_end_utc, e_start, e_end):
            conflicts.append(e)

    return (len(conflicts) == 0), conflicts


def parse_datetime_local(value: str) -> datetime:
    """
    קלטים נתמכים:
    - "YYYY-MM-DD"
    - "YYYY-MM-DD HH:MM"
    - "YYYY-MM-DDTHH:MM"
    - "DD/MM/YYYY"
    - "DD/MM/YYYY HH:MM"

    אם אין שעה, ברירת מחדל 12:00
    """
    s = (value or "").strip()
    if not s:
        raise ValueError("Empty datetime value")

    s = s.replace("T", " ")
    dt = None

    if "/" in s:
        parts = s.split()
        date_part = parts[0]
        time_part = parts[1] if len(parts) > 1 else "12:00"
        d, m, y = date_part.split("/")
        hh, mm = time_part.split(":")
        dt = datetime(int(y), int(m), int(d), int(hh), int(mm))
    else:
        parts = s.split()
        date_part = parts[0]
        time_part = parts[1] if len(parts) > 1 else "12:00"
        y, m, d = date_part.split("-")
        hh, mm = time_part.split(":")
        dt = datetime(int(y), int(m), int(d), int(hh), int(mm))

    return dt.replace(tzinfo=ISRAEL_TZ)


def to_utc(dt_local: datetime) -> datetime:
    if dt_local.tzinfo is None:
        dt_local = dt_local.replace(tzinfo=ISRAEL_TZ)
    return dt_local.astimezone(timezone.utc)


def normalize_text(s: Any) -> str:
    return (str(s) if s is not None else "").strip()


def parse_features_arg(features: str | None) -> list[str]:
    if not features:
        return []
    parts = [p.strip() for p in features.split(",")]
    return [p for p in parts if p]


def cabin_has_features(cabin_features: str, wanted: list[str]) -> tuple[bool, list[str]]:
    if not wanted:
        return True, []
    existing = normalize_text(cabin_features).lower()
    missing = []
    for w in wanted:
        if w.lower() not in existing:
            missing.append(w)
    return len(missing) == 0, missing


def compute_price_for_stay(cabin: dict, check_in_local: datetime, check_out_local: datetime) -> dict:
    """
    מחיר לפי לילות.
    weekend: שישי ושבת (weekday 4 ו 5) עבור הלילה שמתחיל בתאריך הזה.
    """
    base = float(cabin.get("base_price_night") or 0)
    weekend = float(cabin.get("weekend_price") or 0)

    if check_in_local.tzinfo is None:
        check_in_local = check_in_local.replace(tzinfo=ISRAEL_TZ)
    if check_out_local.tzinfo is None:
        check_out_local = check_out_local.replace(tzinfo=ISRAEL_TZ)

    start_date = check_in_local.date()
    end_date = check_out_local.date()

    nights = (end_date - start_date).days
    if nights <= 0:
        nights = 0

    regular_nights = 0
    weekend_nights = 0
    total = 0.0

    for i in range(nights):
        d = start_date + timedelta(days=i)
        wd = d.weekday()
        is_weekend = wd in (4, 5)  # Fri, Sat
        if is_weekend:
            weekend_nights += 1
            total += weekend if weekend > 0 else base
        else:
            regular_nights += 1
            total += base

    return {
        "nights": nights,
        "regular": regular_nights,
        "weekend": weekend_nights,
        "total": float(total),
    }


def filter_cabin(
    cabin: dict,
    adults: int | None,
    kids: int | None,
    area: str | None,
    wanted_features: list[str],
) -> tuple[bool, list[str]]:
    reasons = []

    max_adults = int(cabin.get("max_adults") or 0)
    max_kids = int(cabin.get("max_kids") or 0)

    if adults is not None and adults > max_adults:
        reasons.append(f"adults {adults} > max_adults {max_adults}")
    if kids is not None and kids > max_kids:
        reasons.append(f"kids {kids} > max_kids {max_kids}")

    if area:
        cabin_area = normalize_text(cabin.get("area"))
        if normalize_text(area) != cabin_area:
            reasons.append(f"area '{area}' not match '{cabin_area}'")

    ok_feat, missing = cabin_has_features(cabin.get("features", ""), wanted_features)
    if not ok_feat:
        reasons.append(f"missing features: {missing}")

    return (len(reasons) == 0), reasons


def summarize_conflicts(conflicts: list[dict], limit: int = 3) -> list[str]:
    out = []
    for e in conflicts[:limit]:
        title = e.get("summary", "")
        start = e.get("start", {}).get("dateTime") or e.get("start", {}).get("date")
        end = e.get("end", {}).get("dateTime") or e.get("end", {}).get("date")
        out.append(f"{title} | {start} -> {end}")
    return out


def find_available_cabins(
    service,
    cabins: list[dict],
    check_in_utc: datetime,
    check_out_utc: datetime,
    adults: int | None = None,
    kids: int | None = None,
    area: str | None = None,
    wanted_features: list[str] | None = None,
    verbose: bool = False,
) -> list[dict]:
    """
    מחזיר צימרים שעוברים גם פילטרים וגם זמינות ביומן.
    לא מוחק כלום מהקיים, זו פונקציה מלאה ויציבה לשלב הבא.
    """
    wanted_features = wanted_features or []
    available: list[dict] = []

    for c in cabins:
        cabin_id = c.get("cabin_id", "UNKNOWN")
        cal_id = c.get("calendar_id") or c.get("calendarId")

        if not cal_id:
            if verbose:
                print(f"Cabin {cabin_id} missing calendar_id, skipping")
            continue

        ok_filters, reasons = filter_cabin(c, adults, kids, area, wanted_features)
        if not ok_filters:
            if verbose:
                print(f"Cabin {cabin_id} filtered out: {reasons}")
            continue

        ok, conflicts = is_cabin_available(service, cal_id, check_in_utc, check_out_utc)
        if not ok:
            if verbose:
                examples = summarize_conflicts(conflicts, limit=3)
                print(f"Cabin {cabin_id} NOT available, conflicts={len(conflicts)}")
                for line in examples:
                    print(f"  - {line}")
            continue

        c2 = dict(c)
        c2["conflicts_count"] = 0
        available.append(c2)

    return available


def main_cli():
    import argparse

    parser = argparse.ArgumentParser(description="ZimmerBot availability and booking")
    parser.add_argument("--check-in", required=False, help='Local time, e.g. "2025-12-23 15:00"')
    parser.add_argument("--check-out", required=False, help='Local time, e.g. "2025-12-24 11:00"')

    parser.add_argument("--adults", type=int, required=False, default=None)
    parser.add_argument("--kids", type=int, required=False, default=None)
    parser.add_argument("--area", required=False, default=None)
    parser.add_argument("--features", required=False, default=None, help='Comma list, e.g. "jacuzzi,pool"')

    parser.add_argument("--verbose", action="store_true")

    # הזמנה בפועל
    parser.add_argument("--book", action="store_true", help="Create calendar event for the chosen cabin")
    parser.add_argument("--cabin-id", required=False, default=None, help="Force booking on a specific cabin_id")
    parser.add_argument("--customer", required=False, default=None, help='Customer name, e.g. "ישראל ישראלי"')
    parser.add_argument("--phone", required=False, default=None, help='Phone, e.g. "050-1234567"')
    parser.add_argument("--notes", required=False, default=None, help="Free text notes")

    args = parser.parse_args()

    print("ZimmerBot - availability cli start")

    creds = get_credentials()
    print("OAuth OK")

    service = build_calendar_service(creds)

    cabins = read_cabins_from_sheet(creds)
    print(f"Loaded cabins rows: {len(cabins)}")

    if not cabins:
        print("No rows found in sheet.")
        return

    load_dotenv(BASE_DIR / ".env")
    ci = args.check_in or os.getenv("CHECK_IN")
    co = args.check_out or os.getenv("CHECK_OUT")

    if not ci or not co:
        print('Missing check-in/check-out. Provide --check-in and --check-out, or set CHECK_IN and CHECK_OUT in .env')
        return

    check_in_local = parse_datetime_local(ci)
    check_out_local = parse_datetime_local(co)

    check_in_utc = to_utc(check_in_local)
    check_out_utc = to_utc(check_out_local)

    if args.verbose:
        print(f"Check-in local: {check_in_local.isoformat()}")
        print(f"Check-out local: {check_out_local.isoformat()}")

    wanted_features = parse_features_arg(args.features)

    candidates = find_available_cabins(
        service=service,
        cabins=cabins,
        check_in_utc=check_in_utc,
        check_out_utc=check_out_utc,
        adults=args.adults,
        kids=args.kids,
        area=args.area,
        wanted_features=wanted_features,
        verbose=args.verbose,
    )

    # הדפסה עם מחיר
    print(f"Available cabins: {len(candidates)}")
    for c in candidates:
        pricing = compute_price_for_stay(c, check_in_local, check_out_local)
        print(
            f"- {c.get('cabin_id')} | {c.get('name')} | {c.get('area')} | "
            f"nights={pricing['nights']} regular={pricing['regular']} weekend={pricing['weekend']} | "
            f"total={pricing['total']}"
        )

    # אם לא ביקשו הזמנה, סיימנו
    if not args.book:
        print("ZimmerBot - availability cli done")
        return

    # הזמנה בפועל
    if not candidates:
        print("No available cabins to book.")
        print("ZimmerBot - availability cli done")
        return

    chosen = None
    if args.cabin_id:
        for c in candidates:
            if normalize_text(c.get("cabin_id")).lower() == normalize_text(args.cabin_id).lower():
                chosen = c
                break
        if not chosen:
            print(f"Requested cabin-id not available: {args.cabin_id}")
            print("ZimmerBot - availability cli done")
            return
    else:
        chosen = candidates[0]

    cabin_id = chosen.get("cabin_id", "UNKNOWN")
    cal_id = chosen.get("calendar_id") or chosen.get("calendarId")
    if not cal_id:
        print(f"Chosen cabin missing calendar_id: {cabin_id}")
        print("ZimmerBot - availability cli done")
        return

    customer = args.customer or "לקוח"
    phone = args.phone or ""
    notes = args.notes or ""

    summary = f"הזמנה | {customer}"
    desc_lines = [
        f"Cabin: {cabin_id}",
        f"Customer: {customer}",
        f"Phone: {phone}",
        f"Check-in: {check_in_local.isoformat()}",
        f"Check-out: {check_out_local.isoformat()}",
    ]
    if notes:
        desc_lines.append(f"Notes: {notes}")
    description = "\n".join(desc_lines)

    created = create_calendar_event(
        service=service,
        calendar_id=cal_id,
        summary=summary,
        start_local=check_in_local,
        end_local=check_out_local,
        description=description,
    )

    print("Booked successfully")
    print(f"Cabin: {cabin_id}")
    print(f"EventId: {created.get('id')}")
    if created.get("htmlLink"):
        print(f"Link: {created.get('htmlLink')}")

    print("ZimmerBot - availability cli done")

def get_credentials_api():
    """
    API credentials loader with enforced scopes.
    Creates a separate token file for the API server to avoid conflicts.
    """
    import os
    from pathlib import Path

    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request

    base_dir = Path(__file__).resolve().parents[1]
    data_dir = base_dir / "data"
    data_dir.mkdir(exist_ok=True)

    token_path = data_dir / "token_api.json"

    # Scopes required for:
    # - read cabins from Google Sheets
    # - check availability in Google Calendar
    # - create booking events in Google Calendar
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets.readonly",
        "https://www.googleapis.com/auth/calendar",
    ]

    # Try load existing token
    creds = None
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), scopes=scopes)

    # Refresh or re-auth if needed
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # credentials.json must exist (usually under data/ or project root)
            # If your project uses a different path, update here accordingly.
            candidates = [
                base_dir / "data" / "credentials.json",
                base_dir / "credentials.json",
            ]
            cred_file = None
            for c in candidates:
                if c.exists():
                    cred_file = c
                    break
            if not cred_file:
                raise FileNotFoundError(
                    "credentials.json not found. Put it in data/credentials.json or project root."
                )

            flow = InstalledAppFlow.from_client_secrets_file(str(cred_file), scopes=scopes)
            creds = flow.run_local_server(port=0)

        # Save token
        with open(token_path, "w", encoding="utf-8") as f:
            f.write(creds.to_json())

    return creds



def main():
    """
    נשאר כאן כדי לא לשבור הרצות ישנות.
    """
    main_cli()


if __name__ == "__main__":
    main()

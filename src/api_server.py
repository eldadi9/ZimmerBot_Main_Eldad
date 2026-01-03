"""
API Server for ZimmerBot
FastAPI-based REST API for cabin booking system
"""

import os
from pathlib import Path
from typing import Optional, List, Dict, Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from fastapi.staticfiles import StaticFiles

from src.main import (
    read_cabins_from_sheet,
    build_calendar_service,
    find_available_cabins,
    compute_price_for_stay,
    create_calendar_event,
    parse_datetime_local,
    to_utc,
    parse_features_arg,
    normalize_text,
    is_cabin_available,
    list_calendar_events,
    ISRAEL_TZ,
    _to_rfc3339_z,
    _event_interval_utc,
)
from datetime import datetime, timedelta
from src.pricing import PricingEngine
from src.db import (
    read_cabins_from_db,
    save_customer_to_db,
    save_booking_to_db,
    get_cabin_by_id,
    save_audit_log,
    save_transaction,
    save_quote,
)
from src.hold import get_hold_manager
from src.payment import get_payment_manager
from src.email_service import get_email_service
from decimal import Decimal

BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR / ".env")

# scopes רחבים יותר כדי שלא תקבל 403 על פעולות שנראות "קריאה" אבל בפועל דורשות יותר
REQUIRED_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/calendar",
]

TOKEN_FILE = "data/token_api.json"

# תצורת תיקיות סטטיות
TOOLS_DIR = BASE_DIR / "tools"
DATA_DIR = BASE_DIR / "data"
TOOLS_DIR.mkdir(exist_ok=True)
DATA_DIR.mkdir(exist_ok=True)


def get_credentials_api():
    """
    API credentials with a dedicated token file: data/token_api.json
    Always enforces REQUIRED_SCOPES.
    """
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request

    data_dir = BASE_DIR / "data"
    data_dir.mkdir(exist_ok=True)

    token_path = data_dir / "token_api.json"

    creds = None

    if token_path.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(token_path), scopes=REQUIRED_SCOPES)
        except Exception:
            creds = None

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception:
                creds = None

        if not creds or not creds.valid:
            candidates = [
                BASE_DIR / "data" / "credentials.json",
                BASE_DIR / "credentials.json",
            ]
            cred_file = next((p for p in candidates if p.exists()), None)
            if not cred_file:
                raise FileNotFoundError(
                    "Missing credentials.json. Put it in data/credentials.json or in the project root."
                )

            flow = InstalledAppFlow.from_client_secrets_file(str(cred_file), scopes=REQUIRED_SCOPES)

            # Force consent so Google actually re-grants scopes
            try:
                creds = flow.run_local_server(port=0, prompt="consent")
            except TypeError:
                creds = flow.run_local_server(port=0)

        token_path.write_text(creds.to_json(), encoding="utf-8")

    return creds


app = FastAPI(
    title="ZimmerBot API",
    description="API for cabin booking and availability checking",
    version="1.0.0",
)

# היה אצלך import כפול - משאיר כתיעוד ולא מפעיל
# from fastapi.staticfiles import StaticFiles

# היה אצלך mount כפול - משאיר כתיעוד ולא מפעיל
# app.mount("/data", StaticFiles(directory=str(BASE_DIR / "data")), name="data")
# app.mount("/tools", StaticFiles(directory=str(BASE_DIR / "tools")), name="tools")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# mounts פעילים ומסודרים (פעם אחת בלבד)
# /tools מגיש HTML כלים
# /data מגיש קבצי JSON (כמו features_catalog.json)
app.mount("/tools", StaticFiles(directory=str(TOOLS_DIR), html=True), name="tools")
app.mount("/data", StaticFiles(directory=str(DATA_DIR)), name="data")
app.mount("/zimmers_pic", StaticFiles(directory=str(BASE_DIR / "zimmers_pic")), name="zimmers_pic")

# היה אצלך mount כפול נוסף - משאיר כתיעוד ולא מפעיל
# app.mount("/data", StaticFiles(directory=str(BASE_DIR / "data")), name="data")
# app.mount("/tools", StaticFiles(directory=str(BASE_DIR / "tools"), html=True), name="tools")

_creds = None
_service = None
_cabins = None


def get_service():
    """
    Get calendar service and cabins
    Tries DB first, falls back to Google Sheets if DB unavailable
    """
    global _creds, _service, _cabins
    if _creds is None:
        _creds = get_credentials_api()
    if _service is None:
        _service = build_calendar_service(_creds)
    if _cabins is None:
        # Try DB first, fallback to Sheets
        _cabins = read_cabins_from_db()
        if not _cabins:
            # Fallback to Google Sheets
            _cabins = read_cabins_from_sheet(_creds)
    # Always reload cabins to ensure we have latest data with cabin_id_string
    # This ensures cabin_id_string is always available
    _cabins = read_cabins_from_db() or read_cabins_from_sheet(_creds)
    return _service, _cabins


class AvailabilityRequest(BaseModel):
    check_in: str = Field(..., description="Check-in date/time (YYYY-MM-DD or YYYY-MM-DD HH:MM)")
    check_out: str = Field(..., description="Check-out date/time (YYYY-MM-DD or YYYY-MM-DD HH:MM)")
    adults: Optional[int] = Field(None, description="Number of adults")
    kids: Optional[int] = Field(None, description="Number of kids")
    area: Optional[str] = Field(None, description="Area filter")
    features: Optional[str] = Field(None, description="Comma-separated features (e.g., 'jacuzzi,pool')")


class AddonItem(BaseModel):
    name: str = Field(..., description="Addon name")
    price: float = Field(..., description="Addon price")


class BookingRequest(BaseModel):
    check_in: str = Field(..., description="Check-in date/time")
    check_out: str = Field(..., description="Check-out date/time")
    cabin_id: str = Field(..., description="Cabin ID to book")
    customer: str = Field(..., description="Customer name")
    phone: Optional[str] = Field(None, description="Customer phone")
    notes: Optional[str] = Field(None, description="Additional notes")
    email: Optional[str] = Field(None, description="Customer email")
    adults: Optional[int] = Field(None, description="Number of adults")
    kids: Optional[int] = Field(None, description="Number of kids")
    total_price: Optional[float] = Field(None, description="Total price")
    hold_id: Optional[str] = Field(None, description="Hold ID to convert to booking")
    addons: Optional[List[AddonItem]] = Field(None, description="List of addons")
    # Payment fields (Stage 5)
    create_payment: Optional[bool] = Field(False, description="Create payment intent (Stage 5)")
    payment_intent_id: Optional[str] = Field(None, description="Existing payment intent ID (if already created)")


class CabinInfo(BaseModel):
    cabin_id: str
    name: Optional[str] = None
    area: Optional[str] = None
    max_adults: Optional[int] = None
    max_kids: Optional[int] = None
    features: Optional[str] = None
    base_price_night: Optional[float] = None
    weekend_price: Optional[float] = None
    calendar_id: Optional[str] = None
    images_urls: Optional[List[str]] = None


class AvailabilityResponse(BaseModel):
    cabin_id: str
    name: Optional[str] = None
    area: Optional[str] = None
    nights: int
    regular_nights: int
    weekend_nights: int
    total_price: float
    max_adults: Optional[int] = None
    max_kids: Optional[int] = None
    features: Optional[str] = None
    images_urls: Optional[List[str]] = None


class BookingResponse(BaseModel):
    success: bool
    cabin_id: str
    booking_id: Optional[str] = None
    event_id: Optional[str] = None
    event_link: Optional[str] = None
    payment_intent_id: Optional[str] = None
    client_secret: Optional[str] = None
    message: str


class QuoteRequest(BaseModel):
    cabin_id: str = Field(..., description="Cabin ID to get quote for")
    check_in: str = Field(..., description="Check-in date/time (YYYY-MM-DD or YYYY-MM-DD HH:MM)")
    check_out: str = Field(..., description="Check-out date/time (YYYY-MM-DD or YYYY-MM-DD HH:MM)")
    adults: Optional[int] = Field(None, description="Number of adults")
    kids: Optional[int] = Field(None, description="Number of kids")
    addons: Optional[List[AddonItem]] = Field(None, description="List of addons (optional)")


class QuoteResponse(BaseModel):
    cabin_id: str
    cabin_name: Optional[str] = None
    check_in: str
    check_out: str
    nights: int
    regular_nights: int
    weekend_nights: int
    holiday_nights: int
    high_season_nights: int
    base_total: float
    weekend_surcharge: float
    holiday_surcharge: float
    high_season_surcharge: float
    addons_total: float
    addons: list
    subtotal: float
    discount: dict
    total: float
    breakdown: list


@app.get("/")
async def root():
    return {
        "message": "ZimmerBot API",
        "version": "1.0.0",
        "endpoints": {
            "health": "/health",
            "cabins": "/cabins",
            "availability": "/availability",
            "quote": "/quote",
            "hold": "/hold",
            "book": "/book",
            "admin": {
                "bookings": "/admin/bookings",
                "booking_by_id": "/admin/bookings/{id}",
                "audit": "/admin/audit",
            },
        },
    }


@app.get("/health")
async def health():
    # בריאות עם פירוט, כדי להבין בדיוק איפה זה נופל
    resp = {
        "token_file": TOKEN_FILE,
        "required_scopes": REQUIRED_SCOPES,
    }

    try:
        creds = get_credentials_api()
        resp["creds_scopes"] = list(getattr(creds, "scopes", []) or [])
    except Exception as e:
        resp["status"] = "unhealthy"
        resp["error_credentials"] = str(e)
        return resp

    try:
        service = build_calendar_service(creds)
        resp["calendar_service_ready"] = service is not None
    except Exception as e:
        resp["calendar_service_ready"] = False
        resp["error_calendar"] = str(e)

    try:
        cabins = read_cabins_from_sheet(creds)
        resp["cabins_loaded"] = len(cabins)
    except Exception as e:
        resp["cabins_loaded"] = 0
        resp["error_sheets"] = str(e)

    resp["status"] = "healthy" if resp.get("calendar_service_ready") and resp.get("cabins_loaded", 0) > 0 else "unhealthy"
    return resp


@app.get("/cabins", response_model=list[CabinInfo])
async def list_cabins():
    try:
        _, cabins = get_service()
        result = []
        for cabin in cabins:
            # Convert features from dict to string if needed
            features = cabin.get("features")
            if isinstance(features, dict):
                # If features is a dict (JSONB), check if it has 'raw' key
                if 'raw' in features:
                    features = features['raw']
                else:
                    # Otherwise, convert to comma-separated string from keys
                    features_str = ",".join([k for k, v in features.items() if v])
                    features = features_str if features_str else None
            elif features and not isinstance(features, str):
                features = str(features)
            
            # Always use cabin_id_string (ZB01, ZB02, etc.) - this is what we want to display
            # The cabin_id_string should be set from DB (ZB01, ZB02, ZB03, etc.)
            display_cabin_id = cabin.get("cabin_id_string")
            
            # If cabin_id_string is not set, it means the cabin doesn't have one in DB
            # This shouldn't happen if cabins were imported correctly
            if not display_cabin_id:
                # Fallback: use cabin_id (UUID) only if cabin_id_string is truly missing
                # But this shouldn't happen if cabins were imported correctly
                display_cabin_id = cabin.get("cabin_id", "UNKNOWN")
                # Don't print warning for every request - it's too noisy
                # print(f"Warning: Cabin {cabin.get('name')} missing cabin_id_string. Run: python database/import_cabins_to_db.py")
            
            # Ensure images_urls is always a list
            images_urls = cabin.get("images_urls") or []
            if isinstance(images_urls, str):
                # If it's a string, try to parse as JSON or split by comma
                import json
                try:
                    images_urls = json.loads(images_urls)
                except:
                    # If not JSON, split by comma
                    images_urls = [img.strip() for img in images_urls.split(",") if img.strip()]
            elif not isinstance(images_urls, list):
                # If it's not a list, convert to list
                images_urls = [images_urls] if images_urls else []
            
            result.append(
                CabinInfo(
                    cabin_id=display_cabin_id,  # Always use cabin_id_string (ZB01) if available
                    name=cabin.get("name"),
                    area=cabin.get("area"),
                    max_adults=int(cabin.get("max_adults", 0)) if cabin.get("max_adults") else None,
                    max_kids=int(cabin.get("max_kids", 0)) if cabin.get("max_kids") else None,
                    features=features,
                    base_price_night=float(cabin.get("base_price_night", 0)) if cabin.get("base_price_night") else None,
                    weekend_price=float(cabin.get("weekend_price", 0)) if cabin.get("weekend_price") else None,
                    calendar_id=cabin.get("calendar_id") or cabin.get("calendarId"),
                    images_urls=images_urls,
                )
            )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading cabins: {str(e)}")


@app.post("/availability", response_model=list[AvailabilityResponse])
async def check_availability(request: AvailabilityRequest):
    try:
        service, cabins = get_service()

        check_in_local = parse_datetime_local(request.check_in)
        check_out_local = parse_datetime_local(request.check_out)
        check_in_utc = to_utc(check_in_local)
        check_out_utc = to_utc(check_out_local)

        wanted_features = parse_features_arg(request.features)

        candidates = find_available_cabins(
            service=service,
            cabins=cabins,
            check_in_utc=check_in_utc,
            check_out_utc=check_out_utc,
            adults=request.adults,
            kids=request.kids,
            area=request.area,
            wanted_features=wanted_features,
            verbose=False,
        )

        result = []
        for cabin in candidates:
            pricing = compute_price_for_stay(cabin, check_in_local, check_out_local)
            
            # Convert features from dict to string if needed
            features = cabin.get("features")
            if isinstance(features, dict):
                # If features is a dict (JSONB), check if it has 'raw' key
                if 'raw' in features:
                    features = features['raw']
                else:
                    # Otherwise, convert to comma-separated string from keys
                    features_str = ",".join([k for k, v in features.items() if v])
                    features = features_str if features_str else None
            elif features and not isinstance(features, str):
                features = str(features)
            
            # Use cabin_id_string if available (ZB01, ZB02, etc.) for easier booking
            display_cabin_id = cabin.get("cabin_id_string") or cabin.get("cabin_id", "UNKNOWN")
            
            # Check for local images first, then use images_urls from DB
            local_images = []
            import os
            from pathlib import Path
            
            # Get all possible search IDs - try to match by name or find cabin_id_string
            search_ids = []
            
            # 1. Try cabin_id_string if available (ZB01, ZB02, etc.)
            if cabin.get("cabin_id_string") and len(str(cabin.get("cabin_id_string"))) <= 20:
                search_ids.append(str(cabin.get("cabin_id_string")))
            
            # 2. Try cabin_id if it's a short string (not UUID)
            cabin_id_val = cabin.get("cabin_id", "")
            if cabin_id_val and len(str(cabin_id_val)) <= 20 and "-" not in str(cabin_id_val):
                search_ids.append(str(cabin_id_val))
            
            # 3. Try to find by matching name with directory names in zimmers_pic
            # Map known cabin names to their IDs
            if not search_ids:
                cabin_name = cabin.get("name", "")
                name_to_id_map = {
                    "יולי": "ZB01",
                    "אמי": "ZB02", 
                    "מורן": "ZB03",
                    "מורני": "ZB03"
                }
                for name_key, cabin_id_str in name_to_id_map.items():
                    if name_key in cabin_name:
                        search_ids.append(cabin_id_str)
                        break
            
            # 4. If still no match, try all directories in zimmers_pic
            if not search_ids:
                pic_base_dir = BASE_DIR / "zimmers_pic"
                if pic_base_dir.exists():
                    # Just use the first directory as fallback (not ideal but works)
                    for pic_dir in sorted(pic_base_dir.iterdir()):
                        if pic_dir.is_dir() and (any(pic_dir.glob("*.jpg")) or any(pic_dir.glob("*.jpeg")) or any(pic_dir.glob("*.png"))):
                            search_ids.append(pic_dir.name)
                            break
            
            # Search for images in the found directories
            for search_id in search_ids:
                pic_dir = BASE_DIR / "zimmers_pic" / str(search_id)
                if pic_dir.exists() and pic_dir.is_dir():
                    for img_file in sorted(pic_dir.glob("*.jpg")):
                        local_images.append(f"/zimmers_pic/{search_id}/{img_file.name}")
                    for img_file in sorted(pic_dir.glob("*.jpeg")):
                        local_images.append(f"/zimmers_pic/{search_id}/{img_file.name}")
                    for img_file in sorted(pic_dir.glob("*.png")):
                        local_images.append(f"/zimmers_pic/{search_id}/{img_file.name}")
                    if local_images:
                        break  # Found images, no need to check other IDs
            
            # Use local images if available, otherwise use images_urls from DB
            final_images = local_images if local_images else (cabin.get("images_urls") or [])
            
            result.append(
                AvailabilityResponse(
                    cabin_id=display_cabin_id,  # Use cabin_id_string (ZB01) if available
                    name=cabin.get("name"),
                    area=cabin.get("area"),
                    nights=pricing["nights"],
                    regular_nights=pricing["regular"],
                    weekend_nights=pricing["weekend"],
                    total_price=pricing["total"],
                    max_adults=int(cabin.get("max_adults", 0)) if cabin.get("max_adults") else None,
                    max_kids=int(cabin.get("max_kids", 0)) if cabin.get("max_kids") else None,
                    features=features,
                    images_urls=final_images,
                )
            )

        # Save audit log for availability search
        try:
            import uuid
            search_id = str(uuid.uuid4())
            save_audit_log(
                table_name="availability_search",
                record_id=search_id,
                action="INSERT",  # Changed from "SEARCH" to "INSERT" to match schema constraint
                new_values={
                    "check_in": request.check_in,
                    "check_out": request.check_out,
                    "adults": request.adults,
                    "kids": request.kids,
                    "area": request.area,
                    "features": request.features,
                    "results_count": len(result),
                    "search_type": "availability"  # Add search type to distinguish
                }
            )
        except Exception as audit_error:
            # Don't fail the request if audit log fails
            print(f"Warning: Failed to save audit log: {audit_error}")

        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid input: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error checking availability: {str(e)}")


@app.get("/cabin/calendar/{cabin_id}")
async def get_cabin_calendar(cabin_id: str, start_date: Optional[str] = None, end_date: Optional[str] = None):
    """
    Get calendar events for a specific cabin to display in availability table.
    Returns booked dates and available dates.
    """
    try:
        service, cabins = get_service()
        
        # Find the cabin
        chosen = None
        request_cabin_id_normalized = normalize_text(cabin_id).lower()
        for cabin in cabins:
            cabin_id_string = cabin.get("cabin_id_string")
            if cabin_id_string:
                cabin_id_string_normalized = normalize_text(str(cabin_id_string)).lower()
                if cabin_id_string_normalized == request_cabin_id_normalized:
                    chosen = cabin
                    break
            
            cabin_id_normalized = normalize_text(str(cabin.get("cabin_id", ""))).lower()
            if cabin_id_normalized == request_cabin_id_normalized:
                chosen = cabin
                break
            
            cabin_name_normalized = normalize_text(str(cabin.get("name", ""))).lower()
            if cabin_name_normalized == request_cabin_id_normalized:
                chosen = cabin
                break
        
        if not chosen:
            raise HTTPException(status_code=404, detail=f"Cabin not found: {cabin_id}")
        
        cal_id = chosen.get("calendar_id") or chosen.get("calendarId")
        if not cal_id:
            raise HTTPException(status_code=400, detail=f"Cabin {cabin_id} missing calendar_id")
        
        # Default date range: next 60 days
        if not start_date:
            start_date = datetime.now(ISRAEL_TZ).date().isoformat()
        if not end_date:
            end_date = (datetime.now(ISRAEL_TZ).date() + timedelta(days=60)).isoformat()
        
        # Parse dates
        start_dt = datetime.fromisoformat(start_date).replace(tzinfo=ISRAEL_TZ)
        end_dt = datetime.fromisoformat(end_date).replace(tzinfo=ISRAEL_TZ)
        
        # Get events
        start_utc = to_utc(start_dt)
        end_utc = to_utc(end_dt)
        time_min = _to_rfc3339_z(start_utc)
        time_max = _to_rfc3339_z(end_utc)
        
        events = list_calendar_events(service, cal_id, time_min, time_max)
        
        # Convert events to date ranges
        booked_dates = []
        for e in events:
            e_start, e_end = _event_interval_utc(e)
            e_start_local = e_start.astimezone(ISRAEL_TZ).date()
            e_end_local = e_end.astimezone(ISRAEL_TZ).date()
            
            # Add all dates in the range
            current = e_start_local
            while current < e_end_local:
                booked_dates.append(current.isoformat())
                current += timedelta(days=1)
        
        return {
            "cabin_id": cabin_id,
            "start_date": start_date,
            "end_date": end_date,
            "booked_dates": list(set(booked_dates)),  # Remove duplicates
            "events": [
                {
                    "summary": e.get("summary", ""),
                    "start": e.get("start", {}).get("dateTime") or e.get("start", {}).get("date"),
                    "end": e.get("end", {}).get("dateTime") or e.get("end", {}).get("date"),
                }
                for e in events
            ]
        }
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid input: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting cabin calendar: {str(e)}")


@app.post("/quote", response_model=QuoteResponse)
async def get_quote(request: QuoteRequest):
    """
    מחזיר הצעת מחיר מפורטת עם breakdown מלא
    כולל: עונות, חגים, הנחות, תוספות
    """
    try:
        _, cabins = get_service()
        
        # מצא את הצימר - חיפוש לפי cabin_id_string (ZB01, ZB02), cabin_id (UUID), name, או calendar_id
        chosen = None
        request_cabin_id_normalized = normalize_text(request.cabin_id).lower()
        for cabin in cabins:
            # Try matching by cabin_id_string first (ZB01, ZB02, ZB03, etc.)
            cabin_id_string = cabin.get("cabin_id_string")
            if cabin_id_string:
                cabin_id_string_normalized = normalize_text(str(cabin_id_string)).lower()
                if cabin_id_string_normalized == request_cabin_id_normalized:
                    chosen = cabin
                    break
            
            # Try matching by cabin_id (UUID)
            cabin_id_normalized = normalize_text(str(cabin.get("cabin_id", ""))).lower()
            if cabin_id_normalized == request_cabin_id_normalized:
                chosen = cabin
                break
            
            # Try matching by name
            cabin_name_normalized = normalize_text(str(cabin.get("name", ""))).lower()
            if cabin_name_normalized == request_cabin_id_normalized:
                chosen = cabin
                break
            
            # Try matching by calendar_id (last 8 chars)
            calendar_id = cabin.get("calendar_id") or cabin.get("calendarId")
            if calendar_id:
                calendar_id_normalized = normalize_text(str(calendar_id)).lower()
                if calendar_id_normalized == request_cabin_id_normalized or calendar_id_normalized.endswith(request_cabin_id_normalized):
                    chosen = cabin
                    break
        
        if not chosen:
            # Log available cabin_ids for debugging
            available_ids = []
            for c in cabins[:5]:
                cabin_id = c.get("cabin_id", "N/A")
                name = c.get("name", "N/A")
                available_ids.append(f"{cabin_id} ({name})")
            raise HTTPException(
                status_code=404, 
                detail=f"Cabin not found: {request.cabin_id}. Available IDs (sample): {available_ids}"
            )
        
        # פרס תאריכים
        check_in_local = parse_datetime_local(request.check_in)
        check_out_local = parse_datetime_local(request.check_out)
        
        # המרת addons מ-AddonItem ל-Dict
        addons_list = None
        if request.addons:
            addons_list = [{"name": addon.name, "price": addon.price} for addon in request.addons]
        
        # חישוב מחיר מתקדם
        engine = PricingEngine()
        pricing = engine.calculate_price_breakdown(
            cabin=chosen,
            check_in=check_in_local,
            check_out=check_out_local,
            addons=addons_list,
            apply_discounts=True
        )
        
        quote_response = QuoteResponse(
            cabin_id=request.cabin_id,
            cabin_name=chosen.get("name"),
            check_in=request.check_in,
            check_out=request.check_out,
            nights=pricing["nights"],
            regular_nights=pricing["regular_nights"],
            weekend_nights=pricing["weekend_nights"],
            holiday_nights=pricing["holiday_nights"],
            high_season_nights=pricing["high_season_nights"],
            base_total=pricing["base_total"],
            weekend_surcharge=pricing["weekend_surcharge"],
            holiday_surcharge=pricing["holiday_surcharge"],
            high_season_surcharge=pricing["high_season_surcharge"],
            addons_total=pricing["addons_total"],
            addons=pricing["addons"],
            subtotal=pricing["subtotal"],
            discount=pricing["discount"],
            total=pricing["total"],
            breakdown=pricing["breakdown"]
        )
        
        # Optionally save quote to database
        try:
            save_quote(
                cabin_id=request.cabin_id,
                check_in=request.check_in,
                check_out=request.check_out,
                adults=request.adults,
                kids=request.kids,
                total_price=pricing["total"],
                quote_data=pricing
            )
        except Exception as e:
            # Don't fail if quote save fails
            print(f"Warning: Could not save quote: {e}")
        
        return quote_response
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid input: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error calculating quote: {str(e)}")


# ============================================
# Hold API Endpoints
# ============================================

class HoldRequest(BaseModel):
    cabin_id: str = Field(..., description="Cabin ID to hold")
    check_in: str = Field(..., description="Check-in date/time")
    check_out: str = Field(..., description="Check-out date/time")
    customer_name: Optional[str] = Field(None, description="Customer name")
    customer_id: Optional[str] = Field(None, description="Customer ID from DB")


class HoldResponse(BaseModel):
    hold_id: str
    cabin_id: str
    check_in: str
    check_out: str
    expires_at: str
    status: str
    message: str
    warning: Optional[str] = None


@app.post("/hold", response_model=HoldResponse)
async def create_hold(request: HoldRequest):
    """
    Create a temporary hold on a cabin (15 minutes)
    Prevents double booking while customer completes payment
    """
    try:
        service, cabins = get_service()
        
        # Find cabin
        chosen = None
        request_cabin_id_normalized = normalize_text(request.cabin_id).lower()
        for cabin in cabins:
            cabin_id_string = cabin.get("cabin_id_string")
            if cabin_id_string:
                cabin_id_string_normalized = normalize_text(str(cabin_id_string)).lower()
                if cabin_id_string_normalized == request_cabin_id_normalized:
                    chosen = cabin
                    break
            
            cabin_id_normalized = normalize_text(str(cabin.get("cabin_id", ""))).lower()
            if cabin_id_normalized == request_cabin_id_normalized:
                chosen = cabin
                break
            
            cabin_name_normalized = normalize_text(str(cabin.get("name", ""))).lower()
            if cabin_name_normalized == request_cabin_id_normalized:
                chosen = cabin
                break
            
            calendar_id = cabin.get("calendar_id") or cabin.get("calendarId")
            if calendar_id:
                calendar_id_normalized = normalize_text(str(calendar_id)).lower()
                if calendar_id_normalized == request_cabin_id_normalized or calendar_id_normalized.endswith(request_cabin_id_normalized):
                    chosen = cabin
                    break
        
        if not chosen:
            raise HTTPException(status_code=404, detail=f"Cabin not found: {request.cabin_id}")
        
        # Parse dates
        check_in_local = parse_datetime_local(request.check_in)
        check_out_local = parse_datetime_local(request.check_out)
        check_in_utc = to_utc(check_in_local)
        check_out_utc = to_utc(check_out_local)
        
        # Check availability
        cal_id = chosen.get("calendar_id") or chosen.get("calendarId")
        if not cal_id:
            raise HTTPException(status_code=400, detail=f"Cabin {request.cabin_id} missing calendar_id")
        
        is_available, conflicts = is_cabin_available(service, cal_id, check_in_utc, check_out_utc)
        if not is_available:
            raise HTTPException(
                status_code=409,
                detail=f"Cabin {request.cabin_id} is not available. Conflicts: {len(conflicts)}",
            )
        
        # Create hold
        hold_manager = get_hold_manager()
        
        # Use date strings for hold key (YYYY-MM-DD format)
        check_in_date = check_in_local.date().isoformat()
        check_out_date = check_out_local.date().isoformat()
        
        hold_data = hold_manager.create_hold(
            cabin_id=request.cabin_id,
            check_in=check_in_date,
            check_out=check_out_date,
            customer_name=request.customer_name,
            customer_id=request.customer_id
        )
        
        # Create HOLD event in calendar
        if hold_manager._is_available():
            customer_name = request.customer_name or "לקוח"
            summary = f"🔒 HOLD | {customer_name}"
            description = f"Hold for cabin {request.cabin_id}\nCustomer: {customer_name}\nHold ID: {hold_data['hold_id']}"
            
            try:
                hold_event = create_calendar_event(
                    service=service,
                    calendar_id=cal_id,
                    summary=summary,
                    start_local=check_in_local,
                    end_local=check_out_local,
                    description=description,
                )
                # Store event_id in hold data (optional, for cleanup later)
                # Note: We can't modify Redis data, but we can store it separately if needed
            except Exception as e:
                print(f"Warning: Could not create HOLD calendar event: {e}")
        
        return HoldResponse(
            hold_id=hold_data["hold_id"],
            cabin_id=hold_data["cabin_id"],
            check_in=request.check_in,
            check_out=request.check_out,
            expires_at=hold_data["expires_at"],
            status=hold_data["status"],
            message="Hold created successfully",
            warning=hold_data.get("warning")
        )
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid input: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating hold: {str(e)}")


@app.get("/hold/{hold_id}")
async def get_hold(hold_id: str):
    """
    Get hold status by hold_id
    """
    try:
        hold_manager = get_hold_manager()
        hold_data = hold_manager.get_hold(hold_id)
        
        if not hold_data:
            raise HTTPException(status_code=404, detail="Hold not found or expired")
        
        return {
            "hold_id": hold_data["hold_id"],
            "cabin_id": hold_data["cabin_id"],
            "check_in": hold_data["check_in"],
            "check_out": hold_data["check_out"],
            "expires_at": hold_data["expires_at"],
            "status": hold_data["status"],
            "customer_name": hold_data.get("customer_name"),
            "customer_id": hold_data.get("customer_id"),
            "created_at": hold_data.get("created_at")
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching hold: {str(e)}")


@app.delete("/hold/{hold_id}")
async def release_hold(hold_id: str):
    """
    Release a hold manually
    """
    try:
        hold_manager = get_hold_manager()
        
        # Get hold data first to find calendar event
        hold_data = hold_manager.get_hold(hold_id)
        if not hold_data:
            raise HTTPException(status_code=404, detail="Hold not found or expired")
        
        # Release from Redis
        released = hold_manager.release_hold(hold_id)
        if not released:
            raise HTTPException(status_code=404, detail="Hold not found or already released")
        
        # Try to remove calendar event (optional - may not have event_id stored)
        # For now, we'll leave the calendar event (it will be overwritten by booking or expire)
        # In production, you might want to store event_id in Redis with the hold
        
        return {
            "success": True,
            "message": "Hold released successfully",
            "hold_id": hold_id
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error releasing hold: {str(e)}")


@app.post("/book", response_model=BookingResponse)
async def book_cabin(request: BookingRequest):
    """
    Create a confirmed booking
    If hold_id is provided, converts the hold to a booking
    Otherwise, creates a new booking (with hold check)
    """
    try:
        service, cabins = get_service()

        check_in_local = parse_datetime_local(request.check_in)
        check_out_local = parse_datetime_local(request.check_out)
        check_in_utc = to_utc(check_in_local)
        check_out_utc = to_utc(check_out_local)

        # Find cabin - search by cabin_id_string (ZB01, ZB02), cabin_id (UUID), name, or calendar_id
        chosen = None
        request_cabin_id_normalized = normalize_text(request.cabin_id).lower()
        for cabin in cabins:
            # Try matching by cabin_id_string first (ZB01, ZB02, ZB03, etc.)
            cabin_id_string = cabin.get("cabin_id_string")
            if cabin_id_string:
                cabin_id_string_normalized = normalize_text(str(cabin_id_string)).lower()
                if cabin_id_string_normalized == request_cabin_id_normalized:
                    chosen = cabin
                    break
            
            # Try matching by cabin_id (UUID)
            cabin_id_normalized = normalize_text(str(cabin.get("cabin_id", ""))).lower()
            if cabin_id_normalized == request_cabin_id_normalized:
                chosen = cabin
                break
            
            # Try matching by name
            cabin_name_normalized = normalize_text(str(cabin.get("name", ""))).lower()
            if cabin_name_normalized == request_cabin_id_normalized:
                chosen = cabin
                break
            
            # Try matching by calendar_id (last 8 chars)
            calendar_id = cabin.get("calendar_id") or cabin.get("calendarId")
            if calendar_id:
                calendar_id_normalized = normalize_text(str(calendar_id)).lower()
                if calendar_id_normalized == request_cabin_id_normalized or calendar_id_normalized.endswith(request_cabin_id_normalized):
                    chosen = cabin
                    break

        if not chosen:
            # Log available cabin_ids for debugging
            available_ids = []
            for c in cabins[:5]:
                cabin_id = c.get("cabin_id", "N/A")
                name = c.get("name", "N/A")
                available_ids.append(f"{cabin_id} ({name})")
            raise HTTPException(status_code=404, detail=f"Cabin not found: {request.cabin_id}. Available: {available_ids}")

        cal_id = chosen.get("calendar_id") or chosen.get("calendarId")
        if not cal_id:
            raise HTTPException(status_code=400, detail=f"Cabin {request.cabin_id} missing calendar_id")

        # Check for hold if hold_id provided
        hold_manager = get_hold_manager()
        hold_id = request.hold_id
        
        if hold_id:
            # Verify hold exists and matches booking
            hold_data = hold_manager.get_hold(hold_id)
            if not hold_data:
                raise HTTPException(status_code=404, detail="Hold not found or expired")
            
            if hold_data["cabin_id"] != request.cabin_id:
                raise HTTPException(status_code=400, detail="Hold cabin_id does not match booking")
            
            # Convert hold to booking
            hold_manager.convert_hold_to_booking(hold_id)
        else:
            # Check if cabin is on hold
            if hold_manager.check_hold_exists(request.cabin_id, request.check_in, request.check_out):
                raise HTTPException(
                    status_code=409,
                    detail="Cabin is on hold. Please use the hold_id to complete booking.",
                )

        # Check availability in calendar
        is_available, conflicts = is_cabin_available(service, cal_id, check_in_utc, check_out_utc)
        if not is_available:
            raise HTTPException(
                status_code=409,
                detail=f"Cabin {request.cabin_id} is not available. Conflicts: {len(conflicts)}",
            )

        customer = request.customer or "לקוח"
        phone = request.phone or ""
        notes = request.notes or ""

        # Save customer to DB
        customer_id = save_customer_to_db(
            name=customer,
            email=request.email,
            phone=phone,
        )

        # Create calendar event first (to get event_id and event_link)
        summary = f"הזמנה | {customer}"
        desc_lines = [
            f"Cabin: {request.cabin_id}",
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
        
        event_id = created.get("id")
        event_link = created.get("htmlLink")

        # Calculate total_price if not provided
        total_price = request.total_price
        if total_price is None or total_price == 0:
            # Calculate price using compute_price_for_stay
            from src.main import compute_price_for_stay
            pricing = compute_price_for_stay(chosen, check_in_local, check_out_local)
            total_price = pricing.get("total", 0.0)
            # If addons are provided, add them to the total
            if request.addons:
                from src.pricing import PricingEngine
                engine = PricingEngine()
                addons_total = sum(addon.get("price", 0) for addon in request.addons if isinstance(addon, dict))
                total_price += addons_total

        # Save booking to DB (with event_id and event_link)
        booking_id = save_booking_to_db(
            cabin_id=chosen.get("cabin_id"),
            customer_id=customer_id,
            check_in=check_in_local.date().isoformat(),
            check_out=check_out_local.date().isoformat(),
            adults=request.adults,
            kids=request.kids,
            total_price=total_price,
            status="confirmed",
            event_id=event_id,
            event_link=event_link,
        )
        
        # Payment handling (Stage 5)
        payment_intent_id = None
        client_secret = None
        
        if request.create_payment and total_price and total_price > 0:
            # Create Payment Intent
            try:
                payment_manager = get_payment_manager()
                if payment_manager.is_available():
                    payment_result = payment_manager.create_payment_intent(
                        amount=Decimal(str(total_price)),
                        currency="ils",
                        booking_id=booking_id,
                        customer_id=customer_id,
                        cabin_id=request.cabin_id,
                        description=f"Booking {booking_id} - {chosen.get('name')}",
                        metadata={
                            "cabin_name": chosen.get("name", ""),
                            "check_in": check_in_local.date().isoformat(),
                            "check_out": check_out_local.date().isoformat(),
                        }
                    )
                    payment_intent_id = payment_result["payment_intent_id"]
                    client_secret = payment_result["client_secret"]
                else:
                    print("Warning: Payment gateway not configured. Booking created without payment.")
            except Exception as payment_error:
                print(f"Warning: Could not create payment intent: {payment_error}")
                # Continue without payment - booking is still created
        
        # Save transaction (pending status)
        if booking_id:
            # Use "pending" if payment intent exists, otherwise don't save transaction if no payment
            transaction_status = "pending" if payment_intent_id else None
            if transaction_status:  # Only save if there's a payment intent
                transaction_id = save_transaction(
                    booking_id=booking_id,
                    payment_id=payment_intent_id or request.payment_intent_id,
                    amount=total_price or 0.0,
                    status=transaction_status,
                    payment_method=None
                )
        
        # Save audit log for booking
        if booking_id:
            save_audit_log(
                table_name="bookings",
                record_id=booking_id,
                action="INSERT",
                new_values={
                    "cabin_id": request.cabin_id,
                    "customer_id": customer_id,
                    "check_in": check_in_local.date().isoformat(),
                    "check_out": check_out_local.date().isoformat(),
                    "adults": request.adults,
                    "kids": request.kids,
                    "total_price": total_price,
                    "status": "confirmed",
                    "event_id": event_id,
                    "event_link": event_link,
                    "payment_intent_id": payment_intent_id
                }
            )
        
        # Send booking confirmation email
        if booking_id and request.email:
            try:
                email_service = get_email_service()
                # Get cabin details for email
                cabin_details = chosen
                cabin_address = cabin_details.get("address") or cabin_details.get("location")
                cabin_coordinates = cabin_details.get("coordinates") or cabin_details.get("lat_lon")
                
                email_service.send_booking_confirmation(
                    customer_email=request.email,
                    customer_name=customer,
                    booking_id=booking_id,
                    cabin_name=chosen.get("name", ""),
                    cabin_area=chosen.get("area", ""),
                    check_in=check_in_local.strftime("%d/%m/%Y %H:%M"),
                    check_out=check_out_local.strftime("%d/%m/%Y %H:%M"),
                    adults=request.adults or 0,
                    kids=request.kids or 0,
                    total_price=total_price or 0.0,
                    event_link=event_link,
                    cabin_address=cabin_address,
                    cabin_coordinates=cabin_coordinates
                )
            except Exception as email_error:
                print(f"Warning: Could not send confirmation email: {email_error}")
                # Don't fail the booking if email fails

        return BookingResponse(
            success=True,
            booking_id=booking_id,
            cabin_id=request.cabin_id,
            event_id=event_id,
            event_link=event_link,
            payment_intent_id=payment_intent_id,
            client_secret=client_secret,
            message="Booking created successfully" + (" - Payment required" if payment_intent_id else ""),
        )
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid input: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating booking: {str(e)}")


# ============================================
# Admin API Endpoints
# ============================================

@app.get("/admin/bookings")
async def get_all_bookings(
    status: Optional[str] = None,
    limit: int = 100,
    offset: int = 0
):
    """
    Get all bookings (admin endpoint)
    """
    try:
        from src.db import get_db_connection
        from psycopg2.extras import RealDictCursor
        import psycopg2
        
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor(cursor_factory=RealDictCursor)
                
                # Simple query first - get bookings without transactions
                query = """
                    SELECT 
                        b.id::text as booking_id,
                        b.cabin_id::text as cabin_id,
                        c.name as cabin_name,
                        b.customer_id::text as customer_id,
                        cust.name as customer_name,
                        cust.email as customer_email,
                        cust.phone as customer_phone,
                        b.check_in,
                        b.check_out,
                        b.adults,
                        b.kids,
                        b.status,
                        b.total_price,
                        b.event_id,
                        b.event_link,
                        b.created_at,
                        b.created_at as updated_at
                    FROM bookings b
                    LEFT JOIN cabins c ON b.cabin_id = c.id
                    LEFT JOIN customers cust ON b.customer_id = cust.id
                """
                
                params = []
                if status:
                    query += " WHERE b.status = %s"
                    params.append(status)
                
                query += " ORDER BY b.created_at DESC LIMIT %s OFFSET %s"
                params.extend([limit, offset])
                
                cursor.execute(query, params)
                rows = cursor.fetchall()
                
                # Convert to list of dicts
                bookings = []
                booking_ids = []
                
                for row in rows:
                    booking = dict(row)
                    booking["transactions"] = []  # Initialize empty
                    booking_ids.append(booking["booking_id"])
                    bookings.append(booking)
                
                # Now fetch transactions separately if table exists
                if booking_ids:
                    try:
                        cursor.execute("""
                            SELECT EXISTS (
                                SELECT FROM information_schema.tables 
                                WHERE table_name = 'transactions'
                            )
                        """)
                        has_transactions_table = cursor.fetchone()[0]
                        
                        if has_transactions_table:
                            # Fetch transactions for these bookings
                            placeholders = ','.join(['%s'] * len(booking_ids))
                            cursor.execute(f"""
                                SELECT 
                                    booking_id::text as booking_id,
                                    id::text as transaction_id,
                                    payment_id,
                                    amount,
                                    COALESCE(currency, 'ILS') as currency,
                                    status,
                                    payment_method,
                                    created_at
                                FROM transactions
                                WHERE booking_id::text IN ({placeholders})
                                ORDER BY created_at DESC
                            """, booking_ids)
                            
                            transaction_rows = cursor.fetchall()
                            
                            # Group transactions by booking_id
                            transactions_by_booking = {}
                            for trans_row in transaction_rows:
                                trans_dict = dict(trans_row)
                                booking_id = trans_dict.pop("booking_id")
                                if booking_id not in transactions_by_booking:
                                    transactions_by_booking[booking_id] = []
                                transactions_by_booking[booking_id].append(trans_dict)
                            
                            # Add transactions to bookings
                            for booking in bookings:
                                booking_id = booking["booking_id"]
                                if booking_id in transactions_by_booking:
                                    booking["transactions"] = transactions_by_booking[booking_id]
                    except Exception as trans_error:
                        print(f"Warning: Could not fetch transactions: {trans_error}")
                        import traceback
                        traceback.print_exc()
                        # Continue without transactions
                
                return bookings
        except psycopg2.OperationalError as db_error:
            # Database not available - return empty list
            print(f"Warning: Database not available for /admin/bookings: {db_error}")
            import traceback
            traceback.print_exc()
            return []
            
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Error in /admin/bookings: {error_details}")
        raise HTTPException(status_code=500, detail=f"Error fetching bookings: {str(e)}")


@app.get("/admin/bookings/{booking_id}")
async def get_booking_by_id(booking_id: str):
    """
    Get booking by ID (admin endpoint)
    """
    try:
        from src.db import get_db_connection
        from psycopg2.extras import RealDictCursor
        import uuid
        
        # Validate UUID
        try:
            uuid.UUID(booking_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid booking ID format")
        
        with get_db_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # Check if updated_at column exists
            cursor.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'bookings' AND column_name = 'updated_at'
            """)
            has_updated_at = cursor.fetchone() is not None
            
            if has_updated_at:
                query = """
                    SELECT 
                        b.id::text as booking_id,
                        b.cabin_id::text as cabin_id,
                        c.name as cabin_name,
                        c.area as cabin_area,
                        b.customer_id::text as customer_id,
                        cust.name as customer_name,
                        cust.email as customer_email,
                        cust.phone as customer_phone,
                        b.check_in,
                        b.check_out,
                        b.adults,
                        b.kids,
                        b.status,
                        b.total_price,
                        b.event_id,
                        b.event_link,
                        b.created_at,
                        b.updated_at
                    FROM bookings b
                    LEFT JOIN cabins c ON b.cabin_id = c.id
                    LEFT JOIN customers cust ON b.customer_id = cust.id
                    WHERE b.id = %s::uuid
                """
            else:
                query = """
                    SELECT 
                        b.id::text as booking_id,
                        b.cabin_id::text as cabin_id,
                        c.name as cabin_name,
                        c.area as cabin_area,
                        b.customer_id::text as customer_id,
                        cust.name as customer_name,
                        cust.email as customer_email,
                        cust.phone as customer_phone,
                        b.check_in,
                        b.check_out,
                        b.adults,
                        b.kids,
                        b.status,
                        b.total_price,
                        b.event_id,
                        b.event_link,
                        b.created_at,
                        b.created_at as updated_at
                    FROM bookings b
                    LEFT JOIN cabins c ON b.cabin_id = c.id
                    LEFT JOIN customers cust ON b.customer_id = cust.id
                    WHERE b.id = %s::uuid
                """
            
            cursor.execute(query, (booking_id,))
            
            row = cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Booking not found")
            
            # Get transactions for this booking (if table exists)
            transactions = []
            try:
                # Check if transactions table exists
                cursor.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = 'transactions'
                    )
                """)
                table_exists = cursor.fetchone()[0]
                
                if table_exists:
                    # Try to get transactions - use simple query that works with any schema
                    try:
                        cursor.execute("""
                            SELECT 
                                id::text as transaction_id,
                                COALESCE(payment_id, '') as payment_id,
                                COALESCE(amount, 0) as amount,
                                COALESCE(currency, 'ILS') as currency,
                                COALESCE(status, 'pending') as status,
                                COALESCE(payment_method, '') as payment_method,
                                COALESCE(created_at, NOW()) as created_at,
                                COALESCE(updated_at, created_at, NOW()) as updated_at
                            FROM transactions
                            WHERE booking_id = %s::uuid
                            ORDER BY created_at DESC NULLS LAST
                        """, (booking_id,))
                        trans_rows = cursor.fetchall()
                        if trans_rows:
                            transactions = [dict(row) for row in trans_rows]
                    except Exception as trans_query_error:
                        # If query fails (e.g., missing columns), just return empty list
                        print(f"Warning: Could not fetch transactions: {trans_query_error}")
                        transactions = []
            except Exception as trans_error:
                # If table doesn't exist or any other error, just skip transactions
                print(f"Warning: Transactions table check failed: {trans_error}")
                transactions = []
            
            booking = dict(row)
            booking["transactions"] = transactions
            
            # Extract payment_intent_id from transactions if available
            if transactions and len(transactions) > 0:
                # Get the most recent transaction with a payment_id
                for trans in transactions:
                    if trans.get("payment_id"):
                        booking["payment_intent_id"] = trans["payment_id"]
                        break
            
            return booking
            
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Error in get_booking_by_id: {error_details}")
        raise HTTPException(status_code=500, detail=f"Error fetching booking: {str(e)}")


@app.post("/admin/bookings/{booking_id}/cancel")
async def cancel_booking(booking_id: str):
    """
    Cancel a booking (admin endpoint)
    - Updates status to 'cancelled' in DB
    - Deletes event from Google Calendar
    - Updates availability
    """
    try:
        from src.db import get_db_connection
        from src.main import delete_calendar_event
        from psycopg2.extras import RealDictCursor
        import uuid
        
        # Validate UUID
        try:
            uuid.UUID(booking_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid booking ID format")
        
        # Get booking details
        with get_db_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            cursor.execute("""
                SELECT 
                    b.id::text as booking_id,
                    b.cabin_id::text as cabin_id,
                    b.event_id,
                    b.status,
                    c.calendar_id,
                    c.name as cabin_name
                FROM bookings b
                LEFT JOIN cabins c ON b.cabin_id = c.id
                WHERE b.id = %s::uuid
            """, (booking_id,))
            
            row = cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Booking not found")
            
            booking = dict(row)
            
            # Check if already cancelled
            if booking.get('status') == 'cancelled':
                raise HTTPException(status_code=400, detail="Booking is already cancelled")
            
            # Check if updated_at column exists
            cursor.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'bookings' AND column_name = 'updated_at'
            """)
            has_updated_at = cursor.fetchone() is not None
            
            # Update status in DB
            if has_updated_at:
                cursor.execute("""
                    UPDATE bookings
                    SET status = 'cancelled', updated_at = NOW()
                    WHERE id = %s::uuid
                """, (booking_id,))
            else:
                cursor.execute("""
                    UPDATE bookings
                    SET status = 'cancelled'
                    WHERE id = %s::uuid
                """, (booking_id,))
            
            # Save audit log
            try:
                from src.db import save_audit_log
                save_audit_log(
                    'bookings',
                    booking_id,
                    'UPDATE',
                    old_values={'status': booking.get('status')},
                    new_values={'status': 'cancelled'}
                )
            except Exception as audit_error:
                print(f"Warning: Could not save audit log: {audit_error}")
            
            conn.commit()
            
            # Delete from Google Calendar if event_id exists
            calendar_deleted = False
            if booking.get('event_id') and booking.get('calendar_id'):
                try:
                    service, _ = get_service()
                    calendar_deleted = delete_calendar_event(
                        service,
                        booking.get('calendar_id'),
                        booking.get('event_id')
                    )
                except Exception as cal_error:
                    print(f"Warning: Could not delete calendar event: {cal_error}")
            
            return {
                "success": True,
                "message": "Booking cancelled successfully",
                "booking_id": booking_id,
                "calendar_deleted": calendar_deleted,
                "cabin_name": booking.get('cabin_name')
            }
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error cancelling booking: {str(e)}")


# ============================================
# Payment API Endpoints (Stage 5)
# ============================================

@app.post("/webhooks/stripe")
async def stripe_webhook(request: Request):
    """
    Handle Stripe webhook events
    Verifies payment and updates booking status
    """
    import json
    
    try:
        payload = await request.body()
        signature = request.headers.get("stripe-signature")
        
        if not signature:
            raise HTTPException(status_code=400, detail="Missing stripe-signature header")
        
        payment_manager = get_payment_manager()
        if not payment_manager.is_available():
            raise HTTPException(status_code=503, detail="Payment gateway not configured")
        
        # Verify webhook signature
        event = payment_manager.verify_webhook(payload, signature)
        
        # Handle different event types
        if event["type"] == "payment_intent.succeeded":
            payment_intent = event["data"]["object"]
            payment_intent_id = payment_intent["id"]
            metadata = payment_intent.get("metadata", {})
            booking_id = metadata.get("booking_id")
            
            if booking_id:
                # Update transaction by payment_id
                from src.db import get_db_connection
                from psycopg2.extras import RealDictCursor
                
                with get_db_connection() as conn:
                    cursor = conn.cursor(cursor_factory=RealDictCursor)
                    
                    # Find transaction by payment_id
                    cursor.execute("""
                        SELECT id::text as transaction_id
                        FROM transactions
                        WHERE payment_id = %s
                        LIMIT 1
                    """, (payment_intent_id,))
                    
                    row = cursor.fetchone()
                    if row:
                        transaction_id = row["transaction_id"]
                        from src.db import update_transaction_status
                        payment_method = payment_intent.get("payment_method_types", [None])[0] if payment_intent.get("payment_method_types") else None
                        update_transaction_status(
                            transaction_id=transaction_id,
                            status="completed",
                            payment_method=payment_method
                        )
                        print(f"Payment succeeded for booking {booking_id}, transaction {transaction_id}")
                        
                        # Send payment receipt email
                        try:
                            # Get booking and customer details
                            cursor.execute("""
                                SELECT 
                                    b.id::text as booking_id,
                                    b.total_price,
                                    c.name as customer_name,
                                    c.email as customer_email,
                                    cab.name as cabin_name
                                FROM bookings b
                                LEFT JOIN customers c ON b.customer_id = c.id
                                LEFT JOIN cabins cab ON b.cabin_id = cab.id
                                WHERE b.id = %s::uuid
                            """, (booking_id,))
                            booking_row = cursor.fetchone()
                            
                            if booking_row and booking_row.get("customer_email"):
                                email_service = get_email_service()
                                email_service.send_payment_receipt(
                                    customer_email=booking_row["customer_email"],
                                    customer_name=booking_row["customer_name"] or "לקוח",
                                    booking_id=booking_id,
                                    cabin_name=booking_row["cabin_name"] or "",
                                    payment_amount=float(booking_row["total_price"] or 0),
                                    payment_method=payment_method or "כרטיס אשראי",
                                    transaction_id=payment_intent_id
                                )
                        except Exception as email_error:
                            print(f"Warning: Could not send payment receipt email: {email_error}")
                    else:
                        print(f"Warning: Transaction not found for payment_intent_id {payment_intent_id}")
        
        elif event["type"] == "payment_intent.payment_failed":
            payment_intent = event["data"]["object"]
            payment_intent_id = payment_intent["id"]
            metadata = payment_intent.get("metadata", {})
            booking_id = metadata.get("booking_id")
            
            if booking_id:
                # Update transaction by payment_id
                from src.db import get_db_connection
                from psycopg2.extras import RealDictCursor
                
                with get_db_connection() as conn:
                    cursor = conn.cursor(cursor_factory=RealDictCursor)
                    
                    cursor.execute("""
                        SELECT id::text as transaction_id
                        FROM transactions
                        WHERE payment_id = %s
                        LIMIT 1
                    """, (payment_intent_id,))
                    
                    row = cursor.fetchone()
                    if row:
                        transaction_id = row["transaction_id"]
                        from src.db import update_transaction_status
                        update_transaction_status(
                            transaction_id=transaction_id,
                            status="failed",
                            payment_method=None
                        )
                        print(f"Payment failed for booking {booking_id}, transaction {transaction_id}")
        
        return {"status": "success"}
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Webhook error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing webhook: {str(e)}")


@app.get("/admin/holds")
async def get_all_holds():
    """
    Get all active holds (admin endpoint)
    """
    try:
        hold_manager = get_hold_manager()
        holds = hold_manager.get_all_active_holds()
        
        return {
            "holds": holds,
            "count": len(holds)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching holds: {str(e)}")


@app.get("/admin/audit")
async def get_audit_logs(
    table_name: Optional[str] = None,
    action: Optional[str] = None,
    limit: int = 100,
    offset: int = 0
):
    """
    Get audit logs (admin endpoint)
    Supports both old schema (entity_type, entity_id, payload) and new schema (table_name, record_id, old_values, new_values)
    """
    try:
        from src.db import get_db_connection
        from psycopg2.extras import RealDictCursor
        import psycopg2
        
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor(cursor_factory=RealDictCursor)
                
                # First, check which schema the table uses
                cursor.execute("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'audit_log' 
                    AND column_name IN ('table_name', 'entity_type')
                """)
                columns = [row['column_name'] for row in cursor.fetchall()]
                
                if 'table_name' in columns:
                    # New schema with table_name, record_id, old_values, new_values
                    query = """
                        SELECT 
                            id::text as audit_id,
                            COALESCE(table_name, 'N/A') as table_name,
                            record_id::text as record_id,
                            action,
                            old_values,
                            new_values,
                            user_id::text as user_id,
                            created_at
                        FROM audit_log
                    """
                    
                    conditions = []
                    params = []
                    
                    if table_name:
                        conditions.append("table_name = %s")
                        params.append(table_name)
                    
                    if action:
                        conditions.append("action = %s")
                        params.append(action)
                    
                    if conditions:
                        query += " WHERE " + " AND ".join(conditions)
                    
                    query += " ORDER BY created_at DESC LIMIT %s OFFSET %s"
                    params.extend([limit, offset])
                    
                    cursor.execute(query, params)
                    rows = cursor.fetchall()
                    
                    return [dict(row) for row in rows]
                elif 'entity_type' in columns:
                    # Old schema with entity_type, entity_id, payload
                    query = """
                        SELECT 
                            id::text as audit_id,
                            COALESCE(entity_type, 'N/A') as table_name,
                            entity_id::text as record_id,
                            action,
                            payload->'old_values' as old_values,
                            payload->'new_values' as new_values,
                            payload->>'user_id' as user_id,
                            created_at
                        FROM audit_log
                    """
                    
                    conditions = []
                    params = []
                    
                    if table_name:
                        conditions.append("entity_type = %s")
                        params.append(table_name)
                    
                    if action:
                        conditions.append("action = %s")
                        params.append(action)
                    
                    if conditions:
                        query += " WHERE " + " AND ".join(conditions)
                    
                    query += " ORDER BY created_at DESC LIMIT %s OFFSET %s"
                    params.extend([limit, offset])
                    
                    cursor.execute(query, params)
                    rows = cursor.fetchall()
                    
                    return [dict(row) for row in rows]
                else:
                    # Unknown schema - return empty
                    return []
                    
        except psycopg2.OperationalError as db_error:
            # Database not available - return empty list
            print(f"Warning: Database not available for /admin/audit: {db_error}")
            return []
        except psycopg2.ProgrammingError as schema_error:
            # Schema error - return empty list
            print(f"Warning: Schema error in /admin/audit: {schema_error}")
            return []
            
    except Exception as e:
        print(f"Error in /admin/audit: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching audit logs: {str(e)}")


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("API_PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)

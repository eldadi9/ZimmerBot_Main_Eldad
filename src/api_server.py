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
    create_conversation,
    save_message,
    get_conversation,
    update_conversation_status,
    get_business_fact,
    get_all_business_facts,
    set_business_fact,
    get_approved_faq,
    suggest_faq,
    approve_faq,
    reject_faq,
    get_pending_faqs,
    get_all_faqs,
    update_faq,
    delete_faq,
    delete_business_fact,
)
from src.hold import get_hold_manager
from src.payment import get_payment_manager
from src.email_service import get_email_service
from src.agent import Agent
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
            "agent": {
                "chat": "/agent/chat",
            },
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


@app.put("/admin/bookings/{booking_id}")
async def update_booking(booking_id: str, booking_update: dict):
    """
    Update booking details (admin endpoint)
    """
    try:
        from src.db import get_db_connection, save_customer_to_db
        from psycopg2.extras import RealDictCursor
        import uuid
        from datetime import datetime
        
        # Validate UUID
        try:
            uuid.UUID(booking_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid booking ID format")
        
        # Extract update data
        customer_name = booking_update.get('customer_name')
        customer_email = booking_update.get('customer_email')
        customer_phone = booking_update.get('customer_phone')
        cabin_id_input = booking_update.get('cabin_id')  # Can be UUID or cabin_id_string (ZB01, ZB02)
        check_in = booking_update.get('check_in')
        check_out = booking_update.get('check_out')
        adults = booking_update.get('adults', 0)
        kids = booking_update.get('kids', 0)
        total_price = booking_update.get('total_price', 0)
        status = booking_update.get('status')
        
        if not customer_name:
            raise HTTPException(status_code=400, detail="customer_name is required")
        if not cabin_id_input:
            raise HTTPException(status_code=400, detail="cabin_id is required")
        if not check_in or not check_out:
            raise HTTPException(status_code=400, detail="check_in and check_out are required")
        
        with get_db_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # Convert cabin_id_input (could be UUID or cabin_id_string like ZB01) to UUID
            cabin_uuid = None
            new_calendar_id = None
            try:
                # Try to validate as UUID first
                import uuid as uuid_lib
                uuid_lib.UUID(cabin_id_input)
                cabin_uuid = cabin_id_input
                # Get calendar_id for this cabin
                cursor.execute("""
                    SELECT calendar_id FROM cabins WHERE id = %s::uuid
                """, (cabin_uuid,))
                cabin_row = cursor.fetchone()
                if cabin_row:
                    new_calendar_id = cabin_row['calendar_id']
            except (ValueError, AttributeError):
                # Not a UUID - try to find by cabin_id_string
                cursor.execute("""
                    SELECT id::text, calendar_id 
                    FROM cabins 
                    WHERE cabin_id_string = %s
                """, (cabin_id_input,))
                cabin_row = cursor.fetchone()
                if cabin_row:
                    cabin_uuid = cabin_row['id']
                    new_calendar_id = cabin_row['calendar_id']
                else:
                    raise HTTPException(status_code=404, detail=f"Cabin not found: {cabin_id_input}. Must be a valid UUID or cabin_id_string (e.g., ZB01, ZB02)")
            
            if not cabin_uuid:
                raise HTTPException(status_code=404, detail=f"Cabin not found: {cabin_id_input}")
            
            # Get existing booking with old cabin info for calendar migration
            cursor.execute("""
                SELECT 
                    b.customer_id, 
                    b.cabin_id::text, 
                    b.event_id,
                    c.calendar_id as old_calendar_id
                FROM bookings b
                LEFT JOIN cabins c ON b.cabin_id = c.id
                WHERE b.id = %s::uuid
            """, (booking_id,))
            existing = cursor.fetchone()
            
            if not existing:
                raise HTTPException(status_code=404, detail="Booking not found")
            
            existing_customer_id = existing['customer_id']
            existing_cabin_id = existing['cabin_id']
            event_id = existing['event_id']
            old_calendar_id = existing['old_calendar_id']
            
            # Update or create customer
            customer_id = existing_customer_id
            if customer_id:
                # Update existing customer
                update_fields = []
                update_values = []
                
                if customer_name:
                    update_fields.append("name = %s")
                    update_values.append(customer_name)
                if customer_email:
                    update_fields.append("email = %s")
                    update_values.append(customer_email)
                if customer_phone:
                    update_fields.append("phone = %s")
                    update_values.append(customer_phone)
                
                if update_fields:
                    update_values.append(customer_id)
                    cursor.execute(f"""
                        UPDATE customers SET
                            {', '.join(update_fields)}
                        WHERE id = %s::uuid
                    """, tuple(update_values))
            else:
                # Create new customer
                customer_id = save_customer_to_db(
                    name=customer_name,
                    email=customer_email,
                    phone=customer_phone
                )
            
            # Check if updated_at column exists
            cursor.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'bookings' AND column_name = 'updated_at'
            """)
            has_updated_at = cursor.fetchone() is not None
            
            # Check if cabin changed - if so, need to move event to new calendar
            cabin_changed = cabin_uuid != existing_cabin_id
            calendar_moved = False
            new_event_id = event_id
            new_event_link = None
            
            if cabin_changed and event_id and old_calendar_id and new_calendar_id:
                # Need to move event from old calendar to new calendar
                try:
                    from src.main import get_credentials_api, build_calendar_service, create_calendar_event, delete_calendar_event
                    from src.main import parse_datetime_local, ISRAEL_TZ
                    from datetime import datetime
                    
                    creds = get_credentials_api()
                    service = build_calendar_service(creds)
                    
                    # Parse dates for new event
                    check_in_dt = parse_datetime_local(f"{check_in} 15:00")
                    check_out_dt = parse_datetime_local(f"{check_out} 11:00")
                    
                    # Build description with updated cabin info
                    desc_lines = [
                        f"Cabin: {cabin_uuid}",
                        f"Customer: {customer_name}",
                    ]
                    if customer_email:
                        desc_lines.append(f"Email: {customer_email}")
                    if customer_phone:
                        desc_lines.append(f"Phone: {customer_phone}")
                    desc_lines.extend([
                        f"Check-in: {check_in_dt.isoformat()}",
                        f"Check-out: {check_out_dt.isoformat()}",
                    ])
                    if adults or kids:
                        desc_lines.append(f"Guests: {adults} adults, {kids} kids")
                    if total_price:
                        desc_lines.append(f"Total: {total_price} ILS")
                    description = "\n".join(desc_lines)
                    
                    # Create new event in new calendar
                    summary = f"הזמנה | {customer_name}"
                    new_event = create_calendar_event(
                        service=service,
                        calendar_id=new_calendar_id,
                        summary=summary,
                        start_local=check_in_dt,
                        end_local=check_out_dt,
                        description=description
                    )
                    new_event_id = new_event.get('id')
                    new_event_link = new_event.get('htmlLink')
                    
                    # Delete old event from old calendar
                    try:
                        delete_calendar_event(service, old_calendar_id, event_id)
                        print(f"✅ Moved event {event_id[:20] if event_id and len(event_id) > 20 else (event_id or 'unknown')}... from calendar {old_calendar_id[:20] if old_calendar_id and len(old_calendar_id) > 20 else (old_calendar_id or 'unknown')}... to {new_calendar_id[:20] if new_calendar_id and len(new_calendar_id) > 20 else (new_calendar_id or 'unknown')}...")
                    except Exception as delete_error:
                        print(f"⚠️ Warning: Could not delete old event {event_id[:20] if event_id and len(event_id) > 20 else (event_id or 'unknown')}... from old calendar: {delete_error}")
                    
                    calendar_moved = True
                    print(f"✅ Created new event {new_event_id[:20] if new_event_id and len(new_event_id) > 20 else (new_event_id or 'unknown')}... in new calendar")
                except Exception as calendar_error:
                    print(f"❌ Error moving calendar event: {calendar_error}")
                    import traceback
                    traceback.print_exc()
                    # Continue with DB update even if calendar move failed
            
            # Update booking
            update_fields = []
            update_values = []
            
            if cabin_uuid != existing_cabin_id:
                update_fields.append("cabin_id = %s::uuid")
                update_values.append(cabin_uuid)
            
            if calendar_moved and new_event_id:
                update_fields.append("event_id = %s")
                update_values.append(new_event_id)
                if new_event_link:
                    update_fields.append("event_link = %s")
                    update_values.append(new_event_link)
            
            update_fields.append("customer_id = %s::uuid")
            update_values.append(customer_id)
            
            update_fields.append("check_in = %s::date")
            update_values.append(check_in)
            
            update_fields.append("check_out = %s::date")
            update_values.append(check_out)
            
            update_fields.append("adults = %s")
            update_values.append(adults)
            
            update_fields.append("kids = %s")
            update_values.append(kids)
            
            update_fields.append("total_price = %s")
            update_values.append(total_price)
            
            if status:
                update_fields.append("status = %s")
                update_values.append(status)
            
            if has_updated_at:
                update_fields.append("updated_at = CURRENT_TIMESTAMP")
            
            update_values.append(booking_id)
            
            cursor.execute(f"""
                UPDATE bookings SET
                    {', '.join(update_fields)}
                WHERE id = %s::uuid
            """, tuple(update_values))
            
            conn.commit()
            
            result_message = "Booking updated successfully"
            if calendar_moved:
                result_message += f". Event moved automatically from old calendar to new calendar (event_id: {new_event_id[:20] if new_event_id and len(new_event_id) > 20 else (new_event_id or 'N/A')}...)"
            elif cabin_changed and not calendar_moved:
                result_message += ". Cabin changed but calendar event was not moved automatically (missing event_id or calendar_id). Please sync DB → Calendar manually."
            else:
                result_message += ". Event will be updated on next DB → Calendar sync."
            
            return {
                "success": True,
                "message": result_message,
                "booking_id": booking_id,
                "event_id": new_event_id if calendar_moved else event_id,
                "event_link": new_event_link,
                "calendar_moved": calendar_moved,
                "note": "Event automatically moved to new calendar" if calendar_moved else "Event update needed - run DB → Calendar sync if needed"
            }
            
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Error in update_booking: {error_details}")
        raise HTTPException(status_code=500, detail=f"Error updating booking: {str(e)}")


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


# ============================================
# Agent Chat API Endpoints (Stage A2)
# ============================================

class ChatContext(BaseModel):
    """Context for chat request"""
    check_in: Optional[str] = Field(None, description="Check-in date (YYYY-MM-DD)")
    check_out: Optional[str] = Field(None, description="Check-out date (YYYY-MM-DD)")
    guests: Optional[int] = Field(None, description="Number of guests")
    cabin_id: Optional[str] = Field(None, description="Cabin ID")


class ChatRequest(BaseModel):
    """Request model for agent chat"""
    message: str = Field(..., description="User message")
    customer_id: Optional[str] = Field(None, description="Customer ID (UUID)")
    phone: Optional[str] = Field(None, description="Customer phone number")
    email: Optional[str] = Field(None, description="Customer email address")
    channel: str = Field("web", description="Channel: web, whatsapp, voice, sms")
    conversation_id: Optional[str] = Field(None, description="Existing conversation ID (UUID)")
    context: Optional[ChatContext] = Field(None, description="Conversation context")


class ChatResponse(BaseModel):
    """Response model for agent chat"""
    answer: str = Field(..., description="Agent response")
    actions_suggested: List[str] = Field(default_factory=list, description="Suggested actions")
    confidence: float = Field(0.0, description="Confidence score (0.0-1.0)")
    conversation_id: str = Field(..., description="Conversation ID (UUID)")
    booking_flow: Optional[Dict[str, Any]] = Field(None, description="Booking flow state (if in booking process)")
    show_customer_form: Optional[bool] = Field(False, description="Whether to show customer details form")


class CustomerDetailsRequest(BaseModel):
    """Request model for customer details in booking flow"""
    conversation_id: str = Field(..., description="Conversation ID (UUID)")
    cabin_id: str = Field(..., description="Cabin ID")
    check_in: str = Field(..., description="Check-in date (YYYY-MM-DD)")
    check_out: str = Field(..., description="Check-out date (YYYY-MM-DD)")
    customer_name: str = Field(..., description="Customer full name")
    phone: str = Field(..., description="Customer phone number")
    email: str = Field(..., description="Customer email address")
    adults: int = Field(..., description="Number of adults")
    kids: int = Field(0, description="Number of kids")
    notes: Optional[str] = Field(None, description="Additional notes")
    total_price: Optional[float] = Field(None, description="Total price (optional, will be calculated if not provided)")


class CustomerDetailsResponse(BaseModel):
    """Response model for customer details submission"""
    success: bool
    hold_id: Optional[str] = None
    booking_id: Optional[str] = None
    event_id: Optional[str] = None
    event_link: Optional[str] = None
    expires_at: Optional[str] = None
    message: str
    payment_required: bool = False
    payment_intent_id: Optional[str] = None
    client_secret: Optional[str] = None


@app.post("/agent/chat", response_model=ChatResponse)
async def agent_chat(request: ChatRequest):
    """
    Agent Chat endpoint - handles user messages and returns AI responses
    
    This is a placeholder implementation that:
    - Creates/retrieves conversation
    - Saves user message
    - Returns a simple response
    - Saves assistant response
    
    Future: Will integrate with AI model for intelligent responses
    """
    try:
        import uuid
        
        # Validate channel
        valid_channels = ['web', 'whatsapp', 'voice', 'sms']
        if request.channel not in valid_channels:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid channel. Must be one of: {valid_channels}"
            )
        
        # Get or create customer if phone provided
        customer_id = request.customer_id
        if not customer_id and request.phone:
            # Try to find existing customer by phone
            from src.db import get_db_connection
            from psycopg2.extras import RealDictCursor
            
            try:
                with get_db_connection() as conn:
                    cursor = conn.cursor(cursor_factory=RealDictCursor)
                    cursor.execute("""
                        SELECT id::text as id FROM customers WHERE phone = %s LIMIT 1
                    """, (request.phone,))
                    row = cursor.fetchone()
                    if row:
                        customer_id = row['id']
                    else:
                        # Create new customer with phone only
                        customer_id = save_customer_to_db(
                            name="לקוח",
                            phone=request.phone
                        )
            except Exception as e:
                print(f"Warning: Could not find/create customer: {e}")
        
        # Get or create conversation
        conversation_id = request.conversation_id
        conversation_context = {}
        
        # If conversation_id provided, load previous context
        if conversation_id:
            conversation = get_conversation(conversation_id)
            if conversation:
                # Extract context from previous messages (assistant messages have the context)
                messages = conversation.get('messages', [])
                # Get the most recent assistant message for context
                for msg in reversed(messages[-10:]):  # Last 10 messages
                    if msg.get('role') == 'assistant':
                        msg_metadata = msg.get('metadata', {})
                        if msg_metadata:
                            # Extract cabin_id, dates, quote from previous messages (only if not already set)
                            if 'cabin_id' in msg_metadata and 'cabin_id' not in conversation_context:
                                conversation_context['cabin_id'] = msg_metadata['cabin_id']
                            if 'check_in' in msg_metadata and 'check_in' not in conversation_context:
                                conversation_context['check_in'] = msg_metadata['check_in']
                            if 'check_out' in msg_metadata and 'check_out' not in conversation_context:
                                conversation_context['check_out'] = msg_metadata['check_out']
                            if 'quote' in msg_metadata and 'last_quote' not in conversation_context:
                                conversation_context['last_quote'] = msg_metadata['quote']
                                # Also extract dates from quote
                                quote = msg_metadata['quote']
                                if isinstance(quote, dict):
                                    if 'check_in' in quote and 'check_in' not in conversation_context:
                                        conversation_context['check_in'] = quote['check_in']
                                    if 'check_out' in quote and 'check_out' not in conversation_context:
                                        conversation_context['check_out'] = quote['check_out']
                                    if 'cabin_id' in quote and 'cabin_id' not in conversation_context:
                                        conversation_context['cabin_id'] = quote['cabin_id']
                            # IMPORTANT: Restore booking_flow state from previous message
                            if 'booking_flow' in msg_metadata and 'booking_flow' not in conversation_context:
                                conversation_context['booking_flow'] = msg_metadata['booking_flow']
                        # Break after first assistant message to get most recent context
                        break
        
        # Create new conversation if needed
        if not conversation_id:
            conversation_id = create_conversation(
                customer_id=customer_id,
                channel=request.channel,
                status="active",
                metadata={
                    "context": request.context.dict() if request.context else None,
                    "phone": request.phone
                }
            )
            
            if not conversation_id:
                raise HTTPException(
                    status_code=500,
                    detail="Failed to create conversation"
                )
        
        # Save user message
        user_message_id = save_message(
            conversation_id=conversation_id,
            role="user",
            content=request.message,
            metadata={
                "context": request.context.dict() if request.context else None
            }
        )
        
        if not user_message_id:
            raise HTTPException(
                status_code=500,
                detail="Failed to save user message"
            )
        
        # Initialize Agent
        agent = Agent()
        
        # Prepare context - merge request context with conversation context
        context_dict = request.context.dict() if request.context else {}
        context_dict.update(conversation_context)  # Conversation context overrides request context
        
        # Extract dates and cabin_id from message if not in context
        extracted_dates = agent.extract_dates(request.message)
        if extracted_dates:
            context_dict['check_in'] = context_dict.get('check_in') or extracted_dates.get('check_in')
            context_dict['check_out'] = context_dict.get('check_out') or extracted_dates.get('check_out')
            # If month range, add month name for display
            if extracted_dates.get('is_month_range'):
                month_num = extracted_dates.get('month', 3)
                month_names_he = {
                    1: 'ינואר', 2: 'פברואר', 3: 'מרץ', 4: 'אפריל', 5: 'מאי', 6: 'יוני',
                    7: 'יולי', 8: 'אוגוסט', 9: 'ספטמבר', 10: 'אוקטובר', 11: 'נובמבר', 12: 'דצמבר'
                }
                context_dict['month_name'] = month_names_he.get(month_num, 'החודש')
                context_dict['is_month_range'] = True
        
        extracted_cabin_id = agent.extract_cabin_id(request.message)
        if extracted_cabin_id:
            context_dict['cabin_id'] = context_dict.get('cabin_id') or extracted_cabin_id
        
        # Extract customer name from message
        extracted_customer_name = agent.extract_customer_name(request.message)
        if extracted_customer_name:
            context_dict['customer_name'] = extracted_customer_name
        
        # If message is just a cabin name or "cabin name + info keyword", extract cabin_id
        if not extracted_cabin_id:
            message_lower = request.message.lower()
            message_words = message_lower.split()
            cabin_names = {'אמי': 'ZB02', 'יולי': 'ZB01', 'מורן': 'ZB03', 'מורני': 'ZB03', 'ליאה': 'ZB04'}  # TODO: Verify cabin ID for ליאה
            for name, cabin_id in cabin_names.items():
                # Check if name appears as a word (not part of another word)
                if name in message_words or f'צימר של {name}' in message_lower or f'צימר {name}' in message_lower:
                    context_dict['cabin_id'] = cabin_id
                    break
        
        # A4: Check FAQ first (approved only)
        from src.db import get_approved_faq, suggest_faq, get_business_fact, get_all_business_facts
        
        answer = None
        faq_match = None
        faq_match = get_approved_faq(request.message)
        if faq_match:
            # Check if this FAQ should trigger a dynamic action instead of static answer
            faq_answer = faq_match.get('answer', '')
            faq_question = faq_match.get('question', '')
            
            # Detect if FAQ is about dynamic data (cabins list, availability, etc.)
            # If FAQ contains dynamic keywords, trigger tool instead of using static answer
            # This ensures that dynamic data (like cabin lists) is always up-to-date
            dynamic_keywords = {
                'list_cabins': ['רשימת', 'שמות', 'כל הצימרים', 'צימרים', 'list', 'names', 'all cabins', 'מה הצימרים'],
                'availability': ['זמינות', 'פנוי', 'available', 'availability']
            }
            
            is_dynamic = False
            dynamic_action = None
            for action, keywords in dynamic_keywords.items():
                if any(kw in faq_question.lower() or kw in faq_answer.lower() for kw in keywords):
                    is_dynamic = True
                    dynamic_action = action
                    break
            
            if is_dynamic:
                # This FAQ should trigger a tool call, not return static answer
                # Don't use FAQ answer, proceed with normal intent detection
                # This ensures the answer is always up-to-date (e.g., shows all 10 cabins, not just 3)
                faq_match = None  # Reset to trigger normal flow
                # Force the intent to match the dynamic action
                if dynamic_action == 'list_cabins':
                    # Explicitly trigger list_cabins intent
                    intent = 'list_cabins'
                    actions_suggested = ['list_cabins']
                    confidence = 0.9
                elif dynamic_action == 'availability':
                    # Let normal intent detection handle availability
                    pass
            else:
                # Static FAQ - use answer directly (e.g., "שעות הצק אין הן 15:00")
                answer = faq_answer
                actions_suggested = []
                confidence = 0.95
                intent = 'faq'
        
        if not faq_match and not answer:
            # No FAQ match - proceed with normal intent detection
            # Detect intent
            intent, confidence, actions_suggested = agent.detect_intent(
                request.message,
                context=context_dict
            )
            
            # A4: Check if question is about business facts
            message_lower = request.message.lower()
            business_facts_keywords = {
                'check_in_time': ['שעת צק אין', 'צק אין', 'check in', 'שעה להגעה'],
                'check_out_time': ['שעת צק אאוט', 'צק אאוט', 'check out', 'שעה לעזיבה'],
                'cancellation_policy': ['ביטול', 'מדיניות ביטול', 'cancellation', 'לבטל'],
                'parking': ['חניה', 'parking', 'מקום חניה'],
                'pets_allowed': ['חיות מחמד', 'כלב', 'חתול', 'pets', 'pet'],
                'kosher': ['כשר', 'כשרות', 'kosher'],
                'wifi': ['wifi', 'ווייפיי', 'אינטרנט', 'אינטרנט חינם']
            }
            
            # Check if message is asking about a business fact
            for fact_key, keywords in business_facts_keywords.items():
                if any(kw in message_lower for kw in keywords):
                    fact_value = get_business_fact(fact_key)
                    if fact_value:
                        answer = fact_value
                        actions_suggested = []
                        confidence = 0.9
                        intent = 'business_fact'
                        break
        
        # Call tools based on intent and actions (only if not FAQ or business_fact)
        tool_results = {}
        
        # Tool 0: List all cabins
        if 'list_cabins' in actions_suggested:
            try:
                _, cabins = get_service()
                tool_results['list_cabins'] = []
                for cabin in cabins:
                    cabin_id_str = cabin.get('cabin_id_string') or str(cabin.get('cabin_id', ''))
                    tool_results['list_cabins'].append({
                        'cabin_id': cabin_id_str,
                        'name': cabin.get('name'),
                        'area': cabin.get('area'),
                    })
            except Exception as e:
                print(f"Warning: Could not list cabins: {e}")
                tool_results['list_cabins'] = None
        
        # Tool 1: Check Availability
        if 'availability' in actions_suggested:
            # If no dates provided, check if we have cabin_id to show next month availability
            if not context_dict.get('check_in') or not context_dict.get('check_out'):
                filter_cabin_id = context_dict.get('cabin_id')
                
                # If specific cabin requested without dates, check next month's availability
                if filter_cabin_id:
                    try:
                        service, cabins = get_service()
                        
                        # Find the cabin
                        target_cabin = None
                        for cabin in cabins:
                            cabin_id_str = cabin.get('cabin_id_string') or str(cabin.get('cabin_id', ''))
                            cabin_name = cabin.get('name', '')
                            if (cabin_id_str.upper() == filter_cabin_id.upper() or 
                                normalize_text(cabin_name).lower() == normalize_text(filter_cabin_id).lower()):
                                target_cabin = cabin
                                break
                        
                        if target_cabin:
                            calendar_id = target_cabin.get('calendar_id') or target_cabin.get('calendarId')
                            if calendar_id:
                                # Check availability for next 60 days from today
                                from datetime import datetime, timedelta
                                from src.main import ISRAEL_TZ
                                
                                now = datetime.now(ISRAEL_TZ)
                                # Start from today or tomorrow (don't check past dates)
                                check_in_local = now.replace(hour=15, minute=0, second=0, microsecond=0)
                                # Check next 60 days
                                check_out_local = check_in_local + timedelta(days=60)
                                
                                check_in_utc = to_utc(check_in_local)
                                check_out_utc = to_utc(check_out_local)
                                
                                # Get all events in the range
                                from src.main import list_calendar_events
                                time_min = _to_rfc3339_z(check_in_utc)
                                time_max = _to_rfc3339_z(check_out_utc)
                                events = list_calendar_events(service, calendar_id, time_min, time_max)
                                
                                # Get all booked dates
                                booked_dates = set()
                                for event in events:
                                    start_raw = event.get("start", {}).get("dateTime") or event.get("start", {}).get("date")
                                    end_raw = event.get("end", {}).get("dateTime") or event.get("end", {}).get("date")
                                    if start_raw and end_raw:
                                        from src.main import _parse_event_dt
                                        start_dt = _parse_event_dt(start_raw)
                                        end_dt = _parse_event_dt(end_raw)
                                        
                                        # Add all dates in the range
                                        current = start_dt
                                        while current < end_dt:
                                            booked_dates.add(current.strftime('%Y-%m-%d'))
                                            current += timedelta(days=1)
                                
                                # Get all dates in the range
                                all_dates = []
                                current = check_in_local
                                while current < check_out_local:
                                    all_dates.append(current.strftime('%Y-%m-%d'))
                                    current += timedelta(days=1)
                                
                                # Available dates = all dates - booked dates
                                available_dates = [d for d in all_dates if d not in booked_dates]
                                
                                # Store in tool_results for agent to use
                                tool_results['available_dates'] = available_dates
                                tool_results['availability'] = [{
                                    'cabin_id': target_cabin.get('cabin_id_string') or str(target_cabin.get('cabin_id', '')),
                                    'name': target_cabin.get('name'),
                                    'area': target_cabin.get('area'),
                                    'available_dates': available_dates,
                                    'total_available': len(available_dates),
                                    'total_dates_in_range': len(all_dates),
                                    'booked_dates': sorted(list(booked_dates)),
                                    'is_month_range': True
                                }]
                                # Format month name for display (Hebrew month names)
                                months_he = {
                                    1: 'ינואר', 2: 'פברואר', 3: 'מרץ', 4: 'אפריל', 5: 'מאי', 6: 'יוני',
                                    7: 'יולי', 8: 'אוגוסט', 9: 'ספטמבר', 10: 'אוקטובר', 11: 'נובמבר', 12: 'דצמבר'
                                }
                                month_name_he = months_he.get(check_in_local.month, check_in_local.strftime('%B'))
                                range_description = f"{month_name_he} {check_in_local.year}" if len(available_dates) <= 31 else f"60 הימים הקרובים"
                                
                                tool_results['context'] = {
                                    'is_month_range': True,
                                    'check_in': check_in_local.strftime('%Y-%m-%d'),
                                    'check_out': (check_out_local - timedelta(days=1)).strftime('%Y-%m-%d'),
                                    'cabin_id': filter_cabin_id,
                                    'month_name': range_description
                                }
                            else:
                                tool_results['availability'] = None
                                tool_results['availability_needs_dates'] = True
                        else:
                            tool_results['availability'] = None
                            tool_results['availability_needs_dates'] = True
                    except Exception as e:
                        print(f"Warning: Could not check monthly availability: {e}")
                        tool_results['availability'] = None
                        tool_results['availability_needs_dates'] = True
                else:
                    # No cabin_id and no dates - ask when
                    tool_results['availability'] = None
                    tool_results['availability_needs_dates'] = True
            else:
                # Has dates - proceed with normal availability check
                try:
                    service, cabins = get_service()
                    check_in_local = parse_datetime_local(context_dict['check_in'])
                    check_out_local = parse_datetime_local(context_dict['check_out'])
                    check_in_utc = to_utc(check_in_local)
                    check_out_utc = to_utc(check_out_local)
                    
                    # Check if this is a month range query
                    is_month_range = context_dict.get('is_month_range', False)
                    filter_cabin_id = context_dict.get('cabin_id')
                    
                    # If month range and specific cabin, get available dates list
                    if is_month_range and filter_cabin_id:
                        # Find the cabin
                        target_cabin = None
                        for cabin in cabins:
                            cabin_id_str = cabin.get('cabin_id_string') or str(cabin.get('cabin_id', ''))
                            cabin_name = cabin.get('name', '')
                            if (cabin_id_str.upper() == filter_cabin_id.upper() or 
                                normalize_text(cabin_name).lower() == normalize_text(filter_cabin_id).lower()):
                                target_cabin = cabin
                                break
                        
                        if target_cabin:
                            calendar_id = target_cabin.get('calendar_id') or target_cabin.get('calendarId')
                            if calendar_id:
                                # Get all events in the month
                                from src.main import list_calendar_events
                                time_min = _to_rfc3339_z(check_in_utc)
                                time_max = _to_rfc3339_z(check_out_utc)
                                events = list_calendar_events(service, calendar_id, time_min, time_max)
                                
                                # Get all booked dates
                                booked_dates = set()
                                for event in events:
                                    start_raw = event.get("start", {}).get("dateTime") or event.get("start", {}).get("date")
                                    end_raw = event.get("end", {}).get("dateTime") or event.get("end", {}).get("date")
                                    if start_raw and end_raw:
                                        from src.main import _parse_event_dt
                                        start_dt = _parse_event_dt(start_raw)
                                        end_dt = _parse_event_dt(end_raw)
                                        
                                        # Add all dates in the range
                                        current = start_dt
                                        while current < end_dt:
                                            booked_dates.add(current.strftime('%Y-%m-%d'))
                                            current += timedelta(days=1)
                                
                                # Get all dates in the month
                                all_dates = []
                                current = check_in_local
                                while current <= check_out_local:
                                    all_dates.append(current.strftime('%Y-%m-%d'))
                                    current += timedelta(days=1)
                                
                                # Available dates = all dates - booked dates
                                available_dates = [d for d in all_dates if d not in booked_dates]
                                
                                # Store in tool_results for agent to use
                                tool_results['available_dates'] = available_dates
                                tool_results['context'] = {
                                    'is_month_range': True,
                                    'check_in': context_dict['check_in'],
                                    'check_out': context_dict['check_out'],
                                    'cabin_id': filter_cabin_id,
                                    'month_name': context_dict.get('month_name', 'החודש')
                                }
                                
                                # Also add the cabin to availability results
                                cabin_id_str = target_cabin.get('cabin_id_string') or str(target_cabin.get('cabin_id', ''))
                                images_urls = target_cabin.get('images_urls', [])
                                if not images_urls and cabin_id_str and not '-' in cabin_id_str:
                                    images_urls = [f'/zimmers_pic/{cabin_id_str}/hero-cabin.jpg']
                                
                                tool_results['availability'] = [{
                                    'cabin_id': cabin_id_str,
                                    'name': target_cabin.get('name'),
                                    'area': target_cabin.get('area'),
                                    'available_dates': available_dates,
                                    'booked_dates': sorted(list(booked_dates)),
                                    'total_available': len(available_dates),
                                    'total_dates_in_range': len(all_dates),
                                    'images_urls': images_urls,
                                    'is_month_range': True
                                }]
                            else:
                                tool_results['availability'] = None
                        else:
                            tool_results['availability'] = None
                    else:
                        # Regular availability check (specific date range)
                        wanted_features = None
                        if context_dict.get('features'):
                            wanted_features = parse_features_arg(context_dict['features'])
                        
                        available_cabins = find_available_cabins(
                            service=service,
                            cabins=cabins,
                            check_in_utc=check_in_utc,
                            check_out_utc=check_out_utc,
                            adults=context_dict.get('guests'),
                            kids=None,
                            area=None,
                            wanted_features=wanted_features,
                            verbose=False,
                        )
                        
                        # If cabin_id specified, filter to that cabin only
                        if filter_cabin_id:
                            available_cabins = [
                                c for c in available_cabins 
                                if (c.get('cabin_id_string') or str(c.get('cabin_id', ''))).upper() == filter_cabin_id.upper()
                                or normalize_text(str(c.get('name', ''))).lower() == normalize_text(filter_cabin_id).lower()
                            ]
                        
                        # Format results with more details
                        tool_results['availability'] = []
                        for cabin in available_cabins[:5]:  # Limit to 5 results
                            pricing = compute_price_for_stay(cabin, check_in_local, check_out_local)
                            cabin_id_str = cabin.get('cabin_id_string') or str(cabin.get('cabin_id', ''))
                            
                            # Get images if available
                            images_urls = cabin.get('images_urls', [])
                            if not images_urls and cabin_id_str and not '-' in cabin_id_str:
                                # Try to construct image path
                                images_urls = [f'/zimmers_pic/{cabin_id_str}/hero-cabin.jpg']
                            
                            tool_results['availability'].append({
                                'cabin_id': cabin_id_str,
                                'name': cabin.get('name'),
                                'area': cabin.get('area'),
                                'nights': pricing.get('nights', 0),
                                'total_price': pricing.get('total', 0),
                                'features': cabin.get('features'),
                                'images_urls': images_urls,
                                'description': cabin.get('description') or cabin.get('notes', '')
                            })
                        
                        tool_results['context'] = {
                            'check_in': context_dict['check_in'],
                            'check_out': context_dict['check_out'],
                            'cabin_id': filter_cabin_id
                        }
                except Exception as e:
                    print(f"Warning: Could not check availability: {e}")
                    import traceback
                    traceback.print_exc()
                    tool_results['availability'] = None
        
        # Tool 4: Get Cabin Info (general information) - also used for location requests
        if ('cabin_info' in actions_suggested or intent == 'location') and context_dict.get('cabin_id'):
            try:
                _, cabins = get_service()
                cabin_id = context_dict['cabin_id']
                
                # Find cabin
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
                
                if chosen:
                    cabin_id_str = chosen.get('cabin_id_string') or str(chosen.get('cabin_id', ''))
                    
                    # Get images if available
                    images_urls = chosen.get('images_urls', [])
                    if not images_urls and cabin_id_str and not '-' in cabin_id_str:
                        images_urls = [f'/zimmers_pic/{cabin_id_str}/hero-cabin.jpg']
                    
                    # Get base pricing
                    base_price = chosen.get('base_price', 0) or chosen.get('price', 0)
                    weekend_price = chosen.get('weekend_price', 0) or chosen.get('weekend', 0)
                    
                    # Get address components - try multiple field name variations
                    # First try from chosen (could be from DB or Sheets)
                    street_name = (chosen.get('Street name + number') or 
                                  chosen.get('street_name') or 
                                  chosen.get('street') or 
                                  chosen.get('address_line') or 
                                  chosen.get('Address') or
                                  '')
                    city = (chosen.get('City') or 
                           chosen.get('city') or 
                           chosen.get('location') or
                           '')
                    postal_code = (chosen.get('Postal code') or 
                                  chosen.get('postal_code') or 
                                  chosen.get('postalcode') or
                                  '')
                    
                    # If address components are missing from DB/chosen, try reading directly from Google Sheets
                    if not street_name and not city and not postal_code:
                        try:
                            from src.main import get_credentials
                            creds = get_credentials()
                            sheets_cabins = read_cabins_from_sheet(creds)
                            # Find matching cabin in Sheets by cabin_id_string
                            for sheet_cabin in sheets_cabins:
                                sheet_cabin_id = sheet_cabin.get('cabin_id') or sheet_cabin.get('cabin_id_string', '')
                                if str(sheet_cabin_id).upper() == str(cabin_id_str).upper():
                                    # Found matching cabin in Sheets - use its address data
                                    street_name = (sheet_cabin.get('Street name + number') or 
                                                  sheet_cabin.get('street_name') or 
                                                  sheet_cabin.get('street') or 
                                                  sheet_cabin.get('address_line') or 
                                                  sheet_cabin.get('Address') or
                                                  '')
                                    city = (sheet_cabin.get('City') or 
                                           sheet_cabin.get('city') or 
                                           sheet_cabin.get('location') or
                                           '')
                                    postal_code = (sheet_cabin.get('Postal code') or 
                                                  sheet_cabin.get('postal_code') or 
                                                  sheet_cabin.get('postalcode') or
                                                  '')
                                    break
                        except Exception as sheets_error:
                            print(f"Warning: Could not read address from Google Sheets: {sheets_error}")
                    
                    # Convert postal_code to string if it's a number
                    if postal_code and not isinstance(postal_code, str):
                        postal_code = str(postal_code)
                    
                    # Try to get full address directly first
                    full_address = (chosen.get('address') or 
                                   chosen.get('Address') or 
                                   chosen.get('location') or 
                                   chosen.get('Location') or
                                   '')
                    
                    # If no full address, build from components
                    if not full_address:
                        address_parts = []
                        if street_name:
                            address_parts.append(str(street_name))
                        if city:
                            address_parts.append(str(city))
                        if postal_code:
                            address_parts.append(str(postal_code))
                        full_address = ', '.join(address_parts) if address_parts else ''
                    
                    # Build Google Maps and Waze URLs if address exists
                    google_maps_url = None
                    waze_url = None
                    if full_address:
                        import urllib.parse
                        encoded_address = urllib.parse.quote(full_address)
                        google_maps_url = f"https://www.google.com/maps/search/?api=1&query={encoded_address}"
                        waze_url = f"https://waze.com/ul?q={encoded_address}"
                    else:
                        # Try to use existing URLs from Sheets if address field is missing
                        google_maps_url = chosen.get('google_maps_url') or chosen.get('Google Maps URL') or None
                        waze_url = chosen.get('waze_url') or chosen.get('Waze URL') or None
                    
                    tool_results['cabin_info'] = {
                        'cabin_id': cabin_id_str,
                        'name': chosen.get('name'),
                        'area': chosen.get('area'),
                        'address': full_address,
                        'street_name': street_name,
                        'city': city,
                        'postal_code': postal_code,
                        'google_maps_url': google_maps_url,
                        'waze_url': waze_url,
                        'description': chosen.get('description') or chosen.get('notes', ''),
                        'features': chosen.get('features'),
                        'images_urls': images_urls,
                        'base_price': base_price,
                        'weekend_price': weekend_price,
                        'max_adults': chosen.get('max_adults', 0),
                        'max_kids': chosen.get('max_kids', 0),
                    }
                else:
                    tool_results['cabin_info'] = None
            except Exception as e:
                print(f"Warning: Could not get cabin info: {e}")
                tool_results['cabin_info'] = None
        
        # Tool 2: Get Quote
        if 'quote' in actions_suggested and context_dict.get('cabin_id') and context_dict.get('check_in') and context_dict.get('check_out'):
            try:
                # Use the existing quote endpoint logic
                from src.pricing import PricingEngine
                _, cabins = get_service()
                
                # Find cabin
                chosen = None
                cabin_id = context_dict['cabin_id']
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
                
                if chosen:
                    check_in_local = parse_datetime_local(context_dict['check_in'])
                    check_out_local = parse_datetime_local(context_dict['check_out'])
                    
                    engine = PricingEngine()
                    pricing = engine.calculate_price_breakdown(
                        cabin=chosen,
                        check_in=check_in_local,
                        check_out=check_out_local,
                        addons=None,
                        apply_discounts=True
                    )
                    
                    quote_data = {
                        'cabin_id': cabin_id,
                        'cabin_name': chosen.get('name'),
                        'nights': pricing['nights'],
                        'total': pricing['total'],
                        'breakdown': pricing.get('breakdown', []),
                        'check_in': context_dict['check_in'],
                        'check_out': context_dict['check_out']
                    }
                    tool_results['quote'] = quote_data
                    
                    # If this quote was triggered from availability_confirmed, set booking_flow state
                    booking_flow_check = context_dict.get('booking_flow') or (tool_results.get('booking_flow') if tool_results else None)
                    if booking_flow_check and booking_flow_check.get('step') == 'availability_confirmed':
                        tool_results['booking_flow'] = {
                            'step': 'quote_confirmed',
                            'cabin_id': cabin_id,
                            'check_in': context_dict['check_in'],
                            'check_out': context_dict['check_out'],
                            'total': pricing['total'],
                            'nights': pricing['nights']
                        }
            except Exception as e:
                print(f"Warning: Could not get quote: {e}")
                tool_results['quote'] = None
        
        # Tool 3: Create Hold
        if 'hold' in actions_suggested and context_dict.get('cabin_id') and context_dict.get('check_in') and context_dict.get('check_out'):
            try:
                hold_manager = get_hold_manager()
                
                check_in_date = context_dict['check_in']
                check_out_date = context_dict['check_out']
                
                # Parse dates if needed
                if ' ' in check_in_date:
                    check_in_date = check_in_date.split(' ')[0]
                if ' ' in check_out_date:
                    check_out_date = check_out_date.split(' ')[0]
                
                hold_data = hold_manager.create_hold(
                    cabin_id=context_dict['cabin_id'],
                    check_in=check_in_date,
                    check_out=check_out_date,
                    customer_name=None,
                    customer_id=customer_id
                )
                
                if hold_data:
                    tool_results['hold'] = {
                        'hold_id': hold_data.get('hold_id'),
                        'expires_at': hold_data.get('expires_at'),
                        'status': hold_data.get('status')
                    }
            except Exception as e:
                print(f"Warning: Could not create hold: {e}")
                tool_results['hold'] = None
        
        # Handle booking flow states AFTER all tools are ready
        # This section processes booking_flow transitions based on current state and intent
        
        booking_flow_from_context = context_dict.get('booking_flow')
        booking_flow_from_tools = tool_results.get('booking_flow') if tool_results else None
        
        # Step 1: After quote is generated from availability_confirmed, update state to quote_confirmed
        if booking_flow_from_context and booking_flow_from_context.get('step') == 'availability_confirmed':
            if 'quote' in tool_results and tool_results['quote']:
                # Quote was just generated - update booking_flow to quote_confirmed
                quote_data = tool_results['quote']
                if not booking_flow_from_tools or booking_flow_from_tools.get('step') != 'quote_confirmed':
                    tool_results['booking_flow'] = {
                        'step': 'quote_confirmed',
                        'cabin_id': quote_data.get('cabin_id') or booking_flow_from_context.get('cabin_id'),
                        'check_in': quote_data.get('check_in') or booking_flow_from_context.get('check_in'),
                        'check_out': quote_data.get('check_out') or booking_flow_from_context.get('check_out'),
                        'total': quote_data.get('total', 0),
                        'nights': quote_data.get('nights', 0)
                    }
                    booking_flow_from_tools = tool_results['booking_flow']
        
        # Step 2: If quote confirmed and user confirms → request customer details form
        # Check both booking_flow_from_tools and booking_flow_from_context
        current_booking_flow = booking_flow_from_tools or booking_flow_from_context
        if current_booking_flow and current_booking_flow.get('step') == 'quote_confirmed':
            if intent in ['confirm', 'book_now']:
                # User confirmed quote - request customer details form
                answer = "📝 **מעולה! בואו נתחיל בהזמנה.**\n\n"
                answer += "אני צריך כמה פרטים ממך כדי להשלים את ההזמנה:\n\n"
                answer += "• שם מלא\n"
                answer += "• טלפון\n"
                answer += "• כתובת מייל\n"
                answer += "• מספר מבוגרים\n"
                answer += "• מספר ילדים\n"
                answer += "• הערות (אופציונלי)\n\n"
                answer += "💡 **אני אפתח עבורך טופס מילוי פרטים עכשיו.**"
                
                # Set booking_flow to customer_details step
                tool_results['booking_flow'] = {
                    'step': 'customer_details_needed',
                    'cabin_id': current_booking_flow.get('cabin_id'),
                    'check_in': current_booking_flow.get('check_in'),
                    'check_out': current_booking_flow.get('check_out'),
                    'total': current_booking_flow.get('total'),
                    'nights': current_booking_flow.get('nights')
                }
        
        # Step 3: Fallback - if we have quote (from tool_results or context) and user confirms → request customer details
        elif intent in ['confirm', 'book_now'] and 'quote' in tool_results and tool_results['quote'] and not answer:
            # Try to get quote from tool_results (just generated) or context
            quote = tool_results.get('quote') or context_dict.get('last_quote')
            cabin_id = context_dict.get('cabin_id')
            check_in = context_dict.get('check_in')
            check_out = context_dict.get('check_out')
            
            # If we have quote, extract info from it
            if quote and isinstance(quote, dict):
                cabin_id = quote.get('cabin_id') or cabin_id
                check_in = quote.get('check_in') or check_in
                check_out = quote.get('check_out') or check_out
            
            # If we have quote but no customer details yet, request customer details form instead of creating hold
            if quote and cabin_id and check_in and check_out:
                answer = "📝 **מעולה! בואו נתחיל בהזמנה.**\n\n"
                answer += "אני צריך כמה פרטים ממך כדי להשלים את ההזמנה:\n\n"
                answer += "• שם מלא\n"
                answer += "• טלפון\n"
                answer += "• כתובת מייל\n"
                answer += "• מספר מבוגרים\n"
                answer += "• מספר ילדים\n"
                answer += "• הערות (אופציונלי)\n\n"
                answer += "💡 **אני אפתח עבורך טופס מילוי פרטים עכשיו.**"
                
                tool_results['booking_flow'] = {
                    'step': 'customer_details_needed',
                    'cabin_id': cabin_id,
                    'check_in': check_in,
                    'check_out': check_out,
                    'total': quote.get('total', 0),
                    'nights': quote.get('nights', 0)
                }
        
        # Step 4: If user says "תזמין" but no quote yet → get quote first (don't create hold directly!)
        elif intent == 'book_now' and not answer:
            cabin_id = context_dict.get('cabin_id')
            check_in = context_dict.get('check_in')
            check_out = context_dict.get('check_out')
            
            # Check if we have quote already
            quote = tool_results.get('quote') or context_dict.get('last_quote')
            
            if not quote and cabin_id and check_in and check_out:
                # No quote yet - request quote first
                answer = "💰 **בואו נתחיל בהצעת מחיר.**\n\n"
                answer += f"אני אכין עבורך הצעת מחיר מפורטת לצימר {cabin_id} בתאריכים {check_in} - {check_out}.\n\n"
                answer += "💡 **אחרי שתקבל את ההצעת מחיר, תוכל להזמין.**"
                
                # Trigger quote action
                if 'quote' not in actions_suggested:
                    actions_suggested.append('quote')
                
                # Set booking_flow to availability_confirmed so quote will update it
                if not context_dict.get('booking_flow'):
                    tool_results['booking_flow'] = {
                        'step': 'availability_confirmed',
                        'cabin_id': cabin_id,
                        'check_in': check_in,
                        'check_out': check_out
                    }
            elif quote and cabin_id and check_in and check_out:
                # We have quote - request customer details form
                answer = "📝 **מעולה! בואו נתחיל בהזמנה.**\n\n"
                answer += "אני צריך כמה פרטים ממך כדי להשלים את ההזמנה:\n\n"
                answer += "• שם מלא\n"
                answer += "• טלפון\n"
                answer += "• כתובת מייל\n"
                answer += "• מספר מבוגרים\n"
                answer += "• מספר ילדים\n"
                answer += "• הערות (אופציונלי)\n\n"
                answer += "💡 **אני אפתח עבורך טופס מילוי פרטים עכשיו.**"
                
                tool_results['booking_flow'] = {
                    'step': 'customer_details_needed',
                    'cabin_id': cabin_id,
                    'check_in': check_in,
                    'check_out': check_out,
                    'total': quote.get('total', 0) if isinstance(quote, dict) else 0,
                    'nights': quote.get('nights', 0) if isinstance(quote, dict) else 0
                }
            elif cabin_id and check_in and check_out:
                # This should not happen in normal flow - user said "תזמין" but we don't have quote
                # Request quote first instead of creating hold directly
                answer = "💰 **בואו נתחיל בהצעת מחיר.**\n\n"
                answer += f"אני אכין עבורך הצעת מחיר מפורטת לצימר {cabin_id} בתאריכים {check_in} - {check_out}.\n\n"
                answer += "💡 **אחרי שתקבל את ההצעת מחיר, תוכל להזמין.**"
                
                # Trigger quote action
                if 'quote' not in actions_suggested:
                    actions_suggested.append('quote')
                
                # Set booking_flow to availability_confirmed so quote will update it
                if not context_dict.get('booking_flow'):
                    tool_results['booking_flow'] = {
                        'step': 'availability_confirmed',
                        'cabin_id': cabin_id,
                        'check_in': check_in,
                        'check_out': check_out
                    }
                
                # Don't create hold - wait for quote first
                # This code path should not normally execute - we already handled quote request above
                pass
            else:
                # Missing required information
                answer = f"❌ חסרים פרטים להזמנה.\n"
                if not cabin_id:
                    answer += "• ציין צימר (ZB01, ZB02, ZB03 או שמות: יולי, אמי, מורן)\n"
                if not check_in or not check_out:
                    answer += "• ציין תאריכים (לדוגמה: 15.09.26 - 18.09.26)"
        else:
            # Generate response using Agent (only if not FAQ or business_fact)
            if not answer:
                answer = agent.generate_response(
                    intent=intent,
                    actions=actions_suggested,
                    context=context_dict,
                    tool_results=tool_results
                )
                
                # A4: If Agent generated an answer and no FAQ was found, suggest it as FAQ
                if intent not in ['faq', 'business_fact'] and answer and not faq_match:
                    # Suggest this answer as FAQ for Host approval
                    suggested_faq_id = suggest_faq(
                        question=request.message,
                        answer=answer,
                        customer_id=customer_id
                    )
                    if suggested_faq_id:
                        # Add note to answer that it's pending approval
                        answer += "\n\n💡 הערה: תשובה זו הוצעה לאישור. בעל הצימר יאשר או ידחה אותה."
        
        # Save assistant response with context for next messages
        assistant_metadata = {
            "actions_suggested": actions_suggested,
            "confidence": confidence,
            "intent": intent,
            "tool_results": tool_results
        }
        
        # Save context for next messages (including booking flow state)
        if context_dict.get('cabin_id'):
            assistant_metadata['cabin_id'] = context_dict['cabin_id']
        if context_dict.get('check_in'):
            assistant_metadata['check_in'] = context_dict['check_in']
        if context_dict.get('check_out'):
            assistant_metadata['check_out'] = context_dict['check_out']
        if 'quote' in tool_results and tool_results['quote']:
            assistant_metadata['quote'] = tool_results['quote']
            assistant_metadata['last_quote'] = tool_results['quote']  # Save as last_quote for confirmation
        if 'booking_flow' in tool_results and tool_results['booking_flow']:
            assistant_metadata['booking_flow'] = tool_results['booking_flow']
        
        assistant_message_id = save_message(
            conversation_id=conversation_id,
            role="assistant",
            content=answer,
            metadata=assistant_metadata
        )
        
        # Save audit log for conversation
        try:
            save_audit_log(
                table_name="conversations",
                record_id=conversation_id,
                action="INSERT",
                new_values={
                    "customer_id": customer_id,
                    "channel": request.channel,
                    "status": "active",
                    "message_count": 2  # user + assistant
                }
            )
        except Exception as audit_error:
            print(f"Warning: Could not save audit log: {audit_error}")
        
        # Determine if we should show customer form and prepare booking_flow response
        show_customer_form = False
        booking_flow_response = None
        if 'booking_flow' in tool_results and tool_results['booking_flow']:
            booking_flow_response = tool_results['booking_flow']
            if booking_flow_response.get('step') == 'customer_details_needed':
                show_customer_form = True
        
        return ChatResponse(
            answer=answer,
            actions_suggested=actions_suggested,
            confidence=confidence,
            conversation_id=conversation_id,
            booking_flow=booking_flow_response,
            show_customer_form=show_customer_form
        )
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Error processing chat request: {str(e)}"
        )


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


# ============================================
# A4: Admin Endpoints for FAQ and Business Facts
# ============================================

class FAQApprovalRequest(BaseModel):
    """Request to approve or reject a FAQ"""
    faq_id: str = Field(..., description="FAQ ID to approve/reject")
    approved: bool = Field(..., description="True to approve, False to reject")
    approved_by: Optional[str] = Field(None, description="Host/Admin ID who approved")
    question: Optional[str] = Field(None, description="Edited question (optional)")
    answer: Optional[str] = Field(None, description="Edited answer (optional)")


class FAQUpdateRequest(BaseModel):
    """Request to update a FAQ (approved or pending)"""
    question: Optional[str] = Field(None, description="Updated question")
    answer: Optional[str] = Field(None, description="Updated answer")


class BusinessFactRequest(BaseModel):
    """Request to set a business fact"""
    fact_key: str = Field(..., description="Fact key (e.g., 'check_in_time')")
    fact_value: str = Field(..., description="Fact value (e.g., '15:00')")
    category: Optional[str] = Field(None, description="Category (e.g., 'hours', 'policies')")
    description: Optional[str] = Field(None, description="Description")


@app.get("/admin/faq/pending")
async def get_pending_faqs_endpoint():
    """
    Get all pending FAQs waiting for Host approval
    """
    try:
        pending_faqs = get_pending_faqs()
        return {
            "count": len(pending_faqs),
            "faqs": pending_faqs
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching pending FAQs: {str(e)}")


@app.post("/admin/faq/approve")
async def approve_faq_endpoint(request: FAQApprovalRequest):
    """
    Approve or reject a FAQ (Host only)
    Can optionally update question and answer during approval
    """
    try:
        if request.approved:
            # Call approve_faq which now returns (success, message) tuple
            success, status_message = approve_faq(
                request.faq_id, 
                request.approved_by,
                request.question,
                request.answer
            )
            
            if success:
                if status_message == "already_approved":
                    return {
                        "message": "FAQ כבר מאושר ונשמר. אין צורך לאשר שוב.",
                        "faq_id": request.faq_id,
                        "was_already_approved": True
                    }
                elif status_message == "updated_while_approved":
                    return {
                        "message": "FAQ כבר מאושר ונעדכן בהצלחה.",
                        "faq_id": request.faq_id,
                        "was_already_approved": True
                    }
                elif status_message == "approved":
                    return {
                        "message": "FAQ אושר בהצלחה",
                        "faq_id": request.faq_id,
                        "was_already_approved": False
                    }
                else:
                    # Success but unknown status
                    return {
                        "message": f"FAQ processed: {status_message}",
                        "faq_id": request.faq_id
                    }
            else:
                # Approval failed
                if status_message == "not_found":
                    raise HTTPException(status_code=404, detail="FAQ not found")
                elif status_message == "no_rows_updated":
                    # FAQ might have been approved by another process, check status
                    from src.db import get_all_faqs
                    all_faqs = get_all_faqs(include_pending=True)
                    existing_faq = next((faq for faq in all_faqs if str(faq.get('id')) == request.faq_id), None)
                    if existing_faq and existing_faq.get('approved'):
                        return {
                            "message": "FAQ כבר מאושר ונשמר.",
                            "faq_id": request.faq_id,
                            "was_already_approved": True
                        }
                    raise HTTPException(status_code=400, detail="Failed to approve FAQ - no rows updated")
                else:
                    raise HTTPException(status_code=400, detail=f"Failed to approve FAQ: {status_message}")
        else:
            success = reject_faq(request.faq_id)
            if success:
                return {"message": "FAQ rejected successfully", "faq_id": request.faq_id}
            else:
                raise HTTPException(status_code=404, detail="FAQ not found or already processed")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing FAQ: {str(e)}")


@app.get("/admin/business-facts")
async def get_business_facts_endpoint(category: Optional[str] = None):
    """
    Get all business facts (or filtered by category)
    Returns facts as simple key->value dict for backward compatibility
    Also includes detailed version with categories
    """
    try:
        facts_dict = get_all_business_facts(category)
        # Convert to simple key->value format for backward compatibility
        facts = {key: data['value'] for key, data in facts_dict.items()}
        return {
            "count": len(facts),
            "facts": facts,
            "facts_detailed": facts_dict  # Include detailed version with categories
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching business facts: {str(e)}")


@app.post("/admin/business-facts")
async def set_business_fact_endpoint(request: BusinessFactRequest):
    """
    Set or update a business fact (Host only)
    """
    try:
        success = set_business_fact(
            fact_key=request.fact_key,
            fact_value=request.fact_value,
            category=request.category,
            description=request.description
        )
        if success:
            return {
                "message": "Business fact set successfully",
                "fact_key": request.fact_key,
                "fact_value": request.fact_value
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to set business fact")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error setting business fact: {str(e)}")


@app.get("/admin/faq/all")
async def get_all_faqs_endpoint(include_pending: bool = True):
    """
    Get all FAQs (approved and optionally pending)
    """
    try:
        faqs = get_all_faqs(include_pending=include_pending)
        return {"faqs": faqs, "count": len(faqs)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting FAQs: {str(e)}")


@app.put("/admin/faq/{faq_id}")
async def update_faq_endpoint(faq_id: str, request: FAQUpdateRequest):
    """
    Update an existing FAQ (approved or pending)
    """
    try:
        if not request.question and not request.answer:
            raise HTTPException(status_code=400, detail="At least one of 'question' or 'answer' must be provided")
        
        success = update_faq(
            faq_id=faq_id,
            question=request.question,
            answer=request.answer
        )
        if success:
            return {"message": "FAQ updated successfully", "faq_id": faq_id}
        else:
            # Check if FAQ exists
            from src.db import get_all_faqs
            all_faqs = get_all_faqs(include_pending=True)
            faq_exists = any(str(faq.get('id')) == faq_id for faq in all_faqs)
            if not faq_exists:
                raise HTTPException(status_code=404, detail="FAQ not found")
            else:
                raise HTTPException(status_code=400, detail="No changes detected or update failed")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating FAQ: {str(e)}")


@app.delete("/admin/faq/{faq_id}")
async def delete_faq_endpoint(faq_id: str):
    """
    Delete a FAQ (approved or pending)
    """
    try:
        success = delete_faq(faq_id)
        if success:
            return {"message": "FAQ deleted successfully", "faq_id": faq_id}
        else:
            raise HTTPException(status_code=404, detail="FAQ not found")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting FAQ: {str(e)}")


@app.delete("/admin/business-facts/{fact_key}")
async def delete_business_fact_endpoint(fact_key: str):
    """
    Delete (deactivate) a business fact
    """
    try:
        success = delete_business_fact(fact_key)
        if success:
            return {"message": "Business fact deleted successfully", "fact_key": fact_key}
        else:
            raise HTTPException(status_code=404, detail="Business fact not found")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting business fact: {str(e)}")


# ============================================================================
# Sync Endpoints: Google Sheets ↔ DB and Google Calendar ↔ DB
# ============================================================================

@app.post("/admin/sync/sheets-to-db")
async def sync_sheets_to_db_endpoint():
    """
    Sync cabins from Google Sheets to PostgreSQL database
    """
    try:
        from src.sync_sheets import sync_sheets_to_db
        print(f"\n{'='*60}")
        print(f"Starting Sheets → DB sync")
        print(f"{'='*60}")
        result = sync_sheets_to_db()
        # Handle both old and new return format
        if len(result) == 4:
            imported, updated, errors, error_list = result
        else:
            imported, updated, errors = result
            error_list = []
        print(f"\n{'='*60}")
        print(f"Sheets → DB sync completed: {imported} imported, {updated} updated, {errors} errors")
        if error_list:
            print(f"Error details: {len(error_list)} errors")
            for i, err in enumerate(error_list[:5], 1):  # Show first 5 errors
                print(f"  {i}. [{err.get('type', 'unknown')}] {err.get('cabin', 'N/A')}: {err.get('error', 'Unknown error')}")
            if len(error_list) > 5:
                print(f"  ... and {len(error_list) - 5} more errors (check full list in response)")
        print(f"{'='*60}\n")
        return {
            "success": errors == 0,
            "imported": imported,
            "updated": updated,
            "errors": errors,
            "error_list": error_list[:20] if error_list else [],  # Return first 20 errors
            "message": f"Synced {imported} imported, {updated} updated, {errors} errors",
            "details": "Check 'error_list' field for detailed error information. Also check server console (terminal) for full tracebacks."
        }
    except Exception as e:
        error_msg = str(e)
        print(f"❌ Critical error in sync_sheets_to_db_endpoint: {error_msg}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error syncing Sheets to DB: {error_msg}")


@app.post("/admin/sync/db-to-sheets")
async def sync_db_to_sheets_endpoint():
    """
    Sync cabins from PostgreSQL database to Google Sheets
    """
    try:
        from src.sync_sheets import sync_db_to_sheets
        print(f"\n{'='*60}")
        print(f"Starting DB → Sheets sync")
        print(f"{'='*60}")
        updated, errors = sync_db_to_sheets()
        print(f"\n{'='*60}")
        print(f"DB → Sheets sync completed: {updated} rows updated, {errors} errors")
        print(f"{'='*60}\n")
        return {
            "success": errors == 0,
            "updated": updated,
            "errors": errors,
            "message": f"Synced {updated} rows to Sheets, {errors} errors",
            "details": "Check server console (terminal) for detailed error messages. Press F12 in browser to see sync logs."
        }
    except Exception as e:
        error_msg = str(e)
        print(f"❌ Critical error in sync_db_to_sheets_endpoint: {error_msg}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error syncing DB to Sheets: {error_msg}")


@app.post("/admin/sync/calendar-to-db")
async def sync_calendar_to_db_endpoint(days_back: int = 30, days_forward: int = 365):
    """
    Sync bookings from Google Calendar to PostgreSQL database
    Detects changes in calendar events (name, email, dates) and updates DB
    
    Args:
        days_back: How many days back to sync (default: 30)
        days_forward: How many days forward to sync (default: 365)
    """
    try:
        from src.sync_calendar import sync_calendar_to_db
        print(f"\n{'='*60}")
        print(f"Starting Calendar → DB sync (days_back={days_back}, days_forward={days_forward})")
        print(f"{'='*60}")
        result = sync_calendar_to_db(days_back=days_back, days_forward=days_forward)
        # Handle both old and new return format
        if len(result) == 4:
            imported, updated, errors, error_list = result
        else:
            imported, updated, errors = result
            error_list = []
        print(f"\n{'='*60}")
        print(f"Calendar → DB sync completed: {imported} imported, {updated} updated, {errors} errors")
        if error_list:
            print(f"Error details: {len(error_list)} errors")
            for i, err in enumerate(error_list[:5], 1):  # Show first 5 errors
                print(f"  {i}. [{err.get('type', 'unknown')}] {err.get('error', 'Unknown error')}")
            if len(error_list) > 5:
                print(f"  ... and {len(error_list) - 5} more errors (check full list in response)")
        print(f"{'='*60}\n")
        return {
            "success": errors == 0,
            "imported": imported,
            "updated": updated,
            "errors": errors,
            "error_list": error_list[:20] if error_list else [],  # Return first 20 errors
            "message": f"Synced {imported} imported, {updated} updated, {errors} errors",
            "details": "Check 'error_list' field for detailed error information. Also check server console (terminal) for full tracebacks."
        }
    except Exception as e:
        error_msg = str(e)
        print(f"❌ Critical error in sync_calendar_to_db_endpoint: {error_msg}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error syncing Calendar to DB: {error_msg}")


@app.post("/admin/sync/db-to-calendar")
async def sync_db_to_calendar_endpoint(booking_id: Optional[str] = None):
    """
    Sync booking from PostgreSQL database to Google Calendar
    Updates calendar event if booking was changed in DB
    
    Args:
        booking_id: Specific booking ID to sync (optional, if not provided syncs all recent bookings)
    """
    try:
        from src.sync_calendar import update_calendar_event
        from src.main import get_credentials_api, build_calendar_service
        from src.db import get_db_connection
        from psycopg2.extras import RealDictCursor
        
        creds = get_credentials_api()
        service = build_calendar_service(creds)
        
        with get_db_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            if booking_id:
                # Sync specific booking
                cursor.execute("""
                    SELECT 
                        b.id::text as booking_id,
                        b.event_id,
                        b.check_in,
                        b.check_out,
                        b.adults,
                        b.kids,
                        b.total_price,
                        c.id::text as cabin_id,
                        c.calendar_id,
                        c.name as cabin_name,
                        cust.name as customer_name,
                        cust.email as customer_email,
                        cust.phone as customer_phone
                    FROM bookings b
                    JOIN cabins c ON b.cabin_id = c.id
                    LEFT JOIN customers cust ON b.customer_id = cust.id
                    WHERE b.id = %s::uuid AND b.event_id IS NOT NULL
                """, (booking_id,))
            else:
                # Sync all recent bookings (last 30 days)
                cursor.execute("""
                    SELECT 
                        b.id::text as booking_id,
                        b.event_id,
                        b.check_in,
                        b.check_out,
                        b.adults,
                        b.kids,
                        b.total_price,
                        c.id::text as cabin_id,
                        c.calendar_id,
                        c.name as cabin_name,
                        cust.name as customer_name,
                        cust.email as customer_email,
                        cust.phone as customer_phone
                    FROM bookings b
                    JOIN cabins c ON b.cabin_id = c.id
                    LEFT JOIN customers cust ON b.customer_id = cust.id
                    WHERE b.event_id IS NOT NULL 
                    AND b.check_in >= CURRENT_DATE - INTERVAL '30 days'
                    AND b.check_in <= CURRENT_DATE + INTERVAL '365 days'
                """)
            
            bookings = cursor.fetchall()
            
            if not bookings:
                return {
                    "success": True,
                    "updated": 0,
                    "errors": 0,
                    "message": "No bookings found to sync (all bookings must have event_id and be within date range)"
                }
            
            print(f"Found {len(bookings)} bookings to sync")
            
            updated = 0
            errors = 0
            
            for booking in bookings:
                try:
                    event_id = booking.get('event_id')
                    calendar_id = booking.get('calendar_id')
                    check_in = booking.get('check_in')
                    check_out = booking.get('check_out')
                    cabin_id = booking.get('cabin_id')
                    cabin_name = booking.get('cabin_name', 'Unknown')
                    customer_name = booking.get('customer_name', 'לקוח')
                    customer_email = booking.get('customer_email')
                    customer_phone = booking.get('customer_phone')
                    adults = booking.get('adults', 0) or 0
                    kids = booking.get('kids', 0) or 0
                    total_price = booking.get('total_price', 0) or 0
                    
                    # Validate required fields
                    if not event_id:
                        print(f"Warning: Booking {booking.get('booking_id', 'unknown')} has no event_id, skipping")
                        errors += 1
                        continue
                    
                    if not calendar_id:
                        print(f"Warning: Booking {booking.get('booking_id', 'unknown')} has no calendar_id, skipping")
                        errors += 1
                        continue
                    
                    if not check_in or not check_out:
                        print(f"Warning: Booking {booking.get('booking_id', 'unknown')} has missing dates, skipping")
                        errors += 1
                        continue
                    
                    # Parse dates - handle both date objects and strings
                    try:
                        from datetime import datetime, date
                        from src.main import parse_datetime_local, ISRAEL_TZ
                        
                        # Handle check_in date
                        if isinstance(check_in, date):
                            check_in_dt = datetime.combine(check_in, datetime.min.time()).replace(tzinfo=ISRAEL_TZ)
                            check_in_dt = check_in_dt.replace(hour=15, minute=0)
                        elif isinstance(check_in, datetime):
                            check_in_dt = check_in.replace(tzinfo=ISRAEL_TZ) if check_in.tzinfo is None else check_in
                            check_in_dt = check_in_dt.replace(hour=15, minute=0)
                        elif isinstance(check_in, str):
                            check_in_dt = parse_datetime_local(f"{check_in} 15:00")
                        else:
                            raise ValueError(f"Unsupported check_in type: {type(check_in)}")
                        
                        # Handle check_out date
                        if isinstance(check_out, date):
                            check_out_dt = datetime.combine(check_out, datetime.min.time()).replace(tzinfo=ISRAEL_TZ)
                            check_out_dt = check_out_dt.replace(hour=11, minute=0)
                        elif isinstance(check_out, datetime):
                            check_out_dt = check_out.replace(tzinfo=ISRAEL_TZ) if check_out.tzinfo is None else check_out
                            check_out_dt = check_out_dt.replace(hour=11, minute=0)
                        elif isinstance(check_out, str):
                            check_out_dt = parse_datetime_local(f"{check_out} 11:00")
                        else:
                            raise ValueError(f"Unsupported check_out type: {type(check_out)}")
                    except Exception as date_error:
                        print(f"❌ Error parsing dates for booking {booking.get('booking_id', 'unknown')[:8]}...: {date_error}")
                        import traceback
                        traceback.print_exc()
                        errors += 1
                        continue
                    
                    # Build description with all booking details
                    desc_lines = [
                        f"Cabin: {cabin_id}",
                        f"Customer: {customer_name}",
                    ]
                    if customer_email:
                        desc_lines.append(f"Email: {customer_email}")
                    if customer_phone:
                        desc_lines.append(f"Phone: {customer_phone}")
                    desc_lines.extend([
                        f"Check-in: {check_in_dt.isoformat()}",
                        f"Check-out: {check_out_dt.isoformat()}",
                    ])
                    if adults or kids:
                        desc_lines.append(f"Guests: {adults} adults, {kids} kids")
                    if total_price:
                        desc_lines.append(f"Total: {total_price} ILS")
                    description = "\n".join(desc_lines)
                    
                    # Update calendar event
                    summary = f"הזמנה | {customer_name}"
                    try:
                        result = update_calendar_event(
                            service=service,
                            event_id=event_id,
                            calendar_id=calendar_id,
                            summary=summary,
                            description=description,
                            start_local=check_in_dt,
                            end_local=check_out_dt
                        )
                        
                        if result:
                            updated += 1
                            print(f"✅ Updated calendar event {event_id[:20] if len(event_id) > 20 else event_id}... for booking {booking.get('booking_id', 'unknown')[:8]}...")
                        else:
                            errors += 1
                            print(f"❌ Failed to update calendar event {event_id[:20] if len(event_id) > 20 else event_id}... for booking {booking.get('booking_id', 'unknown')[:8]}... (update_calendar_event returned None)")
                    except Exception as update_error:
                        errors += 1
                        print(f"❌ Exception updating calendar event {event_id[:20] if len(event_id) > 20 else event_id}... for booking {booking.get('booking_id', 'unknown')[:8]}...: {update_error}")
                        import traceback
                        traceback.print_exc()
                except Exception as e:
                    errors += 1
                    booking_id_str = booking.get('booking_id', 'unknown')[:8] if booking else 'unknown'
                    print(f"❌ Error syncing booking {booking_id_str}...: {e}")
                    import traceback
                    traceback.print_exc()
        
        print(f"\n{'='*60}")
        print(f"DB → Calendar sync completed: {updated} updated, {errors} errors")
        print(f"{'='*60}\n")
        return {
            "success": errors == 0,
            "updated": updated,
            "errors": errors,
            "message": f"Synced {updated} bookings to Calendar, {errors} errors",
            "details": "Check server console (terminal) for detailed error messages. Press F12 in browser to see sync logs."
        }
    except Exception as e:
        error_msg = str(e)
        print(f"❌ Critical error in sync_db_to_calendar_endpoint: {error_msg}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error syncing DB to Calendar: {error_msg}")


# ============================================================================
# Auto-Sync: Background Scheduler for Automatic Synchronization
# ============================================================================

# Global state for auto-sync
auto_sync_enabled = True  # Default: enabled
auto_sync_interval_minutes = int(os.getenv("AUTO_SYNC_INTERVAL_MINUTES", "5"))  # Default: 5 minutes
scheduler = None


def run_auto_sync():
    """
    Background task that runs automatic synchronization
    - Calendar → DB: Syncs changes from Google Calendar to database
    - Sheets → DB: Syncs changes from Google Sheets to database
    """
    if not auto_sync_enabled:
        print("ℹ️ Auto-sync is disabled, skipping...")
        return
    
    try:
        from src.sync_calendar import sync_calendar_to_db
        from src.sync_sheets import sync_sheets_to_db
        
        print(f"\n{'='*60}")
        print(f"🔄 Starting automatic sync (Calendar → DB, Sheets → DB)")
        print(f"{'='*60}")
        
        # Sync Calendar → DB (detects changes in calendar events)
        try:
            cal_result = sync_calendar_to_db(days_back=30, days_forward=365)
            if len(cal_result) == 4:
                cal_imported, cal_updated, cal_errors, _ = cal_result
            else:
                cal_imported, cal_updated, cal_errors = cal_result
            print(f"✅ Calendar → DB: {cal_imported} imported, {cal_updated} updated, {cal_errors} errors")
        except Exception as cal_error:
            print(f"❌ Calendar → DB sync failed: {cal_error}")
        
        # Sync Sheets → DB (detects changes in Google Sheets)
        try:
            sheets_result = sync_sheets_to_db()
            if len(sheets_result) == 4:
                sheets_imported, sheets_updated, sheets_errors, _ = sheets_result
            else:
                sheets_imported, sheets_updated, sheets_errors = sheets_result
            print(f"✅ Sheets → DB: {sheets_imported} imported, {sheets_updated} updated, {sheets_errors} errors")
        except Exception as sheets_error:
            print(f"❌ Sheets → DB sync failed: {sheets_error}")
        
        print(f"{'='*60}\n")
        
    except Exception as e:
        print(f"❌ Error in auto-sync: {e}")
        import traceback
        traceback.print_exc()


@app.on_event("startup")
async def startup_event():
    """
    Initialize background scheduler on startup
    """
    global scheduler
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.interval import IntervalTrigger
        
        scheduler = BackgroundScheduler()
        scheduler.add_job(
            run_auto_sync,
            trigger=IntervalTrigger(minutes=auto_sync_interval_minutes),
            id='auto_sync_job',
            name='Automatic Sync (Calendar → DB, Sheets → DB)',
            replace_existing=True
        )
        scheduler.start()
        print(f"✅ Auto-sync scheduler started (interval: {auto_sync_interval_minutes} minutes)")
        print(f"   🔄 Auto-sync will run every {auto_sync_interval_minutes} minutes")
        print(f"   📅 Calendar → DB: Detects changes in calendar events and updates DB")
        print(f"   📊 Sheets → DB: Detects changes in Google Sheets and updates DB")
    except ImportError as e:
        print(f"⚠️ Warning: APScheduler not installed. Install with: pip install apscheduler==3.10.4")
        print(f"   Auto-sync will be disabled until APScheduler is installed")
        scheduler = None
    except Exception as e:
        print(f"⚠️ Warning: Could not start auto-sync scheduler: {e}")
        import traceback
        traceback.print_exc()
        scheduler = None


@app.on_event("shutdown")
async def shutdown_event():
    """
    Shutdown background scheduler on shutdown
    """
    global scheduler
    if scheduler:
        try:
            scheduler.shutdown()
            print("✅ Auto-sync scheduler stopped")
        except Exception as e:
            print(f"⚠️ Warning: Error stopping scheduler: {e}")


@app.get("/admin/sync/auto-status")
async def get_auto_sync_status():
    """
    Get auto-sync status (enabled/disabled, interval, last run time)
    """
    global auto_sync_enabled, auto_sync_interval_minutes, scheduler
    
    last_run_time = None
    next_run_time = None
    
    if scheduler:
        try:
            job = scheduler.get_job('auto_sync_job')
            if job and job.next_run_time:
                next_run_time = job.next_run_time.isoformat()
            else:
                # Calculate next run (current time + interval) if job not scheduled yet
                next_run_time = (datetime.now() + timedelta(minutes=auto_sync_interval_minutes)).isoformat()
        except Exception as e:
            print(f"Warning: Could not get job info: {e}")
    
    return {
        "enabled": auto_sync_enabled,
        "interval_minutes": auto_sync_interval_minutes,
        "last_run_time": last_run_time,
        "next_run_time": next_run_time,
        "scheduler_running": scheduler is not None and scheduler.running if scheduler else False
    }


@app.post("/admin/sync/auto-toggle")
async def toggle_auto_sync():
    """
    Enable/disable auto-sync
    """
    global auto_sync_enabled, scheduler
    
    auto_sync_enabled = not auto_sync_enabled
    
    if scheduler:
        try:
            job = scheduler.get_job('auto_sync_job')
            if job:
                if auto_sync_enabled:
                    scheduler.resume_job('auto_sync_job')
                else:
                    scheduler.pause_job('auto_sync_job')
        except Exception as e:
            print(f"Warning: Could not toggle job: {e}")
    
    return {
        "success": True,
        "enabled": auto_sync_enabled,
        "message": f"Auto-sync {'enabled' if auto_sync_enabled else 'disabled'}"
    }


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("API_PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)

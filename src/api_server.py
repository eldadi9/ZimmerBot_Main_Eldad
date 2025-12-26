"""
API Server for ZimmerBot
FastAPI-based REST API for cabin booking system
"""

import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
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
)
from src.pricing import PricingEngine

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

# היה אצלך mount כפול נוסף - משאיר כתיעוד ולא מפעיל
# app.mount("/data", StaticFiles(directory=str(BASE_DIR / "data")), name="data")
# app.mount("/tools", StaticFiles(directory=str(BASE_DIR / "tools"), html=True), name="tools")

_creds = None
_service = None
_cabins = None


def get_service():
    global _creds, _service, _cabins
    if _creds is None:
        _creds = get_credentials_api()
    if _service is None:
        _service = build_calendar_service(_creds)
    if _cabins is None:
        _cabins = read_cabins_from_sheet(_creds)
    return _service, _cabins


class AvailabilityRequest(BaseModel):
    check_in: str = Field(..., description="Check-in date/time (YYYY-MM-DD or YYYY-MM-DD HH:MM)")
    check_out: str = Field(..., description="Check-out date/time (YYYY-MM-DD or YYYY-MM-DD HH:MM)")
    adults: Optional[int] = Field(None, description="Number of adults")
    kids: Optional[int] = Field(None, description="Number of kids")
    area: Optional[str] = Field(None, description="Area filter")
    features: Optional[str] = Field(None, description="Comma-separated features (e.g., 'jacuzzi,pool')")


class BookingRequest(BaseModel):
    check_in: str = Field(..., description="Check-in date/time")
    check_out: str = Field(..., description="Check-out date/time")
    cabin_id: str = Field(..., description="Cabin ID to book")
    customer: str = Field(..., description="Customer name")
    phone: Optional[str] = Field(None, description="Customer phone")
    notes: Optional[str] = Field(None, description="Additional notes")


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


class BookingResponse(BaseModel):
    success: bool
    cabin_id: str
    event_id: Optional[str] = None
    event_link: Optional[str] = None
    message: str


class QuoteRequest(BaseModel):
    cabin_id: str = Field(..., description="Cabin ID to get quote for")
    check_in: str = Field(..., description="Check-in date/time (YYYY-MM-DD or YYYY-MM-DD HH:MM)")
    check_out: str = Field(..., description="Check-out date/time (YYYY-MM-DD or YYYY-MM-DD HH:MM)")
    adults: Optional[int] = Field(None, description="Number of adults")
    kids: Optional[int] = Field(None, description="Number of kids")
    addons: Optional[list] = Field(None, description="List of addons (optional)")


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
            "book": "/book",
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
            result.append(
                CabinInfo(
                    cabin_id=cabin.get("cabin_id", "UNKNOWN"),
                    name=cabin.get("name"),
                    area=cabin.get("area"),
                    max_adults=int(cabin.get("max_adults", 0)) if cabin.get("max_adults") else None,
                    max_kids=int(cabin.get("max_kids", 0)) if cabin.get("max_kids") else None,
                    features=cabin.get("features"),
                    base_price_night=float(cabin.get("base_price_night", 0)) if cabin.get("base_price_night") else None,
                    weekend_price=float(cabin.get("weekend_price", 0)) if cabin.get("weekend_price") else None,
                    calendar_id=cabin.get("calendar_id") or cabin.get("calendarId"),
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
            result.append(
                AvailabilityResponse(
                    cabin_id=cabin.get("cabin_id", "UNKNOWN"),
                    name=cabin.get("name"),
                    area=cabin.get("area"),
                    nights=pricing["nights"],
                    regular_nights=pricing["regular"],
                    weekend_nights=pricing["weekend"],
                    total_price=pricing["total"],
                    max_adults=int(cabin.get("max_adults", 0)) if cabin.get("max_adults") else None,
                    max_kids=int(cabin.get("max_kids", 0)) if cabin.get("max_kids") else None,
                    features=cabin.get("features"),
                )
            )

        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid input: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error checking availability: {str(e)}")


@app.post("/quote", response_model=QuoteResponse)
async def get_quote(request: QuoteRequest):
    """
    מחזיר הצעת מחיר מפורטת עם breakdown מלא
    כולל: עונות, חגים, הנחות, תוספות
    """
    try:
        _, cabins = get_service()
        
        # מצא את הצימר
        chosen = None
        for cabin in cabins:
            if normalize_text(cabin.get("cabin_id")).lower() == normalize_text(request.cabin_id).lower():
                chosen = cabin
                break
        
        if not chosen:
            raise HTTPException(status_code=404, detail=f"Cabin not found: {request.cabin_id}")
        
        # פרס תאריכים
        check_in_local = parse_datetime_local(request.check_in)
        check_out_local = parse_datetime_local(request.check_out)
        
        # חישוב מחיר מתקדם
        engine = PricingEngine()
        pricing = engine.calculate_price_breakdown(
            cabin=chosen,
            check_in=check_in_local,
            check_out=check_out_local,
            addons=request.addons,
            apply_discounts=True
        )
        
        return QuoteResponse(
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
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid input: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error calculating quote: {str(e)}")


@app.post("/book", response_model=BookingResponse)
async def book_cabin(request: BookingRequest):
    try:
        service, cabins = get_service()

        check_in_local = parse_datetime_local(request.check_in)
        check_out_local = parse_datetime_local(request.check_out)
        check_in_utc = to_utc(check_in_local)
        check_out_utc = to_utc(check_out_local)

        chosen = None
        for cabin in cabins:
            if normalize_text(cabin.get("cabin_id")).lower() == normalize_text(request.cabin_id).lower():
                chosen = cabin
                break

        if not chosen:
            raise HTTPException(status_code=404, detail=f"Cabin not found: {request.cabin_id}")

        cal_id = chosen.get("calendar_id") or chosen.get("calendarId")
        if not cal_id:
            raise HTTPException(status_code=400, detail=f"Cabin {request.cabin_id} missing calendar_id")

        is_available, conflicts = is_cabin_available(service, cal_id, check_in_utc, check_out_utc)
        if not is_available:
            raise HTTPException(
                status_code=409,
                detail=f"Cabin {request.cabin_id} is not available. Conflicts: {len(conflicts)}",
            )

        customer = request.customer or "לקוח"
        phone = request.phone or ""
        notes = request.notes or ""

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

        return BookingResponse(
            success=True,
            cabin_id=request.cabin_id,
            event_id=created.get("id"),
            event_link=created.get("htmlLink"),
            message="Booking created successfully",
        )
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid input: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating booking: {str(e)}")


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("API_PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)

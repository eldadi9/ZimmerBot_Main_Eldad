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
    email: Optional[str] = Field(None, description="Customer email")
    adults: Optional[int] = Field(None, description="Number of adults")
    kids: Optional[int] = Field(None, description="Number of kids")
    total_price: Optional[float] = Field(None, description="Total price")
    hold_id: Optional[str] = Field(None, description="Hold ID to convert to booking")


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

        # Save audit log for availability search
        import uuid
        search_id = str(uuid.uuid4())
        save_audit_log(
            table_name="availability_search",
            record_id=search_id,
            action="SEARCH",
            new_values={
                "check_in": request.check_in,
                "check_out": request.check_out,
                "adults": request.adults,
                "kids": request.kids,
                "area": request.area,
                "features": request.features,
                "results_count": len(result)
            }
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
        request_cabin_id_normalized = normalize_text(request.cabin_id).lower()
        for cabin in cabins:
            cabin_id_normalized = normalize_text(cabin.get("cabin_id")).lower()
            if cabin_id_normalized == request_cabin_id_normalized:
                chosen = cabin
                break
        
        if not chosen:
            # Log available cabin_ids for debugging
            available_ids = [normalize_text(c.get("cabin_id")) for c in cabins[:5]]  # First 5 for debugging
            raise HTTPException(
                status_code=404, 
                detail=f"Cabin not found: {request.cabin_id}. Available IDs (sample): {available_ids}"
            )
        
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

        # Find cabin
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

        # Save booking to DB (with event_id and event_link)
        booking_id = save_booking_to_db(
            cabin_id=chosen.get("cabin_id"),
            customer_id=customer_id,
            check_in=check_in_local.date().isoformat(),
            check_out=check_out_local.date().isoformat(),
            adults=request.adults,
            kids=request.kids,
            total_price=request.total_price,
            status="confirmed",
            event_id=event_id,
            event_link=event_link,
        )
        
        # Save transaction (pending status)
        if booking_id:
            transaction_id = save_transaction(
                booking_id=booking_id,
                amount=request.total_price or 0.0,
                status="pending",
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
                    "total_price": request.total_price,
                    "status": "confirmed",
                    "event_id": event_id,
                    "event_link": event_link
                }
            )

        return BookingResponse(
            success=True,
            cabin_id=request.cabin_id,
            event_id=event_id,
            event_link=event_link,
            message="Booking created successfully",
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
                        b.updated_at
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
                
                return [dict(row) for row in rows]
        except psycopg2.OperationalError as db_error:
            # Database not available - return empty list
            print(f"Warning: Database not available for /admin/bookings: {db_error}")
            return []
            
    except Exception as e:
        print(f"Error in /admin/bookings: {e}")
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
            
            cursor.execute("""
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
            """, (booking_id,))
            
            row = cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Booking not found")
            
            # Get transactions for this booking
            cursor.execute("""
                SELECT 
                    id::text as transaction_id,
                    payment_id,
                    amount,
                    currency,
                    status,
                    payment_method,
                    created_at,
                    updated_at
                FROM transactions
                WHERE booking_id = %s::uuid
                ORDER BY created_at DESC
            """, (booking_id,))
            
            transactions = [dict(row) for row in cursor.fetchall()]
            
            booking = dict(row)
            booking["transactions"] = transactions
            
            return booking
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching booking: {str(e)}")


@app.get("/admin/audit")
async def get_audit_logs(
    table_name: Optional[str] = None,
    action: Optional[str] = None,
    limit: int = 100,
    offset: int = 0
):
    """
    Get audit logs (admin endpoint)
    """
    try:
        from src.db import get_db_connection
        from psycopg2.extras import RealDictCursor
        import psycopg2
        
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor(cursor_factory=RealDictCursor)
                
                query = """
                    SELECT 
                        id::text as audit_id,
                        table_name,
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
        except psycopg2.OperationalError as db_error:
            # Database not available - return empty list
            print(f"Warning: Database not available for /admin/audit: {db_error}")
            return []
            
    except Exception as e:
        print(f"Error in /admin/audit: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching audit logs: {str(e)}")


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("API_PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)

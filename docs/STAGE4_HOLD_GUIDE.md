# Stage 4: Hold Mechanism - Complete Guide

## Overview

The Hold mechanism prevents double booking by temporarily reserving a cabin for 15 minutes while a customer completes payment. This ensures that two customers cannot book the same cabin at the same time.

## Architecture

```
Customer selects cabin
        ↓
Create Hold (15 minutes) → Redis + Calendar
        ↓
Customer completes payment
        ↓
Convert Hold to Booking → DB + Calendar (CONFIRMED)
```

## Components

### 1. Redis (Hold Storage)

- **Purpose**: Fast, temporary storage for holds
- **Duration**: 15 minutes (configurable via `HOLD_DURATION_SECONDS`)
- **Key Format**: `hold:{cabin_id}:{check_in}:{check_out}`
- **Auto-expiration**: Holds automatically expire after duration

### 2. HoldManager (`src/hold.py`)

Main class for managing holds:

- `create_hold()` - Create a new hold
- `get_hold()` - Get hold by ID
- `check_hold_exists()` - Check if hold exists
- `release_hold()` - Release a hold manually
- `convert_hold_to_booking()` - Convert hold to confirmed booking

### 3. Database Integration (`src/db.py`)

- `read_cabins_from_db()` - Read cabins from PostgreSQL (with fallback to Sheets)
- `save_customer_to_db()` - Save customer to database
- `save_booking_to_db()` - Save booking to database

### 4. API Endpoints

#### `POST /hold`

Create a temporary hold on a cabin.

**Request:**
```json
{
  "cabin_id": "cabin-1",
  "check_in": "2026-03-01 15:00",
  "check_out": "2026-03-03 11:00",
  "customer_name": "John Doe",
  "customer_id": "optional-uuid"
}
```

**Response:**
```json
{
  "hold_id": "uuid-here",
  "cabin_id": "cabin-1",
  "check_in": "2026-03-01 15:00",
  "check_out": "2026-03-03 11:00",
  "expires_at": "2026-03-01T15:15:00",
  "status": "active",
  "message": "Hold created successfully"
}
```

#### `GET /hold/{hold_id}`

Get hold status by hold_id.

#### `DELETE /hold/{hold_id}`

Release a hold manually.

#### `POST /book` (Updated)

Create a confirmed booking. Now supports:

- `hold_id` - Optional. If provided, converts the hold to a booking
- Saves customer to DB
- Saves booking to DB
- Creates CONFIRMED event in calendar

**Request:**
```json
{
  "cabin_id": "cabin-1",
  "check_in": "2026-03-01 15:00",
  "check_out": "2026-03-03 11:00",
  "customer": "John Doe",
  "phone": "+972501234567",
  "email": "john@example.com",
  "adults": 2,
  "kids": 0,
  "total_price": 1000.0,
  "hold_id": "optional-hold-id",
  "notes": "Optional notes"
}
```

## Setup

### 1. Install Redis

**Windows:**
```bash
# Download from: https://github.com/microsoftarchive/redis/releases
# Or use WSL: wsl --install
```

**Linux/Mac:**
```bash
# Ubuntu/Debian
sudo apt-get install redis-server

# Mac
brew install redis
```

**Start Redis:**
```bash
# Windows (if installed)
redis-server

# Linux/Mac
sudo systemctl start redis
# Or
redis-server
```

### 2. Configure Environment

Add to `.env`:
```env
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=
HOLD_DURATION_SECONDS=900
```

### 3. Install Dependencies

```bash
pip install redis==5.0.1
```

### 4. Import Cabins to Database

```bash
# Windows
database\run_import_cabins.bat

# Linux/Mac
python database/import_cabins_to_db.py
```

## Testing

### Run Stage 4 Tests

```bash
# Windows
database\run_check_stage4.bat

# Linux/Mac
python database/check_stage4.py
```

### Manual Testing

1. **Create Hold:**
```bash
curl -X POST http://127.0.0.1:8000/hold \
  -H "Content-Type: application/json" \
  -d '{
    "cabin_id": "cabin-1",
    "check_in": "2026-03-01 15:00",
    "check_out": "2026-03-03 11:00",
    "customer_name": "Test Customer"
  }'
```

2. **Get Hold:**
```bash
curl http://127.0.0.1:8000/hold/{hold_id}
```

3. **Convert Hold to Booking:**
```bash
curl -X POST http://127.0.0.1:8000/book \
  -H "Content-Type: application/json" \
  -d '{
    "cabin_id": "cabin-1",
    "check_in": "2026-03-01 15:00",
    "check_out": "2026-03-03 11:00",
    "customer": "Test Customer",
    "phone": "+972501234567",
    "hold_id": "{hold_id_from_step_1}"
  }'
```

## Workflow

### Standard Flow (with Hold)

1. Customer searches for availability → `/availability`
2. Customer selects cabin and gets quote → `/quote`
3. Customer clicks "Book" → `POST /hold` (creates 15-minute hold)
4. Customer completes payment
5. Payment webhook → `POST /book` with `hold_id` (converts hold to booking)

### Direct Booking (without Hold)

1. Customer searches → `/availability`
2. Customer clicks "Book" directly → `POST /book` (checks for existing holds, creates booking)

## Fallback Behavior

If Redis is not available:
- System continues to work
- Holds are created but not protected (warning message)
- Double booking prevention relies only on calendar checks
- **Recommendation**: Always use Redis in production

## Database Schema

### Customers Table
- Stores customer information
- Auto-creates or retrieves existing customer by email/phone

### Bookings Table
- Stores all confirmed bookings
- Links to cabin and customer
- Status: `hold`, `confirmed`, `cancelled`

## Calendar Integration

### Hold Events
- Summary: `🔒 HOLD | {customer_name}`
- Color: Yellow (suggested)
- Auto-deleted when hold expires or is converted

### Confirmed Events
- Summary: `הזמנה | {customer_name}`
- Color: Green (suggested)
- Contains booking ID and full details

## Troubleshooting

### Redis Connection Failed

**Error:** `Warning: Could not connect to Redis`

**Solution:**
1. Check if Redis is running: `redis-cli ping` (should return `PONG`)
2. Check `REDIS_HOST` and `REDIS_PORT` in `.env`
3. Check firewall settings

### Hold Not Expiring

**Issue:** Holds not expiring after 15 minutes

**Solution:**
1. Check `HOLD_DURATION_SECONDS` in `.env`
2. Verify Redis TTL: `redis-cli TTL hold:key:here`
3. Restart Redis if needed

### Double Booking Still Happening

**Issue:** Two customers can still book the same cabin

**Solution:**
1. Ensure Redis is running and connected
2. Check that `/hold` is called before `/book`
3. Verify calendar events are being created correctly
4. Check for timezone issues

## Next Steps

After Stage 4 is complete:
- Stage 5: Payment Integration
- Stage 6: Notifications
- Stage 7: Chat Integration

## Files Created/Modified

### New Files
- `src/hold.py` - HoldManager class
- `src/db.py` - Database connection and utilities
- `database/import_cabins_to_db.py` - Import script
- `database/check_stage4.py` - Test script
- `database/run_import_cabins.bat` - Import batch file
- `database/run_check_stage4.bat` - Test batch file

### Modified Files
- `src/api_server.py` - Added Hold endpoints, DB integration
- `requirements.txt` - Added `redis==5.0.1`


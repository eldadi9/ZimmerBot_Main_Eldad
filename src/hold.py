"""
Hold Manager - Temporary reservation system to prevent double booking
"""
import json
import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
import redis
from dotenv import load_dotenv
from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR / ".env")

# Redis configuration
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "0"))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", None)

# Hold duration in seconds (15 minutes)
HOLD_DURATION = int(os.getenv("HOLD_DURATION_SECONDS", "900"))


class HoldManager:
    """
    Manages temporary holds on cabins to prevent double booking
    """
    
    def __init__(self):
        """Initialize Redis connection"""
        try:
            self.redis_client = redis.Redis(
                host=REDIS_HOST,
                port=REDIS_PORT,
                db=REDIS_DB,
                password=REDIS_PASSWORD,
                decode_responses=True,
                socket_connect_timeout=5
            )
            # Test connection
            self.redis_client.ping()
        except (redis.ConnectionError, redis.TimeoutError) as e:
            print(f"Warning: Could not connect to Redis: {e}")
            print("Hold functionality will be disabled. Install Redis to enable.")
            self.redis_client = None
    
    def _is_available(self) -> bool:
        """Check if Redis is available"""
        return self.redis_client is not None
    
    def _generate_hold_key(self, cabin_id: str, check_in: str, check_out: str) -> str:
        """Generate Redis key for hold"""
        # Normalize dates for key
        return f"hold:{cabin_id}:{check_in}:{check_out}"
    
    def create_hold(
        self,
        cabin_id: str,
        check_in: str,
        check_out: str,
        customer_name: Optional[str] = None,
        customer_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a temporary hold on a cabin
        
        Args:
            cabin_id: Cabin identifier
            check_in: Check-in date (YYYY-MM-DD)
            check_out: Check-out date (YYYY-MM-DD)
            customer_name: Customer name (optional)
            customer_id: Customer ID from DB (optional)
        
        Returns:
            Dict with hold_id, expires_at, and other hold data
        
        Raises:
            ValueError: If hold already exists or Redis unavailable
        """
        if not self._is_available():
            # If Redis unavailable, return a "virtual" hold
            # This allows the system to work without Redis, but without protection
            hold_id = str(uuid.uuid4())
            expires_at = (datetime.now() + timedelta(seconds=HOLD_DURATION)).isoformat()
            return {
                "hold_id": hold_id,
                "cabin_id": cabin_id,
                "check_in": check_in,
                "check_out": check_out,
                "customer_name": customer_name,
                "customer_id": customer_id,
                "expires_at": expires_at,
                "status": "created",
                "warning": "Redis unavailable - hold not protected"
            }
        
        hold_key = self._generate_hold_key(cabin_id, check_in, check_out)
        
        # Check if hold already exists
        existing = self.redis_client.get(hold_key)
        if existing:
            existing_data = json.loads(existing)
            raise ValueError(
                f"Cabin {cabin_id} is already on hold until {existing_data.get('expires_at')}"
            )
        
        # Create hold data
        hold_id = str(uuid.uuid4())
        expires_at = (datetime.now() + timedelta(seconds=HOLD_DURATION)).isoformat()
        
        hold_data = {
            "hold_id": hold_id,
            "cabin_id": cabin_id,
            "check_in": check_in,
            "check_out": check_out,
            "customer_name": customer_name,
            "customer_id": customer_id,
            "created_at": datetime.now().isoformat(),
            "expires_at": expires_at,
            "status": "active"
        }
        
        # Store in Redis with expiration
        self.redis_client.setex(
            hold_key,
            HOLD_DURATION,
            json.dumps(hold_data)
        )
        
        # Also store by hold_id for easy lookup
        self.redis_client.setex(
            f"hold:by_id:{hold_id}",
            HOLD_DURATION,
            hold_key
        )
        
        return hold_data
    
    def get_hold(self, hold_id: str) -> Optional[Dict[str, Any]]:
        """
        Get hold by hold_id
        
        Returns:
            Hold data or None if not found
        """
        if not self._is_available():
            return None
        
        hold_key = self.redis_client.get(f"hold:by_id:{hold_id}")
        if not hold_key:
            return None
        
        hold_data = self.redis_client.get(hold_key)
        if not hold_data:
            return None
        
        return json.loads(hold_data)
    
    def check_hold_exists(self, cabin_id: str, check_in: str, check_out: str) -> bool:
        """
        Check if a hold exists for given cabin and dates
        
        Returns:
            True if hold exists, False otherwise
        """
        if not self._is_available():
            return False
        
        hold_key = self._generate_hold_key(cabin_id, check_in, check_out)
        return self.redis_client.exists(hold_key) > 0
    
    def release_hold(self, hold_id: str) -> bool:
        """
        Release a hold by hold_id
        
        Returns:
            True if released, False if not found
        """
        if not self._is_available():
            return False
        
        hold_key = self.redis_client.get(f"hold:by_id:{hold_id}")
        if not hold_key:
            return False
        
        # Delete both keys
        self.redis_client.delete(hold_key)
        self.redis_client.delete(f"hold:by_id:{hold_id}")
        return True
    
    def release_hold_by_dates(self, cabin_id: str, check_in: str, check_out: str) -> bool:
        """
        Release a hold by cabin_id and dates
        
        Returns:
            True if released, False if not found
        """
        if not self._is_available():
            return False
        
        hold_key = self._generate_hold_key(cabin_id, check_in, check_out)
        hold_data = self.redis_client.get(hold_key)
        
        if not hold_data:
            return False
        
        # Get hold_id from data
        data = json.loads(hold_data)
        hold_id = data.get("hold_id")
        
        # Delete both keys
        self.redis_client.delete(hold_key)
        if hold_id:
            self.redis_client.delete(f"hold:by_id:{hold_id}")
        
        return True
    
    def convert_hold_to_booking(
        self,
        hold_id: str,
        booking_id: Optional[str] = None
    ) -> bool:
        """
        Convert a hold to a confirmed booking
        This releases the hold and marks it as converted
        
        Returns:
            True if converted, False if hold not found
        """
        hold_data = self.get_hold(hold_id)
        if not hold_data:
            return False
        
        # Release the hold
        self.release_hold(hold_id)
        
        # Optionally store conversion info (for logging)
        if self._is_available() and booking_id:
            conversion_key = f"hold:converted:{hold_id}"
            self.redis_client.setex(
                conversion_key,
                86400,  # 24 hours
                json.dumps({
                    "hold_id": hold_id,
                    "booking_id": booking_id,
                    "converted_at": datetime.now().isoformat()
                })
            )
        
        return True
    
    def get_all_active_holds(self) -> List[Dict[str, Any]]:
        """
        Get all active holds (for debugging/admin)
        
        Returns:
            List of hold data dictionaries
        """
        if not self._is_available():
            return []
        
        holds = []
        for key in self.redis_client.scan_iter(match="hold:*:*:*"):
            if ":by_id:" in key:
                continue
            
            hold_data = self.redis_client.get(key)
            if hold_data:
                holds.append(json.loads(hold_data))
        
        return holds


# Global instance
_hold_manager = None


def get_hold_manager() -> HoldManager:
    """Get or create global HoldManager instance"""
    global _hold_manager
    if _hold_manager is None:
        _hold_manager = HoldManager()
    return _hold_manager


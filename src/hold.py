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
        # In-memory fallback storage when Redis is unavailable
        self._memory_holds: Dict[str, Dict[str, Any]] = {}
        
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
            print("Hold functionality will use in-memory storage (not persistent). Install Redis to enable.")
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
            # If Redis unavailable, use in-memory storage
            hold_key = self._generate_hold_key(cabin_id, check_in, check_out)
            
            # Check if hold already exists in memory
            if hold_key in self._memory_holds:
                existing_data = self._memory_holds[hold_key]
                # Check if expired
                expires_at_dt = datetime.fromisoformat(existing_data.get('expires_at'))
                if datetime.now() < expires_at_dt:
                    raise ValueError(
                        f"Cabin {cabin_id} is already on hold until {existing_data.get('expires_at')}"
                    )
                else:
                    # Expired, remove it
                    del self._memory_holds[hold_key]
            
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
                "status": "active",
                "warning": "Redis unavailable - hold not protected"
            }
            
            # Store in memory
            self._memory_holds[hold_key] = hold_data
            self._memory_holds[f"hold:by_id:{hold_id}"] = hold_key
            
            return hold_data
        
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
            # Check in-memory storage
            hold_key_ref = self._memory_holds.get(f"hold:by_id:{hold_id}")
            if not hold_key_ref:
                return None
            
            hold_data = self._memory_holds.get(hold_key_ref)
            if not hold_data:
                return None
            
            # Check if expired
            expires_at_dt = datetime.fromisoformat(hold_data.get('expires_at'))
            if datetime.now() >= expires_at_dt:
                # Expired, clean up
                if hold_key_ref in self._memory_holds:
                    del self._memory_holds[hold_key_ref]
                if f"hold:by_id:{hold_id}" in self._memory_holds:
                    del self._memory_holds[f"hold:by_id:{hold_id}"]
                return None
            
            return hold_data
        
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
            # Check in-memory storage
            hold_key_ref = self._memory_holds.get(f"hold:by_id:{hold_id}")
            if not hold_key_ref:
                return False
            
            # Delete both keys from memory
            if hold_key_ref in self._memory_holds:
                del self._memory_holds[hold_key_ref]
            if f"hold:by_id:{hold_id}" in self._memory_holds:
                del self._memory_holds[f"hold:by_id:{hold_id}"]
            return True
        
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
        holds = []
        
        if not self._is_available():
            # In-memory holds - iterate through _memory_holds
            now = datetime.now()
            for key, hold_data in list(self._memory_holds.items()):
                # Skip the hold:by_id: keys
                if key.startswith("hold:by_id:"):
                    continue
                
                # Check if expired
                expires_at_dt = datetime.fromisoformat(hold_data.get('expires_at'))
                if datetime.now() < expires_at_dt:
                    holds.append(hold_data)
                else:
                    # Expired, clean up
                    hold_id = hold_data.get('hold_id')
                    if hold_id and f"hold:by_id:{hold_id}" in self._memory_holds:
                        del self._memory_holds[f"hold:by_id:{hold_id}"]
                    del self._memory_holds[key]
            
            return holds
        
        # With Redis, scan for all hold keys
        try:
            # Get all hold keys (hold:cabin_id:check_in:check_out)
            keys = list(self.redis_client.scan_iter(match="hold:*:*:*"))
            # Filter out hold:by_id: keys
            hold_keys = [k for k in keys if not k.startswith("hold:by_id:")]
            
            for hold_key in hold_keys:
                hold_data_str = self.redis_client.get(hold_key)
                if hold_data_str:
                    hold_data = json.loads(hold_data_str)
                    # Check if expired
                    expires_at_dt = datetime.fromisoformat(hold_data.get('expires_at'))
                    if datetime.now() < expires_at_dt:
                        holds.append(hold_data)
            
            return holds
        except Exception as e:
            print(f"Error listing holds from Redis: {e}")
            return []


# Global instance
_hold_manager = None


def get_hold_manager() -> HoldManager:
    """Get or create global HoldManager instance"""
    global _hold_manager
    if _hold_manager is None:
        _hold_manager = HoldManager()
    return _hold_manager


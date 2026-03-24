import time
import logging
from typing import Dict, Any, Optional
from threading import Lock

logger = logging.getLogger(__name__)

class APIHealthMonitor:
    """Tracks the health and rate-limit status of LLM providers."""
    
    def __init__(self, key_manager: Any):
        self.km = key_manager
        self._lock = Lock()
        self._last_check = 0
        self._cached_status = {}
        self.TTL = 5  # seconds
        
    def get_status(self) -> Dict[str, Any]:
        """Return live provider health from the key manager."""
        with self._lock:
            now = time.time()
            if self._cached_status and (now - self._last_check) < self.TTL:
                return self._cached_status
            
            try:
                # Assuming km.get_health_status() returns {provider: {valid_keys, total_keys, ...}}
                health = self.km.get_health_status()
                status_map = {}
                for provider, info in health.items():
                    valid = info.get("valid_keys", 0)
                    total = info.get("total_keys", 0)
                    
                    if total == 0:
                        state = "no_key"
                    elif valid > 0:
                        state = "healthy"
                    elif info.get("rate_limited_keys", 0) > 0:
                        state = "rate_limited"
                    else:
                        state = "invalid_key"
                        
                    status_map[provider] = {
                        "status": state,
                        "keys_available": valid,
                        "keys_total": total,
                        "timestamp": now
                    }
                self._cached_status = status_map
                self._last_check = now
                return status_map
            except Exception as e:
                logger.error(f"Health monitor failed: {e}")
                return {}

_monitor_instance = None
_monitor_lock = Lock()

def get_health_monitor() -> Optional[APIHealthMonitor]:
    global _monitor_instance
    if _monitor_instance is None:
        try:
            from src.utils.api_key_manager import get_api_key_manager
            km = get_api_key_manager()
            with _monitor_lock:
                if _monitor_instance is None:
                    _monitor_instance = APIHealthMonitor(km)
        except Exception as e:
            logger.error(f"Failed to create health monitor: {e}")
    return _monitor_instance

import time
import threading
import logging
from enum import Enum

logger = logging.getLogger(__name__)

class CircuitState(Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"

class CircuitBreaker:
    """
    A classic Circuit Breaker to prevent cascading failures.
    Transitions:
      CLOSED -> OPEN when failure_count >= failure_threshold
      OPEN -> HALF_OPEN after recovery_timeout elapses
      HALF_OPEN -> CLOSED on first success
      HALF_OPEN -> OPEN on first failure
    """
    def __init__(self, name: str, failure_threshold: int = 3, recovery_timeout: float = 60.0):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = 0.0
        self._lock = threading.Lock()

    def is_allowed(self) -> bool:
        """Check if request is allowed to proceed."""
        with self._lock:
            if self.state == CircuitState.CLOSED:
                return True
                
            if self.state == CircuitState.OPEN:
                if time.time() - self.last_failure_time > self.recovery_timeout:
                    self.state = CircuitState.HALF_OPEN
                    logger.info(f"Circuit {self.name} transitioned to HALF_OPEN (testing recovery)")
                    return True
                return False
                
            # If HALF_OPEN, we already let one request through to test it,
            # so block others until that one succeeds or fails.
            return False

    def record_success(self):
        """Record a success, closing the breaker if it was HALF_OPEN."""
        with self._lock:
            if self.state == CircuitState.HALF_OPEN:
                logger.info(f"Circuit {self.name} recovered. Transitioned to CLOSED.")
                self.state = CircuitState.CLOSED
                self.failure_count = 0
            elif self.state == CircuitState.CLOSED:
                self.failure_count = 0

    def record_failure(self):
        """Record a failure, potentially tripping the breaker."""
        with self._lock:
            self.failure_count += 1
            self.last_failure_time = time.time()
            if self.state == CircuitState.HALF_OPEN or self.failure_count >= self.failure_threshold:
                if self.state != CircuitState.OPEN:
                    logger.warning(f"Circuit {self.name} tripped! Transitioned to OPEN.")
                self.state = CircuitState.OPEN

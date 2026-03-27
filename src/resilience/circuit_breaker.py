"""
src/resilience/circuit_breaker.py — Final production version.
"""
import time, threading, logging
from enum import Enum

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    CLOSED    = "CLOSED"
    OPEN      = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitBreaker:
    def __init__(self, name: str, failure_threshold: int = 3, recovery_timeout: float = 60.0):
        self.name              = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout  = recovery_timeout
        self.state             = CircuitState.CLOSED
        self.failure_count     = 0
        self.last_failure_time = 0.0
        self._lock             = threading.Lock()

    def is_allowed(self) -> bool:
        with self._lock:
            if self.state == CircuitState.CLOSED:
                return True
            if self.state == CircuitState.OPEN:
                if time.time() - self.last_failure_time > self.recovery_timeout:
                    self.state = CircuitState.HALF_OPEN
                    logger.info("Circuit %s → HALF_OPEN (testing recovery)", self.name)
                    return True
                return False
            return False   # HALF_OPEN — block until probe result comes back

    def record_success(self):
        with self._lock:
            if self.state == CircuitState.HALF_OPEN:
                logger.info("Circuit %s recovered → CLOSED", self.name)
                self.state = CircuitState.CLOSED
            self.failure_count = 0

    def record_failure(self):
        with self._lock:
            self.failure_count    += 1
            self.last_failure_time = time.time()
            if self.state == CircuitState.HALF_OPEN or self.failure_count >= self.failure_threshold:
                if self.state != CircuitState.OPEN:
                    logger.warning("Circuit %s tripped → OPEN", self.name)
                self.state = CircuitState.OPEN

"""
src/resilience/retry_handler.py — Final production version.
"""
import time, random, logging
from functools import wraps
from typing import Tuple, Type

logger = logging.getLogger(__name__)


def with_retry(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,)
):
    """Exponential backoff + jitter retry decorator."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exc = None
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exc = e
                    if attempt == max_retries:
                        break
                    delay      = min(max_delay, base_delay * (2 ** attempt))
                    sleep_time = delay + random.uniform(0, 0.1 * delay)
                    logger.warning("Attempt %d/%d failed for %s (%s). Retrying in %.2fs...",
                                   attempt+1, max_retries+1, func.__name__, type(e).__name__, sleep_time)
                    time.sleep(sleep_time)
            logger.error("All %d attempts failed for %s", max_retries+1, func.__name__)
            raise last_exc
        return wrapper
    return decorator

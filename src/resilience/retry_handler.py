import time
import random
import logging
from functools import wraps
from typing import Tuple, Type

logger = logging.getLogger(__name__)

def with_retry(
    max_retries: int = 3, 
    base_delay: float = 1.0, 
    max_delay: float = 30.0, 
    exceptions: Tuple[Type[Exception], ...] = (Exception,)
):
    """
    Exponential backoff retry decorator with jitter.
    Delay = min(max_delay, base_delay * (2 ^ attempt)) + jitter
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt == max_retries:
                        break
                        
                    # Calculate delay: base * 2^attempt
                    delay = min(max_delay, base_delay * (2 ** attempt))
                    
                    # Add jitter (0 to 10% of delay)
                    jitter = random.uniform(0, 0.1 * delay)
                    sleep_time = delay + jitter
                    
                    logger.warning(
                        f"Attempt {attempt+1}/{max_retries+1} failed for {func.__name__} "
                        f"({type(e).__name__}: {e}). Retrying in {sleep_time:.2f}s..."
                    )
                    time.sleep(sleep_time)
            
            logger.error(f"All {max_retries+1} attempts failed for {func.__name__}")
            raise last_exception
        return wrapper
    return decorator

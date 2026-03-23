import logging
from typing import Callable, Any, List, Optional

logger = logging.getLogger(__name__)

class FallbackHandler:
    """
    Executes a series of operations in order until one succeeds.
    Useful for falling back from Primary -> Secondary -> Cached/Degraded.
    """
    @staticmethod
    def execute(operations: List[Callable[[], Any]], graceful_fallback: Optional[Callable[[], Any]] = None) -> Any:
        last_exception = None
        
        for i, operation in enumerate(operations):
            try:
                return operation()
            except Exception as e:
                last_exception = e
                logger.warning(f"Fallback chain step {i+1} failed: {type(e).__name__} - {e}")
                
        if graceful_fallback is not None:
            logger.warning("All primary operations failed, using graceful fallback.")
            return graceful_fallback()
            
        raise last_exception if last_exception else RuntimeError("All operations in fallback chain failed.")

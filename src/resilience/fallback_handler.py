"""
src/resilience/fallback_handler.py — Final production version.
"""
import logging
from typing import Callable, Any, List, Optional

logger = logging.getLogger(__name__)


class FallbackHandler:
    @staticmethod
    def execute(operations: List[Callable[[], Any]], graceful_fallback: Optional[Callable[[], Any]] = None) -> Any:
        """Try each operation in order. If all fail, call graceful_fallback or re-raise."""
        last_exc = None
        for i, op in enumerate(operations):
            try:
                return op()
            except Exception as e:
                last_exc = e
                logger.warning("Fallback chain step %d failed: %s — %s", i+1, type(e).__name__, e)
        if graceful_fallback is not None:
            logger.warning("All primary operations failed — using graceful fallback.")
            return graceful_fallback()
        raise last_exc if last_exc else RuntimeError("All operations in fallback chain failed.")

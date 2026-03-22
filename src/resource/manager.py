import os
import gc
import logging
import psutil
from typing import Callable, List

logger = logging.getLogger(__name__)

class ResourceManager:
    """
    Singleton manager tracking application RSS memory usage dynamically.
    Enforces the MAX_MEMORY_MB limit by clearing L1 caches and invoking gc.collect()
    when memory pressure hits.
    """
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
        
    def __init__(self):
        if self._initialized:
            return
            
        self.max_memory_mb = float(os.getenv("MAX_MEMORY_MB", "500"))
        self._eviction_callbacks: List[Callable[[], None]] = []
        self._initialized = True
        logger.info(f"ResourceManager initialized with {self.max_memory_mb}MB limit")
        
    def register_evictor(self, callback: Callable[[], None]):
        """Register a callback that frees memory (e.g., clearing caches)."""
        if callback not in self._eviction_callbacks:
            self._eviction_callbacks.append(callback)
            
    def get_current_memory_mb(self) -> float:
        """Returns the current RSS memory footprint in MB."""
        try:
            process = psutil.Process()
            return process.memory_info().rss / (1024 * 1024)
        except Exception as e:
            logger.warning(f"Could not retrieve memory info: {e}")
            return 0.0
            
    def check_and_reclaim(self) -> bool:
        """
        Check if memory exceeds the limit and reclaim if necessary.
        Returns True if memory is within safe limits (or was successfully reclaimed).
        """
        current_mb = self.get_current_memory_mb()
        if current_mb > self.max_memory_mb:
            logger.warning(f"🚨 Memory limit exceeded! Current: {current_mb:.1f}MB, Max: {self.max_memory_mb}MB. Reclaiming...")
            
            # Step 1: Trigger all registered evictors (caching layers)
            for evictor in self._eviction_callbacks:
                try:
                    evictor()
                except Exception as e:
                    logger.error(f"Error in memory evictor: {e}")
                    
            # Step 2: Force garbage collection
            gc.collect()
            
            post_mb = self.get_current_memory_mb()
            logger.info(f"Memory after collection: {post_mb:.1f}MB (Freed: {current_mb - post_mb:.1f}MB)")
            
            if post_mb > self.max_memory_mb:
                logger.error(f"❌ Failed to bring memory under limit! ({post_mb:.1f}MB > {self.max_memory_mb}MB)")
                return False
                
        return True

def get_resource_manager() -> ResourceManager:
    return ResourceManager()

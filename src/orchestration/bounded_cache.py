"""
bounded_cache.py — LRU-bounded in-memory cache.

Acts as the L1 layer in front of the SQLite semantic cache.
Provides O(1) lookup for very recently seen claims within the same session.
Thread-safe via a simple Lock.
"""
from collections import OrderedDict
from threading import Lock
from typing import Any, Optional


class BoundedCache:
    """
    Fixed-size LRU cache. When full, evicts the least-recently-used entry.

    Args:
        maxsize: Maximum number of entries to hold. Default 100.
    """

    def __init__(self, maxsize: int = 100) -> None:
        self._cache: OrderedDict = OrderedDict()
        self._maxsize = maxsize
        self._lock = Lock()

    def get(self, key: str) -> Optional[Any]:
        """Return the cached value for key, or None if not present."""
        with self._lock:
            if key not in self._cache:
                return None
            # Move to end = mark as most-recently-used
            self._cache.move_to_end(key)
            return self._cache[key]

    def put(self, key: str, value: Any) -> None:
        """Insert or update key with value. Evicts LRU entry when full."""
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
            self._cache[key] = value
            if len(self._cache) > self._maxsize:
                self._cache.popitem(last=False)   # Evict oldest (LRU)

    def clear(self) -> None:
        """Empty the cache entirely."""
        with self._lock:
            self._cache.clear()

    def __len__(self) -> int:
        return len(self._cache)

    def __contains__(self, key: str) -> bool:
        return key in self._cache

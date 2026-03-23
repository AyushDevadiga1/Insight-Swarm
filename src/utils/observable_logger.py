"""
ObservableLogger — singleton logger that streams to:
  1. A rotating debug.log file (DEBUG level)
  2. A bounded in-memory queue (for live UI display)
  3. Standard Python logging (INFO → console)

Designed so no single subscriber failure can break the logging pipeline.

Usage:
    from src.utils.observable_logger import get_observable_logger
    log = get_observable_logger()
    log.info("API", "Groq call succeeded", latency=0.42)
"""

import logging
import queue
import threading
from datetime import datetime
from pathlib import Path
from typing import Callable


class ObservableLogger:
    """Singleton observable logger — thread-safe, bounded queue, subscriber pattern."""

    _instance: "ObservableLogger | None" = None
    _lock: threading.Lock = threading.Lock()

    def __new__(cls) -> "ObservableLogger":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    inst = super().__new__(cls)
                    inst._initialized = False
                    cls._instance = inst
        return cls._instance

    def __init__(self, log_file: str = "debug.log") -> None:
        if self._initialized:
            return
        self._initialized = True

        # Bounded in-memory queue (prevents memory leak from logging)
        self._queue: queue.Queue = queue.Queue(maxsize=2000)
        self._subscribers: list[Callable] = []
        self._sub_lock = threading.Lock()

        # ── File handler (DEBUG) ──────────────────────────────────────────────
        log_path = Path(log_file)
        file_handler = logging.FileHandler(log_path, mode="a", encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(logging.Formatter(
            "%(asctime)s  %(levelname)-8s  [%(name)s]  %(message)s"
        ))

        # ── Console handler (INFO) ────────────────────────────────────────────
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(logging.Formatter(
            "%(levelname)-8s  %(message)s"
        ))

        # ── Root logger ───────────────────────────────────────────────────────
        root = logging.getLogger("InsightSwarm")
        root.setLevel(logging.DEBUG)
        if not root.handlers:
            root.addHandler(file_handler)
            root.addHandler(console_handler)

        self._root_logger = root

    # ── Public API ────────────────────────────────────────────────────────────

    def log(self, level: str, component: str, message: str, **metadata) -> None:
        """
        Emit a structured log entry.

        Args:
            level:     "DEBUG" | "INFO" | "WARNING" | "ERROR" | "CRITICAL"
            component: Source component name (e.g. "API", "Orchestrator")
            message:   Human-readable message
            **metadata: Extra structured key/value pairs stored in the entry
        """
        entry = {
            "timestamp": datetime.now().isoformat(timespec="milliseconds"),
            "level": level,
            "component": component,
            "message": message,
            **metadata,
        }

        # Non-blocking enqueue (drop oldest if full to prevent memory growth)
        try:
            self._queue.put_nowait(entry)
        except queue.Full:
            try:
                self._queue.get_nowait()  # discard oldest
                self._queue.put_nowait(entry)
            except Exception:
                pass

        # Notify UI subscribers (silently ignore failures)
        with self._sub_lock:
            subs = list(self._subscribers)
        for sub in subs:
            try:
                sub(entry)
            except Exception:
                pass

        # Also emit to standard logger
        logger = logging.getLogger(f"InsightSwarm.{component}")
        getattr(logger, level.lower(), logger.info)(message)

    def info(self, component: str, message: str, **kw) -> None:
        self.log("INFO", component, message, **kw)

    def debug(self, component: str, message: str, **kw) -> None:
        self.log("DEBUG", component, message, **kw)

    def warning(self, component: str, message: str, **kw) -> None:
        self.log("WARNING", component, message, **kw)

    def error(self, component: str, message: str, **kw) -> None:
        self.log("ERROR", component, message, **kw)

    def subscribe(self, callback: Callable) -> None:
        """Register a callback for real-time log entries (e.g. UI panel)."""
        with self._sub_lock:
            if callback not in self._subscribers:
                self._subscribers.append(callback)

    def unsubscribe(self, callback: Callable) -> None:
        with self._sub_lock:
            self._subscribers = [s for s in self._subscribers if s is not callback]

    def get_recent(self, n: int = 100) -> list[dict]:
        """Return up to the last N entries from the bounded queue (non-destructive)."""
        snapshot: list[dict] = []
        temp: list[dict] = []

        while len(snapshot) < n:
            try:
                entry = self._queue.get_nowait()
                snapshot.append(entry)
                temp.append(entry)
            except queue.Empty:
                break

        # Put them all back
        for entry in temp:
            try:
                self._queue.put_nowait(entry)
            except queue.Full:
                break

        return snapshot[-n:]

    def clear(self) -> None:
        """Empty the queue (useful between test runs)."""
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break


# ── Module-level convenience ──────────────────────────────────────────────────

_logger: ObservableLogger | None = None
_init_lock = threading.Lock()


def get_observable_logger() -> ObservableLogger:
    global _logger
    if _logger is None:
        with _init_lock:
            if _logger is None:
                _logger = ObservableLogger()
    return _logger

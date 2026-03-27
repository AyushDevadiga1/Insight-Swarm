"""
src/utils/observable_logger.py — Final production version.
"""
import logging, queue, threading
from datetime import datetime
from pathlib import Path
from typing import Callable


class ObservableLogger:
    """Thread-safe singleton logger with bounded in-memory queue + subscriber pattern."""
    _instance = None
    _lock     = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    inst = super().__new__(cls)
                    inst._initialized = False
                    cls._instance = inst
        return cls._instance

    def __init__(self, log_file: str = "debug.log") -> None:
        if self._initialized: return
        self._initialized = True
        self._queue      = queue.Queue(maxsize=2000)
        self._subscribers: list = []
        self._sub_lock   = threading.Lock()

        fh = logging.FileHandler(Path(log_file), mode="a", encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(logging.Formatter("%(asctime)s  %(levelname)-8s  [%(name)s]  %(message)s"))
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        ch.setFormatter(logging.Formatter("%(levelname)-8s  %(message)s"))
        root = logging.getLogger("InsightSwarm")
        root.setLevel(logging.DEBUG)
        if not root.handlers:
            root.addHandler(fh)
            root.addHandler(ch)
        self._root_logger = root

    def log(self, level: str, component: str, message: str, **metadata) -> None:
        entry = {"timestamp": datetime.now().isoformat(timespec="milliseconds"),
                 "level": level, "component": component, "message": message, **metadata}
        try:
            self._queue.put_nowait(entry)
        except queue.Full:
            try:
                self._queue.get_nowait()
                self._queue.put_nowait(entry)
            except Exception:
                pass
        with self._sub_lock:
            subs = list(self._subscribers)
        for sub in subs:
            try: sub(entry)
            except Exception: pass
        getattr(logging.getLogger(f"InsightSwarm.{component}"), level.lower(), logging.info)(message)

    def info(self, component, message, **kw):    self.log("INFO",    component, message, **kw)
    def debug(self, component, message, **kw):   self.log("DEBUG",   component, message, **kw)
    def warning(self, component, message, **kw): self.log("WARNING", component, message, **kw)
    def error(self, component, message, **kw):   self.log("ERROR",   component, message, **kw)

    def subscribe(self, callback: Callable) -> None:
        with self._sub_lock:
            if callback not in self._subscribers:
                self._subscribers.append(callback)

    def unsubscribe(self, callback: Callable) -> None:
        with self._sub_lock:
            self._subscribers = [s for s in self._subscribers if s is not callback]

    def get_recent(self, n: int = 100) -> list:
        snapshot, temp = [], []
        while len(snapshot) < n:
            try:
                entry = self._queue.get_nowait()
                snapshot.append(entry); temp.append(entry)
            except queue.Empty:
                break
        for entry in temp:
            try: self._queue.put_nowait(entry)
            except queue.Full: break
        return snapshot[-n:]

    def clear(self) -> None:
        while not self._queue.empty():
            try: self._queue.get_nowait()
            except queue.Empty: break


_logger    = None
_init_lock = threading.Lock()

def get_observable_logger() -> ObservableLogger:
    global _logger
    if _logger is None:
        with _init_lock:
            if _logger is None:
                _logger = ObservableLogger()
    return _logger

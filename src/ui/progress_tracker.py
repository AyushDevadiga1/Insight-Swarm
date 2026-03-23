"""
ProgressTracker — tracks debate pipeline stages and broadcasts updates.

Defines granular Stage enum with a pre-mapped progress percentage.
Subscribers (e.g. Streamlit UI) receive ProgressUpdate objects in real-time.

Usage:
    from src.ui.progress_tracker import ProgressTracker, Stage

    tracker = ProgressTracker()
    tracker.subscribe(lambda u: print(u.message))

    tracker.update(Stage.SEARCHING, "Finding evidence for claim...")
    tracker.update(Stage.ROUND_1_PRO, "ProAgent building case...")
    tracker.update(Stage.COMPLETE, "Debate finished.")
"""

import time
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Optional


class Stage(Enum):
    INITIALIZING  = "initializing"
    SEARCHING     = "searching"
    ROUND_1_PRO   = "round_1_pro"
    ROUND_1_CON   = "round_1_con"
    ROUND_2_PRO   = "round_2_pro"
    ROUND_2_CON   = "round_2_con"
    ROUND_3_PRO   = "round_3_pro"
    ROUND_3_CON   = "round_3_con"
    FACT_CHECKING = "fact_checking"
    MODERATING    = "moderating"
    COMPLETE      = "complete"
    ERROR         = "error"


# Maps each stage to the percentage through the pipeline
_STAGE_PCT: dict[Stage, float] = {
    Stage.INITIALIZING:  0.02,
    Stage.SEARCHING:     0.10,
    Stage.ROUND_1_PRO:   0.22,
    Stage.ROUND_1_CON:   0.35,
    Stage.ROUND_2_PRO:   0.47,
    Stage.ROUND_2_CON:   0.58,
    Stage.ROUND_3_PRO:   0.70,
    Stage.ROUND_3_CON:   0.80,
    Stage.FACT_CHECKING: 0.88,
    Stage.MODERATING:    0.95,
    Stage.COMPLETE:      1.00,
    Stage.ERROR:         0.00,
}

_STAGE_ICON: dict[Stage, str] = {
    Stage.INITIALIZING:  "⚙️",
    Stage.SEARCHING:     "🔍",
    Stage.ROUND_1_PRO:   "💬",
    Stage.ROUND_1_CON:   "🔴",
    Stage.ROUND_2_PRO:   "💬",
    Stage.ROUND_2_CON:   "🔴",
    Stage.ROUND_3_PRO:   "💬",
    Stage.ROUND_3_CON:   "🔴",
    Stage.FACT_CHECKING: "✅",
    Stage.MODERATING:    "⚖️",
    Stage.COMPLETE:      "🎉",
    Stage.ERROR:         "❌",
}


@dataclass
class ProgressUpdate:
    stage: Stage
    message: str
    progress_pct: float          # 0.0 → 1.0
    metadata: dict = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    @property
    def icon(self) -> str:
        return _STAGE_ICON.get(self.stage, "•")

    @property
    def elapsed_label(self) -> str:
        """Formatted elapsed time from `start_time` stored in metadata."""
        start = self.metadata.get("start_time", self.timestamp)
        secs = int(time.time() - start)
        return f"{secs}s"


class ProgressTracker:
    """
    Tracks debate progress.  Thread-safe, subscriber-based.

    Attributes:
        updates: Full history of ProgressUpdate objects.
        current: Most recent update (or None).
    """

    def __init__(self) -> None:
        self.start_time = time.time()
        self.updates: list[ProgressUpdate] = []
        self._callbacks: list[Callable[[ProgressUpdate], None]] = []
        self._lock = threading.Lock()

    # ── Core API ──────────────────────────────────────────────────────────────

    def update(
        self,
        stage: Stage,
        message: str,
        metadata: Optional[dict] = None,
    ) -> None:
        """Emit a progress update and notify all subscribers."""
        meta = {"start_time": self.start_time}
        if metadata:
            meta.update(metadata)

        upd = ProgressUpdate(
            stage=stage,
            message=message,
            progress_pct=_STAGE_PCT[stage],
            metadata=meta,
        )

        with self._lock:
            self.updates.append(upd)
            callbacks = list(self._callbacks)

        for cb in callbacks:
            try:
                cb(upd)
            except Exception:
                pass

    def subscribe(self, callback: Callable[[ProgressUpdate], None]) -> None:
        """Register a callback that receives each ProgressUpdate."""
        with self._lock:
            if callback not in self._callbacks:
                self._callbacks.append(callback)

    def unsubscribe(self, callback: Callable[[ProgressUpdate], None]) -> None:
        with self._lock:
            self._callbacks = [c for c in self._callbacks if c is not callback]

    # ── Properties ────────────────────────────────────────────────────────────

    @property
    def current(self) -> Optional[ProgressUpdate]:
        with self._lock:
            return self.updates[-1] if self.updates else None

    @property
    def elapsed(self) -> float:
        return time.time() - self.start_time

    @property
    def is_complete(self) -> bool:
        c = self.current
        return c is not None and c.stage in (Stage.COMPLETE, Stage.ERROR)

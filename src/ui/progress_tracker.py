"""
src/ui/progress_tracker.py
Extended to expose .updates, .current, .elapsed, .start_time so that
streamlit_observable.py can read them (B3-P1 / B3-P5 fix).
"""
from __future__ import annotations
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class Stage(str, Enum):
    """Pipeline stages.  Covers both the simple 5-stage view and the detailed per-round view."""
    IDLE         = "IDLE"
    CONSENSUS    = "CONSENSUS"
    SEARCHING    = "SEARCHING"
    # Per-round stages (used by render_stage_grid)
    ROUND_1_PRO  = "ROUND_1_PRO"
    ROUND_2_PRO  = "ROUND_2_PRO"
    ROUND_3_PRO  = "ROUND_3_PRO"
    ROUND_1_CON  = "ROUND_1_CON"
    ROUND_2_CON  = "ROUND_2_CON"
    ROUND_3_CON  = "ROUND_3_CON"
    # Generic single-round stages (used by debate.py _set_stage calls)
    PRO          = "PRO"
    CON          = "CON"
    FACT_CHECK   = "FACT_CHECK"
    FACT_CHECKING = "FACT_CHECKING"
    MODERATOR    = "MODERATOR"
    MODERATING   = "MODERATING"
    COMPLETE     = "COMPLETE"
    ERROR        = "ERROR"

    # Icon for display
    @property
    def icon(self) -> str:
        _icons = {
            "IDLE":          "⏸",
            "CONSENSUS":     "🔎",
            "SEARCHING":     "🌐",
            "ROUND_1_PRO":   "💬",
            "ROUND_2_PRO":   "💬",
            "ROUND_3_PRO":   "💬",
            "ROUND_1_CON":   "🔴",
            "ROUND_2_CON":   "🔴",
            "ROUND_3_CON":   "🔴",
            "PRO":           "💬",
            "CON":           "🔴",
            "FACT_CHECK":    "✅",
            "FACT_CHECKING": "✅",
            "MODERATOR":     "⚖️",
            "MODERATING":    "⚖️",
            "COMPLETE":      "🏁",
            "ERROR":         "❌",
        }
        return _icons.get(self.value, "•")


# Maps Stage → numeric progress fraction 0.0–1.0
STAGE_PROGRESS: dict = {
    Stage.IDLE:          0.0,
    Stage.CONSENSUS:     0.05,
    Stage.SEARCHING:     0.1,
    Stage.ROUND_1_PRO:   0.2,
    Stage.ROUND_1_CON:   0.3,
    Stage.ROUND_2_PRO:   0.4,
    Stage.ROUND_2_CON:   0.5,
    Stage.ROUND_3_PRO:   0.6,
    Stage.ROUND_3_CON:   0.7,
    Stage.PRO:           0.35,
    Stage.CON:           0.55,
    Stage.FACT_CHECK:    0.75,
    Stage.FACT_CHECKING: 0.75,
    Stage.MODERATOR:     0.9,
    Stage.MODERATING:    0.9,
    Stage.COMPLETE:      1.0,
    Stage.ERROR:         1.0,
}

# For the simple integer index (used by app.py render_progress)
STAGE_INDEX: dict = {
    Stage.IDLE:          0,
    Stage.CONSENSUS:     0,
    Stage.SEARCHING:     0,
    Stage.PRO:           1,
    Stage.ROUND_1_PRO:   1,
    Stage.ROUND_2_PRO:   1,
    Stage.ROUND_3_PRO:   1,
    Stage.CON:           2,
    Stage.ROUND_1_CON:   2,
    Stage.ROUND_2_CON:   2,
    Stage.ROUND_3_CON:   2,
    Stage.FACT_CHECK:    3,
    Stage.FACT_CHECKING: 3,
    Stage.MODERATOR:     4,
    Stage.MODERATING:    4,
    Stage.COMPLETE:      5,
    Stage.ERROR:         5,
}


@dataclass
class StageUpdate:
    """One recorded stage transition."""
    stage:      Stage
    message:    str
    timestamp:  float = field(default_factory=time.time)

    @property
    def progress_pct(self) -> float:
        return STAGE_PROGRESS.get(self.stage, 0.0)

    @property
    def icon(self) -> str:
        return self.stage.icon


class ProgressTracker:
    """
    Thread-safe pipeline progress tracker.

    Exposes:
      .current        → most recent StageUpdate (or None)
      .updates        → list of all StageUpdates so far
      .elapsed        → seconds since first stage was set
      .start_time     → float timestamp of first set_stage() call
      .current_stage  → Stage enum value
      .stage_index    → int 0-5
      .message        → current message string
    """

    def __init__(self) -> None:
        self._updates: List[StageUpdate] = []
        self._lock      = threading.Lock()
        self._start_time: Optional[float] = None

    def set_stage(self, stage: Stage, message: str = "") -> None:
        with self._lock:
            if self._start_time is None:
                self._start_time = time.time()
            self._updates.append(StageUpdate(stage=stage, message=message))

    @property
    def current(self) -> Optional[StageUpdate]:
        with self._lock:
            return self._updates[-1] if self._updates else None

    @property
    def updates(self) -> List[StageUpdate]:
        with self._lock:
            return list(self._updates)

    @property
    def start_time(self) -> float:
        with self._lock:
            return self._start_time or time.time()

    @property
    def elapsed(self) -> float:
        with self._lock:
            if self._start_time is None:
                return 0.0
            return time.time() - self._start_time

    @property
    def current_stage(self) -> Stage:
        c = self.current
        return c.stage if c else Stage.IDLE

    @property
    def message(self) -> str:
        c = self.current
        return c.message if c else ""

    @property
    def stage_index(self) -> int:
        return STAGE_INDEX.get(self.current_stage, 0)

    def is_complete(self) -> bool:
        return self.current_stage in (Stage.COMPLETE, Stage.ERROR)

    def reset(self) -> None:
        with self._lock:
            self._updates    = []
            self._start_time = None

"""
src/ui/progress_tracker.py — Final production version.
"""
from __future__ import annotations
import threading, time
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class Stage(str, Enum):
    IDLE          = "IDLE"
    CONSENSUS     = "CONSENSUS"
    SEARCHING     = "SEARCHING"
    ROUND_1_PRO   = "ROUND_1_PRO"
    ROUND_2_PRO   = "ROUND_2_PRO"
    ROUND_3_PRO   = "ROUND_3_PRO"
    ROUND_1_CON   = "ROUND_1_CON"
    ROUND_2_CON   = "ROUND_2_CON"
    ROUND_3_CON   = "ROUND_3_CON"
    PRO           = "PRO"
    CON           = "CON"
    FACT_CHECK    = "FACT_CHECK"
    FACT_CHECKING = "FACT_CHECKING"
    MODERATOR     = "MODERATOR"
    MODERATING    = "MODERATING"
    COMPLETE      = "COMPLETE"
    ERROR         = "ERROR"

    @property
    def icon(self) -> str:
        return {
            "IDLE":"⏸","CONSENSUS":"🔎","SEARCHING":"🌐",
            "ROUND_1_PRO":"💬","ROUND_2_PRO":"💬","ROUND_3_PRO":"💬",
            "ROUND_1_CON":"🔴","ROUND_2_CON":"🔴","ROUND_3_CON":"🔴",
            "PRO":"💬","CON":"🔴",
            "FACT_CHECK":"✅","FACT_CHECKING":"✅",
            "MODERATOR":"⚖️","MODERATING":"⚖️",
            "COMPLETE":"🏁","ERROR":"❌",
        }.get(self.value, "•")


STAGE_PROGRESS: dict = {
    Stage.IDLE:0.0,Stage.CONSENSUS:0.05,Stage.SEARCHING:0.1,
    Stage.ROUND_1_PRO:0.2,Stage.ROUND_1_CON:0.3,
    Stage.ROUND_2_PRO:0.4,Stage.ROUND_2_CON:0.5,
    Stage.ROUND_3_PRO:0.6,Stage.ROUND_3_CON:0.7,
    Stage.PRO:0.35,Stage.CON:0.55,
    Stage.FACT_CHECK:0.75,Stage.FACT_CHECKING:0.75,
    Stage.MODERATOR:0.9,Stage.MODERATING:0.9,
    Stage.COMPLETE:1.0,Stage.ERROR:1.0,
}

STAGE_INDEX: dict = {
    Stage.IDLE:0,Stage.CONSENSUS:0,Stage.SEARCHING:0,
    Stage.PRO:1,Stage.ROUND_1_PRO:1,Stage.ROUND_2_PRO:1,Stage.ROUND_3_PRO:1,
    Stage.CON:2,Stage.ROUND_1_CON:2,Stage.ROUND_2_CON:2,Stage.ROUND_3_CON:2,
    Stage.FACT_CHECK:3,Stage.FACT_CHECKING:3,
    Stage.MODERATOR:4,Stage.MODERATING:4,
    Stage.COMPLETE:5,Stage.ERROR:5,
}


@dataclass
class StageUpdate:
    stage:     Stage
    message:   str
    timestamp: float = field(default_factory=time.time)

    @property
    def progress_pct(self) -> float:
        return STAGE_PROGRESS.get(self.stage, 0.0)

    @property
    def icon(self) -> str:
        return self.stage.icon


class ProgressTracker:
    def __init__(self) -> None:
        self._updates:    List[StageUpdate] = []
        self._lock        = threading.Lock()
        self._start_time: Optional[float]   = None

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
            return 0.0 if self._start_time is None else time.time() - self._start_time

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

"""
src/async_tasks/task_queue.py
Lightweight thread-pool task queue for running DebateOrchestrator.run()
in the background so the Streamlit UI can poll for progress without
blocking the main thread (B2-P3 fix).

Design:
  - Single ThreadPoolExecutor (max 2 workers) shared across the process.
  - Tasks are identified by a string task_id.
  - Results and errors are stored in an in-memory dict guarded by a Lock.
  - Streamlit calls get_status(task_id) each rerun; the UI polls with st.rerun().
"""
import threading
import logging
from concurrent.futures import ThreadPoolExecutor, Future
from typing import Any, Callable, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

# Global singleton — created once per process
_task_queue_instance: Optional["TaskQueue"] = None
_task_queue_lock = threading.Lock()


class TaskQueue:
    """Simple thread-pool task queue for background debate execution."""

    def __init__(self, max_workers: int = 2) -> None:
        self._executor = ThreadPoolExecutor(max_workers=max_workers,
                                            thread_name_prefix="insightswarm_task")
        self._tasks: Dict[str, Dict[str, Any]] = {}
        self._lock  = threading.Lock()

    def submit(self, task_id: str, fn: Callable, *args, **kwargs) -> None:
        """Submit a callable to run in the background."""
        with self._lock:
            if task_id in self._tasks and self._tasks[task_id].get("status") == "RUNNING":
                logger.warning("Task %s already running — ignoring duplicate submit", task_id)
                return
            self._tasks[task_id] = {"status": "RUNNING", "result": None, "error": None}

        def _run():
            try:
                result = fn(*args, **kwargs)
                with self._lock:
                    if task_id in self._tasks:
                        self._tasks[task_id].update(status="COMPLETED", result=result)
            except Exception as exc:
                logger.error("Task %s failed: %s", task_id, exc)
                with self._lock:
                    if task_id in self._tasks:
                        self._tasks[task_id].update(status="FAILED", error=exc)

        self._executor.submit(_run)
        logger.debug("Submitted task %s", task_id)

    def get_status(self, task_id: str) -> Tuple[str, Any, Any]:
        """
        Returns (status_code, result, error).
        status_code: "RUNNING" | "COMPLETED" | "FAILED" | "UNKNOWN"
        """
        with self._lock:
            task = self._tasks.get(task_id)
        if task is None:
            return "UNKNOWN", None, None
        return task["status"], task.get("result"), task.get("error")

    def clear_task(self, task_id: str) -> None:
        """Remove a completed/failed task from memory."""
        with self._lock:
            self._tasks.pop(task_id, None)

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False)


def get_task_queue() -> TaskQueue:
    """Get or create the global TaskQueue singleton (thread-safe)."""
    global _task_queue_instance
    if _task_queue_instance is None:
        with _task_queue_lock:
            if _task_queue_instance is None:
                _task_queue_instance = TaskQueue()
    return _task_queue_instance

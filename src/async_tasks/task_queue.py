"""
src/async_tasks/task_queue.py — Final production version.
Thread-pool task queue for background debate execution in Streamlit.
"""
import threading, logging, time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

_task_queue_instance: Optional["TaskQueue"] = None
_task_queue_lock = threading.Lock()


class TaskQueue:
    def __init__(self, max_workers: int = 2) -> None:
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="insightswarm_task")
        self._tasks: Dict[str, Dict[str, Any]] = {}
        self._lock  = threading.Lock()
        self._max_tasks = 100 # Prevent memory leak

    def _cleanup(self):
        """Evict oldest completed tasks if queue is full."""
        if len(self._tasks) > self._max_tasks:
            # Sort by timestamp if you added one, or just pop the first found completed
            completed_ids = [tid for tid, t in self._tasks.items() if t['status'] in ("COMPLETED", "FAILED")]
            for tid in completed_ids[:10]: # Evict batch of 10
                self._tasks.pop(tid, None)

    def submit(self, task_id: str, fn: Callable, *args, **kwargs) -> None:
        with self._lock:
            self._cleanup()
            if task_id in self._tasks and self._tasks[task_id].get("status") == "RUNNING":
                logger.warning("Task %s already running — ignoring duplicate submit", task_id)
                return
            self._tasks[task_id] = {"status":"RUNNING","result":None,"error":None, "ts": time.time()}

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
                        self._tasks[task_id].update(status="FAILED", error=str(exc))

        self._executor.submit(_run)

    def get_status(self, task_id: str) -> Tuple[str, Any, Any]:
        with self._lock:
            task = self._tasks.get(task_id)
        if task is None:
            return "UNKNOWN", None, None
        return task["status"], task.get("result"), task.get("error")

    def clear_task(self, task_id: str) -> None:
        with self._lock:
            self._tasks.pop(task_id, None)

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False)


def get_task_queue() -> TaskQueue:
    global _task_queue_instance
    if _task_queue_instance is None:
        with _task_queue_lock:
            if _task_queue_instance is None:
                _task_queue_instance = TaskQueue()
    return _task_queue_instance

import threading
import queue
import uuid
import logging
import atexit
import time
from typing import Any, Callable, Dict, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, Future

logger = logging.getLogger(__name__)

class BackgroundTaskQueue:
    """
    Manages a background thread pool for long-running LLM tasks.
    Allows Streamlit to poll for status without blocking the UI.
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance.executor = ThreadPoolExecutor(max_workers=3)
                cls._instance.tasks: Dict[str, Tuple[Future, Any]] = {} 
                atexit.register(cls._instance.executor.shutdown, wait=False)
        return cls._instance

    def _prune_old_tasks(self):
        """Remove completed tasks older than 10 minutes to prevent memory leak."""
        now = time.time()
        to_delete = [
            task_id
            for task_id, (future, _) in self.tasks.items()
            if future.done() and (now - getattr(future, '_submitted_at', now)) > 600
        ]
        for task_id in to_delete:
            del self.tasks[task_id]
        
        # Hard cap: if still over 50, evict the oldest completed task
        if len(self.tasks) > 50:
            for tid, (f, _) in list(self.tasks.items()):
                if f.done():
                    del self.tasks[tid]
                    break

    def submit(self, task_id: str, func: Callable, *args, **kwargs) -> str:
        """
        Submit a task to the background executor.
        Returns the task_id.
        """
        self._prune_old_tasks()
        
        if task_id in self.tasks:
            # Task already exists/running
            future, _ = self.tasks[task_id]
            if not future.done():
                return task_id

        # Submit task
        future = self.executor.submit(func, *args, **kwargs)
        future._submitted_at = time.time()
        self.tasks[task_id] = (future, None)
        logger.info(f"Task {task_id} submitted to background queue.")
        return task_id

    def get_status(self, task_id: str) -> Tuple[str, Optional[Any], Optional[Exception]]:
        """
        Check the status of a background task.
        Returns (status, result, error) where status is 'PENDING', 'RUNNING', 'COMPLETED', 'FAILED'.
        """
        if task_id not in self.tasks:
            return "NOT_FOUND", None, None

        future, _ = self.tasks[task_id]
        if future.done():
            try:
                result = future.result()
                return "COMPLETED", result, None
            except Exception as e:
                logger.error(f"Task {task_id} failed: {e}")
                return "FAILED", None, e
        
        return "RUNNING", None, None

    def clear_task(self, task_id: str):
        if task_id in self.tasks:
            del self.tasks[task_id]

_queue_instance = None
def get_task_queue() -> BackgroundTaskQueue:
    global _queue_instance
    if _queue_instance is None:
        _queue_instance = BackgroundTaskQueue()
    return _queue_instance

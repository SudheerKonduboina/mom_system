# app/task_queue.py
# Async background task queue for meeting processing

import asyncio
import logging
import traceback
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, Optional
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger("TaskQueue")


class TaskStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class TaskQueue:
    """
    In-memory async task queue for processing meetings in the background.
    Upgradeable to Celery + Redis for production.
    """

    def __init__(self, max_workers: int = 2):
        self._tasks: Dict[str, Dict[str, Any]] = {}
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._lock = asyncio.Lock()

    async def enqueue(self, task_id: str, func: Callable, *args, **kwargs) -> str:
        """
        Add a task to the queue.
        Returns: task_id
        """
        async with self._lock:
            self._tasks[task_id] = {
                "status": TaskStatus.QUEUED,
                "result": None,
                "error": None,
                "enqueued_at": datetime.utcnow().isoformat(),
                "started_at": None,
                "completed_at": None,
                "progress": 0,
            }

        # Run in background
        asyncio.get_event_loop().run_in_executor(
            self._executor,
            self._run_sync, task_id, func, args, kwargs
        )

        return task_id

    def _run_sync(self, task_id: str, func: Callable, args: tuple, kwargs: dict):
        """Execute task synchronously in thread pool."""
        try:
            self._tasks[task_id]["status"] = TaskStatus.PROCESSING
            self._tasks[task_id]["started_at"] = datetime.utcnow().isoformat()

            result = func(*args, **kwargs)

            self._tasks[task_id]["status"] = TaskStatus.COMPLETED
            self._tasks[task_id]["result"] = result
            self._tasks[task_id]["completed_at"] = datetime.utcnow().isoformat()
            self._tasks[task_id]["progress"] = 100

        except Exception as e:
            self._tasks[task_id]["status"] = TaskStatus.FAILED
            self._tasks[task_id]["error"] = str(e)
            self._tasks[task_id]["completed_at"] = datetime.utcnow().isoformat()
            logger.error(f"Task {task_id} failed: {e}")
            traceback.print_exc()

    def get_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get task status and result."""
        task = self._tasks.get(task_id)
        if not task:
            return None
        return {
            "task_id": task_id,
            "status": task["status"],
            "progress": task["progress"],
            "enqueued_at": task["enqueued_at"],
            "started_at": task["started_at"],
            "completed_at": task["completed_at"],
            "error": task["error"],
            "has_result": task["result"] is not None,
        }

    def get_result(self, task_id: str) -> Optional[Any]:
        """Get task result if completed."""
        task = self._tasks.get(task_id)
        if not task or task["status"] != TaskStatus.COMPLETED:
            return None
        return task["result"]

    def update_progress(self, task_id: str, progress: int):
        """Update task progress (0-100)."""
        if task_id in self._tasks:
            self._tasks[task_id]["progress"] = min(100, max(0, progress))

    def cleanup_old(self, max_age_hours: int = 24):
        """Remove completed/failed tasks older than max_age_hours."""
        now = datetime.utcnow()
        to_remove = []
        for task_id, task in self._tasks.items():
            if task["completed_at"]:
                try:
                    completed = datetime.fromisoformat(task["completed_at"])
                    age = (now - completed).total_seconds() / 3600
                    if age > max_age_hours:
                        to_remove.append(task_id)
                except Exception:
                    pass
        for tid in to_remove:
            del self._tasks[tid]


# Singleton
task_queue = TaskQueue()

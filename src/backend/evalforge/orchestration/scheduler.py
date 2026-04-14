"""
Distributed Scheduler - Stateless job dispatch system.

Manages job queue and dispatch to worker pool. Supports both local parallel
execution and Kubernetes cluster scale-out.
"""

from typing import List, Dict, Any, Callable, Optional
import queue
import threading
from datetime import datetime


class Scheduler:
    """
    Stateless job scheduler for distributed execution.
    
    Strategy: Fire-and-forget job dispatch with back-pressure handling.
    Workers pull jobs from queue on completion.
    """

    def __init__(self, worker_pool: Any):
        self.queue = queue.Queue()
        self.worker_pool = worker_pool
        self.results = []
        self._lock = threading.Lock()
        self._running = False

    def dispatch(self, jobs: List[Dict[str, Any]]) -> None:
        """Dispatch list of jobs to the queue."""
        for job in jobs:
            job["status"] = "queued"
            self.queue.put(job)

    def start(self) -> None:
        """Start scheduler execution."""
        self._running = True
        self.worker_pool.start(self.queue, self._result_callback)

    def stop(self) -> None:
        """Stop scheduler execution."""
        self._running = False
        self.worker_pool.stop()

    def wait(self) -> List[Dict[str, Any]]:
        """Wait for all jobs to complete and return results."""
        self.queue.join()
        self.stop()
        return self.results

    def _result_callback(self, result: Dict[str, Any]) -> None:
        """Internal callback for completed jobs."""
        with self._lock:
            result["completed_at"] = datetime.now().isoformat()
            self.results.append(result)
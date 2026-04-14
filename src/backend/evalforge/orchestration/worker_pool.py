"""
Worker Pool - Local parallel execution engine.

Manages pool of worker processes for local parallel execution.
Supports process isolation for safe tool execution.
"""

from typing import List, Dict, Any, Callable
import multiprocessing
import queue
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class WorkerPool:
    """
    Local process pool executor for benchmark jobs.
    
    Each worker runs in an isolated process to prevent cross-contamination
    between tool executions.
    """

    def __init__(self, num_workers: int = 8):
        self.num_workers = num_workers
        self.workers: List[multiprocessing.Process] = []
        self._running = False

    def start(self, job_queue: queue.Queue, result_callback: Callable) -> None:
        """Start worker pool execution."""
        self._running = True

        for i in range(self.num_workers):
            worker = multiprocessing.Process(
                target=self._worker_loop,
                args=(i, job_queue, result_callback),
                daemon=True
            )
            worker.start()
            self.workers.append(worker)

    def stop(self) -> None:
        """Stop all workers."""
        self._running = False
        for worker in self.workers:
            if worker.is_alive():
                worker.terminate()
                worker.join(timeout=5)

    @staticmethod
    def _worker_loop(
        worker_id: int,
        job_queue: queue.Queue,
        result_callback: Callable
    ) -> None:
        """Main worker execution loop."""
        while True:
            try:
                job = job_queue.get(block=True, timeout=1.0)
            except queue.Empty:
                continue

            try:
                logger.info(f"Worker {worker_id}: Starting job {job['job_id']}")
                job["status"] = "running"
                job["started_at"] = datetime.now().isoformat()

                # Import executor dynamically to avoid circular imports
                from .executor import JobExecutor
                result = JobExecutor.execute(job)

                job["result"] = result
                job["status"] = "completed"
                result_callback(job)

            except Exception as e:
                logger.exception(f"Worker {worker_id}: Job {job['job_id']} failed")
                job["status"] = "failed"
                job["error"] = str(e)
                result_callback(job)

            finally:
                job_queue.task_done()
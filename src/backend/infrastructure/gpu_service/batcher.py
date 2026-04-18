import time
from typing import List, Dict, Any
from .queue import dequeue_batch
from .runtime_settings import BATCH_SIZE, BATCH_TIMEOUT


class Batcher:
    """Collect tasks into batches for efficient GPU processing."""

    def __init__(self, batch_size=None, timeout=None):
        self.batch_size = batch_size or BATCH_SIZE
        self.timeout = timeout or BATCH_TIMEOUT
        self.buffer: List[Dict[str, Any]] = []

    def collect(self) -> List[Dict[str, Any]]:
        """Collect tasks into a batch."""
        start = time.time()

        while len(self.buffer) < self.batch_size:
            tasks = dequeue_batch(self.batch_size - len(self.buffer))
            if tasks:
                self.buffer.extend(tasks)

            if time.time() - start > self.timeout:
                break

        batch = self.buffer[: self.batch_size]
        self.buffer = self.buffer[self.batch_size :]

        return batch

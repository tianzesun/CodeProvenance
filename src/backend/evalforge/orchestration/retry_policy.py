"""
Retry Policy - Failure handling for scientific integrity.

Implements conservative retry logic that ensures failed jobs are retried
appropriately without compromising scientific validity.
"""

from typing import Dict, Any


class RetryPolicy:
    """
    Failure handling policy for benchmark jobs.
    
    Retries transient errors up to 3 times. Fatal errors are not retried
    to maintain scientific integrity.
    """

    MAX_ATTEMPTS = 3
    FATAL_ERRORS = {
        "OutOfMemoryError",
        "SegmentationFault",
        "IllegalInstruction",
        "ToolNotFound",
        "DatasetNotFound"
    }

    @staticmethod
    def should_retry(job: Dict[str, Any]) -> bool:
        """
        Determine if a failed job should be retried.

        Args:
            job: Job record with attempt count and error

        Returns:
            True if job should be retried
        """
        if job["attempt"] >= RetryPolicy.MAX_ATTEMPTS:
            return False

        if "error" not in job:
            return False

        error_message = str(job["error"])

        # Never retry fatal errors
        for fatal in RetryPolicy.FATAL_ERRORS:
            if fatal in error_message:
                return False

        return True

    @staticmethod
    def is_fatal_error(error: Exception) -> bool:
        """Check if an error is considered fatal."""
        return any(fatal in str(error) for fatal in RetryPolicy.FATAL_ERRORS)
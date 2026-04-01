"""
Batch Processing Module for CodeProvenance.

Provides distributed batch similarity computation using Celery workers.
"""

import hashlib
import json
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import asyncio


class BatchStatus(Enum):
    """Batch job status."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class BatchJob:
    """Represents a batch comparison job."""
    job_id: str
    tenant_id: str
    file_ids: List[str]
    status: BatchStatus = BatchStatus.PENDING
    total_comparisons: int = 0
    completed_comparisons: int = 0
    failed_comparisons: int = 0
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None


@dataclass
class BatchResult:
    """Result of a batch comparison job."""
    job_id: str
    results: List[Dict[str, Any]]
    summary: Dict[str, Any]
    execution_time_ms: float
    status: BatchStatus


class BatchProcessor:
    """
    Batch processor for similarity comparisons.
    
    Features:
    - Incremental processing (only new/changed files)
    - Progress tracking
    - Automatic retry for failed comparisons
    - Result caching
    """
    
    def __init__(
        self,
        max_workers: int = 4,
        batch_size: int = 100,
        retry_attempts: int = 3
    ):
        """
        Initialize batch processor.
        
        Args:
            max_workers: Maximum parallel workers
            batch_size: Number of comparisons per batch
            retry_attempts: Number of retry attempts for failures
        """
        self.max_workers = max_workers
        self.batch_size = batch_size
        self.retry_attempts = retry_attempts
        self._results_cache = {}
    
    def generate_comparison_pairs(
        self,
        file_ids: List[str],
        previous_file_ids: Optional[List[str]] = None
    ) -> List[Tuple[str, str]]:
        """
        Generate comparison pairs for a set of files.
        
        Uses incremental comparison when previous_file_ids is provided.
        
        Args:
            file_ids: Current file IDs
            previous_file_ids: Previous file IDs (for incremental processing)
            
        Returns:
            List of (file_id_a, file_id_b) pairs
        """
        if previous_file_ids is None:
            # Full comparison: all pairs
            pairs = []
            for i, file_a in enumerate(file_ids):
                for file_b in file_ids[i+1:]:
                    pairs.append((file_a, file_b))
            return pairs
        
        # Incremental comparison: only compare new files with existing ones
        existing_set = set(previous_file_ids)
        new_files = [f for f in file_ids if f not in existing_set]
        
        pairs = []
        # Compare new files with all existing files
        for new_file in new_files:
            for existing_file in previous_file_ids:
                pairs.append((new_file, existing_file))
        
        return pairs
    
    def process_batch(
        self,
        pairs: List[Tuple[str, str]],
        similarity_function,
        progress_callback: Optional[callable] = None
    ) -> List[Dict[str, Any]]:
        """
        Process a batch of comparisons.
        
        Args:
            pairs: List of (file_id_a, file_id_b) pairs
            similarity_function: Function to compute similarity
            progress_callback: Optional callback for progress updates
            
        Returns:
            List of comparison results
        """
        results = []
        total = len(pairs)
        
        # Process in batches
        for i in range(0, total, self.batch_size):
            batch = pairs[i:i + self.batch_size]
            
            # Process batch in parallel
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                futures = {
                    executor.submit(
                        self._compare_pair,
                        pair,
                        similarity_function
                    ): pair
                    for pair in batch
                }
                
                for future in as_completed(futures):
                    pair = futures[future]
                    try:
                        result = future.result()
                        results.append(result)
                    except Exception as e:
                        results.append({
                            'file_a': pair[0],
                            'file_b': pair[1],
                            'error': str(e),
                            'similarity': 0.0
                        })
            
            # Report progress
            if progress_callback:
                progress = min(i + len(batch), total) / total * 100
                progress_callback(progress, len(results), total)
        
        return results
    
    def _compare_pair(
        self,
        pair: Tuple[str, str],
        similarity_function
    ) -> Dict[str, Any]:
        """Compare a single pair with retry logic."""
        file_a, file_b = pair
        
        # Check cache
        cache_key = self._get_cache_key(file_a, file_b)
        if cache_key in self._results_cache:
            return self._results_cache[cache_key]
        
        for attempt in range(self.retry_attempts):
            try:
                similarity = similarity_function(file_a, file_b)
                result = {
                    'file_a': file_a,
                    'file_b': file_b,
                    'similarity': similarity,
                    'error': None
                }
                self._results_cache[cache_key] = result
                return result
            except Exception as e:
                if attempt == self.retry_attempts - 1:
                    return {
                        'file_a': file_a,
                        'file_b': file_b,
                        'similarity': 0.0,
                        'error': str(e)
                    }
        
        return {'file_a': file_a, 'file_b': file_b, 'similarity': 0.0}
    
    def _get_cache_key(self, file_a: str, file_b: str) -> str:
        """Generate cache key for a pair."""
        sorted_files = sorted([file_a, file_b])
        return f"{sorted_files[0]}:{sorted_files[1]}"
    
    def summarize_results(
        self,
        results: List[Dict[str, Any]],
        threshold: float = 0.5
    ) -> Dict[str, Any]:
        """
        Summarize batch comparison results.
        
        Args:
            results: List of comparison results
            threshold: Threshold for flagging
            
        Returns:
            Summary statistics
        """
        total = len(results)
        errors = sum(1 for r in results if r.get('error'))
        successful = total - errors
        
        similarities = [r['similarity'] for r in results if 'similarity' in r]
        
        if not similarities:
            return {
                'total': total,
                'successful': successful,
                'failed': errors,
                'avg_similarity': 0.0,
                'max_similarity': 0.0,
                'flagged_count': 0
            }
        
        flagged = [s for s in similarities if s >= threshold]
        
        return {
            'total': total,
            'successful': successful,
            'failed': errors,
            'avg_similarity': sum(similarities) / len(similarities),
            'max_similarity': max(similarities),
            'min_similarity': min(similarities),
            'flagged_count': len(flagged),
            'flagged_percentage': len(flagged) / len(similarities) * 100 if similarities else 0
        }


# Celery task definitions
try:
    from celery import Celery, group, chord, chain
    from celery.result import AsyncResult
    import redis
    
    celery_app = Celery('codeprovenance')
    celery_app.config_from_object('src.workers.celery_config')
    
    class CeleryBatchProcessor:
        """
        Celery-based distributed batch processor.
        
        Distributes comparison work across multiple workers.
        """
        
        def __init__(self, redis_url: str = "redis://localhost:6379/0"):
            self.redis_url = redis_url
            self._redis = redis.from_url(redis_url)
        
        def submit_job(
            self,
            job_id: str,
            pairs: List[Tuple[str, str]],
            tenant_id: str
        ) -> str:
            """
            Submit a batch job for processing.
            
            Args:
                job_id: Unique job ID
                pairs: List of (file_id_a, file_id_b) pairs
                tenant_id: Tenant ID for multi-tenancy
                
            Returns:
                Celery task group ID
            """
            # Create batch job record
            job = BatchJob(
                job_id=job_id,
                tenant_id=tenant_id,
                file_ids=[p[0] for p in pairs] + [p[1] for p in pairs],
                total_comparisons=len(pairs),
                status=BatchStatus.PENDING
            )
            self._save_job(job)
            
            # Create comparison tasks
            task_signatures = [
                compare_pair_task.s(job_id, pair[0], pair[1])
                for pair in pairs
            ]
            
            # Create group of tasks
            task_group = group(task_signatures)
            
            # Execute and store result
            result = task_group.apply_async()
            
            # Update job with task group ID
            self._redis.hset(f"job:{job_id}", "task_group_id", result.id)
            
            return result.id
        
        def get_job_status(self, job_id: str) -> Dict[str, Any]:
            """Get job status and progress."""
            job_data = self._redis.hgetall(f"job:{job_id}")
            
            if not job_data:
                return {'status': 'not_found'}
            
            return {
                'job_id': job_id,
                'status': job_data.get(b'status', b'unknown').decode(),
                'total_comparisons': int(job_data.get(b'total_comparisons', 0)),
                'completed_comparisons': int(job_data.get(b'completed_comparisons', 0)),
                'failed_comparisons': int(job_data.get(b'failed_comparisons', 0)),
                'progress': self._calculate_progress(job_data)
            }
        
        def _calculate_progress(self, job_data: bytes) -> float:
            """Calculate job progress percentage."""
            total = int(job_data.get(b'total_comparisons', 0))
            completed = int(job_data.get(b'completed_comparisons', 0))
            
            if total == 0:
                return 0.0
            
            return completed / total * 100
        
        def _save_job(self, job: BatchJob):
            """Save job to Redis."""
            self._redis.hset(f"job:{job.job_id}", mapping={
                'tenant_id': job.tenant_id,
                'status': job.status.value,
                'total_comparisons': str(job.total_comparisons),
                'completed_comparisons': str(job.completed_comparisons),
                'failed_comparisons': str(job.failed_comparisons),
                'created_at': job.created_at.isoformat()
            })
        
        def update_job_progress(self, job_id: str, increment: int = 1):
            """Update job progress."""
            self._redis.hincrby(f"job:{job_id}", 'completed_comparisons', increment)
        
        def get_results(self, job_id: str) -> List[Dict[str, Any]]:
            """Get job results from Redis."""
            results_key = f"results:{job_id}"
            results_json = self._redis.lrange(results_key, 0, -1)
            
            return [json.loads(r.decode()) for r in results_json]
        
        def store_result(self, job_id: str, result: Dict[str, Any]):
            """Store a comparison result."""
            results_key = f"results:{job_id}"
            self._redis.rpush(results_key, json.dumps(result))
    
    @celery_app.task(bind=True, max_retries=3)
    def compare_pair_task(self, job_id: str, file_a: str, file_b: str) -> Dict[str, Any]:
        """
        Celery task to compare a single pair of files.
        
        Args:
            job_id: Batch job ID
            file_a: First file ID
            file_b: Second file ID
            
        Returns:
            Comparison result
        """
        try:
            # Import similarity engine
            from src.engines.similarity.base_similarity import SimilarityEngine, register_builtin_algorithms
            
            # Get code content (would be fetched from storage in real implementation)
            code_a = ""  # Would be: storage.get_file(file_a)
            code_b = ""  # Would be: storage.get_file(file_b)
            
            # Parse code
            from src.core.parser import CodeParser
            parser = CodeParser()
            parsed_a = parser.parse(code_a, file_a.split('.')[-1])
            parsed_b = parser.parse(code_b, file_b.split('.')[-1])
            
            # Compare
            engine = SimilarityEngine()
            register_builtin_algorithms(engine)
            result = engine.compare(parsed_a, parsed_b)
            
            # Store result
            comparison_result = {
                'file_a': file_a,
                'file_b': file_b,
                'similarity': result.get('overall_score', 0.0),
                'individual_scores': result.get('individual_scores', {}),
                'deep_analysis': result.get('deep_analysis', {})
            }
            
            return comparison_result
            
        except Exception as e:
            # Retry on failure
            raise self.retry(exc=e, countdown=5)
    
    @celery_app.task
    def aggregate_results_task(self, job_id: str) -> Dict[str, Any]:
        """
        Celery task to aggregate batch results.
        
        Args:
            job_id: Batch job ID
            
        Returns:
            Aggregated results summary
        """
        from src.workers.batch_processor import BatchProcessor
        
        # This would collect results from Redis
        # For now, return a placeholder
        return {
            'job_id': job_id,
            'status': 'completed',
            'summary': {}
        }
    
except ImportError:
    # Celery not installed, provide stubs
    CeleryBatchProcessor = None
    
    def compare_pair_task(*args, **kwargs):
        raise ImportError("Celery is required for distributed processing. Install with: pip install celery redis")


class IncrementalBatchProcessor:
    """
    Incremental batch processor for efficient updates.
    
    Only compares new/changed files against existing submissions.
    """
    
    def __init__(self, batch_processor: BatchProcessor):
        self.batch_processor = batch_processor
        self._previous_hashes = {}
    
    def detect_changes(
        self,
        file_ids: List[str],
        get_file_hash: callable
    ) -> Tuple[List[str], List[str]]:
        """
        Detect which files have changed.
        
        Args:
            file_ids: Current file IDs
            get_file_hash: Function to get file hash
            
        Returns:
            Tuple of (new_files, changed_files)
        """
        new_files = []
        changed_files = []
        
        for file_id in file_ids:
            current_hash = get_file_hash(file_id)
            
            if file_id not in self._previous_hashes:
                new_files.append(file_id)
            elif self._previous_hashes[file_id] != current_hash:
                changed_files.append(file_id)
        
        return new_files, changed_files
    
    def process_incremental(
        self,
        file_ids: List[str],
        get_file_hash: callable,
        similarity_function,
        progress_callback: Optional[callable] = None
    ) -> Dict[str, Any]:
        """
        Process files incrementally.
        
        Args:
            file_ids: Current file IDs
            get_file_hash: Function to get file hash
            similarity_function: Similarity function
            progress_callback: Progress callback
            
        Returns:
            Incremental comparison results
        """
        new_files, changed_files = self.detect_changes(file_ids, get_file_hash)
        
        # Update hashes
        for file_id in file_ids:
            self._previous_hashes[file_id] = get_file_hash(file_id)
        
        # Generate pairs for new/changed files
        pairs = []
        for file_id in new_files + changed_files:
            for existing_id in self._previous_hashes:
                if existing_id != file_id:
                    pairs.append((file_id, existing_id))
        
        # Process pairs
        results = self.batch_processor.process_batch(
            pairs,
            similarity_function,
            progress_callback
        )
        
        return {
            'new_files': new_files,
            'changed_files': changed_files,
            'comparisons': len(pairs),
            'results': results
        }


# Convenience functions
def create_batch_processor(
    max_workers: int = 4,
    batch_size: int = 100
) -> BatchProcessor:
    """Create a configured batch processor."""
    return BatchProcessor(max_workers=max_workers, batch_size=batch_size)


def estimate_comparison_time(num_files: int, avg_comparison_ms: float = 100) -> float:
    """
    Estimate time for batch comparison.
    
    Args:
        num_files: Number of files
        avg_comparison_ms: Average comparison time in milliseconds
        
    Returns:
        Estimated time in seconds
    """
    # Total pairs = n*(n-1)/2
    total_pairs = num_files * (num_files - 1) / 2
    total_time_ms = total_pairs * avg_comparison_ms
    return total_time_ms / 1000

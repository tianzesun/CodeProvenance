"""Redis queue wrapper with lazy imports."""

from typing import Dict, Any, List, Optional
import json
import uuid

_redis = None


def _get_redis():
    """Lazy import redis."""
    global _redis
    if _redis is None:
        try:
            import redis as _redis_module
            from .runtime_settings import REDIS_URL

            _redis = _redis_module.Redis.from_url(REDIS_URL, decode_responses=True)
        except ImportError:
            raise ImportError("redis is required: pip install redis")
    return _redis


QUEUE_NAME = "gpu_tasks"
RESULT_PREFIX = "gpu_result:"


def enqueue(task: Dict[str, Any]) -> str:
    """Add task to queue. Returns task_id."""
    task_id = task.get("id", str(uuid.uuid4()))
    task["id"] = task_id
    _get_redis().rpush(QUEUE_NAME, json.dumps(task))
    return task_id


def enqueue_batch(tasks: List[Dict[str, Any]]) -> List[str]:
    """Batch enqueue. Returns list of task_ids."""
    return [enqueue(t) for t in tasks]


def dequeue_batch(max_items: int) -> List[Dict[str, Any]]:
    """Dequeue up to max_items tasks."""
    tasks = []
    for _ in range(max_items):
        item = _get_redis().lpop(QUEUE_NAME)
        if not item:
            break
        tasks.append(json.loads(item))
    return tasks


def save_result(task_id: str, result: Dict[str, Any], ttl: int = 3600):
    """Save result with TTL."""
    _get_redis().set(RESULT_PREFIX + task_id, json.dumps(result), ex=ttl)


def get_result(task_id: str) -> Optional[Dict[str, Any]]:
    """Get result by task_id. None if not ready."""
    data = _get_redis().get(RESULT_PREFIX + task_id)
    return json.loads(data) if data else None

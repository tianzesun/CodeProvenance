import redis
import uuid
import json
from typing import Dict, Any, List, Optional
from .config import REDIS_URL

r = redis.Redis.from_url(REDIS_URL, decode_responses=True)
QUEUE_NAME = "gpu_tasks"
RESULT_PREFIX = "gpu_result:"

def enqueue(task: Dict[str, Any]) -> str:
    """Add task to queue. Returns task_id."""
    task_id = task.get("id", str(uuid.uuid4()))
    task["id"] = task_id
    r.rpush(QUEUE_NAME, json.dumps(task))
    return task_id

def enqueue_batch(tasks: List[Dict[str, Any]]) -> List[str]:
    """Batch enqueue. Returns list of task_ids."""
    ids = []
    for t in tasks:
        ids.append(enqueue(t))
    return ids

def dequeue_batch(max_items: int) -> List[Dict[str, Any]]:
    """Dequeue up to max_items tasks."""
    tasks = []
    for _ in range(max_items):
        item = r.lpop(QUEUE_NAME)
        if not item:
            break
        tasks.append(json.loads(item))
    return tasks

def save_result(task_id: str, result: Dict[str, Any], ttl: int = 3600):
    """Save result with TTL."""
    r.set(RESULT_PREFIX + task_id, json.dumps(result), ex=ttl)

def get_result(task_id: str) -> Optional[Dict[str, Any]]:
    """Get result by task_id. None if not ready."""
    data = r.get(RESULT_PREFIX + task_id)
    return json.loads(data) if data else None

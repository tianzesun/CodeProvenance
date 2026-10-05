"""Cache administration API endpoints.

Provides cache statistics, health monitoring, and manual cache control
for administrators.
"""

from __future__ import annotations

import logging
import os
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response

router = APIRouter(prefix="/api/admin/cache", tags=["cache-admin"])
logger = logging.getLogger(__name__)

#: Admin responses describe infrastructure state; keep them out of shared caches.
_NO_STORE = "no-store"


def _require_admin(request: Request) -> Any:
    """Require an authenticated admin and return the resolved user.

    ``server`` imports this router, so it is imported lazily to avoid a cycle.
    """
    from src.backend.api.server import _require_current_user

    return _require_current_user(request, admin_only=True)


def _actor_id(user: Any) -> str:
    """Identify the acting admin for the audit log (id only, no email)."""
    if isinstance(user, dict):
        return str(user.get("id") or "unknown")
    return "unknown"


def _cache_failure(action: str) -> HTTPException:
    """Log the active exception and build a generic 503 with a reference id.

    Call from inside an ``except`` block. The raw error (which can contain the
    Redis host or connection details) goes to the log only; the client gets the
    reference to quote to an operator.
    """
    ref = uuid.uuid4().hex[:12]
    logger.exception("Cache %s failed (ref=%s)", action, ref)
    return HTTPException(
        status_code=503, detail=f"Cache {action} failed. Reference: {ref}"
    )


# These handlers are plain ``def`` on purpose: the cache clients do blocking
# network I/O (Redis), and FastAPI runs sync handlers in a worker thread instead
# of stalling the event loop the way a blocking call inside ``async def`` does.


@router.get("/stats")
def get_cache_stats(request: Request, response: Response) -> dict:
    """Get cache statistics and performance metrics.

    Returns:
        - type: Cache backend type (RedisCache or InMemoryCache)
        - available: Whether cache is operational
        - size: Number of cached items (in-memory only)
        - hit_rate: Cache hit rate (Redis only)
        - keyspace_hits: Total cache hits (Redis only)
        - keyspace_misses: Total cache misses (Redis only)
    """
    from src.backend.infrastructure.cache import cache_stats

    _require_admin(request)
    response.headers["Cache-Control"] = _NO_STORE
    try:
        return cache_stats()
    except Exception:
        raise _cache_failure("statistics lookup") from None


@router.post("/clear")
def clear_cache_endpoint(request: Request) -> dict:
    """Clear all cached values.

    Use this when:
    - Upgrading AI detection models (invalidate old embeddings)
    - After fixing bugs in perplexity computation
    - Testing with fresh analysis
    - Troubleshooting inconsistent results

    Warning: Next analysis will be slower until cache rebuilds.
    """
    from src.backend.infrastructure.cache import clear_cache as _clear_cache

    user = _require_admin(request)
    try:
        _clear_cache()
    except Exception:
        raise _cache_failure("clear") from None

    # Destructive and global, so leave an audit trail of who did it.
    logger.warning("Cache cleared by admin %s", _actor_id(user))
    return {
        "message": "Cache cleared successfully",
        "note": "Next analysis will rebuild cache (slower initially)",
    }


@router.get("/health")
def cache_health(request: Request, response: Response) -> dict:
    """Check cache health and connectivity.

    Returns:
        - cache_type: Backend class name
        - available: Whether the active backend is operational
        - redis_available: Whether Redis is connected and responding
        - fallback_active: Whether using in-memory fallback
        - status: ``healthy``, ``degraded`` (in-memory fallback) or
          ``unhealthy`` (Redis configured but not responding)
        - recommendations: Suggested actions if issues detected
    """
    from src.backend.infrastructure.cache import get_cache

    _require_admin(request)
    response.headers["Cache-Control"] = _NO_STORE

    try:
        cache = get_cache()
        available = bool(getattr(cache, "available", False))
    except Exception:
        raise _cache_failure("health check") from None

    cache_type = cache.__class__.__name__
    health: dict[str, Any] = {"cache_type": cache_type, "available": available}

    if cache_type == "InMemoryCache":
        health["redis_available"] = False
        health["fallback_active"] = True
        health["status"] = "degraded"
        health["recommendations"] = [
            "Install Redis: apt-get install redis-server (Ubuntu) or brew install redis (Mac)",
            "Start Redis: redis-server",
            "Set REDIS_HOST and REDIS_PORT environment variables",
            "Restart application to enable Redis caching",
        ]
    elif available:
        health["redis_available"] = True
        health["fallback_active"] = False
        health["status"] = "healthy"
        health["recommendations"] = []
    else:
        # Redis backend selected but not answering. Previously this reported
        # "healthy" simply because the class was not the in-memory fallback.
        health["redis_available"] = False
        health["fallback_active"] = False
        health["status"] = "unhealthy"
        health["recommendations"] = [
            "Check that the Redis server is running and reachable from this host",
            "Verify REDIS_HOST, REDIS_PORT and REDIS_PASSWORD",
            "Check network/firewall rules between the application and Redis",
        ]

    return health


@router.get("/config")
def cache_config(request: Request, response: Response) -> dict:
    """Get cache configuration.

    Returns current cache settings from environment variables. The Redis
    password is never returned, only whether one is set.
    """
    _require_admin(request)
    response.headers["Cache-Control"] = _NO_STORE

    return {
        "CACHE_ENABLED": os.getenv("CACHE_ENABLED", "true"),
        "REDIS_HOST": os.getenv("REDIS_HOST", "localhost"),
        "REDIS_PORT": os.getenv("REDIS_PORT", "6379"),
        "REDIS_DB": os.getenv("REDIS_DB", "0"),
        "REDIS_PASSWORD": "***" if os.getenv("REDIS_PASSWORD") else None,
    }

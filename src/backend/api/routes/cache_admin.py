"""Cache administration API endpoints.

Provides cache statistics, health monitoring, and manual cache control
for administrators.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

router = APIRouter()


@router.get("/api/admin/cache/stats")
async def get_cache_stats(request: Request):
    """Get cache statistics and performance metrics.

    Returns:
        - type: Cache backend type (RedisCache or InMemoryCache)
        - available: Whether cache is operational
        - size: Number of cached items (in-memory only)
        - hit_rate: Cache hit rate (Redis only)
        - keyspace_hits: Total cache hits (Redis only)
        - keyspace_misses: Total cache misses (Redis only)
    """
    from src.backend.api.server import _require_current_user
    from src.backend.infrastructure.cache import cache_stats

    _require_current_user(request, admin_only=True)
    stats = cache_stats()
    return JSONResponse(content=stats)


@router.post("/api/admin/cache/clear")
async def clear_cache(request: Request):
    """Clear all cached values.

    Use this when:
    - Upgrading AI detection models (invalidate old embeddings)
    - After fixing bugs in perplexity computation
    - Testing with fresh analysis
    - Troubleshooting inconsistent results

    Warning: Next analysis will be slower until cache rebuilds.
    """
    from src.backend.api.server import _require_current_user
    from src.backend.infrastructure.cache import clear_cache

    _require_current_user(request, admin_only=True)
    clear_cache()
    return JSONResponse(
        content={
            "message": "Cache cleared successfully",
            "note": "Next analysis will rebuild cache (slower initially)",
        }
    )


@router.get("/api/admin/cache/health")
async def cache_health(request: Request):
    """Check cache health and connectivity.

    Returns:
        - redis_available: Whether Redis is connected
        - fallback_active: Whether using in-memory fallback
        - recommendations: Suggested actions if issues detected
    """
    from src.backend.api.server import _require_current_user
    from src.backend.infrastructure.cache import get_cache

    _require_current_user(request, admin_only=True)

    cache = get_cache()
    health = {
        "cache_type": cache.__class__.__name__,
        "available": cache.available,
    }

    # Check if we're using fallback
    if cache.__class__.__name__ == "InMemoryCache":
        health["redis_available"] = False
        health["fallback_active"] = True
        health["recommendations"] = [
            "Install Redis: apt-get install redis-server (Ubuntu) or brew install redis (Mac)",
            "Start Redis: redis-server",
            "Set REDIS_HOST and REDIS_PORT environment variables",
            "Restart application to enable Redis caching",
        ]
        health["status"] = "degraded"
    else:
        health["redis_available"] = True
        health["fallback_active"] = False
        health["recommendations"] = []
        health["status"] = "healthy"

    return JSONResponse(content=health)


@router.get("/api/admin/cache/config")
async def cache_config(request: Request):
    """Get cache configuration.

    Returns current cache settings from environment variables.
    """
    import os

    from src.backend.api.server import _require_current_user

    _require_current_user(request, admin_only=True)

    config = {
        "CACHE_ENABLED": os.getenv("CACHE_ENABLED", "true"),
        "REDIS_HOST": os.getenv("REDIS_HOST", "localhost"),
        "REDIS_PORT": os.getenv("REDIS_PORT", "6379"),
        "REDIS_DB": os.getenv("REDIS_DB", "0"),
        "REDIS_PASSWORD": "***" if os.getenv("REDIS_PASSWORD") else None,
    }

    return JSONResponse(content=config)

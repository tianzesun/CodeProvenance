"""Redis-based caching for expensive computations.

Provides 10x speedup on re-analysis by caching:
- Transformer perplexity scores (GPT-2 tokenization + forward pass)
- Code embeddings (UniXcoder/CodeBERT vectors)
- AST structural features
- Model fingerprinting results

Cache keys use semantic hashing (content-based) to detect identical code
even with different filenames.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from typing import Any, Callable, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CacheBackend:
    """Abstract cache backend interface."""

    def get(self, key: str) -> Any | None:
        """Retrieve cached value by key."""
        raise NotImplementedError

    def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """Store value with optional TTL (seconds)."""
        raise NotImplementedError

    def delete(self, key: str) -> None:
        """Remove cached value."""
        raise NotImplementedError

    def clear(self) -> None:
        """Clear all cached values."""
        raise NotImplementedError

    def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        raise NotImplementedError


class RedisCache(CacheBackend):
    """Redis-backed cache with JSON serialization."""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        password: str | None = None,
        key_prefix: str = "integritydesk:",
    ):
        """Initialize Redis connection.

        Args:
            host: Redis server hostname
            port: Redis server port
            db: Redis database number (0-15)
            password: Optional Redis password
            key_prefix: Namespace prefix for all keys
        """
        try:
            import redis

            self.redis = redis.Redis(
                host=host,
                port=port,
                db=db,
                password=password,
                decode_responses=True,  # Auto-decode bytes to str
                socket_connect_timeout=2,
                socket_timeout=2,
            )
            # Test connection
            self.redis.ping()
            self.available = True
            self.key_prefix = key_prefix
            logger.info(f"Redis cache connected: {host}:{port} db={db}")
        except Exception as e:
            logger.warning(f"Redis unavailable, caching disabled: {e}")
            self.redis = None
            self.available = False
            self.key_prefix = key_prefix

    def _make_key(self, key: str) -> str:
        """Add namespace prefix to key."""
        return f"{self.key_prefix}{key}"

    def get(self, key: str) -> Any | None:
        """Retrieve cached value, returns None if not found or Redis unavailable."""
        if not self.available:
            return None
        try:
            value = self.redis.get(self._make_key(key))
            if value is None:
                return None
            return json.loads(value)
        except Exception as e:
            logger.debug(f"Cache get failed for {key}: {e}")
            return None

    def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """Store value with optional TTL.

        Args:
            key: Cache key
            value: JSON-serializable value
            ttl: Time to live in seconds (None = no expiration)
        """
        if not self.available:
            return
        try:
            serialized = json.dumps(value)
            if ttl:
                self.redis.setex(self._make_key(key), ttl, serialized)
            else:
                self.redis.set(self._make_key(key), serialized)
        except Exception as e:
            logger.debug(f"Cache set failed for {key}: {e}")

    def delete(self, key: str) -> None:
        """Remove cached value."""
        if not self.available:
            return
        try:
            self.redis.delete(self._make_key(key))
        except Exception as e:
            logger.debug(f"Cache delete failed for {key}: {e}")

    def clear(self) -> None:
        """Clear all keys with our prefix."""
        if not self.available:
            return
        try:
            # Scan for keys with our prefix and delete in batches
            cursor = 0
            while True:
                cursor, keys = self.redis.scan(
                    cursor, match=f"{self.key_prefix}*", count=100
                )
                if keys:
                    self.redis.delete(*keys)
                if cursor == 0:
                    break
            logger.info("Cache cleared")
        except Exception as e:
            logger.warning(f"Cache clear failed: {e}")

    def exists(self, key: str) -> bool:
        """Check if key exists."""
        if not self.available:
            return False
        try:
            return bool(self.redis.exists(self._make_key(key)))
        except Exception as e:
            logger.debug(f"Cache exists check failed for {key}: {e}")
            return False


class InMemoryCache(CacheBackend):
    """Simple in-memory cache fallback when Redis unavailable.

    Uses LRU eviction with configurable max size.
    """

    def __init__(self, max_size: int = 1000):
        """Initialize in-memory cache.

        Args:
            max_size: Maximum number of cached items before LRU eviction
        """
        from collections import OrderedDict

        self.cache: OrderedDict[str, Any] = OrderedDict()
        self.max_size = max_size
        self.available = True
        logger.info(f"In-memory cache initialized (max_size={max_size})")

    def get(self, key: str) -> Any | None:
        """Retrieve cached value, moving to end (most recently used)."""
        if key not in self.cache:
            return None
        # Move to end (LRU)
        self.cache.move_to_end(key)
        return self.cache[key]

    def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """Store value, evicting oldest if at capacity.

        Note: TTL is ignored in memory cache (no background expiration).
        """
        if key in self.cache:
            # Update existing and move to end
            self.cache.move_to_end(key)
        else:
            # Add new, evict oldest if at capacity
            if len(self.cache) >= self.max_size:
                self.cache.popitem(last=False)  # Remove oldest (FIFO)
        self.cache[key] = value

    def delete(self, key: str) -> None:
        """Remove cached value."""
        self.cache.pop(key, None)

    def clear(self) -> None:
        """Clear all cached values."""
        self.cache.clear()

    def exists(self, key: str) -> bool:
        """Check if key exists."""
        return key in self.cache


# Global cache instance (lazily initialized)
_cache_instance: CacheBackend | None = None


def get_cache() -> CacheBackend:
    """Get global cache instance (Redis or in-memory fallback)."""
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = _initialize_cache()
    return _cache_instance


def _initialize_cache() -> CacheBackend:
    """Initialize cache backend from environment variables.

    Environment variables:
        REDIS_HOST: Redis server hostname (default: localhost)
        REDIS_PORT: Redis server port (default: 6379)
        REDIS_DB: Redis database number (default: 0)
        REDIS_PASSWORD: Redis password (default: None)
        CACHE_ENABLED: Enable caching (default: true)
    """
    # Check if caching is explicitly disabled
    if os.getenv("CACHE_ENABLED", "true").lower() == "false":
        logger.info("Caching explicitly disabled via CACHE_ENABLED=false")
        return InMemoryCache(max_size=0)  # Dummy cache

    # Try Redis first
    try:
        redis_host = os.getenv("REDIS_HOST", "localhost")
        redis_port = int(os.getenv("REDIS_PORT", "6379"))
        redis_db = int(os.getenv("REDIS_DB", "0"))
        redis_password = os.getenv("REDIS_PASSWORD")

        cache = RedisCache(
            host=redis_host,
            port=redis_port,
            db=redis_db,
            password=redis_password,
        )
        if cache.available:
            return cache
    except Exception as e:
        logger.info(f"Redis initialization failed: {e}")

    # Fall back to in-memory cache
    logger.info("Falling back to in-memory cache (no Redis)")
    return InMemoryCache(max_size=1000)


def semantic_hash(code: str) -> str:
    """Generate semantic hash of code for cache keys.

    Uses normalized content (whitespace-insensitive) to detect
    identical code even with different formatting or filenames.

    Args:
        code: Source code string

    Returns:
        SHA256 hex digest (64 chars)
    """
    # Normalize: strip leading/trailing whitespace, collapse multiple spaces
    import re

    normalized = re.sub(r"\s+", " ", code.strip())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def cached(
    cache_key_fn: Callable[..., str],
    ttl: int | None = 3600,
    enabled: bool = True,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator for caching function results.

    Args:
        cache_key_fn: Function to generate cache key from arguments
        ttl: Cache TTL in seconds (default: 1 hour)
        enabled: Enable caching (default: True)

    Example:
        @cached(lambda code: f"perplexity:{semantic_hash(code)}", ttl=3600)
        def compute_perplexity(code: str) -> float:
            # Expensive computation
            return score
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        def wrapper(*args, **kwargs) -> T:
            if not enabled:
                return func(*args, **kwargs)

            cache = get_cache()
            if not cache.available:
                return func(*args, **kwargs)

            # Generate cache key
            try:
                key = cache_key_fn(*args, **kwargs)
            except Exception as e:
                logger.debug(f"Cache key generation failed: {e}")
                return func(*args, **kwargs)

            # Check cache
            cached_value = cache.get(key)
            if cached_value is not None:
                logger.debug(f"Cache HIT: {key}")
                return cached_value

            # Compute and store
            logger.debug(f"Cache MISS: {key}")
            result = func(*args, **kwargs)
            try:
                cache.set(key, result, ttl=ttl)
            except Exception as e:
                logger.debug(f"Cache set failed: {e}")

            return result

        return wrapper

    return decorator


def cache_stats() -> dict[str, Any]:
    """Get cache statistics.

    Returns:
        Dict with cache type, size, hit rate, etc.
    """
    cache = get_cache()
    stats = {
        "type": cache.__class__.__name__,
        "available": cache.available,
    }

    if isinstance(cache, InMemoryCache):
        stats["size"] = len(cache.cache)
        stats["max_size"] = cache.max_size
    elif isinstance(cache, RedisCache) and cache.available:
        try:
            info = cache.redis.info("stats")
            stats["keyspace_hits"] = info.get("keyspace_hits", 0)
            stats["keyspace_misses"] = info.get("keyspace_misses", 0)
            total = stats["keyspace_hits"] + stats["keyspace_misses"]
            stats["hit_rate"] = stats["keyspace_hits"] / total if total > 0 else 0.0
        except Exception as e:
            logger.debug(f"Could not get Redis stats: {e}")

    return stats


def clear_cache() -> None:
    """Clear all cached values."""
    cache = get_cache()
    cache.clear()

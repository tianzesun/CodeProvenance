"""Caching layer for expensive similarity computations.

Provides content-hashed LRU caches for:
- ML embeddings (CodeBERT/UniXcoder/OpenAI)
- AST parse results
- Token fingerprints
"""
from __future__ import annotations

import hashlib
import logging
from functools import lru_cache
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


def _sha256(content: str) -> str:
    """Return the first 16 hex chars of the SHA-256 hash of *content*."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]


# ── Embedding cache (most expensive: ML model forward pass) ──────────

class EmbeddingCache:
    """In-memory LRU cache for dense vector embeddings.

    Call ``get_or_compute()`` with raw code and a compute function.
    The cache key is the SHA-256 hash of the raw code, so identical
    code produces the same key regardless of variable names or file path.
    """

    def __init__(self, maxsize: int = 4096) -> None:
        self._cache: dict[str, list[float]] = {}
        self._order: list[str] = []
        self.maxsize = maxsize
        self.hits = 0
        self.misses = 0

    def _evict(self) -> None:
        if len(self._cache) > self.maxsize:
            oldest = self._order.pop(0)
            self._cache.pop(oldest, None)

    def get_or_compute(
        self,
        code: str,
        compute: Callable[[str], list[float]],
    ) -> list[float]:
        """Return cached embedding or compute and cache *compute(code)*."""
        key = _sha256(code)

        if key in self._cache:
            self.hits += 1
            return list(self._cache[key])

        self.misses += 1
        embedding = compute(code)
        self._cache[key] = embedding
        self._order.append(key)
        self._evict()
        return embedding

    def clear(self) -> None:
        self._cache.clear()
        self._order.clear()
        self.hits = 0
        self.misses = 0

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total else 0.0


# ── Token / fingerprint cache (fast but called many times) ───────────

class TokenCache:
    """LRU cache for tokenized / fingerprinted code.

    Tokenization is CPU-bound but deterministic, so caching avoids
    re-parsing the same file for every pair it participates in.
    """

    def __init__(self, maxsize: int = 8192) -> None:
        self._cache: dict[str, Any] = {}
        self._order: list[str] = []
        self.maxsize = maxsize
        self.hits = 0
        self.misses = 0

    def _evict(self) -> None:
        if len(self._cache) > self.maxsize:
            oldest = self._order.pop(0)
            self._cache.pop(oldest, None)

    def get_or_compute(
        self,
        code: str,
        compute: Callable[[str], Any],
    ) -> Any:
        """Return cached tokens or compute and cache *compute(code)*."""
        key = _sha256(code)

        if key in self._cache:
            self.hits += 1
            return self._cache[key]

        self.misses += 1
        result = compute(code)
        self._cache[key] = result
        self._order.append(key)
        self._evict()
        return result

    def clear(self) -> None:
        self._cache.clear()
        self._order.clear()
        self.hits = 0
        self.misses = 0

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total else 0.0


# ── Global singleton instances ───────────────────────────────────────

_embedding_cache: Optional[EmbeddingCache] = None
_token_cache: Optional[TokenCache] = None


def get_embedding_cache(maxsize: int = 4096) -> EmbeddingCache:
    """Get or create the global ``EmbeddingCache``."""
    global _embedding_cache
    if _embedding_cache is None:
        _embedding_cache = EmbeddingCache(maxsize=maxsize)
    return _embedding_cache


def get_token_cache(maxsize: int = 8192) -> TokenCache:
    """Get or create the global ``TokenCache``."""
    global _token_cache
    if _token_cache is None:
        _token_cache = TokenCache(maxsize=maxsize)
    return _token_cache


def invalidate_all_caches() -> None:
    """Clear both global caches (useful for testing or forced re-compute)."""
    global _embedding_cache, _token_cache
    if _embedding_cache is not None:
        _embedding_cache.clear()
    if _token_cache is not None:
        _token_cache.clear()
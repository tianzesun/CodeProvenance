"""
Redis-based caching layer for CodeProvenance.

Provides caching for:
- Parsed AST results
- Similarity computation results
- Fingerprint hashes
- Batch comparison results
"""

import json
import hashlib
import pickle
from typing import Any, Dict, List, Optional, Tuple
from datetime import timedelta
from pathlib import Path


class CacheManager:
    """
    Manages caching of parsed code and similarity results.
    
    Uses Redis as the cache backend with automatic serialization.
    Falls back to file-based caching if Redis is unavailable.
    """
    
    def __init__(
        self,
        redis_url: str = "redis://localhost:6379/0",
        default_ttl: int = 3600 * 24 * 7,  # 7 days
        file_cache_dir: str = "./.cache"
    ):
        """
        Initialize the cache manager.
        
        Args:
            redis_url: Redis connection URL
            default_ttl: Default TTL in seconds
            file_cache_dir: Directory for file-based fallback cache
        """
        self.default_ttl = default_ttl
        self.redis_url = redis_url
        self.file_cache_dir = Path(file_cache_dir)
        self._redis_client = None
        self._redis_available = False
        
        # Create file cache directory
        self.file_cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Try to connect to Redis
        self._init_redis()
    
    def _init_redis(self):
        """Initialize Redis connection."""
        try:
            import redis
            self._redis_client = redis.from_url(
                self.redis_url,
                decode_responses=False,  # We handle binary data
                socket_connect_timeout=5,
                socket_timeout=5
            )
            # Test connection
            self._redis_client.ping()
            self._redis_available = True
        except Exception:
            self._redis_available = False
            self._redis_client = None
    
    def _get_file_cache_path(self, key: str) -> Path:
        """Get file cache path for a key."""
        key_hash = hashlib.sha256(key.encode()).hexdigest()
        return self.file_cache_dir / f"{key_hash}.cache"
    
    def _serialize(self, value: Any) -> bytes:
        """Serialize a value for caching."""
        try:
            # Try JSON first for simple types
            return json.dumps(value).encode('utf-8')
        except (TypeError, ValueError):
            # Fall back to pickle for complex types
            return pickle.dumps(value)
    
    def _deserialize(self, data: bytes) -> Any:
        """Deserialize a cached value."""
        try:
            # Try JSON first
            return json.loads(data.decode('utf-8'))
        except (UnicodeDecodeError, json.JSONDecodeError):
            # Fall back to pickle
            return pickle.loads(data)
    
    # ==================== Generic Cache Operations ====================
    
    def get(self, key: str) -> Optional[Any]:
        """
        Get a value from cache.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if not found
        """
        if self._redis_available:
            try:
                data = self._redis_client.get(key)
                if data is not None:
                    return self._deserialize(data)
            except Exception:
                pass
        
        # Fall back to file cache
        file_path = self._get_file_cache_path(key)
        if file_path.exists():
            try:
                with open(file_path, 'rb') as f:
                    return self._deserialize(f.read())
            except Exception:
                pass
        
        return None
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """
        Set a value in cache.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: TTL in seconds (uses default if not specified)
            
        Returns:
            True if cached successfully
        """
        ttl = ttl or self.default_ttl
        serialized = self._serialize(value)
        
        if self._redis_available:
            try:
                self._redis_client.setex(key, ttl, serialized)
                return True
            except Exception:
                pass
        
        # Fall back to file cache
        file_path = self._get_file_cache_path(key)
        try:
            with open(file_path, 'wb') as f:
                f.write(serialized)
            return True
        except Exception:
            return False
    
    def delete(self, key: str) -> bool:
        """
        Delete a value from cache.
        
        Args:
            key: Cache key
            
        Returns:
            True if deleted successfully
        """
        if self._redis_available:
            try:
                self._redis_client.delete(key)
            except Exception:
                pass
        
        # Also delete from file cache
        file_path = self._get_file_cache_path(key)
        if file_path.exists():
            try:
                file_path.unlink()
            except Exception:
                pass
        
        return True
    
    def exists(self, key: str) -> bool:
        """
        Check if a key exists in cache.
        
        Args:
            key: Cache key
            
        Returns:
            True if key exists
        """
        if self._redis_available:
            try:
                return bool(self._redis_client.exists(key))
            except Exception:
                pass
        
        # Fall back to file cache
        return self._get_file_cache_path(key).exists()
    
    # ==================== Parsed Code Caching ====================
    
    def get_parsed_code(self, file_hash: str) -> Optional[Dict[str, Any]]:
        """
        Get cached parsed code result.
        
        Args:
            file_hash: Hash of the file content
            
        Returns:
            Parsed code dictionary or None
        """
        key = f"parsed:{file_hash}"
        return self.get(key)
    
    def set_parsed_code(
        self,
        file_hash: str,
        parsed_result: Dict[str, Any],
        ttl: Optional[int] = None
    ) -> bool:
        """
        Cache parsed code result.
        
        Args:
            file_hash: Hash of the file content
            parsed_result: Parsed code dictionary
            ttl: TTL in seconds
            
        Returns:
            True if cached successfully
        """
        key = f"parsed:{file_hash}"
        return self.set(key, parsed_result, ttl)
    
    # ==================== Similarity Result Caching ====================
    
    def get_similarity_result(
        self,
        file_hash_a: str,
        file_hash_b: str,
        algorithm: str = "combined"
    ) -> Optional[Dict[str, Any]]:
        """
        Get cached similarity result between two files.
        
        Args:
            file_hash_a: Hash of first file
            file_hash_b: Hash of second file
            algorithm: Algorithm used for comparison
            
        Returns:
            Similarity result dictionary or None
        """
        # Ensure consistent ordering of file hashes
        sorted_hashes = sorted([file_hash_a, file_hash_b])
        key = f"similarity:{sorted_hashes[0]}:{sorted_hashes[1]}:{algorithm}"
        return self.get(key)
    
    def set_similarity_result(
        self,
        file_hash_a: str,
        file_hash_b: str,
        result: Dict[str, Any],
        algorithm: str = "combined",
        ttl: Optional[int] = None
    ) -> bool:
        """
        Cache similarity result between two files.
        
        Args:
            file_hash_a: Hash of first file
            file_hash_b: Hash of second file
            result: Similarity result dictionary
            algorithm: Algorithm used for comparison
            ttl: TTL in seconds
            
        Returns:
            True if cached successfully
        """
        sorted_hashes = sorted([file_hash_a, file_hash_b])
        key = f"similarity:{sorted_hashes[0]}:{sorted_hashes[1]}:{algorithm}"
        return self.set(key, result, ttl)
    
    # ==================== Batch Comparison Caching ====================
    
    def get_batch_result(self, batch_hash: str) -> Optional[Dict[str, Any]]:
        """
        Get cached batch comparison result.
        
        Args:
            batch_hash: Hash of the batch (based on file set)
            
        Returns:
            Batch result dictionary or None
        """
        key = f"batch:{batch_hash}"
        return self.get(key)
    
    def set_batch_result(
        self,
        batch_hash: str,
        result: Dict[str, Any],
        ttl: Optional[int] = None
    ) -> bool:
        """
        Cache batch comparison result.
        
        Args:
            batch_hash: Hash of the batch
            result: Batch result dictionary
            ttl: TTL in seconds
            
        Returns:
            True if cached successfully
        """
        key = f"batch:{batch_hash}"
        return self.set(key, result, ttl)
    
    # ==================== Fingerprint Caching ====================
    
    def get_fingerprint(self, file_hash: str) -> Optional[List[str]]:
        """
        Get cached fingerprint for a file.
        
        Args:
            file_hash: Hash of the file content
            
        Returns:
            List of fingerprint hashes or None
        """
        key = f"fingerprint:{file_hash}"
        return self.get(key)
    
    def set_fingerprint(
        self,
        file_hash: str,
        fingerprint: List[str],
        ttl: Optional[int] = None
    ) -> bool:
        """
        Cache fingerprint for a file.
        
        Args:
            file_hash: Hash of the file content
            fingerprint: List of fingerprint hashes
            ttl: TTL in seconds
            
        Returns:
            True if cached successfully
        """
        key = f"fingerprint:{file_hash}"
        return self.set(key, fingerprint, ttl)
    
    # ==================== Cache Statistics ====================
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with cache statistics
        """
        stats = {
            'redis_available': self._redis_available,
            'backend': 'redis' if self._redis_available else 'file',
            'file_cache_size': 0,
            'file_cache_count': 0
        }
        
        if self._redis_available:
            try:
                info = self._redis_client.info('memory')
                stats['redis_memory_used'] = info.get('used_memory_human', 'N/A')
                stats['redis_connected_clients'] = info.get('connected_clients', 0)
            except Exception:
                pass
        
        # Calculate file cache stats
        if self.file_cache_dir.exists():
            cache_files = list(self.file_cache_dir.glob("*.cache"))
            stats['file_cache_count'] = len(cache_files)
            stats['file_cache_size'] = sum(
                f.stat().st_size for f in cache_files
            )
        
        return stats
    
    def clear_file_cache(self) -> int:
        """
        Clear the file-based cache.
        
        Returns:
            Number of files deleted
        """
        count = 0
        if self.file_cache_dir.exists():
            for cache_file in self.file_cache_dir.glob("*.cache"):
                try:
                    cache_file.unlink()
                    count += 1
                except Exception:
                    pass
        return count
    
    def clear_all(self) -> bool:
        """
        Clear all caches (Redis and file).
        
        Returns:
            True if successful
        """
        # Clear Redis cache
        if self._redis_available:
            try:
                self._redis_client.flushdb()
            except Exception:
                pass
        
        # Clear file cache
        self.clear_file_cache()
        
        return True


class SimilarityCache:
    """
    Specialized cache for similarity comparisons.
    
    Optimized for caching pairwise similarity computations
    and avoiding redundant comparisons.
    """
    
    def __init__(self, cache_manager: CacheManager):
        """
        Initialize the similarity cache.
        
        Args:
            cache_manager: CacheManager instance
        """
        self.cache = cache_manager
    
    def generate_file_hash(self, content: bytes) -> str:
        """
        Generate a content hash for caching.
        
        Args:
            content: File content bytes
            
        Returns:
            SHA256 hash of content
        """
        return hashlib.sha256(content).hexdigest()
    
    def generate_batch_hash(self, file_hashes: List[str]) -> str:
        """
        Generate a batch hash from a list of file hashes.
        
        Args:
            file_hashes: List of file content hashes
            
        Returns:
            Combined hash of all file hashes
        """
        sorted_hashes = sorted(file_hashes)
        combined = '|'.join(sorted_hashes)
        return hashlib.sha256(combined.encode()).hexdigest()
    
    def get_or_compute_similarity(
        self,
        parsed_a: Dict[str, Any],
        parsed_b: Dict[str, Any],
        compute_fn: callable,
        algorithms: List[str] = None
    ) -> Dict[str, Any]:
        """
        Get cached similarity result or compute it.
        
        Args:
            parsed_a: Parsed code for file A
            parsed_b: Parsed code for file B
            compute_fn: Function to compute similarity if not cached
            algorithms: List of algorithms to use
            
        Returns:
            Similarity result dictionary
        """
        hash_a = parsed_a.get('hash') or self.generate_file_hash(
            str(parsed_a).encode()
        )
        hash_b = parsed_b.get('hash') or self.generate_file_hash(
            str(parsed_b).encode()
        )
        
        algorithm_key = '+'.join(algorithms) if algorithms else 'combined'
        
        # Try to get from cache
        cached_result = self.cache.get_similarity_result(hash_a, hash_b, algorithm_key)
        
        if cached_result is not None:
            cached_result['from_cache'] = True
            return cached_result
        
        # Compute similarity
        result = compute_fn(parsed_a, parsed_b, algorithms)
        result['from_cache'] = False
        
        # Cache the result
        self.cache.set_similarity_result(hash_a, hash_b, result, algorithm_key)
        
        return result
    
    def invalidate_file(self, file_hash: str) -> int:
        """
        Invalidate all cached comparisons involving a file.
        
        Note: This only works with Redis. For file cache,
        individual entries need to be invalidated manually.
        
        Args:
            file_hash: Hash of the file to invalidate
            
        Returns:
            Number of keys invalidated
        """
        if not self.cache._redis_available:
            return 0
        
        try:
            pattern = f"*similarity*{file_hash}*"
            keys = self.cache._redis_client.keys(pattern)
            if keys:
                return self.cache._redis_client.delete(*keys)
        except Exception:
            pass
        
        return 0


# Global cache instance
_cache_instance: Optional[CacheManager] = None


def get_cache() -> CacheManager:
    """
    Get the global cache instance.
    
    Returns:
        CacheManager instance
    """
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = CacheManager()
    return _cache_instance


def init_cache(
    redis_url: str = "redis://localhost:6379/0",
    default_ttl: int = 3600 * 24 * 7
) -> CacheManager:
    """
    Initialize the global cache instance.
    
    Args:
        redis_url: Redis connection URL
        default_ttl: Default TTL in seconds
        
    Returns:
        CacheManager instance
    """
    global _cache_instance
    _cache_instance = CacheManager(redis_url=redis_url, default_ttl=default_ttl)
    return _cache_instance

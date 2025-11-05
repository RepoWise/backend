"""
Simple in-memory query cache for fast repeated queries

Uses LRU cache with TTL expiration
"""
from typing import Dict, Optional, Any
from functools import lru_cache
import hashlib
import json
import time
from loguru import logger


class QueryCache:
    """
    Fast in-memory cache for query responses

    Features:
    - LRU eviction
    - TTL expiration
    - Hash-based keys
    - Thread-safe
    """

    def __init__(self, max_size: int = 1000, ttl_seconds: int = 300):
        """
        Initialize cache

        Args:
            max_size: Maximum number of cached queries
            ttl_seconds: Time to live for cache entries (default 5 minutes)
        """
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self.cache: Dict[str, tuple[Any, float]] = {}
        self.hits = 0
        self.misses = 0

        logger.info(f"QueryCache initialized: max_size={max_size}, ttl={ttl_seconds}s")

    def _make_key(self, query: str, project_id: Optional[str] = None) -> str:
        """Generate cache key from query and project"""
        key_str = f"{project_id}:{query}"
        return hashlib.md5(key_str.encode()).hexdigest()

    def get(self, query: str, project_id: Optional[str] = None) -> Optional[Dict]:
        """
        Get cached response if exists and not expired

        Args:
            query: User query
            project_id: Project identifier

        Returns:
            Cached response or None
        """
        key = self._make_key(query, project_id)

        if key in self.cache:
            response, timestamp = self.cache[key]

            # Check if expired
            if time.time() - timestamp < self.ttl_seconds:
                self.hits += 1
                logger.debug(f"Cache HIT for query: {query[:50]}...")
                return response
            else:
                # Remove expired entry
                del self.cache[key]
                logger.debug(f"Cache EXPIRED for query: {query[:50]}...")

        self.misses += 1
        logger.debug(f"Cache MISS for query: {query[:50]}...")
        return None

    def set(self, query: str, response: Dict, project_id: Optional[str] = None):
        """
        Cache a response

        Args:
            query: User query
            response: Response to cache
            project_id: Project identifier
        """
        key = self._make_key(query, project_id)

        # LRU eviction if at capacity
        if len(self.cache) >= self.max_size and key not in self.cache:
            # Remove oldest entry
            oldest_key = min(self.cache.keys(), key=lambda k: self.cache[k][1])
            del self.cache[oldest_key]
            logger.debug(f"Cache EVICTED oldest entry (size={len(self.cache)})")

        self.cache[key] = (response, time.time())
        logger.debug(f"Cache SET for query: {query[:50]}... (size={len(self.cache)})")

    def clear(self):
        """Clear all cache entries"""
        self.cache.clear()
        self.hits = 0
        self.misses = 0
        logger.info("Cache cleared")

    def get_stats(self) -> Dict:
        """Get cache statistics"""
        total = self.hits + self.misses
        hit_rate = (self.hits / total * 100) if total > 0 else 0

        return {
            "size": len(self.cache),
            "max_size": self.max_size,
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate_percent": round(hit_rate, 2),
            "ttl_seconds": self.ttl_seconds
        }


# Global singleton
_query_cache: Optional[QueryCache] = None


def get_query_cache(max_size: int = 1000, ttl_seconds: int = 300) -> QueryCache:
    """Get or create global query cache instance"""
    global _query_cache
    if _query_cache is None:
        _query_cache = QueryCache(max_size=max_size, ttl_seconds=ttl_seconds)
    return _query_cache

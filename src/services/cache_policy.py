"""Enhanced caching policies with adaptive TTL and warmup strategies."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, Optional, TypeVar

from functools import wraps


class CacheStrategy(Enum):
    """Cache invalidation strategies."""
    TTL = "ttl"  # Time-to-live
    LRU = "lru"  # Least recently used
    LFU = "lfu"  # Least frequently used
    ADAPTIVE = "adaptive"  # Adaptive TTL based on access patterns


@dataclass
class CacheEntry:
    """Cache entry with metadata."""

    key: str
    value: Any
    created_at: float
    accessed_at: float
    access_count: int = 0
    ttl_seconds: float = 300.0
    hit_rate: float = 0.0

    def is_expired(self, current_time: float) -> bool:
        """Check if entry is expired."""
        age = current_time - self.created_at
        return age > self.ttl_seconds

    def touch(self, current_time: float) -> None:
        """Update access metadata."""
        self.accessed_at = current_time
        self.access_count += 1


@dataclass
class CachePolicyConfig:
    """Configuration for cache behavior."""

    # TTL settings
    default_ttl_seconds: float = 300.0
    min_ttl_seconds: float = 10.0
    max_ttl_seconds: float = 3600.0

    # Adaptive TTL settings
    enable_adaptive_ttl: bool = True
    ttl_multiplier_on_hit: float = 1.2  # Increase TTL on cache hits
    ttl_multiplier_on_miss: float = 0.8  # Decrease TTL on cache misses

    # Size limits
    max_entries: int = 1000
    eviction_ratio: float = 0.2  # Evict 20% when full

    # Warmup
    enable_warmup: bool = True
    warmup_keys: list[str] = field(default_factory=list)

    # Staleness
    allow_stale_on_error: bool = True
    stale_ttl_multiplier: float = 2.0


class EnhancedCache:
    """Enhanced cache with adaptive TTL and eviction strategies."""

    def __init__(self, config: Optional[CachePolicyConfig] = None) -> None:
        """Initialize enhanced cache.

        Args:
            config: Cache policy configuration
        """
        self.config = config or CachePolicyConfig()
        self._cache: Dict[str, CacheEntry] = {}
        self._hits = 0
        self._misses = 0
        self._evictions = 0

    def get(self, key: str, current_time: Optional[float] = None) -> Optional[Any]:
        """Get value from cache.

        Args:
            key: Cache key
            current_time: Current timestamp (uses time.time() if not provided)

        Returns:
            Cached value or None if not found/expired
        """
        if current_time is None:
            current_time = time.time()

        entry = self._cache.get(key)

        if entry is None:
            self._misses += 1
            return None

        if entry.is_expired(current_time):
            del self._cache[key]
            self._misses += 1
            return None

        # Update access metadata
        entry.touch(current_time)
        self._hits += 1

        # Adaptive TTL: increase on hit
        if self.config.enable_adaptive_ttl:
            new_ttl = min(
                entry.ttl_seconds * self.config.ttl_multiplier_on_hit,
                self.config.max_ttl_seconds,
            )
            entry.ttl_seconds = new_ttl

        return entry.value

    def set(
        self,
        key: str,
        value: Any,
        ttl_seconds: Optional[float] = None,
        current_time: Optional[float] = None,
    ) -> None:
        """Set value in cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl_seconds: TTL in seconds (uses default if not provided)
            current_time: Current timestamp
        """
        if current_time is None:
            current_time = time.time()

        if ttl_seconds is None:
            ttl_seconds = self.config.default_ttl_seconds

        # Evict if at capacity
        if len(self._cache) >= self.config.max_entries:
            self._evict(current_time)

        entry = CacheEntry(
            key=key,
            value=value,
            created_at=current_time,
            accessed_at=current_time,
            ttl_seconds=ttl_seconds,
        )

        self._cache[key] = entry

    def get_stale(
        self,
        key: str,
        current_time: Optional[float] = None,
    ) -> Optional[Any]:
        """Get value even if expired (for stale-while-revalidate pattern).

        Args:
            key: Cache key
            current_time: Current timestamp

        Returns:
            Cached value or None if not found
        """
        if current_time is None:
            current_time = time.time()

        entry = self._cache.get(key)
        if entry is None:
            return None

        # Allow stale data up to stale_ttl_multiplier * original TTL
        max_stale_age = entry.ttl_seconds * self.config.stale_ttl_multiplier
        age = current_time - entry.created_at

        if age > max_stale_age:
            return None

        return entry.value

    def invalidate(self, key: str) -> None:
        """Invalidate cache entry.

        Args:
            key: Cache key to invalidate
        """
        if key in self._cache:
            del self._cache[key]

    def clear(self) -> None:
        """Clear all cache entries."""
        self._cache.clear()
        self._hits = 0
        self._misses = 0
        self._evictions = 0

    def _evict(self, current_time: float) -> None:
        """Evict entries based on strategy."""
        entries_to_evict = int(self.config.max_entries * self.config.eviction_ratio)

        if entries_to_evict == 0:
            entries_to_evict = 1

        # Evict least recently used
        sorted_entries = sorted(
            self._cache.values(),
            key=lambda e: e.accessed_at,
        )

        for entry in sorted_entries[:entries_to_evict]:
            del self._cache[entry.key]
            self._evictions += 1

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dictionary with cache stats
        """
        total_requests = self._hits + self._misses
        hit_rate = self._hits / total_requests if total_requests > 0 else 0.0

        return {
            "size": len(self._cache),
            "max_size": self.config.max_entries,
            "hits": self._hits,
            "misses": self._misses,
            "evictions": self._evictions,
            "hit_rate": hit_rate,
            "total_requests": total_requests,
        }

    def warmup(self, warmup_func: Callable[[str], Any]) -> None:
        """Warmup cache with predefined keys.

        Args:
            warmup_func: Function to fetch values for warmup keys
        """
        if not self.config.enable_warmup:
            return

        for key in self.config.warmup_keys:
            try:
                value = warmup_func(key)
                self.set(key, value)
            except Exception as exc:
                print(f"Cache warmup failed for key '{key}': {exc}")


# Global cache instance
_global_cache = EnhancedCache()


def get_global_cache() -> EnhancedCache:
    """Get global cache instance.

    Returns:
        Global cache instance
    """
    return _global_cache


T = TypeVar("T")


def cached(
    ttl_seconds: Optional[float] = None,
    key_func: Optional[Callable[..., str]] = None,
    cache_instance: Optional[EnhancedCache] = None,
    allow_stale_on_error: bool = True,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator to cache function results.

    Args:
        ttl_seconds: TTL for cache entries
        key_func: Function to generate cache key from args
        cache_instance: Cache instance (uses global if not provided)
        allow_stale_on_error: Return stale data on error

    Returns:
        Decorated function

    Example:
        @cached(ttl_seconds=60, key_func=lambda symbol: f"price:{symbol}")
        def fetch_price(symbol: str):
            return api.get_price(symbol)
    """
    cache = cache_instance or get_global_cache()

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            # Generate cache key
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                # Default: use function name and args
                cache_key = f"{func.__name__}:{args}:{kwargs}"

            # Try to get from cache
            cached_value = cache.get(cache_key)
            if cached_value is not None:
                return cached_value

            # Fetch fresh value
            try:
                value = func(*args, **kwargs)
                cache.set(cache_key, value, ttl_seconds)
                return value

            except Exception as exc:
                # Try stale data on error
                if allow_stale_on_error:
                    stale_value = cache.get_stale(cache_key)
                    if stale_value is not None:
                        print(f"Using stale cache for {cache_key} due to error: {exc}")
                        return stale_value

                raise exc

        return wrapper

    return decorator


def cache_aside(
    cache_instance: Optional[EnhancedCache] = None,
) -> Callable:
    """Cache-aside pattern decorator (lazy loading).

    Args:
        cache_instance: Cache instance to use

    Returns:
        Decorated function
    """

    def decorator(func: Callable) -> Callable:
        cache = cache_instance or get_global_cache()

        @wraps(func)
        def wrapper(key: str, *args, **kwargs) -> Any:
            # Try cache first
            cached_value = cache.get(key)
            if cached_value is not None:
                return cached_value

            # Fetch and cache
            value = func(key, *args, **kwargs)
            cache.set(key, value)
            return value

        return wrapper

    return decorator

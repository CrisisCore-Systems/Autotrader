"""
Price data caching layer with TTL and LRU eviction.

Reduces API calls by caching recent quotes and bars.
Thread-safe for concurrent monitoring (future-proofed).
"""

from typing import Dict, Optional, TYPE_CHECKING, Any
from datetime import datetime, timedelta
from threading import Lock
from dataclasses import dataclass

if TYPE_CHECKING:
    from .price_provider import Quote, Bar


@dataclass
class CacheEntry:
    """Cache entry with TTL tracking."""
    data: Any
    timestamp: datetime
    
    def is_expired(self, ttl_seconds: int) -> bool:
        """Check if entry has expired."""
        age = (datetime.utcnow() - self.timestamp).total_seconds()
        return age > ttl_seconds


class PriceCache:
    """
    Thread-safe cache for price quotes with TTL and LRU eviction.
    
    Attributes:
        ttl_seconds: Time-to-live for cache entries
        max_size: Maximum number of entries (LRU eviction)
        _cache: Internal cache storage
        _lock: Thread lock for concurrent access
    """
    
    def __init__(self, ttl_seconds: int = 60, max_size: int = 1000):
        """
        Initialize price cache.
        
        Args:
            ttl_seconds: Cache TTL in seconds (default: 60s)
            max_size: Max cache entries before LRU eviction (default: 1000)
        """
        self.ttl_seconds = ttl_seconds
        self.max_size = max_size
        self._cache: Dict[str, CacheEntry] = {}
        self._lock = Lock()
    
    def get_quote(self, ticker: str) -> Optional['Quote']:
        """
        Get cached quote if available and not expired.
        
        Args:
            ticker: Stock ticker symbol
            
        Returns:
            Quote object if cached and fresh, None otherwise
        """
        with self._lock:
            entry = self._cache.get(f"quote:{ticker}")
            
            if not entry:
                return None
            
            if entry.is_expired(self.ttl_seconds):
                # Expired, remove from cache
                del self._cache[f"quote:{ticker}"]
                return None
            
            return entry.data
    
    def set_quote(self, ticker: str, quote: 'Quote') -> None:
        """
        Cache a quote.
        
        Args:
            ticker: Stock ticker symbol
            quote: Quote object to cache
        """
        with self._lock:
            # LRU eviction if cache full
            if len(self._cache) >= self.max_size:
                self._evict_oldest()
            
            key = f"quote:{ticker}"
            self._cache[key] = CacheEntry(
                data=quote,
                timestamp=datetime.utcnow()
            )
    
    def get_bars(self, ticker: str, timeframe: str = '1Min') -> Optional[list]:
        """
        Get cached bars if available and not expired.
        
        Args:
            ticker: Stock ticker symbol
            timeframe: Bar timeframe
            
        Returns:
            List of Bar objects if cached and fresh, None otherwise
        """
        with self._lock:
            entry = self._cache.get(f"bars:{ticker}:{timeframe}")
            
            if not entry:
                return None
            
            if entry.is_expired(self.ttl_seconds):
                del self._cache[f"bars:{ticker}:{timeframe}"]
                return None
            
            return entry.data
    
    def set_bars(self, ticker: str, bars: list, timeframe: str = '1Min') -> None:
        """
        Cache bars.
        
        Args:
            ticker: Stock ticker symbol
            bars: List of Bar objects
            timeframe: Bar timeframe
        """
        with self._lock:
            if len(self._cache) >= self.max_size:
                self._evict_oldest()
            
            key = f"bars:{ticker}:{timeframe}"
            self._cache[key] = CacheEntry(
                data=bars,
                timestamp=datetime.utcnow()
            )
    
    def clear(self) -> None:
        """Clear all cache entries."""
        with self._lock:
            self._cache.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with size, hit_rate, etc.
        """
        with self._lock:
            total_entries = len(self._cache)
            expired_count = sum(
                1 for entry in self._cache.values()
                if entry.is_expired(self.ttl_seconds)
            )
            
            return {
                'total_entries': total_entries,
                'expired_entries': expired_count,
                'fresh_entries': total_entries - expired_count,
                'utilization_pct': (total_entries / self.max_size) * 100
            }
    
    def _evict_oldest(self) -> None:
        """Evict oldest entry (LRU policy)."""
        if not self._cache:
            return
        
        # Find oldest entry
        oldest_key = min(
            self._cache.keys(),
            key=lambda k: self._cache[k].timestamp
        )
        
        del self._cache[oldest_key]

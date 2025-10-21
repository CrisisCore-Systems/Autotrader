"""
VIX Provider: Fetch real-time VIX data for volatility adjustments.

The CBOE Volatility Index (VIX) measures market volatility expectations.
Used by AdjustmentCalculator to dynamically adapt exit targets.

Providers:
- AlpacaVIXProvider: Fetches VIX from Alpaca Markets
- MockVIXProvider: Returns fixed VIX for testing

Features:
- 5-minute caching to reduce API calls
- Error handling with fallback to default VIX (20.0)
- Logging for monitoring and debugging
"""

from abc import ABC, abstractmethod
from typing import Optional
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import logging

try:
    from alpaca.data.requests import StockLatestQuoteRequest, StockSnapshotRequest, StockLatestTradeRequest
    ALPACA_AVAILABLE = True
except ImportError:
    ALPACA_AVAILABLE = False

logger = logging.getLogger(__name__)

EASTERN = ZoneInfo("America/New_York")

# Default VIX when fetch fails (neutral volatility)
DEFAULT_VIX = 20.0

# Cache TTL (5 minutes)
CACHE_TTL_SECONDS = 300


class VIXProvider(ABC):
    """
    Abstract base class for VIX data providers.
    
    Implementations must provide get_vix() method that returns
    current VIX value or None on error.
    """
    
    @abstractmethod
    def get_vix(self) -> Optional[float]:
        """
        Fetch current VIX value.
        
        Returns:
            VIX value as float, or None if fetch fails
        """
        pass


class AlpacaVIXProvider(VIXProvider):
    """
    Fetch VIX from Alpaca Markets API.
    
    VIX symbol: ^VIX (Yahoo Finance style) or VIX (direct)
    Uses Alpaca's get_latest_quote() or get_snapshot() methods.
    
    Features:
    - 5-minute caching to reduce API calls
    - Graceful error handling (returns None on failure)
    - Falls back to default VIX if fetch fails
    
    Usage:
        >>> from alpaca.data.historical import StockHistoricalDataClient
        >>> client = StockHistoricalDataClient(api_key, secret_key)
        >>> provider = AlpacaVIXProvider(client)
        >>> vix = provider.get_vix()
        >>> print(f"Current VIX: {vix}")
    """
    
    def __init__(self, alpaca_client, symbol: str = "VIX", cache_ttl_seconds: int = CACHE_TTL_SECONDS):
        """
        Initialize Alpaca VIX provider.
        
        Args:
            alpaca_client: Alpaca StockHistoricalDataClient or similar
            symbol: VIX symbol (default "VIX", may need "^VIX" depending on provider)
            cache_ttl_seconds: Cache time-to-live in seconds (default 300 = 5 min)
        """
        self.client = alpaca_client
        self.symbol = symbol
        self.cache_ttl = cache_ttl_seconds
        
        # Cache
        self._cached_vix: Optional[float] = None
        self._cache_timestamp: Optional[datetime] = None
    
    def get_vix(self) -> Optional[float]:
        """
        Fetch current VIX with caching.
        
        Returns:
            VIX value, or None if fetch fails
        """
        # Check cache
        if self._is_cache_valid():
            logger.debug(f"VIX cache hit: {self._cached_vix:.2f}")
            return self._cached_vix
        
        # Fetch fresh VIX
        try:
            vix = self._fetch_vix()
            
            if vix is not None:
                # Update cache
                self._cached_vix = vix
                self._cache_timestamp = datetime.now(EASTERN)
                logger.info(f"VIX fetched: {vix:.2f}")
                return vix
            else:
                logger.warning("VIX fetch returned None")
                return None
                
        except Exception as e:
            logger.error(f"VIX fetch failed: {e}")
            return None
    
    def _fetch_vix(self) -> Optional[float]:
        """
        Fetch VIX from Alpaca API.
        
        Returns:
            VIX value or None on error
        """
        if not ALPACA_AVAILABLE:
            logger.error("Alpaca SDK not available")
            return None
            
        try:
            # Try get_latest_quote (preferred method)
            if hasattr(self.client, 'get_latest_quote'):
                request = StockLatestQuoteRequest(symbol_or_symbols=self.symbol)
                quote_data = self.client.get_latest_quote(request)
                
                # Extract VIX from quote
                if self.symbol in quote_data:
                    quote = quote_data[self.symbol]
                    # VIX is typically the last price or mid price
                    vix = float(quote.ask_price + quote.bid_price) / 2.0
                    return vix
            
            # Try get_snapshot (alternative method)
            elif hasattr(self.client, 'get_snapshot'):
                request = StockSnapshotRequest(symbol_or_symbols=self.symbol)
                snapshot_data = self.client.get_snapshot(request)
                
                if self.symbol in snapshot_data:
                    snapshot = snapshot_data[self.symbol]
                    if snapshot.latest_quote:
                        vix = float(snapshot.latest_quote.ask_price + snapshot.latest_quote.bid_price) / 2.0
                        return vix
            
            # Try direct attribute access (some Alpaca versions)
            elif hasattr(self.client, 'get_latest_trade'):
                request = StockLatestTradeRequest(symbol_or_symbols=self.symbol)
                trade_data = self.client.get_latest_trade(request)
                
                if self.symbol in trade_data:
                    trade = trade_data[self.symbol]
                    vix = float(trade.price)
                    return vix
            
            logger.warning(f"No suitable method found to fetch VIX from Alpaca client")
            return None
            
        except Exception as e:
            logger.error(f"Error fetching VIX from Alpaca: {e}")
            return None
    
    def _is_cache_valid(self) -> bool:
        """Check if cached VIX is still valid."""
        if self._cached_vix is None or self._cache_timestamp is None:
            return False
        
        age = (datetime.now(EASTERN) - self._cache_timestamp).total_seconds()
        return age < self.cache_ttl
    
    def clear_cache(self) -> None:
        """Clear cached VIX (force fresh fetch on next get_vix())."""
        self._cached_vix = None
        self._cache_timestamp = None
        logger.debug("VIX cache cleared")


class MockVIXProvider(VIXProvider):
    """
    Mock VIX provider for testing.
    
    Returns fixed VIX value (configurable).
    
    Usage:
        >>> provider = MockVIXProvider(vix_value=25.0)
        >>> vix = provider.get_vix()
        >>> assert vix == 25.0
    """
    
    def __init__(self, vix_value: float = DEFAULT_VIX):
        """
        Initialize mock provider.
        
        Args:
            vix_value: Fixed VIX value to return (default 20.0)
        """
        self.vix_value = vix_value
    
    def get_vix(self) -> Optional[float]:
        """Return fixed VIX value."""
        return self.vix_value
    
    def set_vix(self, vix_value: float) -> None:
        """Update VIX value."""
        self.vix_value = vix_value


class FallbackVIXProvider(VIXProvider):
    """
    VIX provider with fallback logic.
    
    Tries primary provider first, falls back to default VIX on error.
    
    Usage:
        >>> primary = AlpacaVIXProvider(client)
        >>> provider = FallbackVIXProvider(primary, default_vix=20.0)
        >>> vix = provider.get_vix()  # Always returns a value
    """
    
    def __init__(self, primary_provider: VIXProvider, default_vix: float = DEFAULT_VIX):
        """
        Initialize fallback provider.
        
        Args:
            primary_provider: Primary VIX provider to try first
            default_vix: Fallback VIX value if primary fails (default 20.0)
        """
        self.primary = primary_provider
        self.default_vix = default_vix
    
    def get_vix(self) -> float:
        """
        Get VIX with fallback.
        
        Returns:
            VIX value (never None - always returns default on failure)
        """
        try:
            vix = self.primary.get_vix()
            
            if vix is not None:
                return vix
            else:
                logger.warning(f"Primary VIX provider returned None, using default: {self.default_vix}")
                return self.default_vix
                
        except Exception as e:
            logger.error(f"Primary VIX provider failed: {e}, using default: {self.default_vix}")
            return self.default_vix

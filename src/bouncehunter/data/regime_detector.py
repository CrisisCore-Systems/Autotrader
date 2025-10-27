"""
Market Regime Detector: Detect bull/bear/sideways markets using SPY SMA crossover.

Uses SPY 20-day and 50-day simple moving averages to classify market regime:
- BULL: 20-day SMA > 50-day SMA (uptrend)
- BEAR: 20-day SMA < 50-day SMA (downtrend)  
- SIDEWAYS: SMAs within 0.5% of each other (consolidation)

Designed for daily pre-market updates to inform intraday exit adjustments.
"""

import logging
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from zoneinfo import ZoneInfo
from enum import Enum

logger = logging.getLogger(__name__)

EASTERN = ZoneInfo("America/New_York")


class MarketRegime(str, Enum):
    """Market regime classifications."""
    BULL = "BULL"
    BEAR = "BEAR"
    SIDEWAYS = "SIDEWAYS"


class RegimeDetector(ABC):
    """Abstract base class for regime detection."""
    
    @abstractmethod
    def detect_regime(self) -> MarketRegime:
        """
        Detect current market regime.
        
        Returns:
            MarketRegime classification
        """
        pass
    
    @abstractmethod
    def get_regime_details(self) -> Dict[str, Any]:
        """
        Get detailed regime information.
        
        Returns:
            Dictionary with regime details (SMAs, spread, etc.)
        """
        pass


class SPYRegimeDetector(RegimeDetector):
    """
    Detect market regime using SPY 20/50 SMA crossover.
    
    Uses SPY ETF as market proxy:
    - Calculates 20-day and 50-day simple moving averages
    - BULL: 20 SMA > 50 SMA + 0.5% (clear uptrend)
    - BEAR: 20 SMA < 50 SMA - 0.5% (clear downtrend)
    - SIDEWAYS: Within ±0.5% (consolidation/choppy)
    
    Features:
    - Daily caching (regime typically updated pre-market)
    - Fallback to SIDEWAYS on data errors
    - Detailed diagnostics for monitoring
    """
    
    def __init__(
        self,
        price_provider: Any,
        symbol: str = "SPY",
        short_window: int = 20,
        long_window: int = 50,
        sideways_threshold_pct: float = 0.5,
        cache_ttl_hours: int = 24
    ):
        """
        Initialize SPY regime detector.
        
        Args:
            price_provider: Provider with get_bars() method for historical data
            symbol: Symbol to use for regime detection (default: SPY)
            short_window: Short SMA period in days (default: 20)
            long_window: Long SMA period in days (default: 50)
            sideways_threshold_pct: Threshold % for sideways classification (default: 0.5)
            cache_ttl_hours: Cache validity in hours (default: 24)
        """
        self.price_provider = price_provider
        self.symbol = symbol
        self.short_window = short_window
        self.long_window = long_window
        self.sideways_threshold = sideways_threshold_pct / 100.0  # Convert to decimal
        self.cache_ttl_hours = cache_ttl_hours
        
        # Cache
        self._cached_regime: Optional[MarketRegime] = None
        self._cached_details: Optional[Dict[str, Any]] = None
        self._cache_timestamp: Optional[datetime] = None
        
        logger.info(
            f"SPY regime detector initialized: {short_window}/{long_window} SMA, "
            f"sideways threshold: {sideways_threshold_pct}%, cache TTL: {cache_ttl_hours}h"
        )
    
    def detect_regime(self) -> MarketRegime:
        """
        Detect current market regime using SPY SMA crossover.
        
        Returns:
            MarketRegime classification (BULL, BEAR, or SIDEWAYS)
        """
        # Check cache
        if self._is_cache_valid():
            logger.debug(f"Using cached regime: {self._cached_regime}")
            return self._cached_regime
        
        # Calculate fresh regime
        try:
            regime, details = self._calculate_regime()
            
            # Update cache
            self._cached_regime = regime
            self._cached_details = details
            self._cache_timestamp = datetime.now(EASTERN)
            
            logger.info(
                f"Regime detected: {regime.value} "
                f"(20 SMA: ${details['sma_20']:.2f}, 50 SMA: ${details['sma_50']:.2f}, "
                f"spread: {details['spread_pct']:.2f}%)"
            )
            
            return regime
            
        except Exception as e:
            logger.error(f"Failed to detect regime: {e}, defaulting to SIDEWAYS")
            # Return SIDEWAYS as safe fallback
            return MarketRegime.SIDEWAYS
    
    def get_regime_details(self) -> Dict[str, Any]:
        """
        Get detailed regime information including SMAs and spread.
        
        Returns:
            Dictionary with:
            - regime: Current regime classification
            - sma_20: 20-day SMA value
            - sma_50: 50-day SMA value
            - spread_pct: Percentage spread between SMAs
            - last_price: Most recent SPY price
            - calculated_at: Timestamp of calculation
        """
        # Ensure we have fresh regime
        if not self._is_cache_valid():
            self.detect_regime()
        
        return self._cached_details or {
            'regime': MarketRegime.SIDEWAYS.value,
            'sma_20': 0.0,
            'sma_50': 0.0,
            'spread_pct': 0.0,
            'last_price': 0.0,
            'calculated_at': None,
            'error': 'No data available'
        }
    
    def clear_cache(self) -> None:
        """Clear cached regime (force fresh calculation on next call)."""
        self._cached_regime = None
        self._cached_details = None
        self._cache_timestamp = None
        logger.debug("Regime cache cleared")
    
    def _calculate_regime(self) -> tuple[MarketRegime, Dict[str, Any]]:
        """
        Calculate regime from SPY price data.
        
        Returns:
            Tuple of (regime, details_dict)
            
        Raises:
            Exception: If data fetch or calculation fails
        """
        # Fetch historical bars (need long_window + buffer for SMA)
        end_date = datetime.now(EASTERN)
        start_date = end_date - timedelta(days=self.long_window + 10)  # Buffer for weekends/holidays
        
        bars = self.price_provider.get_bars(
            symbol=self.symbol,
            timeframe='1Day',
            start=start_date.isoformat(),
            end=end_date.isoformat()
        )
        
        if not bars or len(bars) < self.long_window:
            raise ValueError(
                f"Insufficient data: got {len(bars) if bars else 0} bars, "
                f"need {self.long_window}"
            )
        
        # Extract closing prices
        closes = [bar.close for bar in bars]
        
        # Calculate SMAs
        sma_20 = sum(closes[-self.short_window:]) / self.short_window
        sma_50 = sum(closes[-self.long_window:]) / self.long_window
        
        # Calculate spread
        spread_pct = ((sma_20 - sma_50) / sma_50) * 100.0
        
        # Classify regime
        if spread_pct > self.sideways_threshold * 100:
            regime = MarketRegime.BULL
        elif spread_pct < -self.sideways_threshold * 100:
            regime = MarketRegime.BEAR
        else:
            regime = MarketRegime.SIDEWAYS
        
        # Build details
        details = {
            'regime': regime.value,
            'sma_20': sma_20,
            'sma_50': sma_50,
            'spread_pct': spread_pct,
            'last_price': closes[-1],
            'calculated_at': datetime.now(EASTERN).isoformat(),
            'bars_used': len(bars)
        }
        
        return regime, details
    
    def _is_cache_valid(self) -> bool:
        """Check if cached regime is still valid."""
        if self._cached_regime is None or self._cache_timestamp is None:
            return False
        
        age = (datetime.now(EASTERN) - self._cache_timestamp).total_seconds()
        return age < (self.cache_ttl_hours * 3600)


class MockRegimeDetector(RegimeDetector):
    """
    Mock regime detector for testing.
    
    Returns fixed regime, useful for unit tests and development.
    """
    
    def __init__(self, regime: MarketRegime = MarketRegime.SIDEWAYS):
        """
        Initialize mock detector.
        
        Args:
            regime: Fixed regime to return (default: SIDEWAYS)
        """
        self.regime = regime
        logger.debug(f"Mock regime detector initialized: {regime.value}")
    
    def detect_regime(self) -> MarketRegime:
        """Return fixed regime."""
        return self.regime
    
    def get_regime_details(self) -> Dict[str, Any]:
        """Return mock details."""
        return {
            'regime': self.regime.value,
            'sma_20': 450.0,
            'sma_50': 450.0,
            'spread_pct': 0.0,
            'last_price': 450.0,
            'calculated_at': datetime.now(EASTERN).isoformat(),
            'mock': True
        }
    
    def set_regime(self, regime: MarketRegime) -> None:
        """Update mock regime."""
        self.regime = regime
        logger.debug(f"Mock regime updated to: {regime.value}")

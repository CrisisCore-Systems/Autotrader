"""
Yahoo Finance VIX Provider - Canadian Trading Compatible

Replaces Alpaca market data for VIX (Volatility Index) using Yahoo Finance.
Provides free, reliable VIX data without API credentials.

Requirements:
    - yfinance: pip install yfinance

Features:
    - No API keys required
    - Real-time VIX data from Yahoo Finance
    - Same interface as Alpaca VIX provider
    - Automatic volatility regime classification
"""

import yfinance as yf
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class VIXSnapshot:
    """VIX data snapshot matching expected interface."""
    value: float
    label: str  # "LOW" | "NORMAL" | "HIGH" | "EXTREME"
    timestamp: datetime
    source: str = "yahoo"


class YahooVIXProvider:
    """
    Yahoo Finance VIX data provider.
    
    Drop-in replacement for Alpaca VIX provider using free Yahoo Finance data.
    Provides real-time VIX values with automatic volatility regime classification.
    """
    
    def __init__(self, 
                 low_threshold: float = 15.0,
                 normal_threshold: float = 25.0,
                 high_threshold: float = 35.0):
        """Initialize VIX provider with thresholds.
        
        Args:
            low_threshold: Below this is LOW volatility (default: 15)
            normal_threshold: Below this is NORMAL volatility (default: 25)
            high_threshold: Below this is HIGH, above is EXTREME (default: 35)
        """
        self.low_threshold = low_threshold
        self.normal_threshold = normal_threshold
        self.high_threshold = high_threshold
        
        self.ticker = yf.Ticker("^VIX")
        logger.info(f"Yahoo VIX provider initialized (thresholds: LOW<{low_threshold}, NORMAL<{normal_threshold}, HIGH<{high_threshold})")
    
    def get_vix(self) -> float:
        """Get current VIX value (compatibility method).
        
        Returns:
            Current VIX value
        """
        snapshot = self.get()
        return snapshot.value
    
    def get(self) -> VIXSnapshot:
        """Get VIX snapshot with classification.
        
        Returns:
            VIXSnapshot with value, label, and timestamp
        """
        try:
            # Get most recent VIX data (1 day, 1-minute intervals)
            hist = self.ticker.history(period="1d", interval="1m")
            
            if hist.empty:
                logger.warning("No VIX data available, using fallback value")
                return self._fallback_snapshot()
            
            # Get most recent close price
            vix_value = float(hist["Close"].iloc[-1])
            timestamp = hist.index[-1].to_pydatetime() if hasattr(hist.index[-1], 'to_pydatetime') else datetime.now()
            
            # Classify volatility regime
            label = self._classify_volatility(vix_value)
            
            logger.debug(f"VIX retrieved: {vix_value:.2f} ({label})")
            
            return VIXSnapshot(
                value=vix_value,
                label=label,
                timestamp=timestamp,
                source="yahoo"
            )
        
        except Exception as e:
            logger.error(f"Failed to fetch VIX from Yahoo: {e}")
            return self._fallback_snapshot()
    
    def _classify_volatility(self, vix: float) -> str:
        """Classify VIX value into volatility regime.
        
        Args:
            vix: VIX value
            
        Returns:
            Volatility label: LOW, NORMAL, HIGH, or EXTREME
        """
        if vix < self.low_threshold:
            return "LOW"
        elif vix < self.normal_threshold:
            return "NORMAL"
        elif vix < self.high_threshold:
            return "HIGH"
        else:
            return "EXTREME"
    
    def _fallback_snapshot(self) -> VIXSnapshot:
        """Return fallback snapshot when data unavailable.
        
        Returns:
            Default VIXSnapshot with NORMAL regime
        """
        fallback_value = 20.0  # Historical average
        logger.warning(f"Using fallback VIX value: {fallback_value}")
        
        return VIXSnapshot(
            value=fallback_value,
            label="NORMAL",
            timestamp=datetime.now(),
            source="fallback"
        )
    
    def get_historical(self, period: str = "5d", interval: str = "1h") -> list:
        """Get historical VIX data (optional feature).
        
        Args:
            period: Time period (1d, 5d, 1mo, etc.)
            interval: Data interval (1m, 5m, 1h, etc.)
            
        Returns:
            List of historical VIX snapshots
        """
        try:
            hist = self.ticker.history(period=period, interval=interval)
            
            snapshots = []
            for idx, row in hist.iterrows():
                vix_value = float(row["Close"])
                timestamp = idx.to_pydatetime() if hasattr(idx, 'to_pydatetime') else datetime.now()
                
                snapshots.append(VIXSnapshot(
                    value=vix_value,
                    label=self._classify_volatility(vix_value),
                    timestamp=timestamp,
                    source="yahoo"
                ))
            
            return snapshots
        
        except Exception as e:
            logger.error(f"Failed to fetch historical VIX: {e}")
            return []
    
    def get_volatility_level(self, vix: Optional[float] = None) -> str:
        """Get volatility level for given VIX (or fetch current).
        
        Args:
            vix: VIX value (if None, fetches current)
            
        Returns:
            Volatility label: LOW, NORMAL, HIGH, or EXTREME
        """
        if vix is None:
            vix = self.get_vix()
        
        return self._classify_volatility(vix)
    
    def is_available(self) -> bool:
        """Check if VIX data is available.
        
        Returns:
            True if can fetch VIX data
        """
        try:
            hist = self.ticker.history(period="1d", interval="1m")
            return not hist.empty
        except Exception as e:
            logger.error(f"VIX availability check failed: {e}")
            return False


# Compatibility alias for existing code
class VIXProvider(YahooVIXProvider):
    """Alias for backwards compatibility."""
    pass


def create_vix_provider(provider_type: str = "yahoo", **kwargs) -> YahooVIXProvider:
    """Factory function for VIX providers.
    
    Args:
        provider_type: Provider type (currently only "yahoo" supported)
        **kwargs: Provider-specific arguments
        
    Returns:
        VIX provider instance
    """
    if provider_type.lower() == "yahoo":
        return YahooVIXProvider(**kwargs)
    else:
        raise ValueError(f"Unsupported VIX provider type: {provider_type}")

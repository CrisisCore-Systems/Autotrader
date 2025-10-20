"""
Market Regime Detector for PennyHunter

Determines if market conditions favor penny stock trading.
Pennies perform best in risk-on environments (SPY above 200MA, low VIX).

Author: BounceHunter Team
"""

import logging
from dataclasses import dataclass
from typing import Optional, Dict
from datetime import datetime
import yfinance as yf

logger = logging.getLogger(__name__)


@dataclass
class MarketRegime:
    """Market regime snapshot"""
    timestamp: datetime
    regime: str  # 'risk_on', 'risk_off', 'neutral'
    spy_price: float
    spy_ma200: float
    spy_above_ma: bool
    spy_day_change_pct: float
    vix_level: float
    vix_regime: str  # 'low', 'medium', 'high', 'extreme'
    allow_penny_trading: bool
    reason: str


class MarketRegimeDetector:
    """
    Detects market regime to filter penny stock trades.

    Rules:
    - RISK ON: SPY > 200MA, VIX < 20, SPY green day → ✅ Trade pennies
    - RISK OFF: SPY < 200MA, VIX > 30 → ❌ Skip pennies
    - NEUTRAL: Mixed signals → Trade with caution
    """

    def __init__(
        self,
        vix_low: float = 20.0,
        vix_medium: float = 30.0,
        vix_high: float = 40.0,
        require_spy_above_ma: bool = True,
        require_spy_green: bool = False,
        cache_minutes: int = 15
    ):
        """
        Initialize regime detector.

        Args:
            vix_low: VIX threshold for low volatility
            vix_medium: VIX threshold for medium volatility
            vix_high: VIX threshold for high volatility
            require_spy_above_ma: Require SPY > 200MA
            require_spy_green: Require SPY green day
            cache_minutes: Cache regime data for N minutes
        """
        self.vix_low = vix_low
        self.vix_medium = vix_medium
        self.vix_high = vix_high
        self.require_spy_above_ma = require_spy_above_ma
        self.require_spy_green = require_spy_green
        self.cache_minutes = cache_minutes

        self._cached_regime: Optional[MarketRegime] = None
        self._cache_time: Optional[datetime] = None

        logger.info(
            f"MarketRegimeDetector initialized: VIX thresholds {vix_low}/{vix_medium}/{vix_high}, "
            f"require_spy_above_ma={require_spy_above_ma}, require_spy_green={require_spy_green}"
        )

    def get_regime(self, force_refresh: bool = False) -> MarketRegime:
        """
        Get current market regime.

        Args:
            force_refresh: Bypass cache and fetch fresh data

        Returns:
            MarketRegime object with trading permission
        """
        # Check cache
        if not force_refresh and self._is_cache_valid():
            logger.debug("Using cached market regime")
            return self._cached_regime

        # Fetch fresh data
        logger.info("Fetching fresh market regime data...")
        regime = self._calculate_regime()

        # Update cache
        self._cached_regime = regime
        self._cache_time = datetime.now()

        return regime

    def _is_cache_valid(self) -> bool:
        """Check if cached regime is still valid"""
        if self._cached_regime is None or self._cache_time is None:
            return False

        age = datetime.now() - self._cache_time
        return age.total_seconds() < (self.cache_minutes * 60)

    def _calculate_regime(self) -> MarketRegime:
        """Calculate market regime from SPY and VIX data"""
        try:
            # Fetch SPY data (need 250 days for 200MA)
            spy = yf.Ticker("SPY")
            spy_hist = spy.history(period="1y")

            if len(spy_hist) < 200:
                logger.error("Insufficient SPY data for 200MA calculation")
                return self._neutral_regime("insufficient_data")

            # Calculate SPY metrics
            spy_price = spy_hist['Close'].iloc[-1]
            spy_ma200 = spy_hist['Close'].rolling(200).mean().iloc[-1]
            spy_above_ma = spy_price > spy_ma200

            spy_open = spy_hist['Open'].iloc[-1]
            spy_day_change_pct = (spy_price - spy_open) / spy_open * 100

            # Fetch VIX data
            vix = yf.Ticker("^VIX")
            vix_hist = vix.history(period="5d")

            if len(vix_hist) == 0:
                logger.error("Unable to fetch VIX data")
                return self._neutral_regime("no_vix_data")

            vix_level = vix_hist['Close'].iloc[-1]

            # Classify VIX regime
            if vix_level < self.vix_low:
                vix_regime = 'low'
            elif vix_level < self.vix_medium:
                vix_regime = 'medium'
            elif vix_level < self.vix_high:
                vix_regime = 'high'
            else:
                vix_regime = 'extreme'

            # Determine overall regime and trading permission
            regime_str, allow, reason = self._classify_regime(
                spy_above_ma, spy_day_change_pct, vix_regime, vix_level
            )

            market_regime = MarketRegime(
                timestamp=datetime.now(),
                regime=regime_str,
                spy_price=spy_price,
                spy_ma200=spy_ma200,
                spy_above_ma=spy_above_ma,
                spy_day_change_pct=spy_day_change_pct,
                vix_level=vix_level,
                vix_regime=vix_regime,
                allow_penny_trading=allow,
                reason=reason
            )

            # Log regime
            logger.info(
                f"📊 Market Regime: {regime_str.upper()} "
                f"(SPY ${spy_price:.2f} {'>' if spy_above_ma else '<'} MA200 ${spy_ma200:.2f}, "
                f"SPY {spy_day_change_pct:+.2f}%, VIX {vix_level:.1f}) "
                f"→ {'✅ TRADE' if allow else '❌ SKIP'} pennies"
            )

            return market_regime

        except Exception as e:
            logger.error(f"Error calculating market regime: {e}")
            return self._neutral_regime(f"error: {e}")

    def _classify_regime(
        self,
        spy_above_ma: bool,
        spy_day_change_pct: float,
        vix_regime: str,
        vix_level: float
    ) -> tuple[str, bool, str]:
        """
        Classify regime and determine if penny trading allowed.

        Returns:
            (regime_string, allow_trading, reason)
        """
        # Count positive signals
        signals = []

        if spy_above_ma:
            signals.append("SPY > 200MA")
        else:
            signals.append("SPY < 200MA ⚠️")

        if spy_day_change_pct > 0:
            signals.append(f"SPY +{spy_day_change_pct:.2f}%")
        else:
            signals.append(f"SPY {spy_day_change_pct:.2f}% ⚠️")

        if vix_regime in ['low', 'medium']:
            signals.append(f"VIX {vix_level:.1f} ({vix_regime})")
        else:
            signals.append(f"VIX {vix_level:.1f} ({vix_regime}) ⚠️")

        # RISK OFF conditions (block trading)
        if not spy_above_ma and self.require_spy_above_ma:
            return ('risk_off', False, f"SPY below 200MA ({', '.join(signals)})")

        if vix_level > self.vix_medium:
            return ('risk_off', False, f"VIX too high ({', '.join(signals)})")

        if spy_day_change_pct < -1.0 and self.require_spy_green:
            return ('risk_off', False, f"SPY red day ({', '.join(signals)})")

        # RISK ON conditions (allow trading)
        if spy_above_ma and vix_regime == 'low' and spy_day_change_pct > 0:
            return ('risk_on', True, f"Optimal conditions ({', '.join(signals)})")

        # NEUTRAL (allow but with caution)
        if spy_above_ma and vix_regime == 'medium':
            return ('neutral', True, f"Mixed signals ({', '.join(signals)})")

        # Default to caution
        return ('neutral', True, f"Neutral market ({', '.join(signals)})")

    def _neutral_regime(self, reason: str) -> MarketRegime:
        """Return neutral regime when data unavailable"""
        return MarketRegime(
            timestamp=datetime.now(),
            regime='neutral',
            spy_price=0.0,
            spy_ma200=0.0,
            spy_above_ma=False,
            spy_day_change_pct=0.0,
            vix_level=0.0,
            vix_regime='unknown',
            allow_penny_trading=True,  # Default to allow (conservative)
            reason=reason
        )

    def should_trade_pennies(self) -> bool:
        """Check if current regime allows penny trading"""
        regime = self.get_regime()
        return regime.allow_penny_trading

    def get_stats(self) -> Dict:
        """Get current regime statistics"""
        regime = self.get_regime()
        return {
            'regime': regime.regime,
            'allow_trading': regime.allow_penny_trading,
            'spy_price': regime.spy_price,
            'spy_ma200': regime.spy_ma200,
            'spy_above_ma': regime.spy_above_ma,
            'spy_day_change_pct': regime.spy_day_change_pct,
            'vix_level': regime.vix_level,
            'vix_regime': regime.vix_regime,
            'reason': regime.reason,
            'cache_valid': self._is_cache_valid()
        }


# ===== Convenience functions =====

def create_regime_detector(config: Optional[Dict] = None) -> MarketRegimeDetector:
    """
    Create MarketRegimeDetector from config.

    Args:
        config: Optional config dict with regime settings

    Returns:
        Configured MarketRegimeDetector
    """
    if config is None:
        config = {}

    return MarketRegimeDetector(
        vix_low=config.get('vix_low', 20.0),
        vix_medium=config.get('vix_medium', 30.0),
        vix_high=config.get('vix_high', 40.0),
        require_spy_above_ma=config.get('require_spy_above_ma', True),
        require_spy_green=config.get('require_spy_green', False),
        cache_minutes=config.get('cache_minutes', 15)
    )


# ===== CLI testing =====

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)

    print("\n" + "="*70)
    print("MARKET REGIME DETECTOR TEST")
    print("="*70)

    # Test with default settings
    detector = MarketRegimeDetector()

    regime = detector.get_regime()

    print(f"\nTimestamp: {regime.timestamp}")
    print(f"Regime: {regime.regime.upper()}")
    print(f"Allow Penny Trading: {'✅ YES' if regime.allow_penny_trading else '❌ NO'}")
    print(f"\nDetails:")
    print(f"  SPY: ${regime.spy_price:.2f} ({'above' if regime.spy_above_ma else 'below'} 200MA ${regime.spy_ma200:.2f})")
    print(f"  SPY Day Change: {regime.spy_day_change_pct:+.2f}%")
    print(f"  VIX: {regime.vix_level:.1f} ({regime.vix_regime})")
    print(f"\nReason: {regime.reason}")

    # Test strict settings
    print("\n" + "="*70)
    print("STRICT MODE (Require SPY green + above 200MA)")
    print("="*70)

    strict_detector = MarketRegimeDetector(
        require_spy_above_ma=True,
        require_spy_green=True,
        vix_medium=25.0  # Stricter VIX threshold
    )

    strict_regime = strict_detector.get_regime()
    print(f"\nAllow Penny Trading: {'✅ YES' if strict_regime.allow_penny_trading else '❌ NO'}")
    print(f"Reason: {strict_regime.reason}")

    # Show stats
    print("\n" + "="*70)
    print("REGIME STATS")
    print("="*70)
    stats = detector.get_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")

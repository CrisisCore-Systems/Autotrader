"""
VWAP Engine: Intraday VWAP calculation and signal detection

Calculates Volume-Weighted Average Price (VWAP) with standard deviation bands.
Detects VWAP reclaims, rejections, and band touches for penny stock entries.

Author: BounceHunter Team
"""

import logging
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
from datetime import datetime, time
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class VWAPBar:
    """Single bar of VWAP data"""
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    vwap: float
    vwap_std: float
    upper_band: float  # +2σ
    lower_band: float  # -2σ


@dataclass
class VWAPEvent:
    """VWAP signal event"""
    timestamp: datetime
    event_type: str  # 'reclaim', 'rejection', 'lower_band_touch', 'upper_band_touch'
    price: float
    vwap: float
    distance_pct: float  # % from VWAP
    volume_spike: float  # volume vs avg
    bars_since_open: int


class VWAPEngine:
    """
    Real-time VWAP calculator with band detection.

    Features:
    - Intraday VWAP from market open
    - ±2σ standard deviation bands
    - Reclaim/rejection detection
    - Volume spike awareness
    - Reset at market open
    """

    def __init__(self, market_open: str = "09:30", reset_daily: bool = True):
        """
        Initialize VWAP engine.

        Args:
            market_open: Market open time (HH:MM format, ET)
            reset_daily: Reset VWAP at market open (vs continuous)
        """
        self.market_open = time.fromisoformat(market_open)
        self.reset_daily = reset_daily

        # Cumulative state (reset at market open)
        self.cum_pv = 0.0  # Cumulative price * volume
        self.cum_v = 0  # Cumulative volume
        self.cum_pv2 = 0.0  # Cumulative (price * volume)^2 for std dev

        # Bar tracking
        self.bars: List[VWAPBar] = []
        self.last_vwap = None
        self.last_bar_time = None
        self.bars_since_open = 0

        # Event detection
        self.above_vwap = None  # Track if price is above VWAP
        self.events: List[VWAPEvent] = []

        # Volume tracking
        self.volume_window = []  # Last N bars for volume average
        self.volume_window_size = 20

        logger.info(f"VWAPEngine initialized: market_open={market_open}, reset_daily={reset_daily}")

    def should_reset(self, timestamp: datetime) -> bool:
        """Check if VWAP should reset (new trading day)"""
        if not self.reset_daily:
            return False

        if self.last_bar_time is None:
            return False

        # Reset if crossed market open time on new day
        last_time = self.last_bar_time.time()
        current_time = timestamp.time()

        if (last_time < self.market_open <= current_time or
            timestamp.date() > self.last_bar_time.date()):
            logger.info(f"🔄 VWAP reset at {timestamp} (new trading day)")
            return True

        return False

    def reset(self):
        """Reset VWAP calculation (at market open)"""
        self.cum_pv = 0.0
        self.cum_v = 0
        self.cum_pv2 = 0.0
        self.bars = []
        self.last_vwap = None
        self.above_vwap = None
        self.bars_since_open = 0
        self.volume_window = []
        # Don't reset events - keep for historical reference

    def add_bar(
        self,
        timestamp: datetime,
        open_price: float,
        high: float,
        low: float,
        close: float,
        volume: int
    ) -> VWAPBar:
        """
        Add a new bar and calculate VWAP.

        Args:
            timestamp: Bar timestamp
            open_price: Open price
            high: High price
            low: Low price
            close: Close price
            volume: Volume

        Returns:
            VWAPBar with calculated VWAP and bands
        """
        # Check for reset
        if self.should_reset(timestamp):
            self.reset()

        # Typical price for VWAP calculation
        typical_price = (high + low + close) / 3

        # Update cumulative values
        pv = typical_price * volume
        self.cum_pv += pv
        self.cum_v += volume
        self.cum_pv2 += (typical_price ** 2) * volume

        # Calculate VWAP
        if self.cum_v > 0:
            vwap = self.cum_pv / self.cum_v
        else:
            vwap = typical_price

        # Calculate standard deviation
        if self.cum_v > 0 and len(self.bars) > 1:
            # Variance = E[X^2] - E[X]^2
            mean_pv2 = self.cum_pv2 / self.cum_v
            vwap_squared = vwap ** 2
            variance = max(0, mean_pv2 - vwap_squared)
            vwap_std = np.sqrt(variance)
        else:
            vwap_std = 0.0

        # Calculate bands (±2σ)
        upper_band = vwap + (2 * vwap_std)
        lower_band = vwap - (2 * vwap_std)

        # Create bar
        bar = VWAPBar(
            timestamp=timestamp,
            open=open_price,
            high=high,
            low=low,
            close=close,
            volume=volume,
            vwap=vwap,
            vwap_std=vwap_std,
            upper_band=upper_band,
            lower_band=lower_band
        )

        # Track volume
        self.volume_window.append(volume)
        if len(self.volume_window) > self.volume_window_size:
            self.volume_window.pop(0)

        # Detect events
        self._detect_events(bar)

        # Update state
        self.bars.append(bar)
        self.last_vwap = vwap
        self.last_bar_time = timestamp
        self.bars_since_open += 1

        return bar

    def _detect_events(self, bar: VWAPBar):
        """Detect VWAP events (reclaim, rejection, band touches)"""
        # Need at least 2 bars to detect crosses
        if len(self.bars) < 1:
            self.above_vwap = bar.close > bar.vwap
            return

        prev_bar = self.bars[-1]

        # Was price above VWAP before?
        was_above = prev_bar.close > prev_bar.vwap
        is_above = bar.close > bar.vwap

        # Calculate volume spike
        avg_volume = np.mean(self.volume_window) if self.volume_window else bar.volume
        volume_spike = bar.volume / avg_volume if avg_volume > 0 else 1.0

        # Calculate distance from VWAP
        distance_pct = (bar.close - bar.vwap) / bar.vwap * 100

        # Detect reclaim (cross above VWAP)
        if not was_above and is_above:
            event = VWAPEvent(
                timestamp=bar.timestamp,
                event_type='reclaim',
                price=bar.close,
                vwap=bar.vwap,
                distance_pct=distance_pct,
                volume_spike=volume_spike,
                bars_since_open=self.bars_since_open
            )
            self.events.append(event)
            logger.info(
                f"🟢 VWAP RECLAIM: {bar.timestamp} price={bar.close:.2f} vwap={bar.vwap:.2f} "
                f"vol_spike={volume_spike:.1f}x"
            )

        # Detect rejection (cross below VWAP)
        elif was_above and not is_above:
            event = VWAPEvent(
                timestamp=bar.timestamp,
                event_type='rejection',
                price=bar.close,
                vwap=bar.vwap,
                distance_pct=distance_pct,
                volume_spike=volume_spike,
                bars_since_open=self.bars_since_open
            )
            self.events.append(event)
            logger.info(
                f"🔴 VWAP REJECTION: {bar.timestamp} price={bar.close:.2f} vwap={bar.vwap:.2f} "
                f"vol_spike={volume_spike:.1f}x"
            )

        # Detect lower band touch (mean revert opportunity)
        if bar.low <= bar.lower_band and bar.close > bar.lower_band:
            event = VWAPEvent(
                timestamp=bar.timestamp,
                event_type='lower_band_touch',
                price=bar.low,
                vwap=bar.vwap,
                distance_pct=(bar.low - bar.vwap) / bar.vwap * 100,
                volume_spike=volume_spike,
                bars_since_open=self.bars_since_open
            )
            self.events.append(event)
            logger.info(
                f"📉 LOWER BAND TOUCH: {bar.timestamp} low={bar.low:.2f} "
                f"lower_band={bar.lower_band:.2f} (-2σ)"
            )

        # Detect upper band touch (potential resistance)
        if bar.high >= bar.upper_band and bar.close < bar.upper_band:
            event = VWAPEvent(
                timestamp=bar.timestamp,
                event_type='upper_band_touch',
                price=bar.high,
                vwap=bar.vwap,
                distance_pct=(bar.high - bar.vwap) / bar.vwap * 100,
                volume_spike=volume_spike,
                bars_since_open=self.bars_since_open
            )
            self.events.append(event)
            logger.info(
                f"📈 UPPER BAND TOUCH: {bar.timestamp} high={bar.high:.2f} "
                f"upper_band={bar.upper_band:.2f} (+2σ)"
            )

        self.above_vwap = is_above

    def get_current_vwap(self) -> Optional[float]:
        """Get current VWAP value"""
        return self.last_vwap

    def get_current_bands(self) -> Optional[Tuple[float, float]]:
        """Get current (lower_band, upper_band)"""
        if not self.bars:
            return None
        last_bar = self.bars[-1]
        return (last_bar.lower_band, last_bar.upper_band)

    def is_above_vwap(self, price: float) -> bool:
        """Check if given price is above current VWAP"""
        if self.last_vwap is None:
            return False
        return price > self.last_vwap

    def distance_from_vwap(self, price: float) -> Optional[float]:
        """Calculate % distance from VWAP"""
        if self.last_vwap is None:
            return None
        return (price - self.last_vwap) / self.last_vwap * 100

    def get_recent_events(self, event_type: Optional[str] = None, minutes: int = 60) -> List[VWAPEvent]:
        """
        Get recent VWAP events.

        Args:
            event_type: Filter by event type ('reclaim', 'rejection', etc.)
            minutes: Lookback window in minutes

        Returns:
            List of recent VWAPEvents
        """
        if not self.events:
            return []

        cutoff_time = datetime.now() - timedelta(minutes=minutes)
        recent = [e for e in self.events if e.timestamp >= cutoff_time]

        if event_type:
            recent = [e for e in recent if e.event_type == event_type]

        return recent

    def get_stats(self) -> Dict:
        """Get VWAP engine statistics"""
        stats = {
            'bars_count': len(self.bars),
            'bars_since_open': self.bars_since_open,
            'current_vwap': self.last_vwap,
            'events_count': len(self.events),
            'cumulative_volume': self.cum_v
        }

        if self.bars:
            last_bar = self.bars[-1]
            stats.update({
                'last_close': last_bar.close,
                'distance_from_vwap_pct': self.distance_from_vwap(last_bar.close),
                'above_vwap': self.above_vwap,
                'vwap_std': last_bar.vwap_std,
                'upper_band': last_bar.upper_band,
                'lower_band': last_bar.lower_band
            })

        # Event breakdown
        event_counts = {}
        for event in self.events:
            event_counts[event.event_type] = event_counts.get(event.event_type, 0) + 1
        stats['events_by_type'] = event_counts

        return stats


# ===== Convenience functions =====

def calculate_vwap_from_bars(bars: List[Dict]) -> List[VWAPBar]:
    """
    Calculate VWAP from a list of bar dictionaries.

    Args:
        bars: List of dicts with keys: timestamp, open, high, low, close, volume

    Returns:
        List of VWAPBar objects
    """
    engine = VWAPEngine()

    vwap_bars = []
    for bar_dict in bars:
        vwap_bar = engine.add_bar(
            timestamp=bar_dict['timestamp'],
            open_price=bar_dict['open'],
            high=bar_dict['high'],
            low=bar_dict['low'],
            close=bar_dict['close'],
            volume=bar_dict['volume']
        )
        vwap_bars.append(vwap_bar)

    return vwap_bars


# ===== CLI testing =====

if __name__ == '__main__':
    from datetime import timedelta  # Need timedelta for test
    logging.basicConfig(level=logging.INFO)

    print("\n" + "="*60)
    print("VWAP ENGINE TEST")
    print("="*60)

    # Simulate intraday bars (datetime already imported at top)
    engine = VWAPEngine(market_open="09:30")

    # Simulate 30 bars of data
    base_time = datetime.now().replace(hour=9, minute=30, second=0, microsecond=0)
    base_price = 2.50

    print("\nSimulating 30 bars...")

    for i in range(30):
        timestamp = base_time + timedelta(minutes=i)

        # Simulate price movement
        drift = np.random.randn() * 0.02  # 2% volatility
        price = base_price * (1 + drift)

        # Simulate OHLC
        open_price = price * (1 + np.random.randn() * 0.005)
        high = price * (1 + abs(np.random.randn()) * 0.01)
        low = price * (1 - abs(np.random.randn()) * 0.01)
        close = price * (1 + np.random.randn() * 0.005)

        # Simulate volume
        volume = int(np.random.uniform(50000, 200000))

        bar = engine.add_bar(timestamp, open_price, high, low, close, volume)

        if i % 5 == 0:  # Print every 5 bars
            print(f"\nBar {i+1}: {timestamp.strftime('%H:%M')}")
            print(f"  Close: ${close:.2f}")
            print(f"  VWAP: ${bar.vwap:.2f}")
            print(f"  Bands: ${bar.lower_band:.2f} - ${bar.upper_band:.2f}")
            print(f"  Distance: {engine.distance_from_vwap(close):.2f}%")

        base_price = close  # Carry forward for next bar

    # Print summary
    print("\n" + "="*60)
    print("VWAP STATS")
    print("="*60)

    stats = engine.get_stats()
    print(f"\nBars processed: {stats['bars_count']}")
    print(f"Current VWAP: ${stats['current_vwap']:.2f}")
    print(f"Last close: ${stats['last_close']:.2f}")
    print(f"Distance from VWAP: {stats['distance_from_vwap_pct']:.2f}%")
    print(f"Above VWAP: {stats['above_vwap']}")

    print(f"\nEvents detected: {stats['events_count']}")
    for event_type, count in stats['events_by_type'].items():
        print(f"  {event_type}: {count}")

    # Show recent events
    print("\n" + "="*60)
    print("RECENT EVENTS")
    print("="*60)

    recent_events = engine.get_recent_events(minutes=30)
    for event in recent_events[-5:]:  # Last 5 events
        print(f"\n{event.event_type.upper()}: {event.timestamp.strftime('%H:%M')}")
        print(f"  Price: ${event.price:.2f}")
        print(f"  VWAP: ${event.vwap:.2f}")
        print(f"  Distance: {event.distance_pct:.2f}%")
        print(f"  Volume spike: {event.volume_spike:.1f}x")

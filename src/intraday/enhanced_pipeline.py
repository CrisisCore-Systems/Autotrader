"""
Enhanced Data Pipeline with Multiple Data Modes

Extends IntradayDataPipeline to support:
1. Live: Real-time IBKR data (market hours, requires subscription)
2. Historical: Replay IBKR historical bars (works 24/7)
3. Simulated: Generate synthetic ticks (works 24/7, no IBKR needed)

Usage:
    # Simulated (for testing, no IBKR connection needed)
    pipeline = EnhancedDataPipeline(mode='simulated', symbol='SPY')
    
    # Historical replay (requires IBKR connection)
    pipeline = EnhancedDataPipeline(
        mode='historical',
        ib=ib,
        symbol='SPY',
        duration='5 D'  # 5 days of history
    )
    
    # Live (requires market hours + subscription)
    pipeline = EnhancedDataPipeline(mode='live', ib=ib, symbol='SPY')
"""

from __future__ import annotations

import time
import logging
from typing import Optional, List, Callable, Deque
from collections import deque
from datetime import datetime

try:
    from ib_insync import IB
except ImportError:
    IB = None

from .data_pipeline import TickData, Bar, OrderBook
from .data_source import (
    DataSource,
    LiveDataSource,
    HistoricalDataSource,
    SimulatedDataSource,
)

logger = logging.getLogger(__name__)


class EnhancedDataPipeline:
    """
    Data pipeline with multiple data source modes.
    
    Automatically handles:
    - Tick buffering
    - Bar aggregation (1-minute)
    - Feature computation callbacks
    - Statistics tracking
    
    Works with live, historical, or simulated data.
    """
    
    def __init__(
        self,
        mode: str = "simulated",  # "live", "historical", "simulated"
        ib: Optional[IB] = None,
        symbol: str = "SPY",
        exchange: str = "SMART",
        currency: str = "USD",
        tick_buffer_size: int = 10000,
        bar_buffer_size: int = 390,
        # Historical mode params
        duration: str = "1 D",
        replay_speed: float = 1.0,
        # Simulated mode params
        initial_price: float = 580.0,
        tick_interval: float = 0.05,
        volatility: float = 0.0001,
    ):
        """
        Initialize enhanced pipeline.
        
        Args:
            mode: Data source mode ("live", "historical", "simulated")
            ib: IB instance (required for live/historical)
            symbol: Stock symbol
            exchange: Exchange code
            currency: Currency
            tick_buffer_size: Max ticks in memory
            bar_buffer_size: Max bars in memory
            duration: Historical data duration (e.g., "1 D", "5 D")
            replay_speed: Historical replay speed multiplier
            initial_price: Starting price for simulated mode
            tick_interval: Seconds between simulated ticks
            volatility: Per-tick volatility for simulated mode
        """
        self.mode = mode
        self.ib = ib
        self.symbol = symbol
        self.exchange = exchange
        self.currency = currency
        
        # Validate mode
        if mode not in ["live", "historical", "simulated"]:
            raise ValueError(f"Invalid mode: {mode}. Use 'live', 'historical', or 'simulated'")
        
        if mode in ["live", "historical"] and ib is None:
            raise ValueError(f"Mode '{mode}' requires an IB connection")
        
        # Data buffers
        self.tick_buffer: Deque[TickData] = deque(maxlen=tick_buffer_size)
        self.bar_buffer: Deque[Bar] = deque(maxlen=bar_buffer_size)
        
        # Order book (placeholder for compatibility)
        self.order_book = OrderBook()
        
        # Bar aggregation
        self.current_bar_ticks: List[TickData] = []
        self.current_bar_start: Optional[float] = None
        
        # Statistics
        self.ticks_received = 0
        self.bars_generated = 0
        self.latencies: Deque[float] = deque(maxlen=1000)
        
        # Data source
        self.data_source: Optional[DataSource] = None
        
        # Create appropriate data source
        if mode == "live":
            self.data_source = LiveDataSource(
                ib=ib,
                symbol=symbol,
                tick_callback=self._on_tick,
                exchange=exchange,
                currency=currency,
            )
        
        elif mode == "historical":
            self.data_source = HistoricalDataSource(
                ib=ib,
                symbol=symbol,
                tick_callback=self._on_tick,
                duration=duration,
                bar_size="1 min",
                replay_speed=replay_speed,
                exchange=exchange,
                currency=currency,
            )
        
        elif mode == "simulated":
            self.data_source = SimulatedDataSource(
                symbol=symbol,
                tick_callback=self._on_tick,
                initial_price=initial_price,
                tick_interval=tick_interval,
                volatility=volatility,
            )
        
        logger.info(
            f"Initialized EnhancedDataPipeline for {symbol} "
            f"(mode={mode}, tick_buffer={tick_buffer_size}, bar_buffer={bar_buffer_size})"
        )
    
    def start(self):
        """Start data feed."""
        if self.data_source:
            self.data_source.start()
            logger.info(f"✅ Started {self.mode} data feed for {self.symbol}")
        else:
            raise RuntimeError("No data source configured")
    
    def stop(self):
        """Stop data feed."""
        if self.data_source:
            self.data_source.stop()
            logger.info(f"⏹️ Stopped {self.mode} data feed for {self.symbol}")
    
    def is_running(self) -> bool:
        """Check if feed is active."""
        return self.data_source.is_running() if self.data_source else False
    
    def _on_tick(self, tick: TickData):
        """Handle incoming tick."""
        # Store tick
        self.tick_buffer.append(tick)
        self.ticks_received += 1
        
        # Aggregate into bars
        self._aggregate_bar(tick)
        
        # Log progress (every 100 ticks)
        if self.ticks_received % 100 == 0:
            logger.debug(
                f"Received {self.ticks_received} ticks, "
                f"{self.bars_generated} bars generated"
            )
    
    def _aggregate_bar(self, tick: TickData):
        """Aggregate ticks into 1-minute bars."""
        # Get current minute timestamp
        tick_time = datetime.fromtimestamp(tick.timestamp)
        bar_minute = tick_time.replace(second=0, microsecond=0).timestamp()
        
        # New bar?
        if self.current_bar_start is None:
            self.current_bar_start = bar_minute
            self.current_bar_ticks = [tick]
            return
        
        # Same bar?
        if bar_minute == self.current_bar_start:
            self.current_bar_ticks.append(tick)
            return
        
        # Next bar - finalize current bar
        if len(self.current_bar_ticks) > 0:
            bar = Bar.from_ticks(self.current_bar_ticks)
            if bar:
                self.bar_buffer.append(bar)
                self.bars_generated += 1
                
                logger.debug(
                    f"Bar {self.bars_generated}: "
                    f"O={bar.open:.2f} H={bar.high:.2f} L={bar.low:.2f} C={bar.close:.2f} "
                    f"V={bar.volume} VWAP={bar.vwap:.2f}"
                )
        
        # Start new bar
        self.current_bar_start = bar_minute
        self.current_bar_ticks = [tick]
    
    def get_latest_ticks(self, n: int = 100) -> List[TickData]:
        """Get last N ticks."""
        return list(self.tick_buffer)[-n:]
    
    def get_latest_bars(self, n: int = 50) -> List[Bar]:
        """Get last N bars."""
        return list(self.bar_buffer)[-n:]
    
    def get_current_price(self) -> float:
        """Get most recent price."""
        if self.tick_buffer:
            return self.tick_buffer[-1].price
        return 0.0
    
    def get_volume_imbalance(self, lookback: int = 100) -> float:
        """
        Calculate buy/sell volume imbalance.
        
        Returns:
            Value from -1.0 (all sell) to +1.0 (all buy)
        """
        ticks = self.get_latest_ticks(lookback)
        if not ticks:
            return 0.0
        
        buy_volume = sum(t.size for t in ticks if t.price >= t.ask)
        sell_volume = sum(t.size for t in ticks if t.price <= t.bid)
        
        total = buy_volume + sell_volume
        if total == 0:
            return 0.0
        
        return (buy_volume - sell_volume) / total
    
    def get_stats(self) -> dict:
        """Get pipeline statistics."""
        current_price = self.get_current_price()
        
        spread = 0.0
        spread_pct = 0.0
        if self.tick_buffer:
            last_tick = self.tick_buffer[-1]
            spread = last_tick.spread
            spread_pct = last_tick.spread_pct * 100
        
        avg_latency = sum(self.latencies) / len(self.latencies) if self.latencies else 0
        max_latency = max(self.latencies) if self.latencies else 0
        
        return {
            'mode': self.mode,
            'symbol': self.symbol,
            'ticks_collected': self.ticks_received,
            'bars_collected': self.bars_generated,
            'current_price': current_price,
            'spread': spread,
            'spread_pct': spread_pct,
            'volume_imbalance': self.get_volume_imbalance(),
            'avg_latency_ms': avg_latency * 1000,
            'max_latency_ms': max_latency * 1000,
            'tick_buffer_usage': len(self.tick_buffer),
            'bar_buffer_usage': len(self.bar_buffer),
        }


if __name__ == "__main__":
    """Test enhanced pipeline."""
    
    logging.basicConfig(level=logging.INFO)
    
    print("="*60)
    print("Testing Enhanced Data Pipeline - Simulated Mode")
    print("="*60)
    
    # Test simulated mode (no IBKR needed)
    pipeline = EnhancedDataPipeline(
        mode='simulated',
        symbol='SPY',
        initial_price=580.0,
        tick_interval=0.01,  # 10ms per tick
    )
    
    pipeline.start()
    
    # Collect data for 10 seconds
    print("\nCollecting data for 10 seconds...")
    for i in range(10):
        time.sleep(1)
        stats = pipeline.get_stats()
        print(f"[{i+1}s] Ticks: {stats['ticks_collected']}, "
              f"Bars: {stats['bars_collected']}, "
              f"Price: ${stats['current_price']:.2f}, "
              f"Imbalance: {stats['volume_imbalance']:.3f}")
    
    pipeline.stop()
    
    # Final stats
    print("\n" + "="*60)
    print("Final Statistics")
    print("="*60)
    stats = pipeline.get_stats()
    for key, value in stats.items():
        print(f"  {key:25s}: {value}")
    
    print("\n✅ Test complete!")
    print("\nTo test with real IBKR data:")
    print("  1. Connect: ib = IB(); ib.connect('127.0.0.1', 7497)")
    print("  2. Historical: EnhancedDataPipeline(mode='historical', ib=ib, symbol='SPY', duration='5 D')")
    print("  3. Live: EnhancedDataPipeline(mode='live', ib=ib, symbol='SPY')")

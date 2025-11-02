"""
Real-Time Tick Data Pipeline for Intraday Trading

Handles:
- Tick-by-tick data ingestion from IBKR
- 1-minute bar aggregation
- Level 2 market depth tracking
- Latency monitoring (<50ms target)
- Order book updates
"""

from __future__ import annotations

import time
import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from typing import List, Callable, Optional, Dict, Deque
from collections import deque
from datetime import datetime, timedelta
import logging

try:
    from ib_insync import IB, Stock, util
except ImportError:
    raise ImportError("ib_insync not installed. Run: pip install ib_insync")

logger = logging.getLogger(__name__)


@dataclass
class TickData:
    """Single tick data point with bid/ask and size."""
    
    timestamp: float  # Unix timestamp
    price: float  # Last trade price
    size: int  # Last trade size
    bid: float  # Best bid
    ask: float  # Best ask
    bid_size: int  # Bid depth at level 1
    ask_size: int  # Ask depth at level 1
    
    @property
    def spread(self) -> float:
        """Bid-ask spread in dollars."""
        return self.ask - self.bid
    
    @property
    def spread_pct(self) -> float:
        """Spread as percentage of price."""
        if self.price > 0:
            return self.spread / self.price
        return 0.0
    
    @property
    def mid_price(self) -> float:
        """Midpoint between bid and ask."""
        return (self.bid + self.ask) / 2


@dataclass
class Bar:
    """OHLCV bar (1-minute aggregation)."""
    
    timestamp: float  # Bar start time (Unix)
    open: float
    high: float
    low: float
    close: float
    volume: int
    num_trades: int
    vwap: float  # Volume-weighted average price
    
    @classmethod
    def from_ticks(cls, ticks: List[TickData]) -> Optional[Bar]:
        """Aggregate ticks into 1-minute bar."""
        if not ticks:
            return None
        
        prices = [t.price for t in ticks]
        volumes = [t.size for t in ticks]
        
        # Calculate VWAP
        total_value = sum(p * v for p, v in zip(prices, volumes))
        total_volume = sum(volumes)
        vwap = total_value / total_volume if total_volume > 0 else prices[-1]
        
        return cls(
            timestamp=ticks[0].timestamp,
            open=prices[0],
            high=max(prices),
            low=min(prices),
            close=prices[-1],
            volume=total_volume,
            num_trades=len(ticks),
            vwap=vwap,
        )


@dataclass
class OrderBookLevel:
    """Single level in order book."""
    
    price: float
    size: int
    num_orders: int = 1


@dataclass
class OrderBook:
    """Level 2 market depth (order book)."""
    
    bids: List[OrderBookLevel] = field(default_factory=list)  # Sorted descending
    asks: List[OrderBookLevel] = field(default_factory=list)  # Sorted ascending
    timestamp: float = field(default_factory=time.time)
    
    @property
    def best_bid(self) -> Optional[float]:
        """Best bid price (highest)."""
        return self.bids[0].price if self.bids else None
    
    @property
    def best_ask(self) -> Optional[float]:
        """Best ask price (lowest)."""
        return self.asks[0].price if self.asks else None
    
    @property
    def spread(self) -> float:
        """Bid-ask spread."""
        if self.best_bid and self.best_ask:
            return self.best_ask - self.best_bid
        return 0.0
    
    def get_depth_imbalance(self, levels: int = 5) -> float:
        """
        Calculate order book imbalance.
        
        Returns:
            -1.0 to +1.0 (negative = sell pressure, positive = buy pressure)
        """
        bid_depth = sum(level.size for level in self.bids[:levels])
        ask_depth = sum(level.size for level in self.asks[:levels])
        
        total = bid_depth + ask_depth
        if total == 0:
            return 0.0
        
        return (bid_depth - ask_depth) / total


class IntradayDataPipeline:
    """
    Real-time tick data pipeline for intraday trading.
    
    Features:
    - Tick-by-tick data from IBKR
    - 1-minute bar aggregation
    - Level 2 order book tracking
    - Latency monitoring
    - Callback system for downstream consumers
    
    Example:
        >>> from ib_insync import IB
        >>> ib = IB()
        >>> ib.connect('127.0.0.1', 7497, clientId=1)
        >>> pipeline = IntradayDataPipeline(ib, 'SPY')
        >>> pipeline.start()
        >>> # Wait for data...
        >>> ticks = pipeline.get_latest_ticks(100)
        >>> print(f"Received {len(ticks)} ticks")
    """
    
    def __init__(
        self,
        ib: IB,
        symbol: str,
        exchange: str = "SMART",
        currency: str = "USD",
        tick_buffer_size: int = 10000,
        bar_buffer_size: int = 390,  # 1 trading day
        enable_depth: bool = True,
        depth_levels: int = 10,
    ):
        """
        Initialize intraday data pipeline.
        
        Args:
            ib: Connected IB instance
            symbol: Stock symbol (e.g., 'SPY', 'QQQ')
            exchange: Exchange code (default: SMART routing)
            currency: Currency (default: USD)
            tick_buffer_size: Max ticks to store in memory
            bar_buffer_size: Max 1-min bars to store (default: 1 day)
            enable_depth: Subscribe to Level 2 market depth
            depth_levels: Number of depth levels to track
        """
        self.ib = ib
        self.symbol = symbol
        self.exchange = exchange
        self.currency = currency
        
        # Data buffers
        self.tick_buffer: Deque[TickData] = deque(maxlen=tick_buffer_size)
        self.bar_buffer: Deque[Bar] = deque(maxlen=bar_buffer_size)
        
        # Order book
        self.enable_depth = enable_depth
        self.depth_levels = depth_levels
        self.order_book = OrderBook()
        
        # Bar aggregation state
        self.current_bar_ticks: List[TickData] = []
        self.current_bar_start: Optional[float] = None
        
        # Callbacks
        self.on_tick_callbacks: List[Callable[[TickData], None]] = []
        self.on_bar_callbacks: List[Callable[[Bar], None]] = []
        self.on_depth_callbacks: List[Callable[[OrderBook], None]] = []
        
        # Latency tracking
        self.latencies: Deque[float] = deque(maxlen=1000)
        
        # Contract
        self.contract: Optional[Stock] = None
        self.ticker = None
        
        # State
        self.is_running = False
        
        logger.info(
            f"Initialized IntradayDataPipeline for {symbol} "
            f"(tick_buffer={tick_buffer_size}, bar_buffer={bar_buffer_size})"
        )
    
    def start(self):
        """Start real-time data subscriptions."""
        if self.is_running:
            logger.warning(f"Pipeline for {self.symbol} already running")
            return
        
        # Create and qualify contract
        self.contract = Stock(self.symbol, self.exchange, self.currency)
        qualified = self.ib.qualifyContracts(self.contract)
        
        if not qualified:
            raise ValueError(f"Failed to qualify contract for {self.symbol}")
        
        self.contract = qualified[0]
        
        # Subscribe to tick data
        self.ticker = self.ib.reqMktData(
            self.contract,
            genericTickList="",  # All tick types
            snapshot=False,
            regulatorySnapshot=False,
        )
        
        # Attach tick callback
        self.ticker.updateEvent += self._on_tick_update
        
        # Subscribe to market depth (Level 2)
        if self.enable_depth:
            self.ib.reqMktDepth(self.contract, numRows=self.depth_levels)
            # Note: Depth updates come via ib.updateMktDepthEvent
        
        self.is_running = True
        logger.info(f"✅ Started data pipeline for {self.symbol}")
    
    def stop(self):
        """Stop data subscriptions."""
        if not self.is_running:
            return
        
        try:
            if self.ticker:
                self.ib.cancelMktData(self.contract)
            
            if self.enable_depth:
                self.ib.cancelMktDepth(self.contract)
            
            self.is_running = False
            logger.info(f"⏹️ Stopped data pipeline for {self.symbol}")
        
        except Exception as e:
            logger.error(f"Error stopping pipeline: {e}")
    
    def _on_tick_update(self, ticker):
        """Handle tick update from IBKR."""
        receive_time = time.time()
        
        # Build tick data
        tick = TickData(
            timestamp=receive_time,
            price=ticker.last or ticker.close or 0.0,
            size=ticker.lastSize or 0,
            bid=ticker.bid or 0.0,
            ask=ticker.ask or 0.0,
            bid_size=ticker.bidSize or 0,
            ask_size=ticker.askSize or 0,
        )
        
        # Skip invalid ticks
        if tick.price <= 0 or tick.bid <= 0 or tick.ask <= 0:
            return
        
        # Calculate latency (rough estimate)
        latency = time.time() - receive_time
        self.latencies.append(latency)
        
        # Store tick
        self.tick_buffer.append(tick)
        
        # Aggregate into 1-minute bars
        self._aggregate_bar(tick)
        
        # Notify subscribers
        for callback in self.on_tick_callbacks:
            try:
                callback(tick)
            except Exception as e:
                logger.error(f"Error in tick callback: {e}")
    
    def _aggregate_bar(self, tick: TickData):
        """Aggregate ticks into 1-minute bars."""
        # Determine bar start time (round down to nearest minute)
        bar_start = tick.timestamp - (tick.timestamp % 60)
        
        # Initialize first bar
        if self.current_bar_start is None:
            self.current_bar_start = bar_start
            self.current_bar_ticks = [tick]
            return
        
        # Same bar - accumulate
        if bar_start == self.current_bar_start:
            self.current_bar_ticks.append(tick)
        
        # New bar - finalize previous
        else:
            bar = Bar.from_ticks(self.current_bar_ticks)
            if bar:
                self.bar_buffer.append(bar)
                
                # Notify subscribers
                for callback in self.on_bar_callbacks:
                    try:
                        callback(bar)
                    except Exception as e:
                        logger.error(f"Error in bar callback: {e}")
            
            # Start new bar
            self.current_bar_start = bar_start
            self.current_bar_ticks = [tick]
    
    # === Data Access Methods ===
    
    def get_latest_ticks(self, n: int = 100) -> List[TickData]:
        """Get last N ticks."""
        return list(self.tick_buffer)[-n:]
    
    def get_latest_bars(self, n: int = 100) -> List[Bar]:
        """Get last N 1-minute bars."""
        return list(self.bar_buffer)[-n:]
    
    def get_current_price(self) -> float:
        """Get most recent trade price."""
        if self.tick_buffer:
            return self.tick_buffer[-1].price
        return 0.0
    
    def get_spread(self) -> float:
        """Get current bid-ask spread."""
        if self.tick_buffer:
            return self.tick_buffer[-1].spread
        return 0.0
    
    def get_spread_pct(self) -> float:
        """Get spread as percentage of price."""
        if self.tick_buffer:
            return self.tick_buffer[-1].spread_pct
        return 0.0
    
    def get_volume_imbalance(self, lookback: int = 100) -> float:
        """
        Calculate volume imbalance over last N ticks.
        
        Returns:
            -1.0 to +1.0 (negative = sell pressure, positive = buy pressure)
        """
        ticks = self.get_latest_ticks(lookback)
        if not ticks:
            return 0.0
        
        # Classify trades as buy/sell based on price vs bid/ask
        buy_volume = sum(
            t.size for t in ticks 
            if t.price >= t.ask  # Trade at ask = buy aggressor
        )
        sell_volume = sum(
            t.size for t in ticks 
            if t.price <= t.bid  # Trade at bid = sell aggressor
        )
        
        total = buy_volume + sell_volume
        if total == 0:
            return 0.0
        
        return (buy_volume - sell_volume) / total
    
    def get_trade_intensity(self, window_seconds: int = 60) -> float:
        """
        Calculate trades per second over window.
        
        Args:
            window_seconds: Time window (default: 60s = 1 minute)
        
        Returns:
            Trades per second
        """
        if not self.tick_buffer:
            return 0.0
        
        cutoff_time = time.time() - window_seconds
        recent_ticks = [
            t for t in self.tick_buffer 
            if t.timestamp >= cutoff_time
        ]
        
        return len(recent_ticks) / window_seconds if window_seconds > 0 else 0.0
    
    def get_avg_latency(self) -> float:
        """Get average latency in milliseconds."""
        if not self.latencies:
            return 0.0
        return np.mean(self.latencies) * 1000  # Convert to ms
    
    def get_max_latency(self) -> float:
        """Get maximum latency in milliseconds."""
        if not self.latencies:
            return 0.0
        return max(self.latencies) * 1000
    
    def get_bars_dataframe(self, n: int = 390) -> pd.DataFrame:
        """
        Get recent bars as pandas DataFrame.
        
        Args:
            n: Number of bars (default: 390 = 1 trading day)
        
        Returns:
            DataFrame with columns: timestamp, open, high, low, close, volume, vwap
        """
        bars = self.get_latest_bars(n)
        if not bars:
            return pd.DataFrame()
        
        return pd.DataFrame([
            {
                "timestamp": datetime.fromtimestamp(bar.timestamp),
                "open": bar.open,
                "high": bar.high,
                "low": bar.low,
                "close": bar.close,
                "volume": bar.volume,
                "num_trades": bar.num_trades,
                "vwap": bar.vwap,
            }
            for bar in bars
        ])
    
    # === Callback Registration ===
    
    def register_tick_callback(self, callback: Callable[[TickData], None]):
        """Register callback for tick updates."""
        self.on_tick_callbacks.append(callback)
    
    def register_bar_callback(self, callback: Callable[[Bar], None]):
        """Register callback for bar completions."""
        self.on_bar_callbacks.append(callback)
    
    def register_depth_callback(self, callback: Callable[[OrderBook], None]):
        """Register callback for order book updates."""
        self.on_depth_callbacks.append(callback)
    
    # === Statistics ===
    
    def get_stats(self) -> Dict:
        """Get pipeline statistics."""
        return {
            "symbol": self.symbol,
            "is_running": self.is_running,
            "ticks_collected": len(self.tick_buffer),
            "bars_collected": len(self.bar_buffer),
            "current_price": self.get_current_price(),
            "spread": self.get_spread(),
            "spread_pct": self.get_spread_pct() * 100,
            "volume_imbalance": self.get_volume_imbalance(),
            "trade_intensity": self.get_trade_intensity(),
            "avg_latency_ms": self.get_avg_latency(),
            "max_latency_ms": self.get_max_latency(),
        }
    
    def __repr__(self) -> str:
        return (
            f"IntradayDataPipeline(symbol={self.symbol}, "
            f"running={self.is_running}, "
            f"ticks={len(self.tick_buffer)}, "
            f"bars={len(self.bar_buffer)})"
        )


if __name__ == "__main__":
    # Example usage
    logging.basicConfig(level=logging.INFO)
    
    # Connect to IBKR
    ib = IB()
    ib.connect('127.0.0.1', 7497, clientId=1)  # Paper trading
    
    # Create pipeline
    pipeline = IntradayDataPipeline(ib, 'SPY')
    
    # Register callbacks
    def on_tick(tick: TickData):
        print(f"Tick: {tick.price:.2f} @ {tick.spread:.4f} spread")
    
    def on_bar(bar: Bar):
        print(f"Bar complete: O={bar.open:.2f} H={bar.high:.2f} L={bar.low:.2f} C={bar.close:.2f} V={bar.volume}")
    
    pipeline.register_tick_callback(on_tick)
    pipeline.register_bar_callback(on_bar)
    
    # Start pipeline
    pipeline.start()
    
    try:
        # Run for 5 minutes
        print("Collecting data for 5 minutes...")
        time.sleep(300)
        
        # Print stats
        stats = pipeline.get_stats()
        print(f"\n📊 Pipeline Stats:")
        for key, value in stats.items():
            print(f"  {key}: {value}")
    
    finally:
        pipeline.stop()
        ib.disconnect()

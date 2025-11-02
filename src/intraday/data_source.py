"""
Data Source Abstraction for Intraday Trading

Supports multiple data modes:
1. Live: Real-time IBKR tick data (market hours only)
2. Historical: Replay historical bar data from IBKR
3. Simulated: Generate synthetic tick data for testing

This allows testing the trading system 24/7, even when markets are closed.
"""

from __future__ import annotations

import time
import random
import threading
import numpy as np
from abc import ABC, abstractmethod
from typing import Optional, Callable, List
from datetime import datetime, timedelta
from dataclasses import dataclass
import logging

try:
    from ib_insync import IB, Stock, util
except ImportError:
    raise ImportError("ib_insync not installed. Run: pip install ib_insync")

from .data_pipeline import TickData, Bar

logger = logging.getLogger(__name__)


class DataSource(ABC):
    """Abstract base class for data sources."""
    
    @abstractmethod
    def start(self):
        """Start data feed."""
        pass
    
    @abstractmethod
    def stop(self):
        """Stop data feed."""
        pass
    
    @abstractmethod
    def is_running(self) -> bool:
        """Check if feed is active."""
        pass


class LiveDataSource(DataSource):
    """
    Live tick data from IBKR.
    
    Requires:
    - Market hours (9:30 AM - 4:00 PM ET)
    - Real-time market data subscription
    - Active IBKR connection
    """
    
    def __init__(
        self,
        ib: IB,
        symbol: str,
        tick_callback: Callable[[TickData], None],
        exchange: str = "SMART",
        currency: str = "USD",
    ):
        self.ib = ib
        self.symbol = symbol
        self.tick_callback = tick_callback
        self.exchange = exchange
        self.currency = currency
        
        self.contract = None
        self.ticker = None
        self._is_running = False
    
    def start(self):
        """Subscribe to live tick data."""
        if self._is_running:
            logger.warning(f"Live feed for {self.symbol} already running")
            return
        
        # Qualify contract
        self.contract = Stock(self.symbol, self.exchange, self.currency)
        qualified = self.ib.qualifyContracts(self.contract)
        
        if not qualified:
            raise ValueError(f"Failed to qualify contract for {self.symbol}")
        
        self.contract = qualified[0]
        
        # Subscribe to tick data
        self.ticker = self.ib.reqMktData(
            self.contract,
            genericTickList="",
            snapshot=False,
            regulatorySnapshot=False,
        )
        
        # Attach callback
        self.ticker.updateEvent += self._on_tick
        
        self._is_running = True
        logger.info(f"✅ Started live data feed for {self.symbol}")
    
    def stop(self):
        """Unsubscribe from tick data."""
        if not self._is_running:
            return
        
        try:
            if self.ticker:
                self.ib.cancelMktData(self.contract)
            self._is_running = False
            logger.info(f"⏹️ Stopped live feed for {self.symbol}")
        except Exception as e:
            logger.error(f"Error stopping live feed: {e}")
    
    def is_running(self) -> bool:
        return self._is_running
    
    def _on_tick(self, ticker):
        """Forward tick to callback."""
        receive_time = time.time()
        
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
        
        self.tick_callback(tick)


class HistoricalDataSource(DataSource):
    """
    Replay historical bar data from IBKR.
    
    Fetches 1-minute bars and converts to simulated ticks.
    Works 24/7, no market data subscription required.
    """
    
    def __init__(
        self,
        ib: IB,
        symbol: str,
        tick_callback: Callable[[TickData], None],
        duration: str = "1 D",  # How much history to fetch
        bar_size: str = "1 min",
        replay_speed: float = 1.0,  # 1.0 = real-time, 10.0 = 10x faster
        exchange: str = "SMART",
        currency: str = "USD",
    ):
        self.ib = ib
        self.symbol = symbol
        self.tick_callback = tick_callback
        self.duration = duration
        self.bar_size = bar_size
        self.replay_speed = replay_speed
        self.exchange = exchange
        self.currency = currency
        
        self.bars: List[Bar] = []
        self.current_bar_idx = 0
        self._is_running = False
        self._stop_requested = False
        self._thread: Optional[threading.Thread] = None
    
    def start(self):
        """Fetch historical bars and start replay."""
        if self._is_running:
            logger.warning(f"Historical replay for {self.symbol} already running")
            return
        
        # Qualify contract
        contract = Stock(self.symbol, self.exchange, self.currency)
        qualified = self.ib.qualifyContracts(contract)
        
        if not qualified:
            raise ValueError(f"Failed to qualify contract for {self.symbol}")
        
        contract = qualified[0]

        logger.info(
            "Historical contract qualified: conId=%s symbol=%s localSymbol=%s exchange=%s primaryExchange=%s multiplier=%s",
            contract.conId,
            contract.symbol,
            contract.localSymbol,
            getattr(contract, "exchange", ""),
            getattr(contract, "primaryExchange", ""),
            getattr(contract, "multiplier", ""),
        )
        
        # Fetch historical bars
        logger.info(f"📊 Fetching {self.duration} of historical data for {self.symbol}...")
        
        bars = self.ib.reqHistoricalData(
            contract,
            endDateTime='',  # Now
            durationStr=self.duration,
            barSizeSetting=self.bar_size,
            whatToShow='TRADES',
            useRTH=True,  # Regular trading hours only
            formatDate=1,
        )
        
        if not bars:
            raise ValueError(f"No historical data received for {self.symbol}")
        
        # Convert IB bars to our Bar format
        self.bars = [
            Bar(
                timestamp=bar.date.timestamp(),
                open=bar.open,
                high=bar.high,
                low=bar.low,
                close=bar.close,
                volume=bar.volume,
                num_trades=bar.barCount if hasattr(bar, 'barCount') else 0,
                vwap=bar.average if bar.average > 0 else bar.close,
            )
            for bar in bars
        ]

        if not self._validate_bars(self.bars):
            logger.warning("Historical data validation failed for %s", self.symbol)

        gaps = self._detect_data_gaps(self.bars)
        if gaps:
            for start_ts, end_ts, gap_duration in gaps[:5]:
                logger.warning(
                    "Historical gap detected for %s: %s -> %s (%s)",
                    self.symbol,
                    datetime.fromtimestamp(start_ts),
                    datetime.fromtimestamp(end_ts),
                    gap_duration,
                )
            if len(gaps) > 5:
                logger.warning("Historical data for %s has %s additional gaps", self.symbol, len(gaps) - 5)
        
        logger.info(f"✅ Loaded {len(self.bars)} historical bars for {self.symbol}")
        # Sanity: log first/last closes to confirm raw price scales
        try:
            head = ", ".join(f"{b.close:.2f}" for b in self.bars[:3])
            tail = ", ".join(f"{b.close:.2f}" for b in self.bars[-3:])
            logger.debug(f"{self.symbol} closes head: [{head}] ... tail: [{tail}]")
            if self.bar_size == "1 min" and "1 D" in str(self.duration):
                if not (300 <= len(self.bars) <= 420):
                    logger.warning(f"Historical bars count unusual for 1D/1min RTH: {len(self.bars)}")
        except Exception:
            pass
        # Sanity: log first/last 3 closes to confirm raw price scales
        try:
            first3 = ", ".join(f"{b.close:.2f}" for b in self.bars[:3])
            last3 = ", ".join(f"{b.close:.2f}" for b in self.bars[-3:])
            logger.debug(f"{self.symbol} closes head: [{first3}] ... tail: [{last3}]")
        except Exception:
            pass
        
        self._is_running = True
        self._stop_requested = False

        # Start replay in background thread so caller can proceed immediately
        def _launch_replay():
            try:
                self._replay_bars()
            except Exception as exc:
                logger.exception(f"Historical replay error for {self.symbol}: {exc}")
            finally:
                self._is_running = False

        self._thread = threading.Thread(
            target=_launch_replay,
            name=f"HistoricalReplay-{self.symbol}",
            daemon=True,
        )
        self._thread.start()
    
    def stop(self):
        """Stop replay."""
        self._stop_requested = True
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        self._thread = None
        self._is_running = False
        logger.info(f"⏹️ Stopped historical replay for {self.symbol}")
    
    def is_running(self) -> bool:
        return self._is_running
    
    def _replay_bars(self):
        """Replay bars as simulated ticks."""
        for bar in self.bars:
            if self._stop_requested:
                break
            
            # Generate ticks within this bar
            ticks = self._bar_to_ticks(bar, num_ticks=20)
            
            for tick in ticks:
                if self._stop_requested:
                    break
                
                self.tick_callback(tick)
                
                # Sleep to simulate real-time (adjusted by replay_speed)
                time.sleep(0.05 / self.replay_speed)  # 50ms per tick
        
        logger.info(f"📺 Replay complete: {len(self.bars)} bars processed")
        self._is_running = False
    
    def _bar_to_ticks(self, bar: Bar, num_ticks: int = 20) -> List[TickData]:
        """Generate a richer tick stream from a historical bar."""
        num_ticks = max(6, num_ticks)
        paths = self._generate_price_paths(bar, num_paths=3, ticks_per_path=max(3, num_ticks // 3))

        ticks: List[TickData] = []
        total_volume = max(int(bar.volume), num_ticks)
        volume_per_tick = total_volume / float(num_ticks)
        base_timestamp = bar.timestamp

        for path_idx, price_path in enumerate(paths):
            base_spread = self._calculate_dynamic_spread(bar, path_idx)
            for tick_idx, mid_price in enumerate(price_path):
                spread = base_spread * (1.0 + 0.5 * random.random())
                bid, ask, bid_size, ask_size = self._simulate_market_depth(mid_price, spread, volume_per_tick)

                if tick_idx > 0:
                    momentum = mid_price - price_path[tick_idx - 1]
                else:
                    momentum = (price_path[1] - price_path[0]) if len(price_path) > 1 else bar.close - bar.open

                trade_price = self._select_trade_price(bid, ask, momentum)

                tick = TickData(
                    timestamp=base_timestamp + ((path_idx * len(price_path)) + tick_idx) * 3.0,
                    price=float(trade_price),
                    size=max(1, int(volume_per_tick * random.uniform(0.5, 1.5))),
                    bid=bid,
                    ask=ask,
                    bid_size=bid_size,
                    ask_size=ask_size,
                )
                ticks.append(tick)

        return ticks

    def _generate_price_paths(self, bar: Bar, num_paths: int, ticks_per_path: int) -> List[List[float]]:
        paths: List[List[float]] = []
        volatility = self._estimate_bar_volatility(bar)
        ticks_per_path = max(3, ticks_per_path)

        for _ in range(num_paths):
            path = [bar.open]
            for i in range(1, ticks_per_path):
                progress = i / (ticks_per_path - 1)
                target = bar.open + (bar.close - bar.open) * progress
                noise = np.random.normal(0, volatility * 0.1)
                next_price = path[-1] + (target - path[-1]) * 0.3 + noise
                next_price = max(bar.low * 0.9995, min(bar.high * 1.0005, next_price))
                path.append(next_price)

            if random.random() < 0.3 and len(path) > 2:
                path[random.randint(1, len(path) - 2)] = bar.high
                path[random.randint(1, len(path) - 2)] = bar.low

            paths.append(path)

        return paths

    def _estimate_bar_volatility(self, bar: Bar) -> float:
        ref = max(bar.low, 1.0)
        return max((bar.high - bar.low) / ref, 0.0005)

    def _calculate_dynamic_spread(self, bar: Bar, path_idx: int) -> float:
        volatility = self._estimate_bar_volatility(bar)
        base_spread = max(0.005, min(0.05, volatility * 120))
        return base_spread * (1.0 + path_idx * 0.1)

    def _simulate_market_depth(self, mid_price: float, spread: float, volume_hint: float) -> tuple[float, float, int, int]:
        bid = float(mid_price - spread / 2)
        ask = float(mid_price + spread / 2)
        depth_base = max(100, int(volume_hint))
        bid_size = int(depth_base * random.uniform(0.8, 1.2))
        ask_size = int(depth_base * random.uniform(0.8, 1.2))
        return bid, ask, bid_size, ask_size

    def _select_trade_price(self, bid: float, ask: float, momentum: float) -> float:
        mid = (ask + bid) / 2
        if momentum > 0 and random.random() < 0.7:
            return ask
        if momentum < 0 and random.random() < 0.7:
            return bid
        return mid

    def _validate_bars(self, bars: List[Bar]) -> bool:
        if not bars:
            return False

        timestamps = np.array([b.timestamp for b in bars])
        if np.any(np.diff(timestamps) <= 0):
            logger.warning("Historical bars for %s have non-monotonic timestamps", self.symbol)

        for bar in bars[:500]:
            if not (bar.low <= bar.open <= bar.high and bar.low <= bar.close <= bar.high):
                logger.warning("Invalid bar encountered for %s: %s", self.symbol, bar)
                return False
            if bar.low <= 0 or bar.volume < 0:
                logger.warning("Non-positive values in bar for %s: %s", self.symbol, bar)
                return False
        return True

    def _detect_data_gaps(self, bars: List[Bar]) -> List[tuple]:
        gaps: List[tuple] = []
        expected_interval = 60
        for idx in range(1, len(bars)):
            time_diff = bars[idx].timestamp - bars[idx - 1].timestamp
            if time_diff > expected_interval * 1.5:
                gap_duration = timedelta(seconds=time_diff - expected_interval)
                gaps.append((bars[idx - 1].timestamp, bars[idx].timestamp, gap_duration))
        return gaps


class SimulatedDataSource(DataSource):
    """
    Generate synthetic tick data for testing.
    
    Creates realistic price movements with:
    - Random walk with drift
    - Intraday volatility patterns
    - Bid-ask spread simulation
    
    Works 24/7, no IBKR connection required.
    """
    
    def __init__(
        self,
        symbol: str,
        tick_callback: Callable[[TickData], None],
        initial_price: float = 580.0,  # Starting price (e.g., SPY ~$580)
        tick_interval: float = 0.05,  # Generate tick every 50ms
        volatility: float = 0.0001,  # Per-tick volatility
        drift: float = 0.00001,  # Upward drift per tick
    ):
        self.symbol = symbol
        self.tick_callback = tick_callback
        self.initial_price = initial_price
        self.tick_interval = tick_interval
        self.volatility = volatility
        self.drift = drift
        
        self.current_price = initial_price
        self._is_running = False
        self._stop_requested = False
    
    def start(self):
        """Start generating ticks."""
        if self._is_running:
            logger.warning(f"Simulated feed for {self.symbol} already running")
            return
        
        self._is_running = True
        self._stop_requested = False
        
        logger.info(f"✅ Started simulated data feed for {self.symbol} at ${self.initial_price:.2f}")
        
        # Generate ticks in background
        self._generate_ticks()
    
    def stop(self):
        """Stop generating ticks."""
        self._stop_requested = True
        self._is_running = False
        logger.info(f"⏹️ Stopped simulated feed for {self.symbol}")
    
    def is_running(self) -> bool:
        return self._is_running
    
    def _generate_ticks(self):
        """Generate synthetic ticks indefinitely."""
        tick_count = 0
        
        while not self._stop_requested:
            # Random walk with drift
            change = np.random.normal(self.drift, self.volatility)
            self.current_price *= (1 + change)
            
            # Keep price positive
            self.current_price = max(self.current_price, 1.0)
            
            # Simulate bid-ask spread (0.01-0.02%)
            spread_pct = random.uniform(0.0001, 0.0002)
            spread = self.current_price * spread_pct
            
            # Generate tick
            tick = TickData(
                timestamp=time.time(),
                price=self.current_price,
                size=random.randint(10, 500),
                bid=self.current_price - spread / 2,
                ask=self.current_price + spread / 2,
                bid_size=random.randint(100, 1000),
                ask_size=random.randint(100, 1000),
            )
            
            self.tick_callback(tick)
            
            tick_count += 1
            
            # Log progress every 1000 ticks
            if tick_count % 1000 == 0:
                logger.debug(f"Generated {tick_count} ticks, price=${self.current_price:.2f}")
            
            # Sleep
            time.sleep(self.tick_interval)


@dataclass
class DataSourceConfig:
    mode: str
    symbol: str
    tick_callback: Callable[[TickData], None]
    duration: str = "1 D"
    bar_size: str = "1 min"
    replay_speed: float = 1.0
    exchange: str = "SMART"
    currency: str = "USD"
    initial_price: float = 100.0
    tick_interval: float = 0.05
    volatility: float = 0.0001


class DataSourceFactory:
    """Factory for creating data sources from configuration."""

    @staticmethod
    def create_from_config(config: DataSourceConfig, ib: Optional[IB] = None) -> DataSource:
        mode = config.mode.lower()

        if mode == "live":
            if ib is None:
                raise ValueError("IB instance required for live data")
            return LiveDataSource(
                ib=ib,
                symbol=config.symbol,
                tick_callback=config.tick_callback,
                exchange=config.exchange,
                currency=config.currency,
            )

        if mode == "historical":
            if ib is None:
                raise ValueError("IB instance required for historical data")
            return HistoricalDataSource(
                ib=ib,
                symbol=config.symbol,
                tick_callback=config.tick_callback,
                duration=config.duration,
                bar_size=config.bar_size,
                replay_speed=config.replay_speed,
                exchange=config.exchange,
                currency=config.currency,
            )

        if mode == "simulated":
            return SimulatedDataSource(
                symbol=config.symbol,
                tick_callback=config.tick_callback,
                initial_price=config.initial_price,
                tick_interval=config.tick_interval,
                volatility=config.volatility,
            )

        raise ValueError(f"Unknown data source mode: {config.mode}")


if __name__ == "__main__":
    """Test data sources."""
    
    logging.basicConfig(level=logging.INFO)
    
    # Test callback
    tick_count = 0
    
    def on_tick(tick: TickData):
        global tick_count
        tick_count += 1
        if tick_count % 100 == 0:
            print(f"Tick {tick_count}: ${tick.price:.2f} | "
                  f"Bid: ${tick.bid:.2f} | Ask: ${tick.ask:.2f} | "
                  f"Spread: {tick.spread_pct * 100:.3f}%")
    
    print("="*60)
    print("Testing Simulated Data Source")
    print("="*60)
    
    # Test simulated feed
    sim_source = SimulatedDataSource(
        symbol='SPY',
        tick_callback=on_tick,
        initial_price=580.0,
        tick_interval=0.01,  # 10ms per tick (fast for testing)
    )
    
    sim_source.start()
    time.sleep(10)  # Run for 10 seconds
    sim_source.stop()
    
    print(f"\n✅ Generated {tick_count} ticks in 10 seconds")
    print(f"   Final price: ${sim_source.current_price:.2f}")
    
    print("\n" + "="*60)
    print("To test Historical or Live sources:")
    print("  1. Connect to IBKR: ib = IB(); ib.connect('127.0.0.1', 7497)")
    print("  2. Historical: HistoricalDataSource(ib, 'SPY', on_tick)")
    print("  3. Live: LiveDataSource(ib, 'SPY', on_tick)")
    print("="*60)

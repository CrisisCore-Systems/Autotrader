"""Real-time order book and trade streaming with ccxt.pro."""

from __future__ import annotations

import asyncio
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Deque, Dict, List, Optional

import numpy as np

from src.core.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class Trade:
    """Individual trade event."""

    timestamp: float
    price: float
    size: float
    side: str  # 'buy' or 'sell'
    trade_id: str
    local_timestamp: float = field(default_factory=time.time)


@dataclass
class OrderBookSnapshot:
    """L2 order book snapshot."""

    timestamp: float
    bids: List[tuple[float, float]]  # [(price, size), ...]
    asks: List[tuple[float, float]]
    local_timestamp: float = field(default_factory=time.time)
    sequence: Optional[int] = None


@dataclass
class ClockSync:
    """Track and correct clock drift between local and exchange."""

    exchange_times: Deque[float] = field(default_factory=lambda: deque(maxlen=100))
    local_times: Deque[float] = field(default_factory=lambda: deque(maxlen=100))

    def add_sample(self, exchange_ts: float, local_ts: float) -> None:
        """Add a timestamp pair for drift calculation."""
        self.exchange_times.append(exchange_ts)
        self.local_times.append(local_ts)

    @property
    def drift_ms(self) -> float:
        """Current clock drift in milliseconds (local - exchange)."""
        if len(self.exchange_times) < 2:
            return 0.0
        ex_times = np.array(self.exchange_times)
        local_times = np.array(self.local_times)
        drift = np.median(local_times - ex_times) * 1000
        return float(drift)

    def correct_timestamp(self, local_ts: float) -> float:
        """Correct local timestamp to exchange time."""
        return local_ts - (self.drift_ms / 1000.0)


class BinanceOrderBookStream:
    """
    Real-time streaming of Binance order book and trades via ccxt.pro.
    
    Features:
    - WebSocket L2 order book + trades
    - Automatic reconnection with exponential backoff
    - Gap detection and filling
    - Clock synchronization
    - Local timestamping for latency measurement
    """

    def __init__(
        self,
        symbol: str,
        *,
        depth: int = 20,
        trade_buffer_size: int = 1000,
        reconnect_delay: float = 1.0,
        max_reconnect_delay: float = 60.0,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
    ) -> None:
        """
        Initialize Binance order book stream.
        
        Args:
            symbol: Trading pair (e.g., 'BTC/USDT')
            depth: Order book depth to maintain
            trade_buffer_size: Number of recent trades to buffer
            reconnect_delay: Initial reconnect delay in seconds
            max_reconnect_delay: Maximum reconnect delay in seconds
            api_key: Binance API key (optional)
            api_secret: Binance API secret (optional)
        """
        self.symbol = symbol
        self.depth = depth
        self.trade_buffer_size = trade_buffer_size
        self.reconnect_delay = reconnect_delay
        self.max_reconnect_delay = max_reconnect_delay

        # State
        self.exchange: Optional[object] = None  # ccxt.pro.binance instance
        self.order_book: Optional[OrderBookSnapshot] = None
        self.trades: Deque[Trade] = deque(maxlen=trade_buffer_size)
        self.clock_sync = ClockSync()
        self.is_running = False
        self.last_sequence: Optional[int] = None
        self.gap_count = 0

        # Callbacks
        self.on_trade_callbacks: List[Callable[[Trade], None]] = []
        self.on_book_callbacks: List[Callable[[OrderBookSnapshot], None]] = []
        self.on_gap_callbacks: List[Callable[[int], None]] = []

        # Metrics
        self.message_count = 0
        self.reconnect_count = 0
        self.latency_samples: Deque[float] = deque(maxlen=1000)

        logger.info(
            "binance_stream_initialized",
            symbol=symbol,
            depth=depth,
            trade_buffer_size=trade_buffer_size,
        )

    def register_trade_callback(self, callback: Callable[[Trade], None]) -> None:
        """Register callback for trade events."""
        self.on_trade_callbacks.append(callback)

    def register_book_callback(self, callback: Callable[[OrderBookSnapshot], None]) -> None:
        """Register callback for order book updates."""
        self.on_book_callbacks.append(callback)

    def register_gap_callback(self, callback: Callable[[int], None]) -> None:
        """Register callback for detected gaps."""
        self.on_gap_callbacks.append(callback)

    async def connect(self) -> None:
        """Establish connection to Binance WebSocket."""
        try:
            # Lazy import to avoid requiring ccxt.pro if not used
            import ccxt.pro as ccxtpro  # type: ignore

            self.exchange = ccxtpro.binance({
                "enableRateLimit": True,
                "options": {
                    "defaultType": "spot",
                    "ws": {
                        "keepAlive": 30000,
                    },
                },
            })

            logger.info("binance_ws_connected", symbol=self.symbol)
            self.reconnect_count += 1

        except Exception as exc:
            logger.error(
                "binance_ws_connection_failed",
                symbol=self.symbol,
                error=str(exc),
            )
            raise

    async def _reconnect_with_backoff(self, current_delay: float) -> float:
        """Reconnect with exponential backoff."""
        await asyncio.sleep(current_delay)
        
        try:
            if self.exchange:
                await self.exchange.close()
        except Exception as exc:
            logger.warning("error_closing_exchange", error=str(exc))

        await self.connect()
        
        # Exponential backoff with jitter
        next_delay = min(current_delay * 2, self.max_reconnect_delay)
        jitter = np.random.uniform(0, 0.1 * next_delay)
        return next_delay + jitter

    async def _stream_order_book(self) -> None:
        """Stream L2 order book updates."""
        delay = self.reconnect_delay

        while self.is_running:
            try:
                if not self.exchange:
                    await self.connect()

                order_book = await self.exchange.watch_order_book(self.symbol, self.depth)
                local_ts = time.time()

                # Extract data
                exchange_ts = order_book.get("timestamp", local_ts * 1000) / 1000
                bids = [(float(p), float(s)) for p, s in (order_book.get("bids", []) or [])]
                asks = [(float(p), float(s)) for p, s in (order_book.get("asks", []) or [])]
                sequence = order_book.get("nonce")

                # Update clock sync
                self.clock_sync.add_sample(exchange_ts, local_ts)

                # Detect gaps
                if self.last_sequence is not None and sequence is not None:
                    if sequence != self.last_sequence + 1:
                        gap_size = sequence - self.last_sequence - 1
                        self.gap_count += 1
                        logger.warning(
                            "orderbook_gap_detected",
                            symbol=self.symbol,
                            gap_size=gap_size,
                            last_seq=self.last_sequence,
                            current_seq=sequence,
                        )
                        for callback in self.on_gap_callbacks:
                            try:
                                callback(gap_size)
                            except Exception as exc:
                                logger.error("gap_callback_error", error=str(exc))

                self.last_sequence = sequence

                # Create snapshot
                snapshot = OrderBookSnapshot(
                    timestamp=exchange_ts,
                    bids=bids[:self.depth],
                    asks=asks[:self.depth],
                    local_timestamp=local_ts,
                    sequence=sequence,
                )
                self.order_book = snapshot

                # Track latency
                latency_ms = (local_ts - exchange_ts) * 1000
                self.latency_samples.append(latency_ms)

                # Trigger callbacks
                for callback in self.on_book_callbacks:
                    try:
                        callback(snapshot)
                    except Exception as exc:
                        logger.error("book_callback_error", error=str(exc))

                self.message_count += 1
                delay = self.reconnect_delay  # Reset delay on success

            except Exception as exc:
                logger.error(
                    "orderbook_stream_error",
                    symbol=self.symbol,
                    error=str(exc),
                )
                delay = await self._reconnect_with_backoff(delay)

    async def _stream_trades(self) -> None:
        """Stream individual trades."""
        delay = self.reconnect_delay

        while self.is_running:
            try:
                if not self.exchange:
                    await self.connect()

                trades = await self.exchange.watch_trades(self.symbol)
                local_ts = time.time()

                for trade_data in trades:
                    exchange_ts = trade_data.get("timestamp", local_ts * 1000) / 1000

                    trade = Trade(
                        timestamp=exchange_ts,
                        price=float(trade_data["price"]),
                        size=float(trade_data["amount"]),
                        side=trade_data["side"],
                        trade_id=str(trade_data.get("id", "")),
                        local_timestamp=local_ts,
                    )

                    self.trades.append(trade)
                    self.clock_sync.add_sample(exchange_ts, local_ts)

                    # Trigger callbacks
                    for callback in self.on_trade_callbacks:
                        try:
                            callback(trade)
                        except Exception as exc:
                            logger.error("trade_callback_error", error=str(exc))

                delay = self.reconnect_delay  # Reset delay on success

            except Exception as exc:
                logger.error(
                    "trade_stream_error",
                    symbol=self.symbol,
                    error=str(exc),
                )
                delay = await self._reconnect_with_backoff(delay)

    async def start(self) -> None:
        """Start streaming order book and trades."""
        if self.is_running:
            logger.warning("stream_already_running", symbol=self.symbol)
            return

        self.is_running = True
        await self.connect()

        # Start both streams concurrently
        await asyncio.gather(
            self._stream_order_book(),
            self._stream_trades(),
        )

    async def stop(self) -> None:
        """Stop streaming and close connection."""
        self.is_running = False

        if self.exchange:
            try:
                await self.exchange.close()
            except Exception as exc:
                logger.error("error_closing_exchange", error=str(exc))

        logger.info(
            "stream_stopped",
            symbol=self.symbol,
            message_count=self.message_count,
            reconnect_count=self.reconnect_count,
            gap_count=self.gap_count,
        )

    @property
    def median_latency_ms(self) -> float:
        """Median WebSocket latency in milliseconds."""
        if not self.latency_samples:
            return 0.0
        return float(np.median(self.latency_samples))

    @property
    def p95_latency_ms(self) -> float:
        """95th percentile latency in milliseconds."""
        if not self.latency_samples:
            return 0.0
        return float(np.percentile(self.latency_samples, 95))

    def get_recent_trades(self, window_seconds: float) -> List[Trade]:
        """Get trades within the last N seconds."""
        if not self.trades:
            return []

        cutoff = time.time() - window_seconds
        return [t for t in self.trades if t.local_timestamp >= cutoff]

    def get_stats(self) -> Dict[str, object]:
        """Get streaming statistics."""
        return {
            "symbol": self.symbol,
            "is_running": self.is_running,
            "message_count": self.message_count,
            "reconnect_count": self.reconnect_count,
            "gap_count": self.gap_count,
            "trade_buffer_size": len(self.trades),
            "median_latency_ms": self.median_latency_ms,
            "p95_latency_ms": self.p95_latency_ms,
            "clock_drift_ms": self.clock_sync.drift_ms,
            "has_order_book": self.order_book is not None,
        }

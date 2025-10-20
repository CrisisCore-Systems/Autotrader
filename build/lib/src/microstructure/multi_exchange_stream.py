"""Multi-exchange real-time order book and trade streaming."""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Callable, Deque, Dict, List, Optional

import numpy as np

from src.core.logging_config import get_logger
from src.microstructure.stream import (
    Trade,
    OrderBookSnapshot,
    ClockSync,
    BinanceOrderBookStream,
)

logger = get_logger(__name__)


class BybitOrderBookStream:
    """
    Real-time streaming of Bybit order book and trades via ccxt.pro.
    
    Features:
    - WebSocket L2 order book + trades
    - Automatic reconnection with exponential backoff
    - Clock synchronization
    - Supports linear perpetuals and spot markets
    """

    def __init__(
        self,
        symbol: str,
        *,
        depth: int = 20,
        trade_buffer_size: int = 1000,
        reconnect_delay: float = 1.0,
        max_reconnect_delay: float = 60.0,
        market_type: str = "linear",  # 'linear' or 'spot'
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
    ) -> None:
        """
        Initialize Bybit order book stream.

        Args:
            symbol: Trading pair symbol (e.g., "BTC/USDT:USDT" for linear perpetual)
            depth: Order book depth to fetch
            trade_buffer_size: Size of trade history buffer
            reconnect_delay: Initial reconnection delay in seconds
            max_reconnect_delay: Maximum reconnection delay
            market_type: Market type ('linear' for perpetuals, 'spot' for spot)
            api_key: Optional Bybit API key
            api_secret: Optional Bybit API secret
        """
        self.symbol = symbol
        self.depth = depth
        self.trade_buffer_size = trade_buffer_size
        self.reconnect_delay = reconnect_delay
        self.max_reconnect_delay = max_reconnect_delay
        self.market_type = market_type

        # Connection state
        self.exchange = None
        self.is_running = False
        self.reconnect_count = 0

        # Data buffers
        self.trades: Deque[Trade] = deque(maxlen=trade_buffer_size)
        self.clock_sync = ClockSync()

        # Callbacks
        self.on_trade_callbacks: List[Callable[[Trade], None]] = []
        self.on_book_callbacks: List[Callable[[OrderBookSnapshot], None]] = []

        # Stats
        self.latency_samples: Deque[float] = deque(maxlen=1000)

        # Credentials
        self._api_key = api_key
        self._api_secret = api_secret

    def register_trade_callback(self, callback: Callable[[Trade], None]) -> None:
        """Register callback for trade events."""
        self.on_trade_callbacks.append(callback)

    def register_book_callback(self, callback: Callable[[OrderBookSnapshot], None]) -> None:
        """Register callback for order book updates."""
        self.on_book_callbacks.append(callback)

    async def connect(self) -> None:
        """Establish connection to Bybit WebSocket."""
        try:
            import ccxt.pro as ccxtpro

            config = {
                "enableRateLimit": True,
                "options": {
                    "defaultType": self.market_type,
                    "ws": {
                        "keepAlive": 30000,
                    },
                },
            }

            if self._api_key and self._api_secret:
                config["apiKey"] = self._api_key
                config["secret"] = self._api_secret

            self.exchange = ccxtpro.bybit(config)

            logger.info(
                "bybit_ws_connected",
                symbol=self.symbol,
                market_type=self.market_type,
            )
            self.reconnect_count += 1

        except Exception as exc:
            logger.error(
                "bybit_ws_connection_failed",
                symbol=self.symbol,
                error=str(exc),
            )
            raise

    async def _reconnect_with_backoff(self, current_delay: float) -> float:
        """Reconnect with exponential backoff."""
        logger.warning(
            "bybit_ws_reconnecting",
            symbol=self.symbol,
            delay=current_delay,
            attempt=self.reconnect_count,
        )
        await asyncio.sleep(current_delay)

        try:
            if self.exchange:
                await self.exchange.close()
        except Exception:
            pass

        await self.connect()
        return min(current_delay * 2, self.max_reconnect_delay)

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

                # Update clock sync
                self.clock_sync.add_sample(exchange_ts, local_ts)

                # Calculate latency
                latency_ms = (local_ts - exchange_ts) * 1000
                self.latency_samples.append(latency_ms)

                # Create snapshot
                snapshot = OrderBookSnapshot(
                    timestamp=exchange_ts,
                    bids=bids,
                    asks=asks,
                    local_timestamp=local_ts,
                )

                # Trigger callbacks
                for callback in self.on_book_callbacks:
                    try:
                        callback(snapshot)
                    except Exception as exc:
                        logger.error("book_callback_error", error=str(exc))

                # Reset delay on success
                delay = self.reconnect_delay

            except Exception as exc:
                logger.error("bybit_orderbook_error", symbol=self.symbol, error=str(exc))
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

                delay = self.reconnect_delay

            except Exception as exc:
                logger.error("bybit_trades_error", symbol=self.symbol, error=str(exc))
                delay = await self._reconnect_with_backoff(delay)

    async def start(self) -> None:
        """Start streaming order book and trades."""
        if self.is_running:
            logger.warning("bybit_stream_already_running", symbol=self.symbol)
            return

        self.is_running = True
        await asyncio.gather(
            self._stream_order_book(),
            self._stream_trades(),
        )

    async def stop(self) -> None:
        """Stop streaming and close connection."""
        self.is_running = False
        if self.exchange:
            await self.exchange.close()
            self.exchange = None
        logger.info("bybit_stream_stopped", symbol=self.symbol)

    @property
    def median_latency_ms(self) -> float:
        """Median WebSocket latency in milliseconds."""
        if not self.latency_samples:
            return 0.0
        return float(np.median(list(self.latency_samples)))

    @property
    def p95_latency_ms(self) -> float:
        """95th percentile WebSocket latency in milliseconds."""
        if not self.latency_samples:
            return 0.0
        return float(np.percentile(list(self.latency_samples), 95))

    def get_stats(self) -> Dict:
        """Get stream statistics."""
        return {
            "symbol": self.symbol,
            "market_type": self.market_type,
            "reconnect_count": self.reconnect_count,
            "trade_count": len(self.trades),
            "median_latency_ms": self.median_latency_ms,
            "p95_latency_ms": self.p95_latency_ms,
            "clock_drift_ms": self.clock_sync.get_drift_ms(),
        }


class CoinbaseOrderBookStream:
    """
    Real-time streaming of Coinbase order book and trades via ccxt.pro.
    
    Features:
    - WebSocket L2 order book + trades
    - Automatic reconnection with exponential backoff
    - Clock synchronization
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
        api_password: Optional[str] = None,
    ) -> None:
        """
        Initialize Coinbase order book stream.

        Args:
            symbol: Trading pair symbol (e.g., "BTC/USD")
            depth: Order book depth to fetch
            trade_buffer_size: Size of trade history buffer
            reconnect_delay: Initial reconnection delay in seconds
            max_reconnect_delay: Maximum reconnection delay
            api_key: Optional Coinbase API key
            api_secret: Optional Coinbase API secret
            api_password: Optional Coinbase API password
        """
        self.symbol = symbol
        self.depth = depth
        self.trade_buffer_size = trade_buffer_size
        self.reconnect_delay = reconnect_delay
        self.max_reconnect_delay = max_reconnect_delay

        # Connection state
        self.exchange = None
        self.is_running = False
        self.reconnect_count = 0

        # Data buffers
        self.trades: Deque[Trade] = deque(maxlen=trade_buffer_size)
        self.clock_sync = ClockSync()

        # Callbacks
        self.on_trade_callbacks: List[Callable[[Trade], None]] = []
        self.on_book_callbacks: List[Callable[[OrderBookSnapshot], None]] = []

        # Stats
        self.latency_samples: Deque[float] = deque(maxlen=1000)

        # Credentials
        self._api_key = api_key
        self._api_secret = api_secret
        self._api_password = api_password

    def register_trade_callback(self, callback: Callable[[Trade], None]) -> None:
        """Register callback for trade events."""
        self.on_trade_callbacks.append(callback)

    def register_book_callback(self, callback: Callable[[OrderBookSnapshot], None]) -> None:
        """Register callback for order book updates."""
        self.on_book_callbacks.append(callback)

    async def connect(self) -> None:
        """Establish connection to Coinbase WebSocket."""
        try:
            import ccxt.pro as ccxtpro

            config = {
                "enableRateLimit": True,
                "options": {
                    "ws": {
                        "keepAlive": 30000,
                    },
                },
            }

            if self._api_key and self._api_secret:
                config["apiKey"] = self._api_key
                config["secret"] = self._api_secret
                if self._api_password:
                    config["password"] = self._api_password

            self.exchange = ccxtpro.coinbase(config)

            logger.info("coinbase_ws_connected", symbol=self.symbol)
            self.reconnect_count += 1

        except Exception as exc:
            logger.error(
                "coinbase_ws_connection_failed",
                symbol=self.symbol,
                error=str(exc),
            )
            raise

    async def _reconnect_with_backoff(self, current_delay: float) -> float:
        """Reconnect with exponential backoff."""
        logger.warning(
            "coinbase_ws_reconnecting",
            symbol=self.symbol,
            delay=current_delay,
            attempt=self.reconnect_count,
        )
        await asyncio.sleep(current_delay)

        try:
            if self.exchange:
                await self.exchange.close()
        except Exception:
            pass

        await self.connect()
        return min(current_delay * 2, self.max_reconnect_delay)

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

                # Update clock sync
                self.clock_sync.add_sample(exchange_ts, local_ts)

                # Calculate latency
                latency_ms = (local_ts - exchange_ts) * 1000
                self.latency_samples.append(latency_ms)

                # Create snapshot
                snapshot = OrderBookSnapshot(
                    timestamp=exchange_ts,
                    bids=bids,
                    asks=asks,
                    local_timestamp=local_ts,
                )

                # Trigger callbacks
                for callback in self.on_book_callbacks:
                    try:
                        callback(snapshot)
                    except Exception as exc:
                        logger.error("book_callback_error", error=str(exc))

                # Reset delay on success
                delay = self.reconnect_delay

            except Exception as exc:
                logger.error("coinbase_orderbook_error", symbol=self.symbol, error=str(exc))
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

                delay = self.reconnect_delay

            except Exception as exc:
                logger.error("coinbase_trades_error", symbol=self.symbol, error=str(exc))
                delay = await self._reconnect_with_backoff(delay)

    async def start(self) -> None:
        """Start streaming order book and trades."""
        if self.is_running:
            logger.warning("coinbase_stream_already_running", symbol=self.symbol)
            return

        self.is_running = True
        await asyncio.gather(
            self._stream_order_book(),
            self._stream_trades(),
        )

    async def stop(self) -> None:
        """Stop streaming and close connection."""
        self.is_running = False
        if self.exchange:
            await self.exchange.close()
            self.exchange = None
        logger.info("coinbase_stream_stopped", symbol=self.symbol)

    @property
    def median_latency_ms(self) -> float:
        """Median WebSocket latency in milliseconds."""
        if not self.latency_samples:
            return 0.0
        return float(np.median(list(self.latency_samples)))

    @property
    def p95_latency_ms(self) -> float:
        """95th percentile WebSocket latency in milliseconds."""
        if not self.latency_samples:
            return 0.0
        return float(np.percentile(list(self.latency_samples), 95))

    def get_stats(self) -> Dict:
        """Get stream statistics."""
        return {
            "symbol": self.symbol,
            "reconnect_count": self.reconnect_count,
            "trade_count": len(self.trades),
            "median_latency_ms": self.median_latency_ms,
            "p95_latency_ms": self.p95_latency_ms,
            "clock_drift_ms": self.clock_sync.get_drift_ms(),
        }


class MultiExchangeAggregator:
    """
    Aggregates order book and trade data from multiple exchanges.
    
    Detects cross-exchange opportunities and arbitrage.
    """

    def __init__(self, exchanges: Dict[str, any]) -> None:
        """
        Initialize multi-exchange aggregator.

        Args:
            exchanges: Dict mapping exchange names to stream instances
        """
        self.exchanges = exchanges
        self.order_books: Dict[str, OrderBookSnapshot] = {}
        self.last_update: Dict[str, float] = {}

        # Register callbacks for each exchange
        for exchange_name, stream in exchanges.items():
            stream.register_book_callback(
                lambda snapshot, name=exchange_name: self._on_book_update(name, snapshot)
            )

    def _on_book_update(self, exchange_name: str, snapshot: OrderBookSnapshot) -> None:
        """Handle order book update from an exchange."""
        self.order_books[exchange_name] = snapshot
        self.last_update[exchange_name] = time.time()

    def get_best_bid_ask(self) -> Dict[str, Dict[str, float]]:
        """Get best bid/ask across all exchanges."""
        result = {}
        for exchange_name, book in self.order_books.items():
            if book.bids and book.asks:
                result[exchange_name] = {
                    "best_bid": book.bids[0][0],
                    "best_ask": book.asks[0][0],
                    "bid_size": book.bids[0][1],
                    "ask_size": book.asks[0][1],
                    "spread": book.asks[0][0] - book.bids[0][0],
                    "timestamp": book.timestamp,
                }
        return result

    def get_arbitrage_opportunities(self, min_profit_bps: float = 5.0) -> List[Dict]:
        """
        Detect arbitrage opportunities across exchanges.

        Args:
            min_profit_bps: Minimum profit in basis points to report

        Returns:
            List of arbitrage opportunities
        """
        opportunities = []
        best_bids_asks = self.get_best_bid_ask()

        # Find all pairs where we can buy on one exchange and sell on another
        exchanges = list(best_bids_asks.keys())
        for i, buy_exchange in enumerate(exchanges):
            for sell_exchange in exchanges[i + 1 :]:
                buy_price = best_bids_asks[buy_exchange]["best_ask"]
                sell_price = best_bids_asks[sell_exchange]["best_bid"]

                # Check if profitable to buy on buy_exchange and sell on sell_exchange
                profit_bps = ((sell_price / buy_price) - 1) * 10000

                if profit_bps >= min_profit_bps:
                    opportunities.append({
                        "buy_exchange": buy_exchange,
                        "sell_exchange": sell_exchange,
                        "buy_price": buy_price,
                        "sell_price": sell_price,
                        "profit_bps": profit_bps,
                        "buy_size": best_bids_asks[buy_exchange]["ask_size"],
                        "sell_size": best_bids_asks[sell_exchange]["bid_size"],
                        "timestamp": max(
                            best_bids_asks[buy_exchange]["timestamp"],
                            best_bids_asks[sell_exchange]["timestamp"],
                        ),
                    })

                # Check reverse direction
                profit_bps_reverse = ((buy_price / sell_price) - 1) * 10000

                if profit_bps_reverse >= min_profit_bps:
                    opportunities.append({
                        "buy_exchange": sell_exchange,
                        "sell_exchange": buy_exchange,
                        "buy_price": best_bids_asks[sell_exchange]["best_ask"],
                        "sell_price": best_bids_asks[buy_exchange]["best_bid"],
                        "profit_bps": profit_bps_reverse,
                        "buy_size": best_bids_asks[sell_exchange]["ask_size"],
                        "sell_size": best_bids_asks[buy_exchange]["bid_size"],
                        "timestamp": max(
                            best_bids_asks[buy_exchange]["timestamp"],
                            best_bids_asks[sell_exchange]["timestamp"],
                        ),
                    })

        return sorted(opportunities, key=lambda x: x["profit_bps"], reverse=True)

    async def start_all(self) -> None:
        """Start all exchange streams."""
        await asyncio.gather(*[stream.start() for stream in self.exchanges.values()])

    async def stop_all(self) -> None:
        """Stop all exchange streams."""
        await asyncio.gather(*[stream.stop() for stream in self.exchanges.values()])

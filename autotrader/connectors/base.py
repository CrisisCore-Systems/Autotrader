"""Base connector interface for market data ingestion."""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from collections import deque
from typing import Any, Callable, Optional

from prometheus_client import Counter, Histogram

from autotrader.schemas.market_data import Depth, Tick

logger = logging.getLogger(__name__)

# Prometheus metrics
ingestion_ticks_total = Counter(
    'ingestion_ticks_total',
    'Total ticks ingested',
    ['venue', 'symbol', 'asset_class']
)

ingestion_latency_seconds = Histogram(
    'ingestion_latency_seconds',
    'End-to-end ingestion latency',
    ['venue', 'asset_class'],
    buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0]
)

connector_errors_total = Counter(
    'connector_errors_total',
    'Connector error count',
    ['venue', 'error_type']
)

websocket_reconnects_total = Counter(
    'websocket_reconnects_total',
    'WebSocket reconnection count',
    ['venue']
)


class MarketDataConnector(ABC):
    """
    Abstract base class for market data connectors.
    
    All venue-specific connectors (IBKR, Binance, Oanda, etc.) inherit from this
    and implement the abstract methods for connection, subscription, and data handling.
    """
    
    def __init__(
        self,
        venue: str,
        buffer_size: int = 1000,
        flush_interval_seconds: float = 1.0
    ):
        """
        Initialize connector.
        
        Args:
            venue: Exchange/broker identifier (e.g., 'BINANCE', 'IBKR')
            buffer_size: Local buffer size before flushing to storage
            flush_interval_seconds: Maximum time between flushes
        """
        self.venue = venue
        self.buffer_size = buffer_size
        self.flush_interval = flush_interval_seconds
        
        self.tick_buffer: deque[Tick] = deque(maxlen=buffer_size)
        self.depth_buffer: deque[Depth] = deque(maxlen=buffer_size)
        
        self._connected = False
        self._running = False
        self._flush_task: Optional[asyncio.Task] = None
        
        # Callbacks for tick and depth updates
        self._tick_callbacks: list[Callable[[Tick], None]] = []
        self._depth_callbacks: list[Callable[[Depth], None]] = []
    
    @abstractmethod
    async def connect(self) -> None:
        """Establish connection to the data source."""
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """Close connection gracefully."""
        pass
    
    @abstractmethod
    async def subscribe(self, symbols: list[str]) -> None:
        """
        Subscribe to market data for given symbols.
        
        Args:
            symbols: List of symbols to subscribe to (venue-specific format)
        """
        pass
    
    @abstractmethod
    async def unsubscribe(self, symbols: list[str]) -> None:
        """
        Unsubscribe from market data.
        
        Args:
            symbols: List of symbols to unsubscribe from
        """
        pass
    
    def register_tick_callback(self, callback: Callable[[Tick], None]) -> None:
        """Register a callback for tick updates."""
        self._tick_callbacks.append(callback)
    
    def register_depth_callback(self, callback: Callable[[Depth], None]) -> None:
        """Register a callback for depth updates."""
        self._depth_callbacks.append(callback)
    
    async def on_tick(self, tick: Tick) -> None:
        """
        Handle incoming tick data.
        
        Subclasses call this method when new tick data arrives.
        """
        # Record metrics
        ingestion_ticks_total.labels(
            venue=self.venue,
            symbol=tick.symbol,
            asset_class=tick.asset_class.value
        ).inc()
        
        if tick.exchange_time_us:
            latency = (tick.event_time_us - tick.exchange_time_us) / 1_000_000
            ingestion_latency_seconds.labels(
                venue=self.venue,
                asset_class=tick.asset_class.value
            ).observe(latency)
        
        # Add to buffer
        self.tick_buffer.append(tick)
        
        # Trigger callbacks
        for callback in self._tick_callbacks:
            try:
                callback(tick)
            except Exception as e:
                logger.error(f"Error in tick callback: {e}")
        
        # Flush if buffer full
        if len(self.tick_buffer) >= self.buffer_size:
            await self.flush_ticks()
    
    async def on_depth(self, depth: Depth) -> None:
        """
        Handle incoming depth data.
        
        Subclasses call this method when new order book data arrives.
        """
        self.depth_buffer.append(depth)
        
        # Trigger callbacks
        for callback in self._depth_callbacks:
            try:
                callback(depth)
            except Exception as e:
                logger.error(f"Error in depth callback: {e}")
        
        # Flush if buffer full
        if len(self.depth_buffer) >= self.buffer_size:
            await self.flush_depth()
    
    async def flush_ticks(self) -> None:
        """Flush tick buffer to storage."""
        if not self.tick_buffer:
            return
        
        ticks = list(self.tick_buffer)
        self.tick_buffer.clear()
        
        try:
            await self._write_ticks(ticks)
            logger.debug(f"Flushed {len(ticks)} ticks to storage")
        except Exception as e:
            logger.error(f"Failed to flush ticks: {e}")
            connector_errors_total.labels(
                venue=self.venue,
                error_type='flush_error'
            ).inc()
    
    async def flush_depth(self) -> None:
        """Flush depth buffer to storage."""
        if not self.depth_buffer:
            return
        
        depths = list(self.depth_buffer)
        self.depth_buffer.clear()
        
        try:
            await self._write_depth(depths)
            logger.debug(f"Flushed {len(depths)} depth snapshots to storage")
        except Exception as e:
            logger.error(f"Failed to flush depth: {e}")
            connector_errors_total.labels(
                venue=self.venue,
                error_type='flush_error'
            ).inc()
    
    @abstractmethod
    async def _write_ticks(self, ticks: list[Tick]) -> None:
        """Write ticks to storage (ClickHouse, Parquet, etc.)."""
        pass
    
    @abstractmethod
    async def _write_depth(self, depths: list[Depth]) -> None:
        """Write depth snapshots to storage."""
        pass
    
    async def _periodic_flush(self) -> None:
        """Periodically flush buffers even if not full."""
        while self._running:
            await asyncio.sleep(self.flush_interval)
            if self.tick_buffer:
                await self.flush_ticks()
            if self.depth_buffer:
                await self.flush_depth()
    
    async def start(self) -> None:
        """Start the connector and periodic flush task."""
        if self._running:
            logger.warning(f"{self.venue} connector already running")
            return
        
        self._running = True
        await self.connect()
        self._flush_task = asyncio.create_task(self._periodic_flush())
        logger.info(f"{self.venue} connector started")
    
    async def stop(self) -> None:
        """Stop the connector and flush remaining data."""
        if not self._running:
            return
        
        self._running = False
        
        # Cancel flush task
        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass
        
        # Final flush
        await self.flush_ticks()
        await self.flush_depth()
        
        # Disconnect
        await self.disconnect()
        logger.info(f"{self.venue} connector stopped")
    
    def is_connected(self) -> bool:
        """Check if connector is connected."""
        return self._connected
    
    def handle_error(self, error_type: str, error: Exception) -> None:
        """Record error metrics and log."""
        connector_errors_total.labels(
            venue=self.venue,
            error_type=error_type
        ).inc()
        logger.error(f"{self.venue} {error_type}: {error}")

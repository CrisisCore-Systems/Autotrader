"""Binance WebSocket connector for crypto market data."""

from __future__ import annotations

import asyncio
import json
import time
from typing import Optional

import websockets

from autotrader.connectors.base import MarketDataConnector, websocket_reconnects_total
from autotrader.schemas.market_data import AssetClass, Depth, DepthLevel, Side, Tick

import logging

logger = logging.getLogger(__name__)


class BinanceConnector(MarketDataConnector):
    """
    Binance WebSocket connector for real-time crypto data.
    
    Supports trades and order book (L2 depth) streams.
    """
    
    def __init__(
        self,
        symbols: Optional[list[str]] = None,
        stream_type: str = "trade",  # 'trade' or 'depth'
        buffer_size: int = 1000,
        flush_interval_seconds: float = 1.0
    ):
        """
        Initialize Binance connector.
        
        Args:
            symbols: List of trading pairs (e.g., ['BTCUSDT', 'ETHUSDT'])
            stream_type: 'trade' for tick data, 'depth' for order book
            buffer_size: Local buffer size
            flush_interval_seconds: Flush interval
        """
        super().__init__(venue="BINANCE", buffer_size=buffer_size, flush_interval_seconds=flush_interval_seconds)
        
        self.symbols = symbols or []
        self.stream_type = stream_type
        self.ws_url = "wss://stream.binance.com:9443/stream"
        
        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self._sequence_counter: dict[str, int] = {}
        self._snapshot_counter: dict[str, int] = {}
    
    async def connect(self) -> None:
        """Establish WebSocket connection to Binance."""
        try:
            # Build stream names
            if self.stream_type == "trade":
                streams = "/".join([f"{s.lower()}@trade" for s in self.symbols])
            elif self.stream_type == "depth":
                streams = "/".join([f"{s.lower()}@depth20@100ms" for s in self.symbols])
            else:
                raise ValueError(f"Unknown stream type: {self.stream_type}")
            
            uri = f"{self.ws_url}?streams={streams}"
            
            self._ws = await websockets.connect(uri, ping_interval=20, ping_timeout=10)
            self._connected = True
            
            logger.info(f"Connected to Binance {self.stream_type} stream for {len(self.symbols)} symbols")
            
            # Start message handler
            asyncio.create_task(self._message_loop())
        
        except Exception as e:
            self.handle_error("connection_error", e)
            raise
    
    async def disconnect(self) -> None:
        """Close WebSocket connection."""
        if self._ws:
            try:
                await self._ws.close()
            except Exception:
                pass  # Already closed or connection lost
            self._connected = False
            logger.info("Disconnected from Binance")
    
    async def subscribe(self, symbols: list[str]) -> None:
        """
        Add symbols to subscription (requires reconnection with new stream list).
        
        For Binance, we need to reconnect with updated symbol list.
        """
        self.symbols.extend([s for s in symbols if s not in self.symbols])
        logger.info(f"Updated symbol list to {len(self.symbols)} symbols. Reconnecting...")
        
        if self._connected:
            await self.disconnect()
            await self.connect()
    
    async def unsubscribe(self, symbols: list[str]) -> None:
        """Remove symbols from subscription."""
        self.symbols = [s for s in self.symbols if s not in symbols]
        logger.info(f"Removed symbols. Now subscribed to {len(self.symbols)} symbols")
        
        if self._connected:
            await self.disconnect()
            await self.connect()
    
    async def _message_loop(self) -> None:
        """Main message processing loop."""
        if not self._ws:
            return
        
        try:
            async for message in self._ws:
                try:
                    data = json.loads(message)
                    
                    if "data" not in data:
                        continue
                    
                    stream_data = data["data"]
                    
                    # Route to appropriate handler
                    if self.stream_type == "trade":
                        await self._handle_trade(stream_data)
                    elif self.stream_type == "depth":
                        await self._handle_depth(stream_data)
                
                except json.JSONDecodeError as e:
                    self.handle_error("parse_error", e)
                except Exception as e:
                    self.handle_error("processing_error", e)
        
        except websockets.exceptions.ConnectionClosed:
            logger.warning("Binance WebSocket connection closed. Reconnecting...")
            websocket_reconnects_total.labels(venue=self.venue).inc()
            await self._reconnect()
        except Exception as e:
            self.handle_error("message_loop_error", e)
    
    async def _reconnect(self) -> None:
        """Reconnect with exponential backoff."""
        backoff = 1
        max_backoff = 60
        
        while self._running:
            try:
                await asyncio.sleep(backoff)
                await self.connect()
                logger.info("Reconnected to Binance")
                return
            except Exception as e:
                backoff = min(backoff * 2, max_backoff)
                logger.error(f"Reconnection failed, retrying in {backoff}s: {e}")
    
    async def _handle_trade(self, data: dict) -> None:
        """Handle trade message."""
        symbol = self._normalize_symbol(data["s"])
        
        tick = Tick(
            event_time_us=int(time.time() * 1_000_000),
            exchange_time_us=int(data["T"]) * 1000,  # Binance uses milliseconds
            symbol=symbol,
            venue=self.venue,
            asset_class=AssetClass.CRYPTO,
            price=float(data["p"]),
            quantity=float(data["q"]),
            side=Side.SELL if data["m"] else Side.BUY,  # m=true means buyer is market maker (sell)
            sequence_id=self._get_next_sequence(symbol),
            flags=""
        )
        
        await self.on_tick(tick)
    
    async def _handle_depth(self, data: dict) -> None:
        """Handle depth (order book) message."""
        symbol = self._normalize_symbol(data["s"])
        
        # Parse bids and asks
        bids = [DepthLevel(price=float(p), size=float(q)) for p, q in data["bids"]]
        asks = [DepthLevel(price=float(p), size=float(q)) for p, q in data["asks"]]
        
        depth = Depth(
            event_time_us=int(time.time() * 1_000_000),
            exchange_time_us=int(data["E"]) * 1000 if "E" in data else None,
            symbol=symbol,
            venue=self.venue,
            bids=bids,
            asks=asks,
            snapshot_id=self._get_next_snapshot(symbol)
        )
        
        await self.on_depth(depth)
    
    def _normalize_symbol(self, binance_symbol: str) -> str:
        """
        Normalize Binance symbol to canonical format.
        
        Example: BTCUSDT -> BTC/USDT
        """
        # Simple heuristic: split common quote currencies
        for quote in ["USDT", "BUSD", "USD", "BTC", "ETH", "BNB"]:
            if binance_symbol.endswith(quote):
                base = binance_symbol[:-len(quote)]
                return f"{base}/{quote}"
        
        return binance_symbol
    
    def _get_next_sequence(self, symbol: str) -> int:
        """Get next sequence ID for symbol."""
        seq = self._sequence_counter.get(symbol, 0)
        self._sequence_counter[symbol] = seq + 1
        return seq
    
    def _get_next_snapshot(self, symbol: str) -> int:
        """Get next snapshot ID for symbol."""
        snap = self._snapshot_counter.get(symbol, 0)
        self._snapshot_counter[symbol] = snap + 1
        return snap
    
    async def _write_ticks(self, ticks: list[Tick]) -> None:
        """
        Write ticks to storage.
        
        TODO: Implement ClickHouse writer.
        """
        logger.debug(f"Writing {len(ticks)} Binance ticks to storage (placeholder)")
        # Placeholder: await clickhouse_client.insert("market_data.tick", [t.dict() for t in ticks])
    
    async def _write_depth(self, depths: list[Depth]) -> None:
        """
        Write depth snapshots to storage.
        
        TODO: Implement ClickHouse writer.
        """
        logger.debug(f"Writing {len(depths)} Binance depth snapshots to storage (placeholder)")
        # Placeholder: await clickhouse_client.insert("market_data.depth", [d.dict() for d in depths])


# Example usage
async def main():
    """Example: Subscribe to BTC and ETH trades."""
    connector = BinanceConnector(
        symbols=["BTCUSDT", "ETHUSDT"],
        stream_type="trade"
    )
    
    # Register callback
    connector.register_tick_callback(
        lambda tick: print(f"Tick: {tick.symbol} @ {tick.price} ({tick.side.value})")
    )
    
    # Start
    await connector.start()
    
    # Run for 60 seconds
    await asyncio.sleep(60)
    
    # Stop
    await connector.stop()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())

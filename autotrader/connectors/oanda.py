"""Oanda v20 API connector for forex streaming."""

from __future__ import annotations

import asyncio
import time
from typing import Optional

import httpx

from autotrader.connectors.base import MarketDataConnector
from autotrader.schemas.market_data import AssetClass, Side, Tick

import logging

logger = logging.getLogger(__name__)


class OandaConnector(MarketDataConnector):
    """
    Oanda v20 API connector for real-time forex data.
    
    Uses streaming pricing endpoint for live bid/ask ticks.
    """
    
    def __init__(
        self,
        api_key: str,
        account_id: str,
        environment: str = "practice",  # 'practice' or 'live'
        buffer_size: int = 1000,
        flush_interval_seconds: float = 1.0
    ):
        """
        Initialize Oanda connector.
        
        Args:
            api_key: Oanda API token
            account_id: Oanda account ID
            environment: 'practice' for demo, 'live' for production
            buffer_size: Local buffer size
            flush_interval_seconds: Flush interval
        """
        super().__init__(venue="OANDA", buffer_size=buffer_size, flush_interval_seconds=flush_interval_seconds)
        
        self.api_key = api_key
        self.account_id = account_id
        
        # Set base URL based on environment
        if environment == "practice":
            self.base_url = "https://stream-fxpractice.oanda.com"
            self.rest_url = "https://api-fxpractice.oanda.com"
        else:
            self.base_url = "https://stream-fxtrade.oanda.com"
            self.rest_url = "https://api-fxtrade.oanda.com"
        
        self._client: Optional[httpx.AsyncClient] = None
        self._stream_task: Optional[asyncio.Task] = None
        self._sequence_counter: dict[str, int] = {}
        
        self._instruments: list[str] = []
    
    async def connect(self) -> None:
        """Initialize HTTP client."""
        self._client = httpx.AsyncClient(
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            },
            timeout=httpx.Timeout(60.0, read=None)  # No read timeout for streaming
        )
        self._connected = True
        logger.info(f"Oanda connector initialized for account {self.account_id}")
    
    async def disconnect(self) -> None:
        """Close HTTP client."""
        if self._stream_task and not self._stream_task.done():
            self._stream_task.cancel()
            try:
                await self._stream_task
            except asyncio.CancelledError:
                pass
        
        if self._client:
            await self._client.aclose()
            self._connected = False
            logger.info("Disconnected from Oanda")
    
    async def subscribe(self, symbols: list[str]) -> None:
        """
        Subscribe to pricing stream for given instruments.
        
        Args:
            symbols: List of instruments (e.g., ['EUR_USD', 'GBP_USD', 'USD_JPY'])
        """
        self._instruments.extend([s for s in symbols if s not in self._instruments])
        
        # Cancel existing stream
        if self._stream_task and not self._stream_task.done():
            self._stream_task.cancel()
            try:
                await self._stream_task
            except asyncio.CancelledError:
                pass
        
        # Start new stream with updated instrument list
        self._stream_task = asyncio.create_task(self._stream_pricing())
        
        logger.info(f"Subscribed to {len(self._instruments)} Oanda instruments")
    
    async def unsubscribe(self, symbols: list[str]) -> None:
        """Remove instruments from subscription."""
        self._instruments = [s for s in self._instruments if s not in symbols]
        logger.info(f"Removed instruments. Now subscribed to {len(self._instruments)} instruments")
        
        # Restart stream with updated list
        if self._instruments:
            await self.subscribe([])  # Trigger restart with current list
    
    async def _stream_pricing(self) -> None:
        """Stream pricing data from Oanda."""
        if not self._client or not self._instruments:
            return
        
        url = f"{self.base_url}/v3/accounts/{self.account_id}/pricing/stream"
        params = {"instruments": ",".join(self._instruments)}
        
        try:
            async with self._client.stream("GET", url, params=params) as response:
                if response.status_code != 200:
                    error_text = await response.aread()
                    self.handle_error("stream_error", Exception(f"HTTP {response.status_code}: {error_text}"))
                    return
                
                logger.info(f"Oanda pricing stream started for {len(self._instruments)} instruments")
                
                async for line in response.aiter_lines():
                    if not line.strip():
                        continue
                    
                    try:
                        import json
                        data = json.loads(line)
                        
                        if data.get("type") == "PRICE":
                            await self._handle_price(data)
                        elif data.get("type") == "HEARTBEAT":
                            logger.debug("Oanda heartbeat received")
                    
                    except json.JSONDecodeError as e:
                        self.handle_error("parse_error", e)
                    except Exception as e:
                        self.handle_error("processing_error", e)
        
        except httpx.HTTPError as e:
            self.handle_error("http_error", e)
        except Exception as e:
            self.handle_error("stream_error", e)
    
    async def _handle_price(self, data: dict) -> None:
        """Handle price update."""
        instrument = data.get("instrument", "")
        symbol = self._normalize_symbol(instrument)
        
        # Extract bid/ask
        bids = data.get("bids", [])
        asks = data.get("asks", [])
        
        if not bids or not asks:
            return
        
        bid_price = float(bids[0]["price"])
        ask_price = float(asks[0]["price"])
        mid_price = (bid_price + ask_price) / 2.0
        
        bid_size = float(bids[0].get("liquidity", 0))
        ask_size = float(asks[0].get("liquidity", 0))
        
        # Parse timestamp
        timestamp_str = data.get("time", "")
        exchange_time_us = self._parse_timestamp(timestamp_str)
        
        # Create tick with mid-price
        tick = Tick(
            event_time_us=int(time.time() * 1_000_000),
            exchange_time_us=exchange_time_us,
            symbol=symbol,
            venue=self.venue,
            asset_class=AssetClass.FOREX,
            price=mid_price,
            quantity=0.0,  # Forex quotes don't have volume in the same sense
            side=Side.UNKNOWN,  # Quote, not a trade
            bid=bid_price,
            ask=ask_price,
            bid_size=bid_size,
            ask_size=ask_size,
            sequence_id=self._get_next_sequence(symbol),
            flags=""
        )
        
        await self.on_tick(tick)
    
    def _normalize_symbol(self, oanda_instrument: str) -> str:
        """
        Normalize Oanda instrument to canonical format.
        
        Example: EUR_USD -> EUR/USD
        """
        return oanda_instrument.replace("_", "/")
    
    def _parse_timestamp(self, timestamp_str: str) -> Optional[int]:
        """Parse Oanda RFC3339 timestamp to microseconds."""
        if not timestamp_str:
            return None
        
        try:
            from datetime import datetime
            dt = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
            return int(dt.timestamp() * 1_000_000)
        except Exception:
            return None
    
    def _get_next_sequence(self, symbol: str) -> int:
        """Get next sequence ID for symbol."""
        seq = self._sequence_counter.get(symbol, 0)
        self._sequence_counter[symbol] = seq + 1
        return seq
    
    async def _write_ticks(self, ticks: list[Tick]) -> None:
        """
        Write ticks to storage.
        
        TODO: Implement ClickHouse writer.
        """
        logger.debug(f"Writing {len(ticks)} Oanda ticks to storage (placeholder)")
        # Placeholder: await clickhouse_client.insert("market_data.tick", [t.dict() for t in ticks])
    
    async def _write_depth(self, depths: list) -> None:
        """Write depth data (not used for Oanda)."""
        pass


# Example usage
async def main():
    """Example: Stream EUR/USD and GBP/USD pricing."""
    import os
    
    api_key = os.environ.get("OANDA_API_KEY", "your-api-key-here")
    account_id = os.environ.get("OANDA_ACCOUNT_ID", "your-account-id")
    
    connector = OandaConnector(
        api_key=api_key,
        account_id=account_id,
        environment="practice"
    )
    
    # Register callback
    connector.register_tick_callback(
        lambda tick: print(f"Tick: {tick.symbol} bid={tick.bid:.5f} ask={tick.ask:.5f} mid={tick.price:.5f}")
    )
    
    # Start
    await connector.start()
    
    # Subscribe
    await connector.subscribe(["EUR_USD", "GBP_USD", "USD_JPY"])
    
    # Run for 60 seconds
    await asyncio.sleep(60)
    
    # Stop
    await connector.stop()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())

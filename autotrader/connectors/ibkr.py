"""Interactive Brokers connector for equities data."""

from __future__ import annotations

import asyncio
import time
from typing import Optional

from ib_insync import IB, BarData, Stock, util

from autotrader.connectors.base import MarketDataConnector
from autotrader.schemas.market_data import AssetClass, OHLCV, Side, Tick

import logging

logger = logging.getLogger(__name__)


class IBKRConnector(MarketDataConnector):
    """
    Interactive Brokers connector using ib_insync library.
    
    Connects to TWS or IB Gateway for real-time equities data.
    """
    
    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 7497,
        client_id: int = 0,
        buffer_size: int = 1000,
        flush_interval_seconds: float = 1.0
    ):
        """
        Initialize IBKR connector.
        
        Args:
            host: TWS/Gateway host (default: localhost)
            port: TWS paper=7497, live=7496; Gateway paper=4002, live=4001
            client_id: Client ID for this connection
            buffer_size: Local buffer size
            flush_interval_seconds: Flush interval
        """
        super().__init__(venue="IBKR", buffer_size=buffer_size, flush_interval_seconds=flush_interval_seconds)
        
        self.host = host
        self.port = port
        self.client_id = client_id
        
        self.ib = IB()
        self._subscriptions: dict[str, Stock] = {}
        self._sequence_counter: dict[str, int] = {}
    
    async def connect(self) -> None:
        """Connect to TWS or IB Gateway."""
        try:
            await self.ib.connectAsync(self.host, self.port, clientId=self.client_id, timeout=10)
            self._connected = True
            logger.info(f"Connected to IBKR at {self.host}:{self.port}")
        except Exception as e:
            self.handle_error("connection_error", e)
            raise
    
    async def disconnect(self) -> None:
        """Disconnect from IBKR."""
        if self.ib.isConnected():
            self.ib.disconnect()
            self._connected = False
            logger.info("Disconnected from IBKR")
    
    async def subscribe(self, symbols: list[str]) -> None:
        """
        Subscribe to real-time tick data for given symbols.
        
        Args:
            symbols: List of stock symbols (e.g., ['AAPL', 'MSFT', 'TSLA'])
        """
        for symbol in symbols:
            if symbol in self._subscriptions:
                logger.warning(f"Already subscribed to {symbol}")
                continue
            
            try:
                # Create contract
                contract = Stock(symbol, 'SMART', 'USD')
                
                # Qualify the contract
                await self.ib.qualifyContractsAsync(contract)
                
                # Subscribe to tick-by-tick trades
                ticker = self.ib.reqTickByTickData(contract, 'AllLast')
                
                # Subscribe to real-time bars (5-second bars)
                self.ib.reqRealTimeBars(
                    contract,
                    barSize=5,
                    whatToShow='TRADES',
                    useRTH=False
                )
                
                # Register callbacks using ticker's updateEvent
                if ticker:
                    ticker.updateEvent += lambda ticks, symbol=symbol: self._on_tick_update(ticks, symbol)
                
                self._subscriptions[symbol] = contract
                self._sequence_counter[symbol] = 0
                
                logger.info(f"Subscribed to {symbol}")
            
            except Exception as e:
                self.handle_error("subscription_error", e)
    
    async def unsubscribe(self, symbols: list[str]) -> None:
        """Unsubscribe from symbols."""
        for symbol in symbols:
            if symbol not in self._subscriptions:
                continue
            
            contract = self._subscriptions[symbol]
            self.ib.cancelTickByTickData(contract, 'AllLast')
            self.ib.cancelRealTimeBars(contract)
            
            del self._subscriptions[symbol]
            logger.info(f"Unsubscribed from {symbol}")
    
    def _on_tick_update(self, ticks, symbol: str) -> None:
        """
        Handle incoming tick updates from ib_insync.
        
        Args:
            ticks: Ticker object from ib_insync (contains tick data)
            symbol: Symbol being updated
        """
        # ticks is a Ticker object, check for new tick-by-tick data
        if hasattr(ticks, 'tickByTicks') and ticks.tickByTicks:
            for trade in ticks.tickByTicks:
                # Create tick from trade data
                tick = Tick(
                    event_time_us=int(time.time() * 1_000_000),
                    exchange_time_us=int(trade.time.timestamp() * 1_000_000) if hasattr(trade, 'time') else None,
                    symbol=symbol,
                    venue=self.venue,
                    asset_class=AssetClass.EQUITY,
                    price=float(trade.price) if hasattr(trade, 'price') else 0.0,
                    quantity=float(trade.size) if hasattr(trade, 'size') else 0.0,
                    side=Side.BUY if getattr(trade, 'tickAttribLast', {}).get('pastLimit', False) else Side.UNKNOWN,
                    sequence_id=self._get_next_sequence(symbol),
                    flags=""
                )
                
                # Schedule async handler
                asyncio.create_task(self.on_tick(tick))
    
    def _get_next_sequence(self, symbol: str) -> int:
        """Get next sequence ID for symbol."""
        seq = self._sequence_counter.get(symbol, 0)
        self._sequence_counter[symbol] = seq + 1
        return seq
    
    async def _write_ticks(self, ticks: list[Tick]) -> None:
        """
        Write ticks to storage.
        
        TODO: Implement ClickHouse or Parquet writer.
        For now, just log.
        """
        logger.debug(f"Writing {len(ticks)} IBKR ticks to storage (placeholder)")
        # Placeholder: In production, batch insert to ClickHouse
        # await clickhouse_client.insert("market_data.tick", [t.dict() for t in ticks])
    
    async def _write_depth(self, depths: list) -> None:
        """Write depth data (not used for IBKR tick-by-tick)."""
        pass


# Example usage
async def main():
    """Example: Subscribe to AAPL and MSFT ticks."""
    connector = IBKRConnector(host="127.0.0.1", port=7497, client_id=1)
    
    # Register callback to print ticks
    connector.register_tick_callback(lambda tick: print(f"Tick: {tick.symbol} @ {tick.price}"))
    
    # Start connector
    await connector.start()
    
    # Subscribe to symbols
    await connector.subscribe(['AAPL', 'MSFT'])
    
    # Run for 60 seconds
    await asyncio.sleep(60)
    
    # Stop
    await connector.stop()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())

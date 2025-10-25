"""Unified market data schemas for cross-asset ingestion."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict


class AssetClass(str, Enum):
    """Asset classification."""
    EQUITY = "EQUITY"
    CRYPTO = "CRYPTO"
    FOREX = "FOREX"
    COMMODITY = "COMMODITY"


class Side(str, Enum):
    """Trade side."""
    BUY = "BUY"
    SELL = "SELL"
    UNKNOWN = "UNKNOWN"


class Tick(BaseModel):
    """Unified tick data schema for all venues and asset classes."""
    
    model_config = ConfigDict(frozen=True)
    
    # Timestamps (microseconds UTC)
    event_time_us: int = Field(..., description="Ingestion timestamp (microseconds UTC)")
    exchange_time_us: Optional[int] = Field(None, description="Exchange-reported timestamp (if available)")
    
    # Identification
    symbol: str = Field(..., description="Canonical symbol (e.g., AAPL, BTC/USD, EUR/USD)")
    venue: str = Field(..., description="Exchange/broker identifier (IBKR, BINANCE, OANDA)")
    asset_class: AssetClass = Field(..., description="Asset classification")
    
    # Trade data
    price: float = Field(..., description="Trade price or mid-quote")
    quantity: float = Field(..., description="Trade size or volume")
    side: Side = Field(default=Side.UNKNOWN, description="Trade side")
    
    # BBO (Best Bid/Offer) snapshot
    bid: Optional[float] = Field(None, description="Best bid price")
    ask: Optional[float] = Field(None, description="Best ask price")
    bid_size: Optional[float] = Field(None, description="Bid quantity")
    ask_size: Optional[float] = Field(None, description="Ask quantity")
    
    # Metadata
    sequence_id: int = Field(..., description="Monotonic counter per venue-symbol pair")
    flags: str = Field(default="", description="Flags: REPLAY, HALTED, ADJUSTED")


class DepthLevel(BaseModel):
    """Single order book level."""
    
    model_config = ConfigDict(frozen=True)
    
    price: float
    size: float


class Depth(BaseModel):
    """Order book depth (L2 snapshot)."""
    
    model_config = ConfigDict(frozen=True)
    
    # Timestamps
    event_time_us: int = Field(..., description="Ingestion timestamp")
    exchange_time_us: Optional[int] = Field(None, description="Exchange snapshot timestamp")
    
    # Identification
    symbol: str = Field(..., description="Canonical symbol")
    venue: str = Field(..., description="Exchange identifier")
    
    # Order book levels
    bids: list[DepthLevel] = Field(..., description="Bid levels (sorted descending by price)")
    asks: list[DepthLevel] = Field(..., description="Ask levels (sorted ascending by price)")
    
    # Metadata
    snapshot_id: int = Field(..., description="Incremental snapshot counter")


class OHLCV(BaseModel):
    """OHLCV bar data."""
    
    model_config = ConfigDict(frozen=True)
    
    # Timestamps
    timestamp: datetime = Field(..., description="Bar open time (UTC)")
    
    # Identification
    symbol: str = Field(..., description="Canonical symbol")
    venue: str = Field(..., description="Exchange identifier")
    asset_class: AssetClass = Field(..., description="Asset classification")
    
    # OHLCV data
    open: float = Field(..., description="Open price")
    high: float = Field(..., description="High price")
    low: float = Field(..., description="Low price")
    close: float = Field(..., description="Close price")
    volume: float = Field(..., description="Traded volume")
    
    # Optional metrics
    vwap: Optional[float] = Field(None, description="Volume-weighted average price")
    trade_count: Optional[int] = Field(None, description="Number of trades in bar")

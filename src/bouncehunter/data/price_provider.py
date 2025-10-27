"""
Price data provider interface and implementations.

Provides abstraction over market data sources (Alpaca API).
Implements caching to reduce API calls and latency.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, TYPE_CHECKING
from datetime import datetime, timedelta
from dataclasses import dataclass

if TYPE_CHECKING:
    from .cache import PriceCache


@dataclass
class Quote:
    """Market quote data."""
    ticker: str
    price: float
    bid: float
    ask: float
    timestamp: datetime
    
    @property
    def spread_pct(self) -> float:
        """Calculate spread as percentage of bid."""
        if self.bid == 0:
            return 100.0
        return ((self.ask - self.bid) / self.bid) * 100


@dataclass
class Bar:
    """OHLCV bar data."""
    ticker: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int


class PriceProvider(ABC):
    """Abstract interface for price data."""
    
    @abstractmethod
    def get_quote(self, ticker: str) -> Quote:
        """
        Get latest quote for ticker.
        
        Args:
            ticker: Stock ticker symbol
            
        Returns:
            Quote object
            
        Raises:
            ValueError: If ticker not found or data unavailable
        """
        pass
    
    @abstractmethod
    def get_quotes(self, tickers: List[str]) -> Dict[str, Quote]:
        """
        Get latest quotes for multiple tickers (batch operation).
        
        Args:
            tickers: List of ticker symbols
            
        Returns:
            Dictionary mapping ticker -> Quote
        """
        pass
    
    @abstractmethod
    def get_recent_bars(self, ticker: str, count: int = 30, timeframe: str = '1Min') -> List[Bar]:
        """
        Get recent bars for ticker.
        
        Args:
            ticker: Stock ticker symbol
            count: Number of bars to retrieve
            timeframe: Bar timeframe ('1Min', '5Min', etc.)
            
        Returns:
            List of Bar objects, most recent last
        """
        pass


class AlpacaPriceProvider(PriceProvider):
    """
    Price provider implementation using Alpaca API.
    
    Attributes:
        client: Alpaca API client
        cache: Optional price cache
    """
    
    def __init__(self, alpaca_client: Any, cache: Optional['PriceCache'] = None):
        """
        Initialize Alpaca price provider.
        
        Args:
            alpaca_client: Alpaca API client instance
            cache: Optional price cache for reducing API calls
        """
        self.client = alpaca_client
        self.cache = cache
    
    def get_quote(self, ticker: str) -> Quote:
        """Get latest quote for ticker."""
        # Check cache first
        if self.cache:
            cached_quote = self.cache.get_quote(ticker)
            if cached_quote:
                return cached_quote
        
        # Fetch from API
        quote = self._fetch_quote(ticker)
        
        # Store in cache
        if self.cache:
            self.cache.set_quote(ticker, quote)
        
        return quote
    
    def get_quotes(self, tickers: List[str]) -> Dict[str, Quote]:
        """Get latest quotes for multiple tickers."""
        # Check cache for all tickers
        quotes = {}
        missing_tickers = []
        
        if self.cache:
            for ticker in tickers:
                cached = self.cache.get_quote(ticker)
                if cached:
                    quotes[ticker] = cached
                else:
                    missing_tickers.append(ticker)
        else:
            missing_tickers = tickers
        
        # Fetch missing quotes from API (batch)
        if missing_tickers:
            fetched = self._fetch_quotes_batch(missing_tickers)
            quotes.update(fetched)
            
            # Cache them
            if self.cache:
                for ticker, quote in fetched.items():
                    self.cache.set_quote(ticker, quote)
        
        return quotes
    
    def get_recent_bars(self, ticker: str, count: int = 30, timeframe: str = '1Min') -> List[Bar]:
        """Get recent bars for ticker."""
        try:
            # Alpaca API call
            bars_response = self.client.get_bars(
                ticker,
                timeframe,
                limit=count
            )
            
            bars = []
            for bar_data in bars_response:
                bars.append(Bar(
                    ticker=ticker,
                    timestamp=bar_data.t,
                    open=float(bar_data.o),
                    high=float(bar_data.h),
                    low=float(bar_data.l),
                    close=float(bar_data.c),
                    volume=int(bar_data.v)
                ))
            
            return bars
        except Exception as e:
            raise ValueError(f"Failed to fetch bars for {ticker}: {e}")
    
    def _fetch_quote(self, ticker: str) -> Quote:
        """Fetch single quote from Alpaca API."""
        try:
            quote_data = self.client.get_latest_quote(ticker)
            
            return Quote(
                ticker=ticker,
                price=(quote_data.bp + quote_data.ap) / 2,  # Mid price
                bid=float(quote_data.bp),
                ask=float(quote_data.ap),
                timestamp=quote_data.t
            )
        except Exception as e:
            raise ValueError(f"Failed to fetch quote for {ticker}: {e}")
    
    def _fetch_quotes_batch(self, tickers: List[str]) -> Dict[str, Quote]:
        """Fetch multiple quotes from Alpaca API."""
        try:
            quotes_response = self.client.get_latest_quotes(tickers)
            
            quotes = {}
            for ticker, quote_data in quotes_response.items():
                quotes[ticker] = Quote(
                    ticker=ticker,
                    price=(quote_data.bp + quote_data.ap) / 2,
                    bid=float(quote_data.bp),
                    ask=float(quote_data.ap),
                    timestamp=quote_data.t
                )
            
            return quotes
        except Exception as e:
            raise ValueError(f"Failed to fetch batch quotes: {e}")


class MockPriceProvider(PriceProvider):
    """
    Mock price provider for testing.
    
    Returns predefined quote and bar data.
    """
    
    def __init__(self, mock_data: Optional[Dict[str, Any]] = None):
        """
        Initialize mock provider.
        
        Args:
            mock_data: Dictionary mapping ticker -> {'quote': Quote, 'bars': List[Bar]}
        """
        self.mock_data = mock_data or {}
    
    def get_quote(self, ticker: str) -> Quote:
        """Get mock quote."""
        if ticker not in self.mock_data:
            raise ValueError(f"No mock data for ticker: {ticker}")
        
        quote_data = self.mock_data[ticker].get('quote')
        if not quote_data:
            raise ValueError(f"No quote data for ticker: {ticker}")
        
        return quote_data
    
    def get_quotes(self, tickers: List[str]) -> Dict[str, Quote]:
        """Get mock quotes."""
        return {ticker: self.get_quote(ticker) for ticker in tickers}
    
    def get_recent_bars(self, ticker: str, count: int = 30, timeframe: str = '1Min') -> List[Bar]:
        """Get mock bars."""
        if ticker not in self.mock_data:
            raise ValueError(f"No mock data for ticker: {ticker}")
        
        bars_data = self.mock_data[ticker].get('bars', [])
        return bars_data[-count:] if bars_data else []
    
    def set_mock_quote(self, ticker: str, quote: Quote) -> None:
        """Set mock quote (test helper)."""
        if ticker not in self.mock_data:
            self.mock_data[ticker] = {}
        self.mock_data[ticker]['quote'] = quote
    
    def set_mock_bars(self, ticker: str, bars: List[Bar]) -> None:
        """Set mock bars (test helper)."""
        if ticker not in self.mock_data:
            self.mock_data[ticker] = {}
        self.mock_data[ticker]['bars'] = bars

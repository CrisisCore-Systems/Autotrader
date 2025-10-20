"""Clients for CEX/DEX order flow and derivatives data."""

from __future__ import annotations

import os
from typing import Any, Dict, List, Mapping, Optional

import httpx

from src.core.clients import BaseClient
from src.core.http_manager import CachePolicy
from src.core.rate_limit import RateLimit


class BinanceClient(BaseClient):
    """Client for Binance spot and futures market data.

    Provides access to:
    - Order book depth (bid/ask levels)
    - Funding rates (perpetual futures)
    - Open interest
    - 24h ticker data
    """

    def __init__(
        self,
        *,
        base_url: str = "https://api.binance.com",
        futures_base_url: str = "https://fapi.binance.com",
        timeout: float = 10.0,
        api_key: str | None = None,
        client: Optional[httpx.Client] = None,
        rate_limits: Mapping[str, RateLimit] | None = None,
    ) -> None:
        """Initialize Binance client.

        Args:
            base_url: Spot API base URL
            futures_base_url: Futures API base URL
            timeout: Request timeout in seconds
            api_key: Optional API key for authenticated endpoints
            client: Optional httpx client instance
            rate_limits: Optional custom rate limits
        """
        headers = {}
        if api_key:
            headers["X-MBX-APIKEY"] = api_key

        session = client or httpx.Client(base_url=base_url, timeout=timeout, headers=headers)
        resolved_limits = rate_limits or {
            "api.binance.com": RateLimit(1200, 60.0),  # 1200 requests per minute
            "fapi.binance.com": RateLimit(2400, 60.0),  # 2400 requests per minute for futures
        }
        super().__init__(
            session,
            rate_limits=resolved_limits,
        )
        self._futures_base_url = futures_base_url
        self._api_key = api_key or os.getenv("BINANCE_API_KEY", "")

    def fetch_order_book_depth(
        self,
        symbol: str,
        *,
        limit: int = 100,
    ) -> Dict[str, Any]:
        """Fetch order book depth for a trading pair.

        Args:
            symbol: Trading pair symbol (e.g., 'BTCUSDT')
            limit: Depth limit (5, 10, 20, 50, 100, 500, 1000, 5000)

        Returns:
            Dict with 'bids' and 'asks' arrays, each containing [price, quantity] pairs
        """
        response = self.requester.request(
            "GET",
            "/api/v3/depth",
            params={"symbol": symbol.upper(), "limit": limit},
            cache_policy=CachePolicy(ttl_seconds=5.0),  # Very short cache for order book
        )
        return response.json()

    def fetch_funding_rate(self, symbol: str | None = None) -> List[Dict[str, Any]]:
        """Fetch current or historical funding rates for perpetual futures.

        Args:
            symbol: Optional futures symbol (e.g., 'BTCUSDT'). If None, returns all symbols.

        Returns:
            List of funding rate records with symbol, fundingRate, and fundingTime
        """
        # Switch to futures base URL
        original_base = self.client.base_url
        try:
            self.client.base_url = httpx.URL(self._futures_base_url)

            params = {}
            if symbol:
                params["symbol"] = symbol.upper()

            response = self.requester.request(
                "GET",
                "/fapi/v1/fundingRate",
                params=params,
                cache_policy=CachePolicy(ttl_seconds=60.0),
            )
            data = response.json()
            return data if isinstance(data, list) else [data]
        finally:
            self.client.base_url = original_base

    def fetch_open_interest(self, symbol: str) -> Dict[str, Any]:
        """Fetch current open interest for a futures symbol.

        Args:
            symbol: Futures symbol (e.g., 'BTCUSDT')

        Returns:
            Dict with openInterest, symbol, and time
        """
        original_base = self.client.base_url
        try:
            self.client.base_url = httpx.URL(self._futures_base_url)

            response = self.requester.request(
                "GET",
                "/fapi/v1/openInterest",
                params={"symbol": symbol.upper()},
                cache_policy=CachePolicy(ttl_seconds=30.0),
            )
            return response.json()
        finally:
            self.client.base_url = original_base

    def fetch_ticker_24h(self, symbol: str | None = None) -> List[Dict[str, Any]] | Dict[str, Any]:
        """Fetch 24-hour ticker statistics.

        Args:
            symbol: Optional trading pair. If None, returns all symbols.

        Returns:
            Single ticker dict or list of tickers
        """
        params = {}
        if symbol:
            params["symbol"] = symbol.upper()

        response = self.requester.request(
            "GET",
            "/api/v3/ticker/24hr",
            params=params,
            cache_policy=CachePolicy(ttl_seconds=10.0),
        )
        return response.json()


class DexscreenerClient(BaseClient):
    """Client for Dexscreener DEX aggregator data.

    Provides access to:
    - Token pair information across DEXes
    - Liquidity depth and reserves
    - Volume and price changes
    - Pool metadata
    """

    def __init__(
        self,
        *,
        base_url: str = "https://api.dexscreener.com",
        timeout: float = 10.0,
        client: Optional[httpx.Client] = None,
    ) -> None:
        """Initialize Dexscreener client.

        Args:
            base_url: API base URL
            timeout: Request timeout in seconds
            client: Optional httpx client instance
        """
        session = client or httpx.Client(base_url=base_url, timeout=timeout)
        super().__init__(
            session,
            rate_limits={"api.dexscreener.com": RateLimit(300, 60.0)},  # 300 requests per minute
        )

    def fetch_token_pairs(
        self,
        token_address: str,
        *,
        chain: str = "ethereum",
    ) -> Dict[str, Any]:
        """Fetch all DEX pairs for a token address.

        Args:
            token_address: Token contract address
            chain: Blockchain name (ethereum, bsc, polygon, etc.)

        Returns:
            Dict with 'pairs' array containing liquidity, volume, and price data
        """
        response = self.requester.request(
            "GET",
            f"/latest/dex/tokens/{token_address}",
            cache_policy=CachePolicy(ttl_seconds=30.0),
        )
        return response.json()

    def fetch_pair_by_address(
        self,
        pair_address: str,
        *,
        chain: str = "ethereum",
    ) -> Dict[str, Any]:
        """Fetch specific pair data by pair address.

        Args:
            pair_address: DEX pair contract address
            chain: Blockchain name

        Returns:
            Dict with pair liquidity, volume, and metadata
        """
        response = self.requester.request(
            "GET",
            f"/latest/dex/pairs/{chain}/{pair_address}",
            cache_policy=CachePolicy(ttl_seconds=30.0),
        )
        return response.json()

    def search_pairs(self, query: str) -> Dict[str, Any]:
        """Search for pairs by token name or symbol.

        Args:
            query: Search query (token name or symbol)

        Returns:
            Dict with 'pairs' array of matching results
        """
        response = self.requester.request(
            "GET",
            f"/latest/dex/search",
            params={"q": query},
            cache_policy=CachePolicy(ttl_seconds=60.0),
        )
        return response.json()


class BybitClient(BaseClient):
    """Client for Bybit derivatives exchange data.

    Provides access to:
    - Order book depth
    - Funding rates
    - Open interest
    - Kline/candlestick data
    """

    def __init__(
        self,
        *,
        base_url: str = "https://api.bybit.com",
        timeout: float = 10.0,
        api_key: str | None = None,
        client: Optional[httpx.Client] = None,
    ) -> None:
        """Initialize Bybit client.

        Args:
            base_url: API base URL
            timeout: Request timeout in seconds
            api_key: Optional API key for authenticated endpoints
            client: Optional httpx client instance
        """
        headers = {}
        if api_key:
            headers["X-BAPI-API-KEY"] = api_key

        session = client or httpx.Client(base_url=base_url, timeout=timeout, headers=headers)
        super().__init__(
            session,
            rate_limits={"api.bybit.com": RateLimit(600, 60.0)},  # 600 requests per minute
        )
        self._api_key = api_key or os.getenv("BYBIT_API_KEY", "")

    def fetch_order_book(
        self,
        symbol: str,
        *,
        category: str = "linear",
        limit: int = 50,
    ) -> Dict[str, Any]:
        """Fetch order book depth.

        Args:
            symbol: Trading symbol (e.g., 'BTCUSDT')
            category: Product category (spot, linear, inverse, option)
            limit: Depth limit (1-200)

        Returns:
            Dict with order book data including bids and asks
        """
        response = self.requester.request(
            "GET",
            "/v5/market/orderbook",
            params={"category": category, "symbol": symbol.upper(), "limit": limit},
            cache_policy=CachePolicy(ttl_seconds=5.0),
        )
        return response.json()

    def fetch_funding_history(
        self,
        symbol: str,
        *,
        category: str = "linear",
        limit: int = 200,
    ) -> Dict[str, Any]:
        """Fetch historical funding rates.

        Args:
            symbol: Trading symbol (e.g., 'BTCUSDT')
            category: Product category (linear, inverse)
            limit: Number of records to return (1-200)

        Returns:
            Dict with list of funding rate records
        """
        response = self.requester.request(
            "GET",
            "/v5/market/funding/history",
            params={"category": category, "symbol": symbol.upper(), "limit": limit},
            cache_policy=CachePolicy(ttl_seconds=60.0),
        )
        return response.json()

    def fetch_open_interest(
        self,
        symbol: str,
        *,
        category: str = "linear",
        interval_time: str = "5min",
    ) -> Dict[str, Any]:
        """Fetch open interest data.

        Args:
            symbol: Trading symbol (e.g., 'BTCUSDT')
            category: Product category (linear, inverse)
            interval_time: Data interval (5min, 15min, 30min, 1h, 4h, 1d)

        Returns:
            Dict with open interest data
        """
        response = self.requester.request(
            "GET",
            "/v5/market/open-interest",
            params={
                "category": category,
                "symbol": symbol.upper(),
                "intervalTime": interval_time,
            },
            cache_policy=CachePolicy(ttl_seconds=30.0),
        )
        return response.json()

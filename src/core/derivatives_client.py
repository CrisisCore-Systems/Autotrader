"""Client for derivatives market data (funding rates, open interest, liquidations)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
import asyncio
import httpx

from src.core.clients import BaseClient
from src.core.rate_limit import RateLimit
from src.core.http_manager import RateAwareRequester


class DerivativesClient(BaseClient):
    """Client for derivatives market data from various exchanges."""

    # Rate limits for different exchanges
    EXCHANGE_RATE_LIMITS = {
        "api.binance.com": RateLimit(1200, 60.0),  # 1200 requests per minute
        "fapi.binance.com": RateLimit(2400, 60.0),  # Futures API
        "api.bybit.com": RateLimit(120, 60.0),     # 120 requests per minute
        "api.kraken.com": RateLimit(15, 30.0),     # 15 requests per 30 seconds
        "fapi.huobi.pro": RateLimit(800, 60.0),    # Huobi Futures
        "api.okx.com": RateLimit(300, 60.0),       # OKX API
    }

    def __init__(
        self,
        *,
        timeout: float = 15.0,
        client: Optional[httpx.Client] = None,
    ) -> None:
        session = client or httpx.Client(timeout=timeout)
        super().__init__(session, rate_limits=self.EXCHANGE_RATE_LIMITS)

    async def get_funding_rate(self, exchange: str, symbol: str) -> Optional[Dict[str, Any]]:
        """Get current funding rate for a symbol."""
        try:
            if exchange.lower() == "binance":
                return await self._get_binance_funding_rate(symbol)
            elif exchange.lower() == "bybit":
                return await self._get_bybit_funding_rate(symbol)
            elif exchange.lower() == "kraken":
                return await self._get_kraken_funding_rate(symbol)
            elif exchange.lower() == "huobi":
                return await self._get_huobi_funding_rate(symbol)
            elif exchange.lower() == "okx":
                return await self._get_okx_funding_rate(symbol)
            else:
                raise ValueError(f"Unsupported exchange: {exchange}")
        except Exception as e:
            print(f"Error fetching funding rate for {exchange}:{symbol}: {e}")
            return None

    async def get_open_interest(self, exchange: str, symbol: str) -> Optional[Dict[str, Any]]:
        """Get open interest for a symbol."""
        try:
            if exchange.lower() == "binance":
                return await self._get_binance_open_interest(symbol)
            elif exchange.lower() == "bybit":
                return await self._get_bybit_open_interest(symbol)
            elif exchange.lower() == "kraken":
                return await self._get_kraken_open_interest(symbol)
            elif exchange.lower() == "huobi":
                return await self._get_huobi_open_interest(symbol)
            elif exchange.lower() == "okx":
                return await self._get_okx_open_interest(symbol)
            else:
                raise ValueError(f"Unsupported exchange: {exchange}")
        except Exception as e:
            print(f"Error fetching open interest for {exchange}:{symbol}: {e}")
            return None

    async def get_liquidations(self, exchange: str, symbol: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent liquidations for a symbol."""
        try:
            if exchange.lower() == "binance":
                return await self._get_binance_liquidations(symbol, limit)
            elif exchange.lower() == "bybit":
                return await self._get_bybit_liquidations(symbol, limit)
            elif exchange.lower() == "kraken":
                return await self._get_kraken_liquidations(symbol, limit)
            elif exchange.lower() == "huobi":
                return await self._get_huobi_liquidations(symbol, limit)
            elif exchange.lower() == "okx":
                return await self._get_okx_liquidations(symbol, limit)
            else:
                return []
        except Exception as e:
            print(f"Error fetching liquidations for {exchange}:{symbol}: {e}")
            return []

    # Binance implementations
    async def _get_binance_funding_rate(self, symbol: str) -> Dict[str, Any]:
        """Get funding rate from Binance."""
        response = await self.requester.arequest(
            "GET",
            "https://fapi.binance.com/fapi/v1/premiumIndex",
            params={"symbol": symbol}
        )
        data = response.json()
        return {
            "exchange": "binance",
            "symbol": symbol,
            "funding_rate": float(data["lastFundingRate"]),
            "mark_price": float(data["markPrice"]),
            "index_price": float(data["indexPrice"]),
            "timestamp": datetime.fromtimestamp(data["time"] / 1000)
        }

    async def _get_binance_open_interest(self, symbol: str) -> Dict[str, Any]:
        """Get open interest from Binance."""
        response = await self.requester.arequest(
            "GET",
            "https://fapi.binance.com/fapi/v1/openInterest",
            params={"symbol": symbol}
        )
        data = response.json()
        return {
            "exchange": "binance",
            "symbol": symbol,
            "open_interest": float(data["openInterest"]),
            "timestamp": datetime.fromtimestamp(data["time"] / 1000)
        }

    async def _get_binance_liquidations(self, symbol: str, limit: int) -> List[Dict[str, Any]]:
        """Get liquidations from Binance."""
        response = await self.requester.arequest(
            "GET",
            "https://fapi.binance.com/fapi/v1/allForceOrders",
            params={"symbol": symbol, "limit": min(limit, 100)}
        )
        data = response.json()
        return [{
            "exchange": "binance",
            "symbol": symbol,
            "side": item["side"],
            "price": float(item["price"]),
            "quantity": float(item["origQty"]),
            "average_price": float(item["avgPrice"]),
            "timestamp": datetime.fromtimestamp(item["time"] / 1000)
        } for item in data]

    # Bybit implementations
    async def _get_bybit_funding_rate(self, symbol: str) -> Dict[str, Any]:
        """Get funding rate from Bybit."""
        response = await self.requester.arequest(
            "GET",
            "https://api.bybit.com/v2/public/tickers",
            params={"symbol": symbol}
        )
        data = response.json()
        if data["result"]:
            ticker = data["result"][0]
            return {
                "exchange": "bybit",
                "symbol": symbol,
                "funding_rate": float(ticker.get("funding_rate", 0)),
                "mark_price": float(ticker.get("mark_price", 0)),
                "timestamp": datetime.now()
            }
        return None

    async def _get_bybit_open_interest(self, symbol: str) -> Dict[str, Any]:
        """Get open interest from Bybit."""
        response = await self.requester.arequest(
            "GET",
            "https://api.bybit.com/v2/public/open-interest",
            params={"symbol": symbol}
        )
        data = response.json()
        if data["result"]:
            oi = data["result"]
            return {
                "exchange": "bybit",
                "symbol": symbol,
                "open_interest": float(oi.get("open_interest", 0)),
                "timestamp": datetime.now()
            }
        return None

    async def _get_bybit_liquidations(self, symbol: str, limit: int) -> List[Dict[str, Any]]:
        """Get liquidations from Bybit."""
        # Bybit doesn't have a direct liquidation endpoint, return empty list
        return []

    # Placeholder implementations for other exchanges
    async def _get_kraken_funding_rate(self, symbol: str) -> Dict[str, Any]:
        """Get funding rate from Kraken."""
        # Placeholder - would need Kraken API implementation
        return {
            "exchange": "kraken",
            "symbol": symbol,
            "funding_rate": 0.0,
            "timestamp": datetime.now()
        }

    async def _get_kraken_open_interest(self, symbol: str) -> Dict[str, Any]:
        """Get open interest from Kraken."""
        return {
            "exchange": "kraken",
            "symbol": symbol,
            "open_interest": 0.0,
            "timestamp": datetime.now()
        }

    async def _get_kraken_liquidations(self, symbol: str, limit: int) -> List[Dict[str, Any]]:
        """Get liquidations from Kraken."""
        return []

    async def _get_huobi_funding_rate(self, symbol: str) -> Dict[str, Any]:
        """Get funding rate from Huobi."""
        return {
            "exchange": "huobi",
            "symbol": symbol,
            "funding_rate": 0.0,
            "timestamp": datetime.now()
        }

    async def _get_huobi_open_interest(self, symbol: str) -> Dict[str, Any]:
        """Get open interest from Huobi."""
        return {
            "exchange": "huobi",
            "symbol": symbol,
            "open_interest": 0.0,
            "timestamp": datetime.now()
        }

    async def _get_huobi_liquidations(self, symbol: str, limit: int) -> List[Dict[str, Any]]:
        """Get liquidations from Huobi."""
        return []

    async def _get_okx_funding_rate(self, symbol: str) -> Dict[str, Any]:
        """Get funding rate from OKX."""
        return {
            "exchange": "okx",
            "symbol": symbol,
            "funding_rate": 0.0,
            "timestamp": datetime.now()
        }

    async def _get_okx_open_interest(self, symbol: str) -> Dict[str, Any]:
        """Get open interest from OKX."""
        return {
            "exchange": "okx",
            "symbol": symbol,
            "open_interest": 0.0,
            "timestamp": datetime.now()
        }

    async def _get_okx_liquidations(self, symbol: str, limit: int) -> List[Dict[str, Any]]:
        """Get liquidations from OKX."""
        return []
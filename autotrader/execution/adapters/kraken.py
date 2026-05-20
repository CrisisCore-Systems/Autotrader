import os
import time
import hmac
import hashlib
import base64
import logging
import urllib.parse
from typing import Dict, Any, Optional, Callable, Awaitable
from datetime import datetime, timezone

import aiohttp

from autotrader.execution.adapters import BaseBrokerAdapter, Order, OrderStatus, Fill, OrderSide, OrderType

class KrakenAdapter(BaseBrokerAdapter):
    """
    Authenticated execution adapter for Kraken.
    Implements BaseBrokerAdapter for LiveOMS compatibility.
    """
    BASE_URL = "https://api.kraken.com"

    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger("autotrader.execution.adapters.kraken")
        self.api_key = os.getenv("KRAKEN_API_KEY")
        self.api_secret = os.getenv("KRAKEN_API_SECRET")
        if not self.api_key or not self.api_secret:
            self.logger.warning("Kraken credentials missing from environment variables.")
        self.session: Optional[aiohttp.ClientSession] = None
        self._fill_callbacks: list[Callable[[Fill], Awaitable[None]]] = []
        self._orders: Dict[str, Order] = {}
        self._order_pairs: Dict[str, str] = {}

    async def connect(self) -> bool:
        try:
            if not self.api_key or not self.api_secret:
                self.logger.error("Kraken credentials are required. Set KRAKEN_API_KEY and KRAKEN_API_SECRET.")
                return False
            if not self.session:
                self.session = aiohttp.ClientSession(headers={"API-Key": self.api_key})
            self.logger.info("KrakenAdapter session initialized.")
            return True
        except Exception as e:
            self.logger.error(f"Failed to connect adapter: {e}")
            return False

    async def disconnect(self) -> bool:
        try:
            if self.session:
                await self.session.close()
                self.session = None
            return True
        except Exception as e:
            self.logger.error(f"Failed to disconnect adapter: {e}")
            return False

    def subscribe_fills(self, callback: Callable[[Fill], Awaitable[None]]) -> None:
        self._fill_callbacks.append(callback)

    def _generate_signature(self, urlpath: str, data: Dict[str, Any], nonce: str) -> str:
        postdata = urllib.parse.urlencode(data)
        encoded = (nonce + postdata).encode()
        message = urlpath.encode() + hashlib.sha256(encoded).digest()
        mac = hmac.new(base64.b64decode(self.api_secret), message, hashlib.sha512)
        return base64.b64encode(mac.digest()).decode()

    async def _private_request(self, endpoint: str, data: Dict[str, Any] = None) -> dict:
        if not self.session:
            raise RuntimeError("Adapter not connected. Call await connect() first.")
        data = data or {}
        nonce = str(int(time.time() * 1000))
        data['nonce'] = nonce
        urlpath = f"/0/private/{endpoint}"
        signature = self._generate_signature(urlpath, data, nonce)
        headers = {
            "API-Key": self.api_key,
            "API-Sign": signature,
        }
        url = f"{self.BASE_URL}{urlpath}"
        async with self.session.post(url, data=data, headers=headers) as response:
            result = await response.json()
            if response.status != 200 or result.get('error'):
                self.logger.error(f"Kraken API Error: {result}")
                raise Exception(f"API Error {response.status}: {result.get('error')}")
            return result.get('result', {})

    def _map_kraken_status(self, status: str) -> OrderStatus:
        mapping = {
            "pending": OrderStatus.SUBMITTED,
            "open": OrderStatus.SUBMITTED,
            "closed": OrderStatus.FILLED,
            "partial": OrderStatus.PARTIAL_FILL,
            "canceled": OrderStatus.CANCELLED,
            "expired": OrderStatus.EXPIRED,
        }
        return mapping.get(status, OrderStatus.PENDING)

    def _normalize_pair(self, symbol: str) -> str:
        raw = str(symbol).strip().upper().replace("-", "/")
        if "/" not in raw:
            if raw.endswith("USDT"):
                raw = raw[:-4] + "/USDT"
            elif raw.endswith("USD"):
                raw = raw[:-3] + "/USD"
        base, quote = raw.split("/", 1)
        if base == "BTC":
            base = "XBT"
        return f"{base}{quote}"

    def _canonical_asset(self, asset: str) -> str:
        raw = str(asset).strip().upper()
        explicit = {
            "XXBT": "BTC",
            "XBT": "BTC",
            "ZUSD": "USD",
            "ZEUR": "EUR",
            "ZGBP": "GBP",
            "ZJPY": "JPY",
            "USDT": "USDT",
        }
        if raw in explicit:
            return explicit[raw]
        if len(raw) == 4 and raw[0] in {"X", "Z"}:
            return raw[1:]
        return raw

    async def get_account_balance(self) -> Dict[str, float]:
        result = await self._private_request("Balance")
        balances: Dict[str, float] = {}
        for asset, amount in result.items():
            canonical = self._canonical_asset(asset)
            balances[canonical] = balances.get(canonical, 0.0) + float(amount)
        return balances

    async def submit_order(self, order: Order) -> Order:
        data = {
            "pair": self._normalize_pair(order.symbol),
            "type": order.side.value,
            "ordertype": order.order_type.value,
            "volume": order.quantity,
        }
        if order.order_type.value == "limit" and order.price:
            data["price"] = order.price
        result = await self._private_request("AddOrder", data)
        txid = result.get("txid", [None])[0]
        order.order_id = txid or ""
        order.status = OrderStatus.SUBMITTED
        order.submitted_at = datetime.now(timezone.utc)
        if order.order_id:
            self._orders[order.order_id] = order
            self._order_pairs[order.order_id] = data["pair"]
        # Kraken fills are not immediate; fill callback would be triggered by polling or websocket in production
        return order

    async def cancel_order(self, order_id: str) -> bool:
        result = await self._private_request("CancelOrder", {"txid": order_id})
        cancelled = bool(result.get("count", 0))
        if cancelled and order_id in self._orders:
            self._orders[order_id].status = OrderStatus.CANCELLED
        return cancelled

    async def modify_order(self, order_id: str, quantity: Optional[float] = None, price: Optional[float] = None) -> Order:
        raise NotImplementedError("Order modification not implemented for Kraken.")

    async def get_order_status(self, order_id: str) -> Order:
        result = await self._private_request("QueryOrders", {"txid": order_id})
        info = result.get(order_id, {})
        side = OrderSide.BUY if str(info.get("descr", {}).get("type", "buy")).lower() == "buy" else OrderSide.SELL
        raw_type = str(info.get("descr", {}).get("ordertype", "limit")).lower()
        if raw_type.startswith("market"):
            order_type = OrderType.MARKET
        elif raw_type.startswith("stop"):
            order_type = OrderType.STOP
        else:
            order_type = OrderType.LIMIT
        order = Order(
            order_id=order_id,
            symbol=info.get("descr", {}).get("pair", ""),
            side=side,
            order_type=order_type,
            quantity=float(info.get("vol", 0)),
            price=float(info.get("descr", {}).get("price", 0.0) or 0.0),
            status=self._map_kraken_status(info.get("status", "pending")),
            filled_quantity=float(info.get("vol_exec", 0)),
            avg_fill_price=float(info.get("price", 0.0) or 0.0),
            commission=0.0,
        )
        self._orders[order_id] = order
        return order

    async def get_positions(self) -> Dict[str, float]:
        # Kraken spot: positions are balances
        return await self.get_account_balance()

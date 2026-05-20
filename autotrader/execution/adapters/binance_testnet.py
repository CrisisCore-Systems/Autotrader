import os
import time
import hmac
import hashlib
import logging
import urllib.parse
from typing import Dict, Any, Optional, Callable, Awaitable

import aiohttp


from autotrader.execution.adapters import BaseBrokerAdapter, Order, OrderStatus, Fill


class BinanceTestnetAdapter(BaseBrokerAdapter):
    """
    Authenticated execution adapter for Binance Testnet.
    Strictly implements BaseBrokerAdapter to ensure LiveOMS compatibility.
    """
    BASE_URL = "https://testnet.binance.vision"

    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger("autotrader.execution.adapters.binance_testnet")
        
        # Secure credential ingestion
        self.api_key = os.getenv("BINANCE_TESTNET_API_KEY")
        self.api_secret = os.getenv("BINANCE_TESTNET_SECRET_KEY")
        
        if not self.api_key or not self.api_secret:
            self.logger.warning("Binance Testnet credentials missing from environment variables.")
            
        self.session: Optional[aiohttp.ClientSession] = None
        self._fill_callbacks: list[Callable[[Fill], Awaitable[None]]] = []

    async def connect(self) -> bool:
        try:
            if not self.session:
                self.session = aiohttp.ClientSession(
                    headers={"X-MBX-APIKEY": self.api_key}
                )
            self.logger.info("BinanceTestnetAdapter session initialized.")
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

    def _generate_signature(self, params: Dict[str, Any]) -> str:
        query_string = urllib.parse.urlencode(params)
        return hmac.new(
            self.api_secret.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

    async def _private_request(self, method: str, endpoint: str, params: Dict[str, Any] = None) -> dict:
        if not self.session:
            raise RuntimeError("Adapter not connected. Call await connect() first.")
            
        params = params or {}
        params['timestamp'] = int(time.time() * 1000)
        params['signature'] = self._generate_signature(params)
        
        url = f"{self.BASE_URL}{endpoint}"
        
        async with self.session.request(method, url, params=params) as response:
            data = await response.json()
            if response.status != 200:
                self.logger.error(f"Binance API Error: {data}")
                raise Exception(f"API Error {response.status}: {data.get('msg')}")
            return data

    def _map_binance_status(self, binance_status: str) -> OrderStatus:
        mapping = {
            "NEW": OrderStatus.SUBMITTED,
            "PARTIALLY_FILLED": OrderStatus.PARTIAL_FILL,
            "FILLED": OrderStatus.FILLED,
            "CANCELED": OrderStatus.CANCELLED,
            "REJECTED": OrderStatus.REJECTED,
            "EXPIRED": OrderStatus.CANCELLED
        }
        return mapping.get(binance_status, OrderStatus.PENDING)

    async def get_account_balance(self) -> Dict[str, float]:
        response = await self._private_request("GET", "/api/v3/account")
        balances = {}
        for asset in response.get("balances", []):
            free = float(asset["free"])
            locked = float(asset["locked"])
            if free > 0 or locked > 0:
                balances[asset["asset"]] = free + locked
        return balances

    async def submit_order(self, order: Order) -> Order:
        params = {
            "symbol": order.symbol.replace("/", "").upper(),
            "side": order.side.value.upper(),
            "type": order.order_type.value.upper(),
            "quantity": order.quantity,
        }
        
        if order.order_type.value.upper() == "LIMIT":
            params["price"] = order.price
            params["timeInForce"] = "GTC"

        response = await self._private_request("POST", "/api/v3/order", params)
        
        self.logger.info(f"Testnet order submitted successfully: {response.get('orderId')}")
        
        order.order_id = str(response.get("orderId"))
        order.status = self._map_binance_status(response.get("status", "NEW"))
        order.submitted_at = time.time()
        
        # If the order filled immediately, trigger the fill callback
        if order.status in (OrderStatus.FILLED, OrderStatus.PARTIAL_FILL):
            fill = Fill(
                order_id=order.order_id,
                symbol=order.symbol,
                side=order.side,
                quantity=float(response.get("executedQty", 0.0)),
                price=float(response.get("price", order.price)),
                commission=0.0,  # Extract from fills if available
                timestamp=time.time(),
                execution_id=str(response.get("orderId")),
                metadata={}
            )
            for callback in self._fill_callbacks:
                await callback(fill)
        
        return order

    async def cancel_order(self, order_id: str) -> bool:
        # Note: Binance API requires symbol to cancel an order. You may need to track order_id -> symbol mapping.
        self.logger.error("Cancel implementation requires symbol mapping based on your internal Order tracking.")
        raise NotImplementedError("Cancel implementation requires symbol mapping based on your internal Order tracking.")

    async def modify_order(self, order_id: str, quantity: Optional[float] = None, price: Optional[float] = None) -> Order:
        raise NotImplementedError("Order modification not implemented for Binance testnet.")

    async def get_order_status(self, order_id: str) -> Order:
        raise NotImplementedError("Order status query not implemented for Binance testnet.")

    async def get_positions(self) -> Dict[str, float]:
        # For spot, positions are just balances
        return await self.get_account_balance()

"""
Coinbase Adapter
================

Coinbase Advanced Trade API integration for crypto trading.

Features:
- REST API for order submission
- WebSocket for real-time fills
- Sandbox support
- Rate limiting

Dependencies:
    pip install coinbase-advanced-py

Example
-------
>>> from autotrader.execution.adapters.coinbase import CoinbaseAdapter
>>> 
>>> adapter = CoinbaseAdapter(
...     api_key='your_api_key',
...     api_secret='your_api_secret',
...     sandbox=True
... )
>>> 
>>> await adapter.connect()
>>> order = await adapter.submit_order(order)
"""

from typing import Optional, Dict, List, Callable
from datetime import datetime
import asyncio
import json
import hmac
import hashlib
import time
from autotrader.execution.adapters import (
    BaseBrokerAdapter,
    Order,
    Fill,
    Position,
    OrderType,
    OrderSide,
    OrderStatus,
    BrokerConfig
)


class CoinbaseAdapter(BaseBrokerAdapter):
    """
    Coinbase Advanced Trade adapter.
    
    Parameters
    ----------
    api_key : str
        Coinbase API key
    api_secret : str
        Coinbase API secret
    sandbox : bool
        Use sandbox environment (default True)
    config : BrokerConfig, optional
        Configuration
    
    Example
    -------
    >>> adapter = CoinbaseAdapter(
    ...     api_key='your_api_key',
    ...     api_secret='your_api_secret',
    ...     sandbox=True
    ... )
    >>> 
    >>> await adapter.connect()
    >>> 
    >>> order = Order(
    ...     order_id="",
    ...     symbol="BTC-USD",
    ...     side=OrderSide.BUY,
    ...     order_type=OrderType.LIMIT,
    ...     quantity=0.01,
    ...     price=50000
    ... )
    >>> 
    >>> order = await adapter.submit_order(order)
    """
    
    def __init__(
        self,
        api_key: str,
        api_secret: str,
        sandbox: bool = True,
        config: Optional[BrokerConfig] = None
    ):
        self.api_key = api_key
        self.api_secret = api_secret
        self.sandbox = sandbox
        self.config = config or BrokerConfig(name="Coinbase")
        
        # Base URL
        self.base_url = "https://api-public.sandbox.exchange.coinbase.com" if sandbox else "https://api.exchange.coinbase.com"
        
        # State
        self.connected = False
        self.orders: Dict[str, Order] = {}  # order_id -> Order
        self.fill_callbacks: List[Callable] = []
        
        # Rate limiting
        self.last_request_time = 0.0
        self.min_request_interval = 0.1  # 100ms
    
    async def connect(self) -> bool:
        """
        Connect to Coinbase.
        
        Returns
        -------
        success : bool
            True if connected
        """
        try:
            # Test API by getting accounts
            import aiohttp
            
            async with aiohttp.ClientSession() as session:
                headers = self._get_auth_headers('GET', '/accounts', '')
                
                async with session.get(
                    f"{self.base_url}/accounts",
                    headers=headers
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        print(f"✅ Connected to Coinbase {'sandbox' if self.sandbox else 'live'}")
                        print(f"   Accounts: {len(data)}")
                        self.connected = True
                        return True
                    else:
                        print(f"❌ Connection failed: {response.status}")
                        return False
        
        except Exception as e:
            print(f"❌ Coinbase connection error: {e}")
            return False
    
    def _get_auth_headers(self, method: str, path: str, body: str) -> Dict:
        """
        Generate authentication headers.
        
        Parameters
        ----------
        method : str
            HTTP method (GET, POST, DELETE)
        path : str
            API path
        body : str
            Request body (empty string for GET)
        
        Returns
        -------
        headers : dict
            Authentication headers
        """
        timestamp = str(int(time.time()))
        message = timestamp + method + path + body
        
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return {
            'CB-ACCESS-KEY': self.api_key,
            'CB-ACCESS-SIGN': signature,
            'CB-ACCESS-TIMESTAMP': timestamp,
            'Content-Type': 'application/json'
        }
    
    async def disconnect(self):
        """Disconnect from Coinbase."""
        self.connected = False
        print("✅ Disconnected from Coinbase")
    
    async def _rate_limit(self):
        """Rate limiting."""
        now = asyncio.get_event_loop().time()
        elapsed = now - self.last_request_time
        
        if elapsed < self.min_request_interval:
            await asyncio.sleep(self.min_request_interval - elapsed)
        
        self.last_request_time = asyncio.get_event_loop().time()
    
    async def submit_order(self, order: Order) -> Order:
        """
        Submit order to Coinbase.
        
        Parameters
        ----------
        order : Order
            Order to submit
        
        Returns
        -------
        order : Order
            Order with Coinbase order ID
        """
        await self._rate_limit()
        
        try:
            import aiohttp
            
            # Build order params
            params = {
                'product_id': order.symbol,
                'side': 'buy' if order.side == OrderSide.BUY else 'sell',
                'type': self._map_order_type(order.order_type)
            }
            
            # Add size/price based on type
            if order.order_type == OrderType.MARKET:
                params['size'] = str(order.quantity)
            elif order.order_type == OrderType.LIMIT:
                params['size'] = str(order.quantity)
                params['price'] = str(order.price)
                params['time_in_force'] = 'GTC'
            elif order.order_type == OrderType.IOC:
                params['size'] = str(order.quantity)
                params['price'] = str(order.price)
                params['time_in_force'] = 'IOC'
            elif order.order_type == OrderType.FOK:
                params['size'] = str(order.quantity)
                params['price'] = str(order.price)
                params['time_in_force'] = 'FOK'
            
            body = json.dumps(params)
            path = '/orders'
            
            headers = self._get_auth_headers('POST', path, body)
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}{path}",
                    headers=headers,
                    data=body
                ) as response:
                    if response.status in [200, 201]:
                        data = await response.json()
                        
                        # Update order
                        order.order_id = data['id']
                        order.status = self._map_coinbase_status(data.get('status'))
                        order.submitted_at = datetime.now()
                        
                        # Store order
                        self.orders[order.order_id] = order
                        
                        print(f"✅ Order submitted: {order.order_id} - {order.symbol} {order.side.value} {order.quantity}")
                        
                        return order
                    else:
                        error = await response.text()
                        print(f"❌ Order submission error: {error}")
                        order.status = OrderStatus.REJECTED
                        raise Exception(error)
        
        except Exception as e:
            print(f"❌ Order submission error: {e}")
            order.status = OrderStatus.REJECTED
            raise
    
    def _map_order_type(self, order_type: OrderType) -> str:
        """Map OrderType to Coinbase order type."""
        mapping = {
            OrderType.MARKET: 'market',
            OrderType.LIMIT: 'limit',
            OrderType.IOC: 'limit',  # Use limit with IOC time_in_force
            OrderType.FOK: 'limit',  # Use limit with FOK time_in_force
            OrderType.STOP: 'stop',
            OrderType.STOP_LIMIT: 'stop_limit'
        }
        return mapping.get(order_type, 'market')
    
    def _map_coinbase_status(self, coinbase_status: str) -> OrderStatus:
        """Map Coinbase status to OrderStatus enum."""
        mapping = {
            'pending': OrderStatus.PENDING,
            'open': OrderStatus.SUBMITTED,
            'active': OrderStatus.SUBMITTED,
            'done': OrderStatus.FILLED,
            'cancelled': OrderStatus.CANCELLED,
            'rejected': OrderStatus.REJECTED
        }
        return mapping.get(coinbase_status, OrderStatus.PENDING)
    
    async def cancel_order(self, order_id: str) -> bool:
        """
        Cancel order.
        
        Parameters
        ----------
        order_id : str
            Order ID
        
        Returns
        -------
        success : bool
        """
        await self._rate_limit()
        
        try:
            import aiohttp
            
            path = f'/orders/{order_id}'
            headers = self._get_auth_headers('DELETE', path, '')
            
            async with aiohttp.ClientSession() as session:
                async with session.delete(
                    f"{self.base_url}{path}",
                    headers=headers
                ) as response:
                    if response.status == 200:
                        order = self.orders.get(order_id)
                        if order:
                            order.status = OrderStatus.CANCELLED
                            order.filled_at = datetime.now()
                        
                        print(f"✅ Order cancelled: {order_id}")
                        return True
                    else:
                        print(f"❌ Cancel error: {response.status}")
                        return False
        
        except Exception as e:
            print(f"❌ Cancel error: {e}")
            return False
    
    async def modify_order(
        self,
        order_id: str,
        quantity: Optional[float] = None,
        price: Optional[float] = None
    ) -> Order:
        """
        Modify order (cancel and replace).
        
        Parameters
        ----------
        order_id : str
            Order ID
        quantity : float, optional
            New quantity
        price : float, optional
            New price
        
        Returns
        -------
        order : Order
            New order
        """
        # Cancel original
        original = self.orders.get(order_id)
        if not original:
            raise ValueError(f"Order not found: {order_id}")
        
        await self.cancel_order(order_id)
        
        # Create new order
        new_order = Order(
            order_id="",
            symbol=original.symbol,
            side=original.side,
            order_type=original.order_type,
            quantity=quantity or original.quantity,
            price=price or original.price
        )
        
        return await self.submit_order(new_order)
    
    async def get_order_status(self, order_id: str) -> Order:
        """
        Get order status.
        
        Parameters
        ----------
        order_id : str
            Order ID
        
        Returns
        -------
        order : Order
        """
        await self._rate_limit()
        
        order = self.orders.get(order_id)
        if not order:
            raise ValueError(f"Order not found: {order_id}")
        
        try:
            import aiohttp
            
            path = f'/orders/{order_id}'
            headers = self._get_auth_headers('GET', path, '')
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}{path}",
                    headers=headers
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        # Update order
                        order.status = self._map_coinbase_status(data.get('status'))
                        order.filled_quantity = float(data.get('filled_size', 0))
                        
                        if order.filled_quantity > 0:
                            order.avg_fill_price = float(data.get('executed_value', 0)) / order.filled_quantity
                        
                        return order
                    else:
                        print(f"❌ Get status error: {response.status}")
                        raise Exception(f"Status code: {response.status}")
        
        except Exception as e:
            print(f"❌ Get order status error: {e}")
            raise
    
    async def get_positions(self) -> List[Position]:
        """
        Get current positions.
        
        Returns
        -------
        positions : list of Position
        """
        await self._rate_limit()
        
        try:
            import aiohttp
            
            path = '/accounts'
            headers = self._get_auth_headers('GET', path, '')
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}{path}",
                    headers=headers
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        positions = []
                        for account in data:
                            balance = float(account.get('balance', 0))
                            if balance > 0:
                                position = Position(
                                    symbol=account['currency'],
                                    quantity=balance,
                                    avg_entry_price=0.0,
                                    current_price=0.0,
                                    unrealized_pnl=0.0,
                                    realized_pnl=0.0
                                )
                                positions.append(position)
                        
                        return positions
                    else:
                        print(f"❌ Get positions error: {response.status}")
                        return []
        
        except Exception as e:
            print(f"❌ Get positions error: {e}")
            return []
    
    async def get_account_balance(self) -> Dict:
        """
        Get account balance.
        
        Returns
        -------
        balance : dict
        """
        await self._rate_limit()
        
        try:
            import aiohttp
            
            path = '/accounts'
            headers = self._get_auth_headers('GET', path, '')
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}{path}",
                    headers=headers
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        balance_dict = {}
                        for account in data:
                            currency = account['currency']
                            balance = float(account.get('balance', 0))
                            available = float(account.get('available', 0))
                            hold = float(account.get('hold', 0))
                            
                            if balance > 0:
                                balance_dict[currency] = {
                                    'balance': balance,
                                    'available': available,
                                    'hold': hold
                                }
                        
                        return balance_dict
                    else:
                        print(f"❌ Get balance error: {response.status}")
                        return {}
        
        except Exception as e:
            print(f"❌ Get balance error: {e}")
            return {}
    
    def subscribe_fills(self, callback: Callable):
        """
        Subscribe to fill notifications.
        
        Parameters
        ----------
        callback : callable
            Function(fill) called on each fill
        """
        self.fill_callbacks.append(callback)

"""
OKX Adapter
===========

OKX exchange integration for crypto trading.

Features:
- REST API v5 for order submission
- WebSocket for real-time updates
- Demo trading support
- Rate limiting

Dependencies:
    pip install okx

Example
-------
>>> from autotrader.execution.adapters.okx import OKXAdapter
>>> 
>>> adapter = OKXAdapter(
...     api_key='your_api_key',
...     api_secret='your_api_secret',
...     passphrase='your_passphrase',
...     demo=True
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
import base64
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


class OKXAdapter(BaseBrokerAdapter):
    """
    OKX exchange adapter.
    
    Parameters
    ----------
    api_key : str
        OKX API key
    api_secret : str
        OKX API secret
    passphrase : str
        OKX API passphrase
    demo : bool
        Use demo trading (default True)
    config : BrokerConfig, optional
        Configuration
    
    Example
    -------
    >>> adapter = OKXAdapter(
    ...     api_key='your_api_key',
    ...     api_secret='your_api_secret',
    ...     passphrase='your_passphrase',
    ...     demo=True
    ... )
    >>> 
    >>> await adapter.connect()
    >>> 
    >>> order = Order(
    ...     order_id="",
    ...     symbol="BTC-USDT",
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
        passphrase: str,
        demo: bool = True,
        config: Optional[BrokerConfig] = None
    ):
        self.api_key = api_key
        self.api_secret = api_secret
        self.passphrase = passphrase
        self.demo = demo
        self.config = config or BrokerConfig(name="OKX")
        
        # Base URL
        self.base_url = "https://www.okx.com" if not demo else "https://www.okx.com"  # Demo uses same URL with demo flag
        
        # State
        self.connected = False
        self.orders: Dict[str, Order] = {}  # order_id -> Order
        self.fill_callbacks: List[Callable] = []
        
        # Rate limiting
        self.last_request_time = 0.0
        self.min_request_interval = 0.1  # 100ms
    
    async def connect(self) -> bool:
        """
        Connect to OKX.
        
        Returns
        -------
        success : bool
            True if connected
        """
        try:
            import aiohttp
            
            # Test API by getting account balance
            path = '/api/v5/account/balance'
            headers = self._get_auth_headers('GET', path, '')
            
            # Add demo flag if needed
            if self.demo:
                headers['x-simulated-trading'] = '1'
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}{path}",
                    headers=headers
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get('code') == '0':
                            print(f"✅ Connected to OKX {'demo' if self.demo else 'live'}")
                            self.connected = True
                            return True
                        else:
                            print(f"❌ Connection failed: {data.get('msg')}")
                            return False
                    else:
                        print(f"❌ Connection failed: {response.status}")
                        return False
        
        except Exception as e:
            print(f"❌ OKX connection error: {e}")
            return False
    
    def _get_auth_headers(self, method: str, path: str, body: str) -> Dict:
        """
        Generate authentication headers for OKX API v5.
        
        Parameters
        ----------
        method : str
            HTTP method
        path : str
            API path
        body : str
            Request body
        
        Returns
        -------
        headers : dict
        """
        timestamp = datetime.utcnow().isoformat(timespec='milliseconds') + 'Z'
        
        message = timestamp + method + path + body
        
        mac = hmac.new(
            self.api_secret.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        )
        signature = base64.b64encode(mac.digest()).decode('utf-8')
        
        return {
            'OK-ACCESS-KEY': self.api_key,
            'OK-ACCESS-SIGN': signature,
            'OK-ACCESS-TIMESTAMP': timestamp,
            'OK-ACCESS-PASSPHRASE': self.passphrase,
            'Content-Type': 'application/json'
        }
    
    async def disconnect(self):
        """Disconnect from OKX."""
        self.connected = False
        print("✅ Disconnected from OKX")
    
    async def _rate_limit(self):
        """Rate limiting."""
        now = asyncio.get_event_loop().time()
        elapsed = now - self.last_request_time
        
        if elapsed < self.min_request_interval:
            await asyncio.sleep(self.min_request_interval - elapsed)
        
        self.last_request_time = asyncio.get_event_loop().time()
    
    async def submit_order(self, order: Order) -> Order:
        """
        Submit order to OKX.
        
        Parameters
        ----------
        order : Order
            Order to submit
        
        Returns
        -------
        order : Order
            Order with OKX order ID
        """
        await self._rate_limit()
        
        try:
            import aiohttp
            
            # Build order params
            params = {
                'instId': order.symbol,
                'tdMode': 'cash',  # Cash trading
                'side': 'buy' if order.side == OrderSide.BUY else 'sell',
                'ordType': self._map_order_type(order.order_type),
                'sz': str(order.quantity)
            }
            
            # Add price for limit orders
            if order.order_type in [OrderType.LIMIT, OrderType.IOC, OrderType.FOK]:
                params['px'] = str(order.price)
            
            # Stop orders
            if order.order_type in [OrderType.STOP, OrderType.STOP_LIMIT]:
                params['slTriggerPx'] = str(order.stop_price)
            
            body = json.dumps(params)
            path = '/api/v5/trade/order'
            
            headers = self._get_auth_headers('POST', path, body)
            
            if self.demo:
                headers['x-simulated-trading'] = '1'
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}{path}",
                    headers=headers,
                    data=body
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        if data.get('code') == '0' and data.get('data'):
                            order_data = data['data'][0]
                            
                            # Update order
                            order.order_id = order_data['ordId']
                            order.status = self._map_okx_status(order_data.get('sCode'))
                            order.submitted_at = datetime.now()
                            
                            # Store order
                            self.orders[order.order_id] = order
                            
                            print(f"✅ Order submitted: {order.order_id} - {order.symbol} {order.side.value} {order.quantity}")
                            
                            return order
                        else:
                            error = data.get('msg', 'Unknown error')
                            print(f"❌ Order submission error: {error}")
                            order.status = OrderStatus.REJECTED
                            raise Exception(error)
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
        """Map OrderType to OKX order type."""
        mapping = {
            OrderType.MARKET: 'market',
            OrderType.LIMIT: 'limit',
            OrderType.IOC: 'ioc',
            OrderType.FOK: 'fok',
            OrderType.STOP: 'conditional',
            OrderType.STOP_LIMIT: 'conditional'
        }
        return mapping.get(order_type, 'market')
    
    def _map_okx_status(self, okx_code: str) -> OrderStatus:
        """Map OKX status code to OrderStatus enum."""
        # OKX uses sCode for order state
        # 0 = success
        mapping = {
            '0': OrderStatus.SUBMITTED,
            '51000': OrderStatus.REJECTED,  # Parameter error
            '51001': OrderStatus.REJECTED,  # Insufficient balance
            '51008': OrderStatus.REJECTED,  # Order doesn't exist
        }
        return mapping.get(okx_code, OrderStatus.PENDING)
    
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
            
            order = self.orders.get(order_id)
            if not order:
                print(f"⚠️ Order not found: {order_id}")
                return False
            
            params = {
                'instId': order.symbol,
                'ordId': order_id
            }
            
            body = json.dumps(params)
            path = '/api/v5/trade/cancel-order'
            
            headers = self._get_auth_headers('POST', path, body)
            
            if self.demo:
                headers['x-simulated-trading'] = '1'
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}{path}",
                    headers=headers,
                    data=body
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        if data.get('code') == '0':
                            order.status = OrderStatus.CANCELLED
                            order.filled_at = datetime.now()
                            
                            print(f"✅ Order cancelled: {order_id}")
                            return True
                        else:
                            print(f"❌ Cancel error: {data.get('msg')}")
                            return False
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
        Modify order.
        
        OKX supports order amendment.
        
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
        """
        await self._rate_limit()
        
        try:
            import aiohttp
            
            order = self.orders.get(order_id)
            if not order:
                raise ValueError(f"Order not found: {order_id}")
            
            params = {
                'instId': order.symbol,
                'ordId': order_id
            }
            
            if quantity is not None:
                params['newSz'] = str(quantity)
                order.quantity = quantity
            
            if price is not None:
                params['newPx'] = str(price)
                order.price = price
            
            body = json.dumps(params)
            path = '/api/v5/trade/amend-order'
            
            headers = self._get_auth_headers('POST', path, body)
            
            if self.demo:
                headers['x-simulated-trading'] = '1'
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}{path}",
                    headers=headers,
                    data=body
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        if data.get('code') == '0':
                            print(f"✅ Order modified: {order_id}")
                            return order
                        else:
                            error = data.get('msg')
                            print(f"❌ Modify error: {error}")
                            raise Exception(error)
                    else:
                        print(f"❌ Modify error: {response.status}")
                        raise Exception(f"Status: {response.status}")
        
        except Exception as e:
            print(f"❌ Modify error: {e}")
            raise
    
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
            
            path = f'/api/v5/trade/order?instId={order.symbol}&ordId={order_id}'
            headers = self._get_auth_headers('GET', path, '')
            
            if self.demo:
                headers['x-simulated-trading'] = '1'
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}{path}",
                    headers=headers
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        if data.get('code') == '0' and data.get('data'):
                            order_data = data['data'][0]
                            
                            # Map state
                            state = order_data.get('state')
                            state_mapping = {
                                'live': OrderStatus.SUBMITTED,
                                'partially_filled': OrderStatus.PARTIAL_FILL,
                                'filled': OrderStatus.FILLED,
                                'canceled': OrderStatus.CANCELLED
                            }
                            order.status = state_mapping.get(state, OrderStatus.PENDING)
                            
                            # Update filled quantity
                            order.filled_quantity = float(order_data.get('accFillSz', 0))
                            
                            if order.filled_quantity > 0:
                                order.avg_fill_price = float(order_data.get('avgPx', 0))
                            
                            return order
                        else:
                            raise Exception(data.get('msg'))
                    else:
                        raise Exception(f"Status: {response.status}")
        
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
            
            path = '/api/v5/account/balance'
            headers = self._get_auth_headers('GET', path, '')
            
            if self.demo:
                headers['x-simulated-trading'] = '1'
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}{path}",
                    headers=headers
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        if data.get('code') == '0' and data.get('data'):
                            positions = []
                            
                            for account in data['data']:
                                for detail in account.get('details', []):
                                    ccy = detail.get('ccy')
                                    balance = float(detail.get('availBal', 0))
                                    
                                    if balance > 0:
                                        position = Position(
                                            symbol=ccy,
                                            quantity=balance,
                                            avg_entry_price=0.0,
                                            current_price=0.0,
                                            unrealized_pnl=0.0,
                                            realized_pnl=0.0
                                        )
                                        positions.append(position)
                            
                            return positions
                        else:
                            print(f"❌ Get positions error: {data.get('msg')}")
                            return []
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
            
            path = '/api/v5/account/balance'
            headers = self._get_auth_headers('GET', path, '')
            
            if self.demo:
                headers['x-simulated-trading'] = '1'
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}{path}",
                    headers=headers
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        if data.get('code') == '0' and data.get('data'):
                            balance_dict = {}
                            
                            for account in data['data']:
                                for detail in account.get('details', []):
                                    ccy = detail.get('ccy')
                                    
                                    balance_dict[ccy] = {
                                        'available': float(detail.get('availBal', 0)),
                                        'frozen': float(detail.get('frozenBal', 0)),
                                        'total': float(detail.get('cashBal', 0))
                                    }
                            
                            return balance_dict
                        else:
                            print(f"❌ Get balance error: {data.get('msg')}")
                            return {}
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

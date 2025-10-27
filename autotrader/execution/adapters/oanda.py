"""
Oanda Adapter
=============

Oanda v20 API integration for FX trading.

Features:
- REST API v20 for order submission
- Streaming for real-time prices
- Practice account support
- Position management

Dependencies:
    pip install oandapyV20

Example
-------
>>> from autotrader.execution.adapters.oanda import OandaAdapter
>>> 
>>> adapter = OandaAdapter(
...     account_id='your_account_id',
...     access_token='your_access_token',
...     practice=True
... )
>>> 
>>> await adapter.connect()
>>> order = await adapter.submit_order(order)
"""

from typing import Optional, Dict, List, Callable
from datetime import datetime
import asyncio
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


class OandaAdapter(BaseBrokerAdapter):
    """
    Oanda v20 adapter for FX trading.
    
    Parameters
    ----------
    account_id : str
        Oanda account ID
    access_token : str
        Oanda API access token
    practice : bool
        Use practice account (default True)
    config : BrokerConfig, optional
        Configuration
    
    Example
    -------
    >>> adapter = OandaAdapter(
    ...     account_id='001-001-1234567-001',
    ...     access_token='your_token',
    ...     practice=True
    ... )
    >>> 
    >>> await adapter.connect()
    >>> 
    >>> order = Order(
    ...     order_id="",
    ...     symbol="EUR_USD",
    ...     side=OrderSide.BUY,
    ...     order_type=OrderType.MARKET,
    ...     quantity=10000  # 10k units
    ... )
    >>> 
    >>> order = await adapter.submit_order(order)
    """
    
    def __init__(
        self,
        account_id: str,
        access_token: str,
        practice: bool = True,
        config: Optional[BrokerConfig] = None
    ):
        self.account_id = account_id
        self.access_token = access_token
        self.practice = practice
        self.config = config or BrokerConfig(name="Oanda")
        
        # Base URL
        self.base_url = "https://api-fxpractice.oanda.com" if practice else "https://api-fxtrade.oanda.com"
        
        # State
        self.connected = False
        self.orders: Dict[str, Order] = {}  # order_id -> Order
        self.fill_callbacks: List[Callable] = []
        
        # Rate limiting
        self.last_request_time = 0.0
        self.min_request_interval = 0.1  # 100ms
    
    async def connect(self) -> bool:
        """
        Connect to Oanda.
        
        Returns
        -------
        success : bool
            True if connected
        """
        try:
            import aiohttp
            
            # Test API by getting account info
            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Content-Type': 'application/json'
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/v3/accounts/{self.account_id}",
                    headers=headers
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        account = data.get('account', {})
                        
                        print(f"✅ Connected to Oanda {'practice' if self.practice else 'live'}")
                        print(f"   Account: {account.get('alias', self.account_id)}")
                        print(f"   Balance: {account.get('balance', 'N/A')}")
                        
                        self.connected = True
                        return True
                    else:
                        error = await response.text()
                        print(f"❌ Connection failed: {error}")
                        return False
        
        except Exception as e:
            print(f"❌ Oanda connection error: {e}")
            return False
    
    async def disconnect(self):
        """Disconnect from Oanda."""
        self.connected = False
        print("✅ Disconnected from Oanda")
    
    async def _rate_limit(self):
        """Rate limiting."""
        now = asyncio.get_event_loop().time()
        elapsed = now - self.last_request_time
        
        if elapsed < self.min_request_interval:
            await asyncio.sleep(self.min_request_interval - elapsed)
        
        self.last_request_time = asyncio.get_event_loop().time()
    
    async def submit_order(self, order: Order) -> Order:
        """
        Submit order to Oanda.
        
        Oanda uses units instead of quantity:
        - Positive units = buy
        - Negative units = sell
        
        Parameters
        ----------
        order : Order
            Order to submit
        
        Returns
        -------
        order : Order
            Order with Oanda order ID
        """
        await self._rate_limit()
        
        try:
            import aiohttp
            import json
            
            # Calculate units (positive for buy, negative for sell)
            units = order.quantity if order.side == OrderSide.BUY else -order.quantity
            
            # Build order request
            order_request = {
                'order': {
                    'instrument': order.symbol,
                    'units': str(int(units)),
                    'type': self._map_order_type(order.order_type),
                    'timeInForce': 'FOK' if order.order_type == OrderType.FOK else 'GTC'
                }
            }
            
            # Add price for limit orders
            if order.order_type in [OrderType.LIMIT, OrderType.IOC, OrderType.FOK]:
                order_request['order']['price'] = str(order.price)
            
            # Stop orders
            if order.order_type == OrderType.STOP:
                order_request['order']['priceBound'] = str(order.stop_price)
            
            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Content-Type': 'application/json'
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/v3/accounts/{self.account_id}/orders",
                    headers=headers,
                    data=json.dumps(order_request)
                ) as response:
                    if response.status in [200, 201]:
                        data = await response.json()
                        
                        # Get order details
                        order_fill = data.get('orderFillTransaction')
                        order_create = data.get('orderCreateTransaction')
                        
                        if order_fill:
                            # Market order filled immediately
                            order.order_id = order_fill['id']
                            order.status = OrderStatus.FILLED
                            order.filled_quantity = abs(float(order_fill['units']))
                            order.avg_fill_price = float(order_fill['price'])
                            order.submitted_at = datetime.now()
                            order.filled_at = datetime.now()
                            
                            # Create fill
                            fill = Fill(
                                order_id=order.order_id,
                                symbol=order.symbol,
                                side=order.side,
                                quantity=order.filled_quantity,
                                price=order.avg_fill_price,
                                commission=0.0,  # Oanda uses spread instead
                                timestamp=datetime.now(),
                                execution_id=order_fill['id'],
                                metadata={'oanda_transaction_id': order_fill['id']}
                            )
                            
                            # Notify callbacks
                            self._notify_fills(fill)
                        
                        elif order_create:
                            # Limit order created
                            order.order_id = order_create['id']
                            order.status = OrderStatus.SUBMITTED
                            order.submitted_at = datetime.now()
                        
                        else:
                            raise Exception("No order or fill transaction in response")
                        
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
        """Map OrderType to Oanda order type."""
        mapping = {
            OrderType.MARKET: 'MARKET',
            OrderType.LIMIT: 'LIMIT',
            OrderType.IOC: 'LIMIT',  # Use LIMIT with IOC timeInForce
            OrderType.FOK: 'LIMIT',  # Use LIMIT with FOK timeInForce
            OrderType.STOP: 'STOP',
            OrderType.STOP_LIMIT: 'STOP'
        }
        return mapping.get(order_type, 'MARKET')
    
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
            
            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Content-Type': 'application/json'
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.put(
                    f"{self.base_url}/v3/accounts/{self.account_id}/orders/{order_id}/cancel",
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
                        error = await response.text()
                        print(f"❌ Cancel error: {error}")
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
        
        Oanda doesn't support order modification directly.
        
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
            
            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Content-Type': 'application/json'
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/v3/accounts/{self.account_id}/orders/{order_id}",
                    headers=headers
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        order_data = data.get('order', {})
                        
                        # Map state
                        state = order_data.get('state')
                        state_mapping = {
                            'PENDING': OrderStatus.PENDING,
                            'FILLED': OrderStatus.FILLED,
                            'TRIGGERED': OrderStatus.SUBMITTED,
                            'CANCELLED': OrderStatus.CANCELLED
                        }
                        order.status = state_mapping.get(state, OrderStatus.PENDING)
                        
                        # Update fill info
                        filled_units = abs(float(order_data.get('filledUnits', 0)))
                        if filled_units > 0:
                            order.filled_quantity = filled_units
                            order.avg_fill_price = float(order_data.get('averageFillPrice', 0))
                        
                        return order
                    else:
                        error = await response.text()
                        print(f"❌ Get status error: {error}")
                        raise Exception(error)
        
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
            
            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Content-Type': 'application/json'
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/v3/accounts/{self.account_id}/openPositions",
                    headers=headers
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        positions_data = data.get('positions', [])
                        
                        positions = []
                        
                        for pos in positions_data:
                            instrument = pos.get('instrument')
                            long_units = float(pos.get('long', {}).get('units', 0))
                            short_units = float(pos.get('short', {}).get('units', 0))
                            
                            # Net position
                            net_units = long_units + short_units
                            
                            if net_units != 0:
                                avg_price = 0.0
                                unrealized_pl = 0.0
                                
                                if long_units != 0:
                                    avg_price = float(pos.get('long', {}).get('averagePrice', 0))
                                    unrealized_pl = float(pos.get('long', {}).get('unrealizedPL', 0))
                                elif short_units != 0:
                                    avg_price = float(pos.get('short', {}).get('averagePrice', 0))
                                    unrealized_pl = float(pos.get('short', {}).get('unrealizedPL', 0))
                                
                                position = Position(
                                    symbol=instrument,
                                    quantity=net_units,
                                    avg_entry_price=avg_price,
                                    current_price=0.0,  # Would need market data
                                    unrealized_pnl=unrealized_pl,
                                    realized_pnl=0.0
                                )
                                positions.append(position)
                        
                        return positions
                    else:
                        error = await response.text()
                        print(f"❌ Get positions error: {error}")
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
            
            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Content-Type': 'application/json'
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/v3/accounts/{self.account_id}/summary",
                    headers=headers
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        account = data.get('account', {})
                        
                        balance = {
                            'balance': float(account.get('balance', 0)),
                            'nav': float(account.get('NAV', 0)),
                            'unrealized_pl': float(account.get('unrealizedPL', 0)),
                            'margin_used': float(account.get('marginUsed', 0)),
                            'margin_available': float(account.get('marginAvailable', 0))
                        }
                        
                        return balance
                    else:
                        error = await response.text()
                        print(f"❌ Get balance error: {error}")
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

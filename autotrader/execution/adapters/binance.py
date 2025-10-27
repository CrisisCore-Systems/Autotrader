"""
Binance Adapter
===============

Binance exchange integration for crypto trading.

Features:
- REST API for order submission
- WebSocket for real-time fills
- User data stream for order updates
- Testnet support
- Rate limiting

Dependencies:
    pip install binance-connector-python

Example
-------
>>> from autotrader.execution.adapters.binance import BinanceAdapter
>>> 
>>> adapter = BinanceAdapter(
...     api_key='your_api_key',
...     api_secret='your_api_secret',
...     testnet=True
... )
>>> 
>>> await adapter.connect()
>>> order = await adapter.submit_order(order)
"""

from typing import Optional, Dict, List, Callable
from datetime import datetime
import asyncio
import json
from binance.spot import Spot
from binance.websocket.spot.websocket_stream import SpotWebsocketStreamClient
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


class BinanceAdapter(BaseBrokerAdapter):
    """
    Binance exchange adapter.
    
    Parameters
    ----------
    api_key : str
        Binance API key
    api_secret : str
        Binance API secret
    testnet : bool
        Use testnet (default True for safety)
    config : BrokerConfig, optional
        Configuration
    
    Example
    -------
    >>> adapter = BinanceAdapter(
    ...     api_key='your_api_key',
    ...     api_secret='your_api_secret',
    ...     testnet=True
    ... )
    >>> 
    >>> await adapter.connect()
    >>> 
    >>> order = Order(
    ...     order_id="",
    ...     symbol="BTCUSDT",
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
        testnet: bool = True,
        config: Optional[BrokerConfig] = None
    ):
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet
        self.config = config or BrokerConfig(name="Binance")
        
        # Binance clients
        base_url = "https://testnet.binance.vision" if testnet else "https://api.binance.com"
        self.client = Spot(api_key=api_key, api_secret=api_secret, base_url=base_url)
        
        # WebSocket
        self.ws_client: Optional[SpotWebsocketStreamClient] = None
        self.listen_key: Optional[str] = None
        
        # State
        self.connected = False
        self.orders: Dict[str, Order] = {}  # order_id -> Order
        self.fill_callbacks: List[Callable] = []
        
        # Rate limiting
        self.last_request_time = 0.0
        self.min_request_interval = 0.1  # 100ms between requests
    
    async def connect(self) -> bool:
        """
        Connect to Binance.
        
        Steps:
        1. Test REST API
        2. Get listen key for user data stream
        3. Start WebSocket
        4. Subscribe to user data stream
        
        Returns
        -------
        success : bool
            True if connected
        """
        try:
            # Test REST API
            account = self.client.account()
            print(f"✅ Connected to Binance {'testnet' if self.testnet else 'live'}")
            print(f"   Account: {account.get('accountType', 'N/A')}")
            
            # Get listen key for user data stream
            listen_key_response = self.client.new_listen_key()
            self.listen_key = listen_key_response.get('listenKey')
            
            if not self.listen_key:
                print("❌ Failed to get listen key")
                return False
            
            # Start WebSocket
            await self._start_websocket()
            
            self.connected = True
            return True
        
        except Exception as e:
            print(f"❌ Binance connection error: {e}")
            return False
    
    async def _start_websocket(self):
        """Start WebSocket for user data stream."""
        ws_base = "wss://testnet.binance.vision" if self.testnet else "wss://stream.binance.com:9443"
        
        self.ws_client = SpotWebsocketStreamClient(
            on_message=self._handle_user_data,
            on_error=self._handle_ws_error,
            on_close=self._handle_ws_close
        )
        
        # Subscribe to user data stream
        self.ws_client.user_data(listen_key=self.listen_key)
        print(f"✅ WebSocket connected - user data stream active")
    
    def _handle_user_data(self, _, message: str):
        """
        Handle user data stream messages.
        
        Processes executionReport events for order updates and fills.
        
        Parameters
        ----------
        message : str
            JSON message from WebSocket
        """
        try:
            data = json.loads(message)
            event_type = data.get('e')
            
            if event_type == 'executionReport':
                self._process_execution_report(data)
        
        except Exception as e:
            print(f"Error processing user data: {e}")
    
    def _process_execution_report(self, data: Dict):
        """
        Process executionReport from user data stream.
        
        Updates order status and creates Fill objects.
        
        Binance executionReport fields:
        - s: symbol
        - c: clientOrderId
        - S: side (BUY/SELL)
        - o: order type
        - q: original quantity
        - p: price
        - X: order status
        - z: cumulative filled quantity
        - Z: cumulative quote asset filled
        - n: commission amount
        - T: transaction time
        - i: order ID
        - l: last executed quantity
        - L: last executed price
        
        Parameters
        ----------
        data : dict
            executionReport data
        """
        order_id = str(data.get('i'))  # Binance order ID
        client_order_id = data.get('c', '')
        
        # Find order
        order = self.orders.get(order_id) or self.orders.get(client_order_id)
        
        if not order:
            print(f"⚠️ Unknown order in execution report: {order_id}")
            return
        
        # Update order status
        binance_status = data.get('X')
        order.status = self._map_binance_status(binance_status)
        
        order.filled_quantity = float(data.get('z', 0))
        
        # Calculate average fill price
        cumulative_quote = float(data.get('Z', 0))
        if order.filled_quantity > 0:
            order.avg_fill_price = cumulative_quote / order.filled_quantity
        
        # Commission
        order.commission = float(data.get('n', 0))
        
        # Check if new fill occurred
        last_executed_qty = float(data.get('l', 0))
        last_executed_price = float(data.get('L', 0))
        
        if last_executed_qty > 0:
            # Create Fill object
            fill = Fill(
                order_id=order.order_id,
                symbol=order.symbol,
                side=order.side,
                quantity=last_executed_qty,
                price=last_executed_price,
                commission=float(data.get('n', 0)),
                timestamp=datetime.fromtimestamp(data.get('T', 0) / 1000),
                execution_id=f"{order_id}_{data.get('T')}",
                metadata={'binance_trade_id': data.get('t')}
            )
            
            # Notify callbacks
            self._notify_fills(fill)
        
        # Update timestamps
        if order.status in [OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.REJECTED]:
            order.filled_at = datetime.now()
    
    def _map_binance_status(self, binance_status: str) -> OrderStatus:
        """
        Map Binance order status to OrderStatus enum.
        
        Binance statuses:
        - NEW: Order accepted
        - PARTIALLY_FILLED: Partial fill
        - FILLED: Fully filled
        - CANCELED: Cancelled
        - REJECTED: Rejected
        - EXPIRED: Expired (IOC/FOK)
        
        Parameters
        ----------
        binance_status : str
            Binance status
        
        Returns
        -------
        status : OrderStatus
        """
        mapping = {
            'NEW': OrderStatus.SUBMITTED,
            'PARTIALLY_FILLED': OrderStatus.PARTIAL_FILL,
            'FILLED': OrderStatus.FILLED,
            'CANCELED': OrderStatus.CANCELLED,
            'REJECTED': OrderStatus.REJECTED,
            'EXPIRED': OrderStatus.EXPIRED
        }
        
        return mapping.get(binance_status, OrderStatus.PENDING)
    
    def _handle_ws_error(self, _, error):
        """Handle WebSocket error."""
        print(f"❌ WebSocket error: {error}")
    
    def _handle_ws_close(self, _):
        """Handle WebSocket close."""
        print("⚠️ WebSocket closed")
        self.connected = False
    
    async def disconnect(self):
        """Disconnect from Binance."""
        # Stop WebSocket
        if self.ws_client:
            self.ws_client.stop()
        
        # Delete listen key
        if self.listen_key:
            try:
                self.client.close_listen_key(self.listen_key)
            except Exception as e:
                print(f"Error closing listen key: {e}")
        
        self.connected = False
        print("✅ Disconnected from Binance")
    
    async def _rate_limit(self):
        """Rate limiting between requests."""
        now = asyncio.get_event_loop().time()
        elapsed = now - self.last_request_time
        
        if elapsed < self.min_request_interval:
            await asyncio.sleep(self.min_request_interval - elapsed)
        
        self.last_request_time = asyncio.get_event_loop().time()
    
    async def submit_order(self, order: Order) -> Order:
        """
        Submit order to Binance.
        
        Parameters
        ----------
        order : Order
            Order to submit
        
        Returns
        -------
        order : Order
            Order with Binance order ID
        """
        await self._rate_limit()
        
        try:
            # Map order type
            binance_type = self._map_order_type(order.order_type)
            
            # Map side
            binance_side = 'BUY' if order.side == OrderSide.BUY else 'SELL'
            
            # Build parameters
            params = {
                'symbol': order.symbol,
                'side': binance_side,
                'type': binance_type,
                'quantity': order.quantity
            }
            
            # Add price for limit orders
            if order.order_type in [OrderType.LIMIT, OrderType.STOP_LIMIT]:
                params['price'] = order.price
                params['timeInForce'] = 'GTC'  # Good Till Cancel
            
            # Add stop price for stop orders
            if order.order_type in [OrderType.STOP, OrderType.STOP_LIMIT]:
                params['stopPrice'] = order.stop_price
            
            # IOC time in force
            if order.order_type == OrderType.IOC:
                params['timeInForce'] = 'IOC'
            
            # FOK time in force
            if order.order_type == OrderType.FOK:
                params['timeInForce'] = 'FOK'
            
            # Submit order
            response = self.client.new_order(**params)
            
            # Update order
            order.order_id = str(response['orderId'])
            order.status = self._map_binance_status(response['status'])
            order.submitted_at = datetime.now()
            
            # Store order
            self.orders[order.order_id] = order
            
            print(f"✅ Order submitted: {order.order_id} - {order.symbol} {order.side.value} {order.quantity}")
            
            return order
        
        except Exception as e:
            print(f"❌ Order submission error: {e}")
            order.status = OrderStatus.REJECTED
            raise
    
    def _map_order_type(self, order_type: OrderType) -> str:
        """
        Map OrderType to Binance order type.
        
        Parameters
        ----------
        order_type : OrderType
        
        Returns
        -------
        binance_type : str
        """
        mapping = {
            OrderType.MARKET: 'MARKET',
            OrderType.LIMIT: 'LIMIT',
            OrderType.IOC: 'LIMIT',  # Use LIMIT with IOC timeInForce
            OrderType.FOK: 'LIMIT',  # Use LIMIT with FOK timeInForce
            OrderType.STOP: 'STOP_LOSS',
            OrderType.STOP_LIMIT: 'STOP_LOSS_LIMIT'
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
            order = self.orders.get(order_id)
            if not order:
                print(f"⚠️ Order not found: {order_id}")
                return False
            
            # Cancel order
            self.client.cancel_order(symbol=order.symbol, orderId=int(order_id))
            
            # Update status
            order.status = OrderStatus.CANCELLED
            order.filled_at = datetime.now()
            
            print(f"✅ Order cancelled: {order_id}")
            return True
        
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
        
        Binance doesn't support order modification - must cancel and resubmit.
        
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
        # Get original order
        original = self.orders.get(order_id)
        if not original:
            raise ValueError(f"Order not found: {order_id}")
        
        # Cancel original
        await self.cancel_order(order_id)
        
        # Create new order with updated params
        new_order = Order(
            order_id="",
            symbol=original.symbol,
            side=original.side,
            order_type=original.order_type,
            quantity=quantity or original.quantity,
            price=price or original.price,
            stop_price=original.stop_price
        )
        
        # Submit new order
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
            # Query Binance
            response = self.client.get_order(
                symbol=order.symbol,
                orderId=int(order_id)
            )
            
            # Update order
            order.status = self._map_binance_status(response['status'])
            order.filled_quantity = float(response['executedQty'])
            
            # Calculate avg fill price
            cumulative_quote = float(response.get('cummulativeQuoteQty', 0))
            if order.filled_quantity > 0:
                order.avg_fill_price = cumulative_quote / order.filled_quantity
            
            return order
        
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
            account = self.client.account()
            balances = account.get('balances', [])
            
            positions = []
            
            for balance in balances:
                asset = balance['asset']
                free = float(balance['free'])
                locked = float(balance['locked'])
                total = free + locked
                
                if total > 0:
                    # Create position (simplified - would need price data)
                    position = Position(
                        symbol=asset,
                        quantity=total,
                        avg_entry_price=0.0,  # Would need trade history
                        current_price=0.0,    # Would need market data
                        unrealized_pnl=0.0,
                        realized_pnl=0.0
                    )
                    positions.append(position)
            
            return positions
        
        except Exception as e:
            print(f"❌ Get positions error: {e}")
            return []
    
    async def get_account_balance(self) -> Dict:
        """
        Get account balance.
        
        Returns
        -------
        balance : dict
            {'asset': balance, ...}
        """
        await self._rate_limit()
        
        try:
            account = self.client.account()
            balances = account.get('balances', [])
            
            balance_dict = {}
            for balance in balances:
                asset = balance['asset']
                free = float(balance['free'])
                locked = float(balance['locked'])
                total = free + locked
                
                if total > 0:
                    balance_dict[asset] = {
                        'free': free,
                        'locked': locked,
                        'total': total
                    }
            
            return balance_dict
        
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

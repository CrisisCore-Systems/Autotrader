"""
Interactive Brokers Adapter
===========================

IBKR integration for equities, options, futures, and forex.

Features:
- TWS/Gateway connection
- Contract creation (STK/OPT/FUT/FX)
- Order routing
- Position tracking
- Real-time fills via callbacks

Dependencies:
    pip install ibapi

Example
-------
>>> from autotrader.execution.adapters.ibkr import IBKRAdapter
>>> 
>>> adapter = IBKRAdapter(
...     host='127.0.0.1',
...     port=7497,  # Paper trading
...     client_id=1
... )
>>> 
>>> await adapter.connect()
>>> order = await adapter.submit_order(order)
"""

from typing import Optional, Dict, List, Callable
from datetime import datetime
import asyncio
import threading
from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.contract import Contract
from ibapi.order import Order as IBOrder
from ibapi.common import OrderId
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


class IBKRAdapter(EWrapper, EClient, BaseBrokerAdapter):
    """
    Interactive Brokers adapter.
    
    Implements both EWrapper (callbacks) and EClient (requests).
    
    Parameters
    ----------
    host : str
        TWS/Gateway host (default '127.0.0.1')
    port : int
        TWS/Gateway port (7497 for paper, 7496 for live)
    client_id : int
        Client ID (1-32)
    config : BrokerConfig, optional
        Configuration
    
    Example
    -------
    >>> adapter = IBKRAdapter(
    ...     host='127.0.0.1',
    ...     port=7497,
    ...     client_id=1
    ... )
    >>> 
    >>> await adapter.connect()
    >>> 
    >>> # Create order
    >>> order = Order(
    ...     order_id="",
    ...     symbol="AAPL",
    ...     side=OrderSide.BUY,
    ...     order_type=OrderType.LIMIT,
    ...     quantity=100,
    ...     price=150.0
    ... )
    >>> 
    >>> order = await adapter.submit_order(order)
    """
    
    def __init__(
        self,
        host: str = '127.0.0.1',
        port: int = 7497,
        client_id: int = 1,
        config: Optional[BrokerConfig] = None
    ):
        EWrapper.__init__(self)
        EClient.__init__(self, wrapper=self)
        
        self.host = host
        self.port = port
        self.client_id = client_id
        self.config = config or BrokerConfig(name="IBKR")
        
        # State
        self.connected_flag = False
        self.next_order_id: Optional[int] = None
        self.orders: Dict[str, Order] = {}  # order_id -> Order
        self.ib_to_our_order: Dict[int, str] = {}  # IB order ID -> our order ID
        self.positions_dict: Dict[str, Position] = {}
        self.fill_callbacks: List[Callable] = []
        
        # Threading
        self.thread: Optional[threading.Thread] = None
        self.connection_event = asyncio.Event()
    
    # EWrapper callbacks
    
    def nextValidId(self, orderId: OrderId):
        """
        Callback: Next valid order ID.
        
        Called after connection is established.
        
        Parameters
        ----------
        orderId : int
            Next valid order ID
        """
        self.next_order_id = orderId
        self.connected_flag = True
        self.connection_event.set()
        print(f"✅ Connected to IBKR - next order ID: {orderId}")
    
    def orderStatus(
        self,
        orderId: OrderId,
        status: str,
        filled: float,
        remaining: float,
        avgFillPrice: float,
        permId: int,
        parentId: int,
        lastFillPrice: float,
        clientId: int,
        whyHeld: str,
        mktCapPrice: float
    ):
        """
        Callback: Order status update.
        
        Parameters
        ----------
        orderId : int
            IB order ID
        status : str
            Order status (Submitted, Filled, Cancelled, etc.)
        filled : float
            Filled quantity
        remaining : float
            Remaining quantity
        avgFillPrice : float
            Average fill price
        """
        # Find our order
        our_order_id = self.ib_to_our_order.get(orderId)
        if not our_order_id:
            return
        
        order = self.orders.get(our_order_id)
        if not order:
            return
        
        # Update status
        order.status = self._map_ib_status(status)
        order.filled_quantity = filled
        order.avg_fill_price = avgFillPrice
        
        # Update timestamps
        if order.status in [OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.REJECTED]:
            order.filled_at = datetime.now()
        
        print(f"📊 Order {orderId} status: {status} - filled: {filled}/{order.quantity}")
    
    def execDetails(self, reqId: int, contract: Contract, execution):
        """
        Callback: Execution details (fill).
        
        Parameters
        ----------
        reqId : int
            Request ID
        contract : Contract
            Contract
        execution : Execution
            Execution details
        """
        # Find our order
        ib_order_id = execution.orderId
        our_order_id = self.ib_to_our_order.get(ib_order_id)
        
        if not our_order_id:
            return
        
        order = self.orders.get(our_order_id)
        if not order:
            return
        
        # Create Fill
        fill = Fill(
            order_id=our_order_id,
            symbol=contract.symbol,
            side=OrderSide.BUY if execution.side == 'BOT' else OrderSide.SELL,
            quantity=execution.shares,
            price=execution.price,
            commission=0.0,  # Will be updated in commissionReport
            timestamp=datetime.strptime(execution.time, '%Y%m%d  %H:%M:%S'),
            execution_id=execution.execId,
            metadata={
                'ib_order_id': ib_order_id,
                'ib_exec_id': execution.execId,
                'exchange': execution.exchange
            }
        )
        
        # Notify callbacks
        self._notify_fills(fill)
        
        print(f"✅ Fill: {contract.symbol} {execution.shares} @ {execution.price}")
    
    def commissionReport(self, commissionReport):
        """
        Callback: Commission report.
        
        Parameters
        ----------
        commissionReport : CommissionReport
            Commission details
        """
        # Find the latest fill for this execution
        exec_id = commissionReport.execId
        commission = commissionReport.commission
        
        # Update order commission
        for order in self.orders.values():
            if order.commission is None:
                order.commission = 0.0
            order.commission += commission
        
        print(f"💰 Commission: ${commission:.2f} for execution {exec_id}")
    
    def position(self, account: str, contract: Contract, position: float, avgCost: float):
        """
        Callback: Position update.
        
        Parameters
        ----------
        account : str
            Account ID
        contract : Contract
            Contract
        position : float
            Position size (positive=long, negative=short)
        avgCost : float
            Average cost
        """
        if position != 0:
            self.positions_dict[contract.symbol] = Position(
                symbol=contract.symbol,
                quantity=position,
                avg_entry_price=avgCost,
                current_price=0.0,  # Would need market data
                unrealized_pnl=0.0,  # Would need market data
                realized_pnl=0.0
            )
    
    def error(self, reqId: int, errorCode: int, errorString: str, advancedOrderRejectJson: str = ""):
        """
        Callback: Error.
        
        Parameters
        ----------
        reqId : int
            Request ID
        errorCode : int
            Error code
        errorString : str
            Error message
        """
        # Some "errors" are just informational
        if errorCode in [2104, 2106, 2158]:  # Market data farm connection
            return
        
        print(f"⚠️ IBKR Error {errorCode}: {errorString}")
        
        # Check if this is an order error
        if reqId in self.ib_to_our_order:
            our_order_id = self.ib_to_our_order[reqId]
            order = self.orders.get(our_order_id)
            if order:
                order.status = OrderStatus.REJECTED
                order.filled_at = datetime.now()
    
    def _map_ib_status(self, ib_status: str) -> OrderStatus:
        """
        Map IB order status to OrderStatus enum.
        
        IB statuses:
        - PendingSubmit: About to submit
        - PendingCancel: About to cancel
        - PreSubmitted: Submitted to IB system
        - Submitted: Submitted to exchange
        - Cancelled: Cancelled
        - Filled: Fully filled
        - Inactive: Order inactive
        
        Parameters
        ----------
        ib_status : str
            IB status
        
        Returns
        -------
        status : OrderStatus
        """
        mapping = {
            'PendingSubmit': OrderStatus.PENDING,
            'PendingCancel': OrderStatus.SUBMITTED,
            'PreSubmitted': OrderStatus.SUBMITTED,
            'Submitted': OrderStatus.SUBMITTED,
            'Cancelled': OrderStatus.CANCELLED,
            'Filled': OrderStatus.FILLED,
            'Inactive': OrderStatus.CANCELLED
        }
        
        return mapping.get(ib_status, OrderStatus.PENDING)
    
    # BaseBrokerAdapter implementation
    
    async def connect(self) -> bool:
        """
        Connect to TWS/Gateway.
        
        Returns
        -------
        success : bool
            True if connected
        """
        try:
            # Start connection
            self.connect(self.host, self.port, self.client_id)
            
            # Start thread to run message loop
            self.thread = threading.Thread(target=self.run, daemon=True)
            self.thread.start()
            
            # Wait for connection (nextValidId callback)
            try:
                await asyncio.wait_for(self.connection_event.wait(), timeout=10.0)
            except asyncio.TimeoutError:
                print("❌ Connection timeout")
                return False
            
            # Request positions
            self.reqPositions()
            
            return True
        
        except Exception as e:
            print(f"❌ IBKR connection error: {e}")
            return False
    
    async def disconnect(self):
        """Disconnect from TWS/Gateway."""
        self.disconnect()
        self.connected_flag = False
        print("✅ Disconnected from IBKR")
    
    def _create_contract(
        self,
        symbol: str,
        sec_type: str = 'STK',
        exchange: str = 'SMART',
        currency: str = 'USD'
    ) -> Contract:
        """
        Create IB Contract.
        
        Parameters
        ----------
        symbol : str
            Symbol
        sec_type : str
            Security type (STK/OPT/FUT/FX)
        exchange : str
            Exchange (SMART for stocks)
        currency : str
            Currency
        
        Returns
        -------
        contract : Contract
        """
        contract = Contract()
        contract.symbol = symbol
        contract.secType = sec_type
        contract.exchange = exchange
        contract.currency = currency
        
        return contract
    
    def _create_ib_order(self, order: Order) -> IBOrder:
        """
        Convert Order to IB Order.
        
        Parameters
        ----------
        order : Order
            Our order
        
        Returns
        -------
        ib_order : IBOrder
            IB order
        """
        ib_order = IBOrder()
        
        # Action
        ib_order.action = 'BUY' if order.side == OrderSide.BUY else 'SELL'
        
        # Quantity
        ib_order.totalQuantity = order.quantity
        
        # Order type
        if order.order_type == OrderType.MARKET:
            ib_order.orderType = 'MKT'
        elif order.order_type == OrderType.LIMIT:
            ib_order.orderType = 'LMT'
            ib_order.lmtPrice = order.price
        elif order.order_type == OrderType.STOP:
            ib_order.orderType = 'STP'
            ib_order.auxPrice = order.stop_price
        elif order.order_type == OrderType.STOP_LIMIT:
            ib_order.orderType = 'STP LMT'
            ib_order.lmtPrice = order.price
            ib_order.auxPrice = order.stop_price
        elif order.order_type == OrderType.IOC:
            ib_order.orderType = 'LMT'
            ib_order.lmtPrice = order.price
            ib_order.tif = 'IOC'
        elif order.order_type == OrderType.FOK:
            ib_order.orderType = 'LMT'
            ib_order.lmtPrice = order.price
            ib_order.tif = 'FOK'
        
        return ib_order
    
    async def submit_order(self, order: Order) -> Order:
        """
        Submit order to IBKR.
        
        Parameters
        ----------
        order : Order
            Order to submit
        
        Returns
        -------
        order : Order
            Order with IB order ID
        """
        if not self.connected_flag or self.next_order_id is None:
            raise RuntimeError("Not connected to IBKR")
        
        try:
            # Get next order ID
            ib_order_id = self.next_order_id
            self.next_order_id += 1
            
            # Create contract
            contract = self._create_contract(order.symbol)
            
            # Create IB order
            ib_order = self._create_ib_order(order)
            
            # Place order
            self.placeOrder(ib_order_id, contract, ib_order)
            
            # Update our order
            order.order_id = str(ib_order_id)
            order.status = OrderStatus.SUBMITTED
            order.submitted_at = datetime.now()
            
            # Store mapping
            self.orders[order.order_id] = order
            self.ib_to_our_order[ib_order_id] = order.order_id
            
            print(f"✅ Order submitted: {order.order_id} - {order.symbol} {order.side.value} {order.quantity}")
            
            return order
        
        except Exception as e:
            print(f"❌ Order submission error: {e}")
            order.status = OrderStatus.REJECTED
            raise
    
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
        try:
            ib_order_id = int(order_id)
            self.cancelOrder(ib_order_id, "")
            
            order = self.orders.get(order_id)
            if order:
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
        Modify order.
        
        IBKR supports order modification.
        
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
            Modified order
        """
        # Get original order
        order = self.orders.get(order_id)
        if not order:
            raise ValueError(f"Order not found: {order_id}")
        
        # Update order
        if quantity is not None:
            order.quantity = quantity
        if price is not None:
            order.price = price
        
        # Create contract
        contract = self._create_contract(order.symbol)
        
        # Create IB order with updated params
        ib_order = self._create_ib_order(order)
        
        # Place modified order (same order ID)
        ib_order_id = int(order_id)
        self.placeOrder(ib_order_id, contract, ib_order)
        
        print(f"✅ Order modified: {order_id}")
        
        return order
    
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
        order = self.orders.get(order_id)
        if not order:
            raise ValueError(f"Order not found: {order_id}")
        
        # Request order status (will trigger orderStatus callback)
        self.reqOpenOrders()
        
        # Wait briefly for callback
        await asyncio.sleep(0.5)
        
        return order
    
    async def get_positions(self) -> List[Position]:
        """
        Get current positions.
        
        Returns
        -------
        positions : list of Position
        """
        # Request positions (will trigger position callback)
        self.reqPositions()
        
        # Wait briefly for callbacks
        await asyncio.sleep(0.5)
        
        return list(self.positions_dict.values())
    
    async def get_account_balance(self) -> Dict:
        """
        Get account balance.
        
        Returns
        -------
        balance : dict
        """
        # Would need to implement accountSummary callback
        # For now, return placeholder
        return {
            'cash': 0.0,
            'stock_value': 0.0,
            'total_equity': 0.0
        }
    
    def subscribe_fills(self, callback: Callable):
        """
        Subscribe to fill notifications.
        
        Parameters
        ----------
        callback : callable
            Function(fill) called on each fill
        """
        self.fill_callbacks.append(callback)

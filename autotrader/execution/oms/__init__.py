"""
Order Management System (OMS)
==============================

Track order lifecycle, manage positions, and provide analytics.

This module implements:
- Order submission with tracking
- Cancel/replace logic
- Fill reconciliation
- Position tracking
- Performance metrics

Example
-------
>>> from autotrader.execution.oms import OrderManager
>>> from autotrader.execution.adapters.paper import PaperTradingAdapter
>>> 
>>> adapter = PaperTradingAdapter()
>>> await adapter.connect()
>>> 
>>> oms = OrderManager(adapter)
>>> 
>>> # Submit order
>>> order = await oms.submit_order(
...     symbol='BTCUSDT',
...     side=OrderSide.BUY,
...     quantity=0.1,
...     order_type=OrderType.LIMIT,
...     price=50000
... )
>>> 
>>> # Check position
>>> position = oms.get_position('BTCUSDT')
>>> print(f"Position: {position}")
"""

from typing import Dict, List, Optional, Callable
from datetime import datetime, timedelta
import asyncio
from autotrader.execution.adapters import (
    BaseBrokerAdapter,
    Order,
    Fill,
    Position,
    OrderType,
    OrderSide,
    OrderStatus
)


class OrderManager:
    """
    Order Management System.
    
    Tracks all orders, manages lifecycle, provides analytics.
    
    Parameters
    ----------
    adapter : BaseBrokerAdapter
        Broker adapter
    max_open_orders : int
        Maximum open orders allowed
    order_timeout_seconds : float
        Timeout for open orders
    
    Example
    -------
    >>> oms = OrderManager(adapter)
    >>> order = await oms.submit_order(
    ...     symbol='BTCUSDT',
    ...     side=OrderSide.BUY,
    ...     quantity=0.1
    ... )
    """
    
    def __init__(
        self,
        adapter: BaseBrokerAdapter,
        max_open_orders: int = 100,
        order_timeout_seconds: float = 300
    ):
        self.adapter = adapter
        self.max_open_orders = max_open_orders
        self.order_timeout_seconds = order_timeout_seconds
        
        # Order tracking
        self.active_orders: Dict[str, Order] = {}
        self.completed_orders: List[Order] = []
        
        # Fill tracking
        self.fills: List[Fill] = []
        
        # Position tracking (symbol -> quantity)
        self.positions: Dict[str, float] = {}
        
        # Performance metrics
        self.total_filled_notional: float = 0.0
        self.total_commission: float = 0.0
        
        # Subscribe to fills
        adapter.subscribe_fills(self._handle_fill)
        
        # Background tasks
        self.monitor_task: Optional[asyncio.Task] = None
    
    async def submit_order(
        self,
        symbol: str,
        side: OrderSide,
        quantity: float,
        order_type: OrderType = OrderType.LIMIT,
        price: Optional[float] = None,
        stop_price: Optional[float] = None,
        time_in_force: str = "GTC",
        **kwargs
    ) -> Order:
        """
        Submit order.
        
        Parameters
        ----------
        symbol : str
            Trading symbol
        side : OrderSide
            BUY or SELL
        quantity : float
            Order quantity
        order_type : OrderType
            Order type
        price : float, optional
            Limit price
        stop_price : float, optional
            Stop price
        time_in_force : str
            GTC, IOC, FOK, DAY
        **kwargs
            Additional parameters
        
        Returns
        -------
        order : Order
            Submitted order
        """
        # Check order limits
        if len(self.active_orders) >= self.max_open_orders:
            raise ValueError(f"Maximum open orders ({self.max_open_orders}) reached")
        
        # Create order
        order = Order(
            order_id="",  # Assigned by broker
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price,
            stop_price=stop_price,
            time_in_force=time_in_force,
            metadata=kwargs
        )
        
        # Submit to broker
        order = await self.adapter.submit_order(order)
        
        # Track
        self.active_orders[order.order_id] = order
        
        return order
    
    async def cancel_order(self, order_id: str) -> bool:
        """
        Cancel order.
        
        Parameters
        ----------
        order_id : str
            Order ID to cancel
        
        Returns
        -------
        success : bool
            True if cancellation successful
        """
        if order_id not in self.active_orders:
            return False
        
        success = await self.adapter.cancel_order(order_id)
        
        if success:
            order = self.active_orders[order_id]
            order.status = OrderStatus.CANCELLED
            
            # Move to completed
            self.completed_orders.append(order)
            del self.active_orders[order_id]
        
        return success
    
    async def modify_order(
        self,
        order_id: str,
        quantity: Optional[float] = None,
        price: Optional[float] = None
    ) -> Order:
        """
        Modify order (cancel/replace).
        
        Parameters
        ----------
        order_id : str
            Order ID to modify
        quantity : float, optional
            New quantity
        price : float, optional
            New price
        
        Returns
        -------
        order : Order
            New order
        """
        if order_id not in self.active_orders:
            raise ValueError(f"Order {order_id} not found")
        
        old_order = self.active_orders[order_id]
        
        # Cancel old order
        await self.cancel_order(order_id)
        
        # Submit new order with updated parameters
        new_order = await self.submit_order(
            symbol=old_order.symbol,
            side=old_order.side,
            quantity=quantity or old_order.quantity,
            order_type=old_order.order_type,
            price=price or old_order.price,
            stop_price=old_order.stop_price,
            time_in_force=old_order.time_in_force
        )
        
        # Link orders
        new_order.metadata['replaced_order_id'] = order_id
        
        return new_order
    
    async def cancel_all_orders(self, symbol: Optional[str] = None):
        """
        Cancel all open orders.
        
        Parameters
        ----------
        symbol : str, optional
            Only cancel orders for this symbol
        """
        orders_to_cancel = list(self.active_orders.keys())
        
        for order_id in orders_to_cancel:
            order = self.active_orders[order_id]
            
            if symbol is None or order.symbol == symbol:
                await self.cancel_order(order_id)
    
    def _handle_fill(self, fill: Fill):
        """
        Handle fill notification.
        
        Parameters
        ----------
        fill : Fill
            Fill report
        """
        self.fills.append(fill)
        
        # Update metrics
        self.total_filled_notional += fill.notional_value()
        self.total_commission += fill.commission
        
        # Update position
        if fill.symbol not in self.positions:
            self.positions[fill.symbol] = 0.0
        
        if fill.side == OrderSide.BUY:
            self.positions[fill.symbol] += fill.quantity
        else:
            self.positions[fill.symbol] -= fill.quantity
        
        # Update order
        if fill.order_id in self.active_orders:
            order = self.active_orders[fill.order_id]
            
            # If order is filled, move to completed
            if order.status == OrderStatus.FILLED:
                self.completed_orders.append(order)
                del self.active_orders[fill.order_id]
    
    def get_position(self, symbol: str) -> float:
        """
        Get current position for symbol.
        
        Parameters
        ----------
        symbol : str
            Symbol to query
        
        Returns
        -------
        position : float
            Net position (positive = long, negative = short)
        """
        return self.positions.get(symbol, 0.0)
    
    def get_all_positions(self) -> Dict[str, float]:
        """
        Get all positions.
        
        Returns
        -------
        positions : dict
            Symbol -> quantity mapping
        """
        return self.positions.copy()
    
    def get_open_orders(self, symbol: Optional[str] = None) -> List[Order]:
        """
        Get open orders.
        
        Parameters
        ----------
        symbol : str, optional
            Filter by symbol
        
        Returns
        -------
        orders : list
            Open orders
        """
        orders = list(self.active_orders.values())
        
        if symbol:
            orders = [o for o in orders if o.symbol == symbol]
        
        return orders
    
    def get_completed_orders(
        self,
        symbol: Optional[str] = None,
        since: Optional[datetime] = None
    ) -> List[Order]:
        """
        Get completed orders.
        
        Parameters
        ----------
        symbol : str, optional
            Filter by symbol
        since : datetime, optional
            Only orders after this time
        
        Returns
        -------
        orders : list
            Completed orders
        """
        orders = self.completed_orders
        
        if symbol:
            orders = [o for o in orders if o.symbol == symbol]
        
        if since:
            orders = [o for o in orders if o.filled_at and o.filled_at >= since]
        
        return orders
    
    def get_fills(
        self,
        symbol: Optional[str] = None,
        since: Optional[datetime] = None
    ) -> List[Fill]:
        """
        Get fills.
        
        Parameters
        ----------
        symbol : str, optional
            Filter by symbol
        since : datetime, optional
            Only fills after this time
        
        Returns
        -------
        fills : list
            Fill reports
        """
        fills = self.fills
        
        if symbol:
            fills = [f for f in fills if f.symbol == symbol]
        
        if since:
            fills = [f for f in fills if f.timestamp >= since]
        
        return fills
    
    def get_performance_metrics(self) -> Dict:
        """
        Get performance metrics.
        
        Returns
        -------
        metrics : dict
            Performance metrics
        """
        total_orders = len(self.completed_orders) + len(self.active_orders)
        filled_orders = len([o for o in self.completed_orders if o.status == OrderStatus.FILLED])
        cancelled_orders = len([o for o in self.completed_orders if o.status == OrderStatus.CANCELLED])
        
        fill_rate = filled_orders / total_orders if total_orders > 0 else 0
        
        # Calculate average fill latency
        fill_latencies = []
        for order in self.completed_orders:
            if order.status == OrderStatus.FILLED and order.submitted_at and order.filled_at:
                latency = (order.filled_at - order.submitted_at).total_seconds()
                fill_latencies.append(latency)
        
        avg_latency = sum(fill_latencies) / len(fill_latencies) if fill_latencies else 0
        
        return {
            'total_orders': total_orders,
            'filled_orders': filled_orders,
            'cancelled_orders': cancelled_orders,
            'fill_rate': fill_rate,
            'avg_fill_latency_seconds': avg_latency,
            'total_filled_notional': self.total_filled_notional,
            'total_commission': self.total_commission,
            'open_orders': len(self.active_orders),
            'total_fills': len(self.fills)
        }
    
    async def start_monitoring(self):
        """Start background monitoring task."""
        if self.monitor_task is None:
            self.monitor_task = asyncio.create_task(self._monitor_orders())
    
    async def stop_monitoring(self):
        """Stop background monitoring task."""
        if self.monitor_task:
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass
            self.monitor_task = None
    
    async def _monitor_orders(self):
        """
        Background task to monitor orders.
        
        Cancels orders that exceed timeout.
        """
        while True:
            try:
                now = datetime.now()
                timeout = timedelta(seconds=self.order_timeout_seconds)
                
                # Check for timed-out orders
                orders_to_cancel = []
                
                for order_id, order in self.active_orders.items():
                    if order.submitted_at:
                        age = now - order.submitted_at
                        if age > timeout:
                            orders_to_cancel.append(order_id)
                
                # Cancel timed-out orders
                for order_id in orders_to_cancel:
                    await self.cancel_order(order_id)
                
                # Sleep before next check
                await asyncio.sleep(10)  # Check every 10 seconds
            
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Error in order monitoring: {e}")
                await asyncio.sleep(10)


# Export
__all__ = ['OrderManager']

"""
Paper Trading Adapter
====================

Simulated execution for testing without real capital.

This adapter simulates realistic order fills with:
- Configurable latency (10-50ms default)
- Slippage modeling (5 bps default)
- Commission calculation (10 bps default)
- Balance and position tracking
- Realistic fill logic

Example
-------
>>> from autotrader.execution.adapters.paper import PaperTradingAdapter
>>> 
>>> adapter = PaperTradingAdapter(
...     initial_balance=100000,
...     latency_ms=(10, 50),
...     slippage_bps=5,
...     commission_bps=10
... )
>>> 
>>> await adapter.connect()
>>> 
>>> order = Order(
...     order_id="",
...     symbol="BTCUSDT",
...     side=OrderSide.BUY,
...     order_type=OrderType.LIMIT,
...     quantity=0.1,
...     price=50000
... )
>>> 
>>> filled_order = await adapter.submit_order(order)
"""

from typing import Dict, List, Tuple, Optional, Callable
import asyncio
import random
from datetime import datetime
from autotrader.execution.adapters import (
    BaseBrokerAdapter,
    Order,
    Fill,
    Position,
    OrderType,
    OrderSide,
    OrderStatus
)


class PaperTradingAdapter(BaseBrokerAdapter):
    """
    Paper trading simulator.
    
    Simulates order fills with realistic latency and slippage.
    
    Parameters
    ----------
    initial_balance : float
        Starting cash balance
    latency_ms : tuple
        (min, max) latency in milliseconds
    slippage_bps : float
        Slippage in basis points (100 bps = 1%)
    commission_bps : float
        Commission in basis points
    fill_probability : float
        Probability of limit order fill (0.0-1.0)
    
    Example
    -------
    >>> adapter = PaperTradingAdapter(
    ...     initial_balance=100000,
    ...     latency_ms=(10, 50),
    ...     slippage_bps=5
    ... )
    """
    
    def __init__(
        self,
        initial_balance: float = 100000.0,
        latency_ms: Tuple[int, int] = (10, 50),
        slippage_bps: float = 5.0,
        commission_bps: float = 10.0,
        fill_probability: float = 0.95
    ):
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.latency_ms = latency_ms
        self.slippage_bps = slippage_bps
        self.commission_bps = commission_bps
        self.fill_probability = fill_probability
        
        # State
        self.positions: Dict[str, Position] = {}
        self.orders: Dict[str, Order] = {}
        self.order_counter = 0
        
        # Market data (mock)
        self.current_prices: Dict[str, float] = {}
        
        # Callbacks
        self.fill_callbacks: List[Callable] = []
        
        # Connected state
        self.connected = False
    
    async def connect(self) -> bool:
        """Connect (instant for paper trading)."""
        self.connected = True
        return True
    
    async def disconnect(self):
        """Disconnect."""
        self.connected = False
    
    async def submit_order(self, order: Order) -> Order:
        """
        Submit order (simulated).
        
        Parameters
        ----------
        order : Order
            Order to submit
        
        Returns
        -------
        order : Order
            Order with assigned ID and status
        """
        if not self.connected:
            raise ConnectionError("Not connected")
        
        # Assign order ID
        self.order_counter += 1
        order.order_id = f"PAPER_{self.order_counter}"
        order.status = OrderStatus.SUBMITTED
        order.submitted_at = datetime.now()
        
        # Track order
        self.orders[order.order_id] = order
        
        # Simulate latency
        latency = random.randint(*self.latency_ms) / 1000.0
        await asyncio.sleep(latency)
        
        # Simulate fill
        await self._simulate_fill(order)
        
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
        if order_id not in self.orders:
            return False
        
        order = self.orders[order_id]
        
        if order.is_completed():
            return False
        
        order.status = OrderStatus.CANCELLED
        
        return True
    
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
        if order_id not in self.orders:
            raise ValueError(f"Order {order_id} not found")
        
        old_order = self.orders[order_id]
        
        # Cancel old order
        await self.cancel_order(order_id)
        
        # Create new order
        new_order = Order(
            order_id="",
            symbol=old_order.symbol,
            side=old_order.side,
            order_type=old_order.order_type,
            quantity=quantity or old_order.quantity,
            price=price or old_order.price,
            time_in_force=old_order.time_in_force
        )
        
        new_order.metadata['replaced_order_id'] = order_id
        
        return await self.submit_order(new_order)
    
    async def get_order_status(self, order_id: str) -> Order:
        """
        Get order status.
        
        Parameters
        ----------
        order_id : str
            Order ID to query
        
        Returns
        -------
        order : Order
            Current order
        """
        if order_id not in self.orders:
            raise ValueError(f"Order {order_id} not found")
        
        return self.orders[order_id]
    
    async def get_positions(self) -> Dict[str, Position]:
        """
        Get current positions.
        
        Returns
        -------
        positions : dict
            Symbol -> Position mapping
        """
        return self.positions.copy()
    
    async def get_account_balance(self) -> Dict[str, float]:
        """
        Get account balance.
        
        Returns
        -------
        balances : dict
            Currency -> balance mapping
        """
        # Calculate total position value
        position_value = sum(
            pos.quantity * pos.current_price
            for pos in self.positions.values()
        )
        
        total_equity = self.balance + position_value
        
        return {
            'cash': self.balance,
            'position_value': position_value,
            'total_equity': total_equity
        }
    
    def subscribe_fills(self, callback: Callable[[Fill], None]):
        """
        Subscribe to fill notifications.
        
        Parameters
        ----------
        callback : callable
            Function to call on each fill
        """
        self.fill_callbacks.append(callback)
    
    def set_price(self, symbol: str, price: float):
        """
        Set current market price (for testing).
        
        Parameters
        ----------
        symbol : str
            Symbol
        price : float
            Current price
        """
        self.current_prices[symbol] = price
        
        # Update position unrealized P&L
        if symbol in self.positions:
            self.positions[symbol].update_price(price)
    
    async def _simulate_fill(self, order: Order):
        """
        Simulate order fill.
        
        Parameters
        ----------
        order : Order
            Order to fill
        """
        # Get current price
        current_price = self.current_prices.get(order.symbol)
        
        if current_price is None:
            # No price available - use order price if limit
            if order.order_type == OrderType.LIMIT and order.price:
                current_price = order.price
            else:
                # Can't fill without price
                order.status = OrderStatus.REJECTED
                return
        
        # Check if limit order should fill
        if order.order_type == OrderType.LIMIT:
            should_fill = self._check_limit_fill(order, current_price)
            if not should_fill:
                # Order stays open
                return
        
        # Calculate fill price with slippage
        fill_price = self._calculate_fill_price(order, current_price)
        
        # Calculate commission
        notional = order.quantity * fill_price
        commission = notional * (self.commission_bps / 10000.0)
        
        # Check if we have enough balance
        if order.side == OrderSide.BUY:
            required = notional + commission
            if required > self.balance:
                order.status = OrderStatus.REJECTED
                order.metadata['reject_reason'] = 'Insufficient balance'
                return
        
        # Fill order
        order.status = OrderStatus.FILLED
        order.filled_quantity = order.quantity
        order.avg_fill_price = fill_price
        order.commission = commission
        order.filled_at = datetime.now()
        
        # Update balance
        if order.side == OrderSide.BUY:
            self.balance -= (notional + commission)
        else:
            self.balance += (notional - commission)
        
        # Update position
        self._update_position(order, fill_price)
        
        # Create fill
        fill = Fill(
            order_id=order.order_id,
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            price=fill_price,
            commission=commission,
            timestamp=datetime.now(),
            execution_id=f"FILL_{order.order_id}"
        )
        
        # Notify
        self._notify_fills(fill)
    
    def _check_limit_fill(self, order: Order, current_price: float) -> bool:
        """
        Check if limit order should fill.
        
        Parameters
        ----------
        order : Order
            Limit order
        current_price : float
            Current market price
        
        Returns
        -------
        should_fill : bool
            True if order should fill
        """
        if order.price is None:
            return False
        
        # Buy limit: fill if market <= limit
        if order.side == OrderSide.BUY:
            if current_price <= order.price:
                return random.random() < self.fill_probability
        
        # Sell limit: fill if market >= limit
        else:
            if current_price >= order.price:
                return random.random() < self.fill_probability
        
        return False
    
    def _calculate_fill_price(self, order: Order, current_price: float) -> float:
        """
        Calculate fill price with slippage.
        
        Parameters
        ----------
        order : Order
            Order to fill
        current_price : float
            Current market price
        
        Returns
        -------
        fill_price : float
            Actual fill price
        """
        if order.order_type == OrderType.MARKET:
            # Market order - apply slippage
            if order.side == OrderSide.BUY:
                fill_price = current_price * (1 + self.slippage_bps / 10000.0)
            else:
                fill_price = current_price * (1 - self.slippage_bps / 10000.0)
        
        elif order.order_type == OrderType.LIMIT:
            # Limit order - fill at limit price (or better)
            if order.side == OrderSide.BUY:
                # Fill at limit or below
                fill_price = min(order.price, current_price)
            else:
                # Fill at limit or above
                fill_price = max(order.price, current_price)
        
        else:
            # Other order types - use current price
            fill_price = current_price
        
        return fill_price
    
    def _update_position(self, order: Order, fill_price: float):
        """
        Update position after fill.
        
        Parameters
        ----------
        order : Order
            Filled order
        fill_price : float
            Fill price
        """
        symbol = order.symbol
        
        if symbol not in self.positions:
            # New position
            self.positions[symbol] = Position(
                symbol=symbol,
                quantity=0.0,
                avg_entry_price=0.0,
                current_price=fill_price
            )
        
        position = self.positions[symbol]
        
        # Calculate new position
        if order.side == OrderSide.BUY:
            new_quantity = position.quantity + order.quantity
            
            # Update average entry price
            if new_quantity > 0:
                total_cost = (
                    position.quantity * position.avg_entry_price +
                    order.quantity * fill_price
                )
                position.avg_entry_price = total_cost / new_quantity
            
            position.quantity = new_quantity
        
        else:  # SELL
            old_quantity = position.quantity
            new_quantity = position.quantity - order.quantity
            
            # Calculate realized P&L
            if old_quantity > 0:
                realized_pnl = (fill_price - position.avg_entry_price) * min(order.quantity, old_quantity)
                position.realized_pnl += realized_pnl
            
            position.quantity = new_quantity
            
            # If position closed, reset avg entry price
            if position.quantity == 0:
                position.avg_entry_price = 0.0
        
        # Update current price
        position.update_price(fill_price)
        
        # Remove position if flat
        if position.is_flat():
            del self.positions[symbol]


# Export
__all__ = ['PaperTradingAdapter']

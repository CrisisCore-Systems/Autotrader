"""
Broker Adapter Interface
========================

Abstract base class and common types for all broker adapters.

This module defines:
- Order, Fill, Position dataclasses
- OrderType, OrderSide, OrderStatus enums
- BaseBrokerAdapter abstract class
- Common utilities

Example
-------
>>> from autotrader.execution.adapters import BaseBrokerAdapter, Order, OrderType, OrderSide
>>> 
>>> class MyBroker(BaseBrokerAdapter):
...     async def connect(self):
...         # Implementation
...         pass
...     
...     async def submit_order(self, order):
...         # Implementation
...         pass
"""

from typing import Optional, Dict, List, Callable, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from abc import ABC, abstractmethod
import asyncio


class OrderType(Enum):
    """Order type."""
    MARKET = "market"
    LIMIT = "limit"
    IOC = "ioc"  # Immediate-or-cancel
    FOK = "fok"  # Fill-or-kill
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


class OrderSide(Enum):
    """Order side."""
    BUY = "buy"
    SELL = "sell"


class OrderStatus(Enum):
    """Order status."""
    PENDING = "pending"
    SUBMITTED = "submitted"
    PARTIAL_FILL = "partial_fill"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"


@dataclass
class Order:
    """
    Universal order representation.
    
    Attributes
    ----------
    order_id : str
        Unique order identifier (assigned by broker)
    symbol : str
        Trading symbol
    side : OrderSide
        BUY or SELL
    order_type : OrderType
        Order type
    quantity : float
        Order quantity
    price : float, optional
        Limit price (None for market orders)
    stop_price : float, optional
        Stop trigger price
    time_in_force : str
        GTC, IOC, FOK, DAY
    status : OrderStatus
        Current order status
    filled_quantity : float
        Filled quantity
    avg_fill_price : float
        Average fill price
    commission : float
        Total commission paid
    submitted_at : datetime, optional
        Submission timestamp
    filled_at : datetime, optional
        Fill timestamp
    metadata : dict
        Additional broker-specific data
    """
    order_id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: float
    price: Optional[float] = None
    stop_price: Optional[float] = None
    time_in_force: str = "GTC"
    
    status: OrderStatus = OrderStatus.PENDING
    filled_quantity: float = 0.0
    avg_fill_price: float = 0.0
    commission: float = 0.0
    
    submitted_at: Optional[datetime] = None
    filled_at: Optional[datetime] = None
    
    metadata: Dict = field(default_factory=dict)
    
    def is_open(self) -> bool:
        """Check if order is open."""
        return self.status in [OrderStatus.SUBMITTED, OrderStatus.PARTIAL_FILL]
    
    def is_completed(self) -> bool:
        """Check if order is completed."""
        return self.status in [OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.REJECTED, OrderStatus.EXPIRED]
    
    def remaining_quantity(self) -> float:
        """Get remaining quantity to fill."""
        return self.quantity - self.filled_quantity


@dataclass
class Fill:
    """
    Order fill report.
    
    Attributes
    ----------
    order_id : str
        Order ID this fill belongs to
    symbol : str
        Trading symbol
    side : OrderSide
        BUY or SELL
    quantity : float
        Fill quantity
    price : float
        Fill price
    commission : float
        Commission paid
    timestamp : datetime
        Fill timestamp
    execution_id : str
        Unique execution identifier
    metadata : dict
        Additional broker-specific data
    """
    order_id: str
    symbol: str
    side: OrderSide
    quantity: float
    price: float
    commission: float
    timestamp: datetime
    execution_id: str
    metadata: Dict = field(default_factory=dict)
    
    def notional_value(self) -> float:
        """Calculate notional value."""
        return self.quantity * self.price


@dataclass
class Position:
    """
    Position information.
    
    Attributes
    ----------
    symbol : str
        Trading symbol
    quantity : float
        Position quantity (positive = long, negative = short)
    avg_entry_price : float
        Average entry price
    current_price : float
        Current market price
    unrealized_pnl : float
        Unrealized P&L
    realized_pnl : float
        Realized P&L
    metadata : dict
        Additional data
    """
    symbol: str
    quantity: float
    avg_entry_price: float
    current_price: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    metadata: Dict = field(default_factory=dict)
    
    def is_long(self) -> bool:
        """Check if long position."""
        return self.quantity > 0
    
    def is_short(self) -> bool:
        """Check if short position."""
        return self.quantity < 0
    
    def is_flat(self) -> bool:
        """Check if flat (no position)."""
        return self.quantity == 0
    
    def update_price(self, price: float):
        """Update current price and unrealized P&L."""
        self.current_price = price
        
        if self.quantity > 0:
            # Long position
            self.unrealized_pnl = (price - self.avg_entry_price) * self.quantity
        elif self.quantity < 0:
            # Short position
            self.unrealized_pnl = (self.avg_entry_price - price) * abs(self.quantity)
        else:
            self.unrealized_pnl = 0.0


class BaseBrokerAdapter(ABC):
    """
    Abstract base class for all broker adapters.
    
    All adapters must implement this interface for unified access.
    
    Example
    -------
    >>> class MyBroker(BaseBrokerAdapter):
    ...     async def connect(self):
    ...         # Connect to broker API
    ...         return True
    ...     
    ...     async def submit_order(self, order):
    ...         # Submit order
    ...         return order
    ...     
    ...     # ... implement other methods
    """
    
    @abstractmethod
    async def connect(self) -> bool:
        """
        Establish connection to broker.
        
        Returns
        -------
        success : bool
            True if connection successful
        """
        pass
    
    @abstractmethod
    async def disconnect(self):
        """Close connection to broker."""
        pass
    
    @abstractmethod
    async def submit_order(self, order: Order) -> Order:
        """
        Submit order to broker.
        
        Parameters
        ----------
        order : Order
            Order to submit
        
        Returns
        -------
        order : Order
            Order with broker-assigned ID and status
        """
        pass
    
    @abstractmethod
    async def cancel_order(self, order_id: str) -> bool:
        """
        Cancel existing order.
        
        Parameters
        ----------
        order_id : str
            Order ID to cancel
        
        Returns
        -------
        success : bool
            True if cancellation successful
        """
        pass
    
    @abstractmethod
    async def modify_order(
        self,
        order_id: str,
        quantity: Optional[float] = None,
        price: Optional[float] = None
    ) -> Order:
        """
        Modify existing order (cancel/replace).
        
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
            Modified order
        """
        pass
    
    @abstractmethod
    async def get_order_status(self, order_id: str) -> Order:
        """
        Query order status.
        
        Parameters
        ----------
        order_id : str
            Order ID to query
        
        Returns
        -------
        order : Order
            Current order status
        """
        pass
    
    @abstractmethod
    async def get_positions(self) -> Dict[str, Position]:
        """
        Get current positions.
        
        Returns
        -------
        positions : dict
            Symbol -> Position mapping
        """
        pass
    
    @abstractmethod
    async def get_account_balance(self) -> Dict[str, float]:
        """
        Get account balances.
        
        Returns
        -------
        balances : dict
            Currency -> balance mapping
        """
        pass
    
    @abstractmethod
    def subscribe_fills(self, callback: Callable[[Fill], None]):
        """
        Subscribe to fill reports.
        
        Parameters
        ----------
        callback : callable
            Function to call on each fill
        """
        pass
    
    def _notify_fills(self, fill: Fill):
        """Notify all fill subscribers."""
        if hasattr(self, 'fill_callbacks'):
            for callback in self.fill_callbacks:
                try:
                    callback(fill)
                except Exception as e:
                    print(f"Error in fill callback: {e}")


class BrokerConfig:
    """
    Base configuration for broker adapters.
    
    Attributes
    ----------
    name : str
        Broker name
    enabled : bool
        Whether broker is enabled
    timeout_seconds : float
        Connection timeout
    retry_attempts : int
        Number of retry attempts
    """
    
    def __init__(
        self,
        name: str,
        enabled: bool = True,
        timeout_seconds: float = 30.0,
        retry_attempts: int = 3
    ):
        self.name = name
        self.enabled = enabled
        self.timeout_seconds = timeout_seconds
        self.retry_attempts = retry_attempts


# Export public API
__all__ = [
    'OrderType',
    'OrderSide',
    'OrderStatus',
    'Order',
    'Fill',
    'Position',
    'BaseBrokerAdapter',
    'BrokerConfig',
]

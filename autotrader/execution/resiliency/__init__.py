"""
Resiliency Layer
================

Handle failures, retries, reconnection, and circuit breakers.

This module implements:
- Exponential backoff retry
- Dead-letter queue for failed operations
- Automatic reconnection
- Circuit breaker pattern
- Health monitoring

Example
-------
>>> from autotrader.execution.resiliency import ResiliencyManager
>>> 
>>> manager = ResiliencyManager(
...     adapter=adapter,
...     max_retries=3,
...     circuit_breaker_threshold=5
... )
>>> 
>>> # Submit with retry
>>> order = await manager.submit_order_with_retry(order)
>>> 
>>> # Reconnect if needed
>>> await manager.reconnect_if_needed()
"""

from typing import List, Tuple, Optional, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
import asyncio
from enum import Enum
from autotrader.execution.adapters import BaseBrokerAdapter, Order


class CircuitState(Enum):
    """Circuit breaker state."""
    CLOSED = "closed"  # Normal operation
    OPEN = "open"      # Blocking requests
    HALF_OPEN = "half_open"  # Testing recovery


@dataclass
class FailureRecord:
    """Record of a failure."""
    timestamp: datetime
    operation: str
    error: Exception
    context: dict = field(default_factory=dict)


class ResiliencyManager:
    """
    Manage execution resiliency.
    
    Features:
    - Exponential backoff retry
    - Dead-letter queue for failed orders
    - Automatic reconnection
    - Circuit breaker
    - Health monitoring
    
    Parameters
    ----------
    adapter : BaseBrokerAdapter
        Broker adapter
    max_retries : int
        Maximum retry attempts
    initial_backoff : float
        Initial backoff delay (seconds)
    backoff_multiplier : float
        Backoff multiplier
    circuit_breaker_threshold : int
        Failures to trigger circuit breaker
    circuit_breaker_timeout : float
        Seconds before attempting recovery
    
    Example
    -------
    >>> manager = ResiliencyManager(
    ...     adapter=adapter,
    ...     max_retries=3,
    ...     circuit_breaker_threshold=5
    ... )
    >>> 
    >>> order = await manager.submit_order_with_retry(order)
    """
    
    def __init__(
        self,
        adapter: BaseBrokerAdapter,
        max_retries: int = 3,
        initial_backoff: float = 1.0,
        backoff_multiplier: float = 2.0,
        circuit_breaker_threshold: int = 5,
        circuit_breaker_timeout: float = 60.0
    ):
        self.adapter = adapter
        self.max_retries = max_retries
        self.initial_backoff = initial_backoff
        self.backoff_multiplier = backoff_multiplier
        self.circuit_breaker_threshold = circuit_breaker_threshold
        self.circuit_breaker_timeout = circuit_breaker_timeout
        
        # Circuit breaker state
        self.circuit_state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure: Optional[datetime] = None
        self.circuit_opened_at: Optional[datetime] = None
        
        # Dead-letter queue
        self.dead_letter_queue: List[Tuple[Order, Exception]] = []
        
        # Failure history
        self.failure_history: List[FailureRecord] = []
        
        # Health monitoring
        self.health_check_interval = 30.0  # seconds
        self.health_task: Optional[asyncio.Task] = None
    
    async def submit_order_with_retry(self, order: Order) -> Order:
        """
        Submit order with exponential backoff retry.
        
        Parameters
        ----------
        order : Order
            Order to submit
        
        Returns
        -------
        order : Order
            Submitted order
        
        Raises
        ------
        Exception
            If circuit breaker open or all retries exhausted
        """
        # Check circuit breaker
        if self.circuit_state == CircuitState.OPEN:
            await self._check_circuit_recovery()
            
            if self.circuit_state == CircuitState.OPEN:
                raise Exception("Circuit breaker open - service unavailable")
        
        backoff = self.initial_backoff
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                # Attempt submission
                result = await self.adapter.submit_order(order)
                
                # Success - reset failure count
                self._record_success()
                
                return result
            
            except Exception as e:
                last_error = e
                self._record_failure('submit_order', e, {'order_id': order.order_id})
                
                # Check if should retry
                if attempt < self.max_retries - 1:
                    # Exponential backoff
                    await asyncio.sleep(backoff)
                    backoff *= self.backoff_multiplier
                else:
                    # All retries exhausted - add to DLQ
                    self.dead_letter_queue.append((order, e))
        
        # All retries failed
        raise last_error
    
    async def cancel_order_with_retry(self, order_id: str) -> bool:
        """
        Cancel order with retry.
        
        Parameters
        ----------
        order_id : str
            Order ID to cancel
        
        Returns
        -------
        success : bool
            True if cancellation successful
        """
        if self.circuit_state == CircuitState.OPEN:
            return False
        
        backoff = self.initial_backoff
        
        for attempt in range(self.max_retries):
            try:
                result = await self.adapter.cancel_order(order_id)
                self._record_success()
                return result
            
            except Exception as e:
                self._record_failure('cancel_order', e, {'order_id': order_id})
                
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(backoff)
                    backoff *= self.backoff_multiplier
        
        return False
    
    async def reconnect_if_needed(self) -> bool:
        """
        Attempt to reconnect to broker if connection lost.
        
        Returns
        -------
        success : bool
            True if reconnection successful
        """
        try:
            # Try to disconnect first
            try:
                await self.adapter.disconnect()
            except Exception:
                pass
            
            # Wait before reconnecting
            await asyncio.sleep(5)
            
            # Attempt reconnection
            success = await self.adapter.connect()
            
            if success:
                self._record_success()
                return True
            
            return False
        
        except Exception as e:
            self._record_failure('reconnect', e)
            return False
    
    async def process_dead_letter_queue(self) -> int:
        """
        Attempt to reprocess failed orders.
        
        Returns
        -------
        reprocessed : int
            Number of orders successfully reprocessed
        """
        if not self.dead_letter_queue:
            return 0
        
        reprocessed = []
        count = 0
        
        for order, error in self.dead_letter_queue:
            try:
                await self.adapter.submit_order(order)
                reprocessed.append((order, error))
                count += 1
            except Exception:
                continue  # Leave in DLQ
        
        # Remove reprocessed items
        for item in reprocessed:
            self.dead_letter_queue.remove(item)
        
        return count
    
    def _record_failure(self, operation: str, error: Exception, context: dict = None):
        """
        Record a failure.
        
        Parameters
        ----------
        operation : str
            Operation that failed
        error : Exception
            Error that occurred
        context : dict, optional
            Additional context
        """
        self.failure_count += 1
        self.last_failure = datetime.now()
        
        # Add to history
        self.failure_history.append(
            FailureRecord(
                timestamp=datetime.now(),
                operation=operation,
                error=error,
                context=context or {}
            )
        )
        
        # Check circuit breaker
        if self.failure_count >= self.circuit_breaker_threshold:
            self._open_circuit()
    
    def _record_success(self):
        """Record a successful operation."""
        self.failure_count = 0
        
        # Close circuit if in half-open state
        if self.circuit_state == CircuitState.HALF_OPEN:
            self._close_circuit()
    
    def _open_circuit(self):
        """Open circuit breaker."""
        self.circuit_state = CircuitState.OPEN
        self.circuit_opened_at = datetime.now()
        print(f"🚨 Circuit breaker OPENED at {self.circuit_opened_at}")
    
    def _close_circuit(self):
        """Close circuit breaker."""
        self.circuit_state = CircuitState.CLOSED
        self.failure_count = 0
        self.circuit_opened_at = None
        print(f"✅ Circuit breaker CLOSED")
    
    async def _check_circuit_recovery(self):
        """Check if circuit should transition to half-open."""
        if self.circuit_state != CircuitState.OPEN:
            return
        
        if self.circuit_opened_at is None:
            return
        
        # Check timeout
        elapsed = (datetime.now() - self.circuit_opened_at).total_seconds()
        
        if elapsed >= self.circuit_breaker_timeout:
            # Transition to half-open
            self.circuit_state = CircuitState.HALF_OPEN
            print(f"⚠️ Circuit breaker HALF-OPEN - testing recovery")
    
    def get_failure_stats(self) -> dict:
        """
        Get failure statistics.
        
        Returns
        -------
        stats : dict
            Failure statistics
        """
        now = datetime.now()
        
        # Count recent failures
        recent_failures = [
            f for f in self.failure_history
            if (now - f.timestamp) < timedelta(minutes=5)
        ]
        
        return {
            'circuit_state': self.circuit_state.value,
            'failure_count': self.failure_count,
            'last_failure': self.last_failure.isoformat() if self.last_failure else None,
            'recent_failures_5min': len(recent_failures),
            'dlq_size': len(self.dead_letter_queue),
            'total_failures': len(self.failure_history)
        }
    
    async def start_health_monitoring(self):
        """Start health monitoring task."""
        if self.health_task is None:
            self.health_task = asyncio.create_task(self._health_monitor())
    
    async def stop_health_monitoring(self):
        """Stop health monitoring task."""
        if self.health_task:
            self.health_task.cancel()
            try:
                await self.health_task
            except asyncio.CancelledError:
                pass
            self.health_task = None
    
    async def _health_monitor(self):
        """
        Background health monitoring.
        
        Periodically checks connection health and attempts recovery.
        """
        while True:
            try:
                await asyncio.sleep(self.health_check_interval)
                
                # Check if circuit is open
                if self.circuit_state == CircuitState.OPEN:
                    await self._check_circuit_recovery()
                
                # Try to process DLQ if circuit is closed
                if self.circuit_state == CircuitState.CLOSED and self.dead_letter_queue:
                    await self.process_dead_letter_queue()
            
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Error in health monitoring: {e}")


class ConnectionPool:
    """
    Manage multiple broker connections.
    
    Parameters
    ----------
    adapters : list
        List of broker adapters
    
    Example
    -------
    >>> pool = ConnectionPool([adapter1, adapter2])
    >>> await pool.connect_all()
    """
    
    def __init__(self, adapters: List[BaseBrokerAdapter]):
        self.adapters = adapters
        self.connected: List[bool] = [False] * len(adapters)
    
    async def connect_all(self) -> List[bool]:
        """
        Connect to all adapters.
        
        Returns
        -------
        results : list
            Connection results
        """
        tasks = [adapter.connect() for adapter in self.adapters]
        self.connected = await asyncio.gather(*tasks, return_exceptions=True)
        
        return [isinstance(r, bool) and r for r in self.connected]
    
    async def disconnect_all(self):
        """Disconnect from all adapters."""
        tasks = [adapter.disconnect() for adapter in self.adapters]
        await asyncio.gather(*tasks, return_exceptions=True)
        self.connected = [False] * len(self.adapters)
    
    def get_connected_adapters(self) -> List[BaseBrokerAdapter]:
        """Get list of connected adapters."""
        return [
            adapter for i, adapter in enumerate(self.adapters)
            if self.connected[i]
        ]


# Export
__all__ = [
    'CircuitState',
    'FailureRecord',
    'ResiliencyManager',
    'ConnectionPool',
]

"""
Phase 5 live execution contracts.

These types formalize the boundary between live network I/O and the
synchronous portfolio/risk core.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

from autotrader.execution.adapters import Order, OrderStatus, Fill


class LiveEventType(Enum):
    """Event types emitted by the live OMS/runtime boundary."""

    ORDER_SUBMITTED = "order_submitted"
    ORDER_CANCELLED = "order_cancelled"
    ORDER_REJECTED = "order_rejected"
    FILL_RECEIVED = "fill_received"
    STATE_SNAPSHOT = "state_snapshot"
    STATE_DIVERGENCE = "state_divergence"
    KILL_SWITCH_ENGAGED = "kill_switch_engaged"
    HEARTBEAT_LOST = "heartbeat_lost"


@dataclass
class LiveOrderEvent:
    """Structured event emitted by the live OMS."""

    event_type: LiveEventType
    timestamp: datetime
    order_id: str = ""
    symbol: str = ""
    status: Optional[OrderStatus] = None
    payload: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PortfolioStateSnapshot:
    """Point-in-time portfolio state for reconciliation and audit."""

    timestamp: datetime
    positions: Dict[str, float] = field(default_factory=dict)
    open_order_ids: List[str] = field(default_factory=list)
    cash: Optional[float] = None
    equity: Optional[float] = None
    source: str = "engine"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StateDivergence:
    """Reconciliation mismatch between local and exchange state."""

    timestamp: datetime
    symbol: str
    local_quantity: float
    exchange_quantity: float
    absolute_difference: float
    details: Dict[str, Any] = field(default_factory=dict)


class StateDivergenceException(RuntimeError):
    """Raised when live exchange state diverges from the engine state."""

    def __init__(self, message: str, divergences: Optional[List[StateDivergence]] = None):
        super().__init__(message)
        self.divergences = list(divergences or [])


@runtime_checkable
class LiveOMSProtocol(Protocol):
    """Typed contract for a live OMS implementation."""

    async def submit_order(
        self,
        symbol: str,
        side,
        quantity: float,
        order_type,
        price: Optional[float] = None,
        stop_price: Optional[float] = None,
        time_in_force: str = "GTC",
        **kwargs: Any,
    ) -> Order:
        ...

    async def cancel_order(self, order_id: str) -> bool:
        ...

    async def get_order_status(self, order_id: str) -> Order:
        ...

    def get_event_log(self) -> List[LiveOrderEvent]:
        ...

    def snapshot_state(self) -> PortfolioStateSnapshot:
        ...

    def reconcile_with_exchange(self) -> bool:
        ...

    def engage_kill_switch(self, reason: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        ...

    async def emergency_kill(self, reason: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        ...

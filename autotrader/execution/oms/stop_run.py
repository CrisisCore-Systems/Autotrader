from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Sequence

from autotrader.execution.adapters import OrderSide, OrderStatus, OrderType
from autotrader.execution.oms import OrderManager


@dataclass(frozen=True)
class StructuralTrapSignal:
    symbol: str
    trap_id: str
    structural_price: float
    breach_price: float
    side: OrderSide
    total_size: float
    layer_offsets_bps: Sequence[float]
    layer_weights: Sequence[float]
    ttl_seconds: float
    invalidation_price: float
    liquidity_score: Optional[float] = None
    node_density: Optional[float] = None

    def __post_init__(self) -> None:
        if self.total_size <= 0:
            raise ValueError("total_size must be positive")
        if self.ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")
        if not self.layer_offsets_bps:
            raise ValueError("layer_offsets_bps must not be empty")
        if len(self.layer_offsets_bps) != len(self.layer_weights):
            raise ValueError("layer_weights must match layer_offsets_bps length")
        if sum(float(weight) for weight in self.layer_weights) <= 0:
            raise ValueError("layer_weights must sum to a positive value")


@dataclass
class StopRunLayer:
    order_id: str
    price: float
    quantity: float
    offset_bps: float


@dataclass
class StopRunTrapContext:
    trap_id: str
    symbol: str
    side: OrderSide
    structural_price: float
    breach_price: float
    invalidation_price: float
    created_at: datetime
    expires_at: datetime
    layers: List[StopRunLayer] = field(default_factory=list)
    liquidity_score: Optional[float] = None
    node_density: Optional[float] = None
    cancelled_at: Optional[datetime] = None
    cancel_reason: Optional[str] = None

    @property
    def order_ids(self) -> List[str]:
        return [layer.order_id for layer in self.layers]


class StopRunCoordinator:
    """Manage layered post-only stop-run entry traps above the primitive OMS."""

    def __init__(self, oms: OrderManager):
        self.oms = oms
        self.traps: Dict[str, StopRunTrapContext] = {}
        self.order_to_trap: Dict[str, str] = {}

    async def deploy_trap(
        self,
        signal: StructuralTrapSignal,
        metadata: Optional[Dict[str, object]] = None,
    ) -> StopRunTrapContext:
        created_at = datetime.now()
        expires_at = created_at + timedelta(seconds=float(signal.ttl_seconds))
        trap_context = StopRunTrapContext(
            trap_id=signal.trap_id,
            symbol=signal.symbol,
            side=signal.side,
            structural_price=float(signal.structural_price),
            breach_price=float(signal.breach_price),
            invalidation_price=float(signal.invalidation_price),
            created_at=created_at,
            expires_at=expires_at,
            liquidity_score=signal.liquidity_score,
            node_density=signal.node_density,
        )

        quantities = self._split_quantities(signal.total_size, len(signal.layer_offsets_bps), signal.layer_weights)
        trap_metadata = dict(metadata or {})
        trap_metadata["structural_price"] = float(signal.structural_price)
        trap_metadata["breach_price"] = float(signal.breach_price)
        trap_metadata["invalidation_price"] = float(signal.invalidation_price)
        if signal.liquidity_score is not None:
            trap_metadata["liquidity_score"] = float(signal.liquidity_score)
        if signal.node_density is not None:
            trap_metadata["node_density"] = float(signal.node_density)

        for idx, (offset_bps, quantity) in enumerate(zip(signal.layer_offsets_bps, quantities), start=1):
            layer_price = self._price_for_layer(
                side=signal.side,
                structural_price=signal.structural_price,
                offset_bps=float(offset_bps),
            )
            order = await self.oms.submit_order(
                symbol=signal.symbol,
                side=signal.side,
                quantity=quantity,
                order_type=OrderType.LIMIT,
                price=layer_price,
                post_only=True,
                trap_id=signal.trap_id,
                trap_layer_index=idx,
                trap_offset_bps=float(offset_bps),
                **trap_metadata,
            )
            layer = StopRunLayer(
                order_id=order.order_id,
                price=float(layer_price),
                quantity=float(quantity),
                offset_bps=float(offset_bps),
            )
            trap_context.layers.append(layer)
            self.order_to_trap[order.order_id] = signal.trap_id

        self.traps[signal.trap_id] = trap_context
        return trap_context

    async def reconcile_trap(self, trap_id: str) -> StopRunTrapContext:
        trap = self.traps[trap_id]
        if trap.cancelled_at is not None:
            return trap

        self._sync_terminal_orders(trap)
        statuses = [self._get_order_status(order_id) for order_id in trap.order_ids]
        if any(status == OrderStatus.REJECTED for status in statuses):
            await self.cancel_trap(trap_id, reason="layer_rejected")
            self._sync_terminal_orders(trap)

        return trap

    async def cancel_stale_traps(self, now: Optional[datetime] = None) -> List[str]:
        effective_now = now or datetime.now()
        cancelled: List[str] = []
        for trap_id, trap in list(self.traps.items()):
            if trap.cancelled_at is not None:
                continue
            if effective_now >= trap.expires_at:
                await self.cancel_trap(trap_id, reason="ttl_expired")
                cancelled.append(trap_id)
        return cancelled

    async def cancel_invalidated_traps(self, symbol_prices: Dict[str, float]) -> List[str]:
        cancelled: List[str] = []
        for trap_id, trap in list(self.traps.items()):
            if trap.cancelled_at is not None:
                continue
            current_price = symbol_prices.get(trap.symbol)
            if current_price is None:
                continue
            if self._is_invalidation_triggered(trap, float(current_price)):
                await self.cancel_trap(trap_id, reason="invalidation_touched")
                cancelled.append(trap_id)
        return cancelled

    async def cancel_trap(self, trap_id: str, *, reason: str) -> StopRunTrapContext:
        trap = self.traps[trap_id]
        active_order_ids = [
            order_id
            for order_id in trap.order_ids
            if self._get_order_status(order_id) in {OrderStatus.SUBMITTED, OrderStatus.PARTIAL_FILL}
        ]
        for order_id in active_order_ids:
            await self.oms.cancel_order(order_id)
        trap.cancelled_at = datetime.now()
        trap.cancel_reason = reason
        return trap

    def get_trap(self, trap_id: str) -> StopRunTrapContext:
        return self.traps[trap_id]

    def _get_order_status(self, order_id: str) -> OrderStatus:
        if order_id in self.oms.active_orders:
            return self.oms.active_orders[order_id].status
        for order in reversed(self.oms.completed_orders):
            if order.order_id == order_id:
                return order.status
        raise KeyError(f"Unknown order_id: {order_id}")

    @staticmethod
    def _price_for_layer(*, side: OrderSide, structural_price: float, offset_bps: float) -> float:
        basis = float(offset_bps) / 10000.0
        if side == OrderSide.BUY:
            return float(structural_price) * (1.0 - basis)
        return float(structural_price) * (1.0 + basis)

    @staticmethod
    def _is_invalidation_triggered(trap: StopRunTrapContext, current_price: float) -> bool:
        if trap.side == OrderSide.BUY:
            return float(current_price) <= float(trap.invalidation_price)
        return float(current_price) >= float(trap.invalidation_price)

    def _sync_terminal_orders(self, trap: StopRunTrapContext) -> None:
        for order_id in trap.order_ids:
            order = self.oms.active_orders.get(order_id)
            if order is None:
                continue
            if order.status in {OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.REJECTED, OrderStatus.EXPIRED}:
                self.oms.completed_orders.append(order)
                del self.oms.active_orders[order_id]

    @staticmethod
    def _split_quantities(
        total_quantity: float,
        layer_count: int,
        quantity_weights: Optional[Sequence[float]],
    ) -> List[float]:
        if quantity_weights is None:
            weights = [1.0] * layer_count
        else:
            if len(quantity_weights) != layer_count:
                raise ValueError("quantity_weights must match layer_offsets_bps length")
            weights = [float(weight) for weight in quantity_weights]

        weight_sum = sum(weights)
        if weight_sum <= 0:
            raise ValueError("quantity_weights must sum to a positive value")

        allocated = [float(total_quantity) * (weight / weight_sum) for weight in weights]
        allocated[-1] = float(total_quantity) - sum(allocated[:-1])
        return allocated
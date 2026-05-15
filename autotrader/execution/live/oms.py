"""
Live OMS wrapper.

This class extends the existing OMS with explicit event logging,
state snapshots, and a kill-switch-aware reconciliation hook.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from autotrader.execution.adapters import BaseBrokerAdapter, Fill, Order, OrderSide, OrderStatus
from autotrader.execution.oms import OrderManager

from .contracts import LiveEventType, LiveOrderEvent, PortfolioStateSnapshot, StateDivergence


class LiveOMS(OrderManager):
    """Phase 5 live OMS with explicit audit events and kill-switch state."""

    def __init__(
        self,
        adapter: BaseBrokerAdapter,
        max_open_orders: int = 100,
        order_timeout_seconds: float = 300,
        state_snapshot_provider: Optional[Callable[[], PortfolioStateSnapshot]] = None,
        exchange_snapshot_provider: Optional[Callable[[], PortfolioStateSnapshot]] = None,
        drift_tolerance_qty: float = 0.0,
    ):
        super().__init__(adapter=adapter, max_open_orders=max_open_orders, order_timeout_seconds=order_timeout_seconds)
        self._event_log: List[LiveOrderEvent] = []
        self._state_snapshot_provider = state_snapshot_provider
        self._exchange_snapshot_provider = exchange_snapshot_provider
        self._drift_tolerance_qty = float(drift_tolerance_qty)
        self._kill_switch_engaged = False
        self._kill_switch_reason: Optional[str] = None
        self._kill_switch_metadata: Dict[str, Any] = {}

    @property
    def kill_switch_engaged(self) -> bool:
        return self._kill_switch_engaged

    @property
    def kill_switch_reason(self) -> Optional[str]:
        return self._kill_switch_reason

    def get_event_log(self) -> List[LiveOrderEvent]:
        return list(self._event_log)

    def engage_kill_switch(self, reason: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        self._kill_switch_engaged = True
        self._kill_switch_reason = reason
        self._kill_switch_metadata = dict(metadata or {})
        self._append_event(
            LiveEventType.KILL_SWITCH_ENGAGED,
            order_id="",
            symbol="",
            payload={"reason": reason, "metadata": self._kill_switch_metadata},
        )

    async def emergency_kill(self, reason: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        self.engage_kill_switch(reason=reason, metadata=metadata)

        # Best-effort flush: cancel tracked orders first, then call a broker-level
        # bulk cancel if the adapter exposes one.
        await self.cancel_all_orders()

        broker_cancel_all = getattr(self.adapter, "cancel_all_orders", None)
        if callable(broker_cancel_all):
            result = broker_cancel_all()
            if hasattr(result, "__await__"):
                await result

    def snapshot_state(self) -> PortfolioStateSnapshot:
        if self._state_snapshot_provider:
            snapshot = self._state_snapshot_provider()
        else:
            snapshot = PortfolioStateSnapshot(
                timestamp=datetime.now(timezone.utc),
                positions=self.get_all_positions(),
                open_order_ids=list(self.active_orders.keys()),
                source="live_oms",
            )
        self._append_event(
            LiveEventType.STATE_SNAPSHOT,
            order_id="",
            symbol="",
            payload={"snapshot": asdict(snapshot)},
        )
        return snapshot

    def reconcile_with_exchange(self) -> bool:
        if not self._exchange_snapshot_provider:
            return True

        local = self.snapshot_state()
        exchange = self._exchange_snapshot_provider()

        mismatches: list[StateDivergence] = []
        symbols = sorted(set(local.positions) | set(exchange.positions))
        for symbol in symbols:
            local_qty = float(local.positions.get(symbol, 0.0))
            exchange_qty = float(exchange.positions.get(symbol, 0.0))
            delta = abs(local_qty - exchange_qty)
            if delta > self._drift_tolerance_qty:
                mismatches.append(
                    StateDivergence(
                        timestamp=datetime.now(timezone.utc),
                        symbol=symbol,
                        local_quantity=local_qty,
                        exchange_quantity=exchange_qty,
                        absolute_difference=delta,
                        details={
                            "local_open_order_ids": local.open_order_ids,
                            "exchange_open_order_ids": exchange.open_order_ids,
                        },
                    )
                )

        if mismatches:
            self.engage_kill_switch(
                "state_divergence",
                {
                    "divergences": [asdict(item) for item in mismatches],
                },
            )
            self._append_event(
                LiveEventType.STATE_DIVERGENCE,
                order_id="",
                symbol="",
                payload={"divergences": [asdict(item) for item in mismatches]},
            )
            return False

        return True

    async def submit_order(
        self,
        symbol: str,
        side: OrderSide,
        quantity: float,
        order_type,
        price: Optional[float] = None,
        stop_price: Optional[float] = None,
        time_in_force: str = "GTC",
        **kwargs: Any,
    ) -> Order:
        if self._kill_switch_engaged:
            raise RuntimeError(f"Kill switch engaged: {self._kill_switch_reason or 'unknown'}")

        order = await super().submit_order(
            symbol=symbol,
            side=side,
            quantity=quantity,
            order_type=order_type,
            price=price,
            stop_price=stop_price,
            time_in_force=time_in_force,
            **kwargs,
        )
        self._append_event(
            LiveEventType.ORDER_SUBMITTED,
            order_id=order.order_id,
            symbol=order.symbol,
            status=order.status,
            payload={
                "side": order.side.value,
                "quantity": order.quantity,
                "order_type": order.order_type.value,
                "price": order.price,
                "stop_price": order.stop_price,
                "time_in_force": order.time_in_force,
            },
        )
        return order

    async def cancel_order(self, order_id: str) -> bool:
        order = self.active_orders.get(order_id)
        success = await super().cancel_order(order_id)
        if success:
            self._append_event(
                LiveEventType.ORDER_CANCELLED,
                order_id=order_id,
                symbol=order.symbol if order else "",
                status=OrderStatus.CANCELLED,
            )
        return success

    async def get_order_status(self, order_id: str) -> Order:
        order = self.active_orders.get(order_id)
        if order is None:
            order = next((item for item in self.completed_orders if item.order_id == order_id), None)
        if order is None:
            order = await self.adapter.get_order_status(order_id)

        self._append_event(
            LiveEventType.STATE_SNAPSHOT,
            order_id=order_id,
            symbol=order.symbol,
            status=order.status,
            payload={
                "filled_quantity": order.filled_quantity,
                "avg_fill_price": order.avg_fill_price,
                "remaining_quantity": order.remaining_quantity(),
            },
        )
        return order

    def _handle_fill(self, fill: Fill):
        super()._handle_fill(fill)
        self._append_event(
            LiveEventType.FILL_RECEIVED,
            order_id=fill.order_id,
            symbol=fill.symbol,
            payload={
                "side": fill.side.value,
                "quantity": fill.quantity,
                "price": fill.price,
                "commission": fill.commission,
                "execution_id": fill.execution_id,
            },
        )

    def _append_event(
        self,
        event_type: LiveEventType,
        order_id: str,
        symbol: str,
        status: Optional[OrderStatus] = None,
        payload: Optional[Dict[str, Any]] = None,
    ) -> None:
        event = LiveOrderEvent(
            event_type=event_type,
            timestamp=datetime.now(timezone.utc),
            order_id=order_id,
            symbol=symbol,
            status=status,
            payload=dict(payload or {}),
        )
        self._event_log.append(event)

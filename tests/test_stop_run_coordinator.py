from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from autotrader.execution.adapters import Order, OrderSide, OrderStatus
from autotrader.execution.oms import OrderManager, StopRunCoordinator, StructuralTrapSignal


class RecordingAdapter:
    def __init__(self) -> None:
        self.connected = True
        self.orders: dict[str, Order] = {}
        self.order_counter = 0
        self.cancelled_order_ids: list[str] = []
        self.fill_callbacks = []

    def subscribe_fills(self, callback):
        self.fill_callbacks.append(callback)

    async def submit_order(self, order: Order) -> Order:
        self.order_counter += 1
        order.order_id = f"REC_{self.order_counter}"
        order.status = OrderStatus.SUBMITTED
        order.submitted_at = datetime.now()
        self.orders[order.order_id] = order
        return order

    async def cancel_order(self, order_id: str) -> bool:
        order = self.orders.get(order_id)
        if order is None or not order.is_open():
            return False
        order.status = OrderStatus.CANCELLED
        order.filled_at = datetime.now()
        self.cancelled_order_ids.append(order_id)
        return True


@pytest.mark.asyncio
async def test_stop_run_coordinator_deploys_layered_post_only_trap():
    adapter = RecordingAdapter()
    oms = OrderManager(adapter)
    coordinator = StopRunCoordinator(oms)
    signal = StructuralTrapSignal(
        symbol="BTCUSDT",
        trap_id="trap_buy_1",
        structural_price=100.0,
        breach_price=99.95,
        side=OrderSide.BUY,
        total_size=3.0,
        layer_offsets_bps=[10.0, 20.0, 30.0],
        layer_weights=[1.0, 1.0, 1.0],
        ttl_seconds=30.0,
        invalidation_price=99.5,
        liquidity_score=0.8,
        node_density=0.6,
    )

    trap = await coordinator.deploy_trap(signal)

    assert len(trap.layers) == 3
    assert trap.order_ids == ["REC_1", "REC_2", "REC_3"]
    assert [layer.price for layer in trap.layers] == pytest.approx([99.9, 99.8, 99.7])
    assert [layer.quantity for layer in trap.layers] == pytest.approx([1.0, 1.0, 1.0])
    assert all(oms.active_orders[order_id].post_only for order_id in trap.order_ids)
    assert all(oms.active_orders[order_id].metadata["trap_id"] == trap.trap_id for order_id in trap.order_ids)
    assert trap.breach_price == pytest.approx(99.95)
    assert trap.invalidation_price == pytest.approx(99.5)


@pytest.mark.asyncio
async def test_stop_run_coordinator_scrubs_remaining_layers_after_rejection():
    adapter = RecordingAdapter()
    oms = OrderManager(adapter)
    coordinator = StopRunCoordinator(oms)
    signal = StructuralTrapSignal(
        symbol="BTCUSDT",
        trap_id="trap_buy_2",
        structural_price=100.0,
        breach_price=99.9,
        side=OrderSide.BUY,
        total_size=2.0,
        layer_offsets_bps=[10.0, 20.0],
        layer_weights=[1.0, 1.0],
        ttl_seconds=30.0,
        invalidation_price=99.4,
    )

    trap = await coordinator.deploy_trap(signal)

    oms.active_orders[trap.order_ids[0]].status = OrderStatus.REJECTED

    await coordinator.reconcile_trap(trap.trap_id)

    assert coordinator.get_trap(trap.trap_id).cancel_reason == "layer_rejected"
    assert trap.order_ids[1] in adapter.cancelled_order_ids
    assert oms.active_orders == {}


@pytest.mark.asyncio
async def test_stop_run_coordinator_cancels_stale_traps_on_internal_ttl():
    adapter = RecordingAdapter()
    oms = OrderManager(adapter)
    coordinator = StopRunCoordinator(oms)
    signal = StructuralTrapSignal(
        symbol="BTCUSDT",
        trap_id="trap_sell_1",
        structural_price=100.0,
        breach_price=100.05,
        side=OrderSide.SELL,
        total_size=2.0,
        layer_offsets_bps=[15.0, 25.0],
        layer_weights=[1.0, 3.0],
        ttl_seconds=5.0,
        invalidation_price=100.5,
    )

    trap = await coordinator.deploy_trap(signal)

    cancelled = await coordinator.cancel_stale_traps(now=trap.created_at + timedelta(seconds=6))

    assert cancelled == [trap.trap_id]
    assert coordinator.get_trap(trap.trap_id).cancel_reason == "ttl_expired"
    assert [layer.quantity for layer in trap.layers] == pytest.approx([0.5, 1.5])
    assert set(adapter.cancelled_order_ids) == set(trap.order_ids)


@pytest.mark.asyncio
async def test_stop_run_coordinator_cancels_invalidated_traps():
    adapter = RecordingAdapter()
    oms = OrderManager(adapter)
    coordinator = StopRunCoordinator(oms)
    signal = StructuralTrapSignal(
        symbol="BTCUSDT",
        trap_id="trap_buy_3",
        structural_price=100.0,
        breach_price=99.97,
        side=OrderSide.BUY,
        total_size=1.5,
        layer_offsets_bps=[5.0, 10.0],
        layer_weights=[1.0, 2.0],
        ttl_seconds=30.0,
        invalidation_price=99.6,
    )

    trap = await coordinator.deploy_trap(signal)
    cancelled = await coordinator.cancel_invalidated_traps({"BTCUSDT": 99.55})

    assert cancelled == [trap.trap_id]
    assert coordinator.get_trap(trap.trap_id).cancel_reason == "invalidation_touched"


def test_structural_trap_signal_rejects_mismatched_layer_shapes():
    with pytest.raises(ValueError, match="layer_weights must match layer_offsets_bps length"):
        StructuralTrapSignal(
            symbol="BTCUSDT",
            trap_id="trap_bad_1",
            structural_price=100.0,
            breach_price=99.9,
            side=OrderSide.BUY,
            total_size=1.0,
            layer_offsets_bps=[5.0, 10.0],
            layer_weights=[1.0],
            ttl_seconds=10.0,
            invalidation_price=99.5,
        )
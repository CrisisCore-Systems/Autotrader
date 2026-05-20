from __future__ import annotations

from datetime import datetime

import pandas as pd
import pytest

from autotrader.execution.adapters import Order, OrderSide, OrderStatus
from autotrader.execution.oms import (
    OrderManager,
    StopRunCoordinator,
    StructuralTrapDetector,
    StructuralTrapSignal,
    TrapPipeline,
)
from autotrader.strategy.bars import TickToBarAggregator


class RecordingAdapter:
    def __init__(self) -> None:
        self.connected = True
        self.orders: dict[str, Order] = {}
        self.order_counter = 0
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
        return True


class FixedSignalDetector(StructuralTrapDetector):
    def __init__(self, signal: StructuralTrapSignal):
        self.signal = signal

    def detect(self, finalized_bars):
        return [self.signal]


def _emit_bar(aggregator: TickToBarAggregator, *, minute: str, ticks: list[tuple[str, float, float, float, float]]):
    emitted = []
    for second, bid, ask, bid_size, ask_size in ticks:
        emitted.extend(
            aggregator.update(
            symbol="BTCUSDT",
            timestamp=pd.Timestamp(f"2024-10-21T{minute}:{second}Z"),
            bid=bid,
            ask=ask,
            bid_size=bid_size,
            ask_size=ask_size,
        )
        )
    return emitted


@pytest.mark.asyncio
async def test_trap_pipeline_deploys_orders_from_finalized_bars_via_aggregator():
    adapter = RecordingAdapter()
    oms = OrderManager(adapter)
    coordinator = StopRunCoordinator(oms)
    detector = FixedSignalDetector(
        StructuralTrapSignal(
            symbol="BTCUSDT",
            trap_id="agg_trap_1",
            structural_price=100.0,
            breach_price=99.8,
            side=OrderSide.BUY,
            total_size=2.0,
            layer_offsets_bps=[5.0, 10.0, 15.0],
            layer_weights=[1.0, 1.0, 1.0],
            ttl_seconds=30.0,
            invalidation_price=99.5,
        )
    )
    pipeline = TrapPipeline(detector, coordinator)
    aggregator = TickToBarAggregator("1m")

    assert _emit_bar(
        aggregator,
        minute="12:00",
        ticks=[("10", 99.95, 100.05, 50.0, 50.0), ("50", 100.35, 100.45, 50.0, 50.0)],
    ) == []
    deployed = await pipeline.on_finalized_bars(
        _emit_bar(
            aggregator,
            minute="12:01",
            ticks=[("10", 100.15, 100.25, 55.0, 55.0), ("50", 100.55, 100.65, 55.0, 55.0)],
        )
    )
    assert len(deployed) == 1

    deployed = await pipeline.on_finalized_bars(
        _emit_bar(
            aggregator,
            minute="12:02",
            ticks=[("05", 100.10, 100.20, 40.0, 40.0)],
        )
    )

    assert deployed == []
    assert len(oms.active_orders) == 3
    assert all(order.post_only for order in oms.active_orders.values())
    assert len(pipeline.history_for_symbol("BTCUSDT")) == 2


@pytest.mark.asyncio
async def test_trap_pipeline_skips_duplicate_trap_ids_from_detector():
    adapter = RecordingAdapter()
    oms = OrderManager(adapter)
    coordinator = StopRunCoordinator(oms)
    signal = StructuralTrapSignal(
        symbol="BTCUSDT",
        trap_id="fixed_trap_1",
        structural_price=100.0,
        breach_price=99.8,
        side=OrderSide.BUY,
        total_size=1.0,
        layer_offsets_bps=[5.0, 10.0],
        layer_weights=[1.0, 1.0],
        ttl_seconds=30.0,
        invalidation_price=99.5,
    )
    detector = FixedSignalDetector(signal)
    pipeline = TrapPipeline(detector, coordinator)

    bar = {
        "symbol": "BTCUSDT",
        "bar_start_ts": pd.Timestamp("2024-10-21T12:00:00Z"),
        "bar_end_ts": pd.Timestamp("2024-10-21T12:01:00Z"),
        "mid_low": 99.8,
        "mid_high": 100.3,
        "mid_close": 100.1,
        "volume_proxy": 100.0,
    }

    first = await pipeline.on_finalized_bar(bar)
    second = await pipeline.on_finalized_bar(bar)

    assert len(first) == 1
    assert second == []
    assert len(coordinator.traps) == 1
    assert len(oms.active_orders) == 2
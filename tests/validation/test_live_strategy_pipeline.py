import pytest

from autotrader.execution.adapters import Fill, Order, OrderSide, OrderStatus, OrderType
from autotrader.strategy.pipeline import LiveStrategyPipeline


class FakeAdapter:
    def __init__(self):
        self.fill_callbacks = []
        self.order_update_callbacks = []

    def subscribe_fills(self, callback):
        self.fill_callbacks.append(callback)

    def subscribe_order_updates(self, callback):
        self.order_update_callbacks.append(callback)

    def emit_fill(self, fill: Fill):
        for callback in self.fill_callbacks:
            callback(fill)

    def emit_order_update(self, order: Order):
        for callback in self.order_update_callbacks:
            callback(order)


class FakeRouter:
    def __init__(self, adapter):
        self.adapter = adapter

    async def route_order(self, **_kwargs):
        return ["11", "12"]


@pytest.mark.asyncio
async def test_pipeline_tracks_partial_fill_lifecycle():
    adapter = FakeAdapter()
    pipeline = LiveStrategyPipeline(router=FakeRouter(adapter), target_accounts=["DU1", "DU2"])

    await pipeline.execute_strategy_signal(symbol="AMD", total_qty=10, side="BUY")

    assert pipeline.active_signals["AMD"]["status"] == "ROUTED"

    fill = Fill(
        order_id="11",
        symbol="AMD",
        side=OrderSide.BUY,
        quantity=5.0,
        price=100.25,
        commission=0.0,
        timestamp=None,
        execution_id="exec-1",
    )
    adapter.emit_fill(fill)

    order = Order(
        order_id="11",
        symbol="AMD",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=5.0,
        status=OrderStatus.PARTIAL_FILL,
        filled_quantity=5.0,
        avg_fill_price=100.25,
    )
    adapter.emit_order_update(order)

    signal_state = pipeline.active_signals["AMD"]
    assert signal_state["filled_quantity"] == 5.0
    assert signal_state["status"] == "PARTIAL_FILL"
    assert signal_state["fills"][0]["execution_id"] == "exec-1"


@pytest.mark.asyncio
async def test_pipeline_tracks_cancelled_orders():
    adapter = FakeAdapter()
    pipeline = LiveStrategyPipeline(router=FakeRouter(adapter), target_accounts=["DU1", "DU2"])

    await pipeline.execute_strategy_signal(symbol="AMD", total_qty=10, side="BUY")

    for order_id in ["11", "12"]:
        order = Order(
            order_id=order_id,
            symbol="AMD",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=5.0,
            status=OrderStatus.CANCELLED,
        )
        adapter.emit_order_update(order)

    signal_state = pipeline.active_signals["AMD"]
    assert signal_state["status"] == "CANCELLED"
    assert signal_state["last_order_status"] == OrderStatus.CANCELLED.value

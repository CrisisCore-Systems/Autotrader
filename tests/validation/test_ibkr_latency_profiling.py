from __future__ import annotations

import time
from datetime import datetime
from types import SimpleNamespace

import pytest


pytest.importorskip("ibapi")

from autotrader.execution.adapters import Order, OrderSide, OrderStatus, OrderType
from autotrader.execution.adapters.ibkr import IBKRAdapter
from autotrader.execution.telemetry import TelemetryEngine


def test_loop_latency_profile_payload_shape_and_values() -> None:
    adapter = IBKRAdapter(host="127.0.0.1", port=7497, client_id=260)
    captured = {}

    def _capture(event_type: str, payload=None) -> None:
        captured["event_type"] = event_type
        captured["payload"] = payload or {}

    adapter._emit_telemetry_event = _capture  # type: ignore[method-assign]

    adapter._emit_loop_latency_profile(
        phase="submit_order",
        symbol="USD:AAPL",
        account_id="U1111111",
        interlock_duration_ns=10,
        wal_durability_duration_ns=20,
        wire_serialization_duration_ns=30,
        total_loop_transit_ns=60,
        order_id=77,
        signal_id="sig-77",
    )

    assert captured["event_type"] == "LOOP_LATENCY_PROFILE"
    payload = captured["payload"]
    assert payload["phase"] == "submit_order"
    assert payload["symbol"] == "USD:AAPL"
    assert payload["account_id"] == "U1111111"
    assert payload["order_id"] == 77
    assert payload["signal_id"] == "sig-77"
    assert payload["metrics_ns"]["interlock_duration"] == 10
    assert payload["metrics_ns"]["wal_durability_duration"] == 20
    assert payload["metrics_ns"]["wire_serialization_duration"] == 30
    assert payload["metrics_ns"]["total_loop_transit"] == 60


@pytest.mark.asyncio
async def test_submit_order_emits_latency_profile() -> None:
    adapter = IBKRAdapter(host="127.0.0.1", port=7497, client_id=261)
    emitted = []

    def _capture(event_type: str, payload=None) -> None:
        emitted.append((event_type, payload or {}))

    adapter._emit_telemetry_event = _capture  # type: ignore[method-assign]
    adapter.connected_flag = True
    adapter.next_order_id = 1
    adapter.placeOrder = lambda *args, **kwargs: None
    adapter.reqMktData = lambda *args, **kwargs: None

    order = Order(
        order_id="",
        symbol="AAPL",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=1,
        price=100.0,
        metadata={"account_id": "U1111111", "signal_id": "sig-submit-1"},
    )

    submitted = await adapter.submit_order(order)

    latency_events = [payload for event_type, payload in emitted if event_type == "LOOP_LATENCY_PROFILE"]
    assert submitted.status == OrderStatus.SUBMITTED
    assert len(latency_events) >= 1
    submit_packet = latency_events[-1]
    assert submit_packet["phase"] == "submit_order"
    assert submit_packet["metrics_ns"]["interlock_duration"] >= 0
    assert submit_packet["metrics_ns"]["wal_durability_duration"] == 0
    assert submit_packet["metrics_ns"]["wire_serialization_duration"] >= 0
    assert submit_packet["metrics_ns"]["total_loop_transit"] >= submit_packet["metrics_ns"]["wire_serialization_duration"]


def test_exec_details_emits_latency_profile() -> None:
    adapter = IBKRAdapter(host="127.0.0.1", port=7497, client_id=262)
    emitted = []
    test_order_id = "770001"

    def _capture(event_type: str, payload=None) -> None:
        emitted.append((event_type, payload or {}))

    adapter._emit_telemetry_event = _capture  # type: ignore[method-assign]
    adapter._should_accept_execution = lambda order_id, fingerprint: True
    adapter.wal_engine.append_execution_fingerprint = lambda **kwargs: 0
    adapter.wal_engine.append_execution_shortfall = lambda **kwargs: 0

    order = Order(
        order_id=test_order_id,
        symbol="AAPL",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=2,
        price=101.0,
        status=OrderStatus.SUBMITTED,
        metadata={"signal_id": "sig-exec-77"},
    )
    order.submitted_at = datetime.now()
    adapter.orders[test_order_id] = order
    adapter.ib_to_our_order[int(test_order_id)] = test_order_id

    contract = adapter._create_contract(symbol="AAPL", sec_type="STK", exchange="SMART", currency="USD")
    execution = SimpleNamespace(
        orderId=int(test_order_id),
        execId=f"E-{test_order_id}",
        price=101.25,
        shares=1.0,
        side="BOT",
        time="20250101  09:30:00",
        exchange="SMART",
    )

    adapter.execDetails(0, contract, execution)

    latency_events = [payload for event_type, payload in emitted if event_type == "LOOP_LATENCY_PROFILE"]
    assert len(latency_events) >= 1
    exec_packet = latency_events[-1]
    assert exec_packet["phase"] == "exec_details"
    assert exec_packet["metrics_ns"]["interlock_duration"] >= 0
    assert exec_packet["metrics_ns"]["wal_durability_duration"] >= 0
    assert exec_packet["metrics_ns"]["wire_serialization_duration"] >= 0
    assert exec_packet["metrics_ns"]["total_loop_transit"] >= exec_packet["metrics_ns"]["wal_durability_duration"]


def test_latency_gateway_remains_bounded_under_load() -> None:
    adapter = IBKRAdapter(host="127.0.0.1", port=7497, client_id=263)
    adapter.telemetry_gateway.shutdown()
    adapter.telemetry_gateway = TelemetryEngine(queue_maxsize=8, sink=lambda event: None)

    try:
        for i in range(2000):
            adapter._emit_loop_latency_profile(
                phase="stress",
                symbol="USD:AAPL",
                account_id="U1111111",
                interlock_duration_ns=i,
                wal_durability_duration_ns=i,
                wire_serialization_duration_ns=i,
                total_loop_transit_ns=i * 3,
                order_id=i,
                signal_id=f"sig-{i}",
            )
        time.sleep(0.05)

        assert adapter.telemetry_gateway._queue.qsize() <= 8
        assert adapter.telemetry_gateway.dropped_events >= 0
    finally:
        adapter.telemetry_gateway.shutdown()

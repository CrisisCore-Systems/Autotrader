from __future__ import annotations

import time
from types import SimpleNamespace

import pytest

from autotrader.execution.telemetry import TelemetryEngine


pytest.importorskip("ibapi")

from autotrader.execution.adapters import Position
from autotrader.execution.adapters.ibkr import IBKRAdapter


class _CaptureGateway:
    def __init__(self):
        self.events = []
        self.dropped_events = 0

    def publish(self, event_type: str, state: str, payload=None):
        self.events.append(
            {
                "event_type": event_type,
                "state": state,
                "payload": payload or {},
            }
        )

    def shutdown(self):
        return None


def _contract(symbol: str, currency: str = "USD") -> SimpleNamespace:
    return SimpleNamespace(symbol=symbol, currency=currency)


def test_telemetry_engine_drop_oldest_policy() -> None:
    received = []

    def slow_sink(event):
        time.sleep(0.02)
        received.append(event)

    engine = TelemetryEngine(queue_maxsize=2, sink=slow_sink)
    try:
        for _ in range(30):
            engine.publish("SYSTEM_HEARTBEAT", "OPERATIONAL", {"metrics": {"n": 1}})
        time.sleep(0.6)
        assert engine.dropped_events > 0
        assert len(received) > 0
    finally:
        engine.shutdown()


def test_adapter_emits_circuit_breach_event() -> None:
    adapter = IBKRAdapter(host="127.0.0.1", port=7497, client_id=193)
    adapter.telemetry_gateway.shutdown()
    capture = _CaptureGateway()
    adapter.telemetry_gateway = capture
    adapter._rehydration_complete = True
    adapter._max_drift_pct = 0.01
    adapter.positions_dict["SNDL"] = Position(symbol="SNDL", quantity=10.0, avg_entry_price=1.0)

    adapter.position("DU1", _contract("SNDL"), 5.0, 1.0)

    assert any(item["event_type"] == "CIRCUIT_BREACH" for item in capture.events)


def test_adapter_emits_heartbeat_envelope() -> None:
    adapter = IBKRAdapter(host="127.0.0.1", port=7497, client_id=194)
    adapter.telemetry_gateway.shutdown()
    capture = _CaptureGateway()
    adapter.telemetry_gateway = capture
    adapter._rehydration_complete = True
    adapter._heartbeat_interval_ms = 0
    adapter.positions_dict["SNDL"] = Position(symbol="SNDL", quantity=1.0, avg_entry_price=1.0)

    adapter.position("DU1", _contract("SNDL"), 1.0, 1.0)

    heartbeat_events = [item for item in capture.events if item["event_type"] == "SYSTEM_HEARTBEAT"]
    assert len(heartbeat_events) >= 1
    metrics = heartbeat_events[-1]["payload"].get("metrics", {})
    assert "gross_portfolio_drift_notional" in metrics
    assert "active_symbol_locks" in metrics

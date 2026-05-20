from __future__ import annotations

import pytest


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


def _webhook_events(capture: _CaptureGateway):
    return [e for e in capture.events if e["event_type"] == "WEBHOOK_DISPATCH"]


def test_first_breach_triggers_single_webhook_dispatch() -> None:
    adapter = IBKRAdapter(host="127.0.0.1", port=7497, client_id=197)
    adapter.telemetry_gateway.shutdown()
    capture = _CaptureGateway()
    adapter.telemetry_gateway = capture
    adapter._webhook_url = "https://example.invalid/webhook"

    adapter._emit_circuit_breach_event(
        trigger_type="SYMBOL_DRIFT",
        symbol="SNDL",
        drift_pct=0.02,
        drift_abs=1.0,
    )

    webhook_events = _webhook_events(capture)
    assert len(webhook_events) == 1
    assert webhook_events[0]["payload"]["url"] == "https://example.invalid/webhook"


def test_sustained_breach_is_suppressed_until_rearm() -> None:
    adapter = IBKRAdapter(host="127.0.0.1", port=7497, client_id=198)
    adapter.telemetry_gateway.shutdown()
    capture = _CaptureGateway()
    adapter.telemetry_gateway = capture
    adapter._webhook_url = "https://example.invalid/webhook"

    adapter._emit_circuit_breach_event("SYMBOL_DRIFT", "SNDL", 0.02, 1.0)
    adapter._emit_circuit_breach_event("SYMBOL_DRIFT", "SNDL", 0.03, 2.0)

    assert len(_webhook_events(capture)) == 1


def test_operator_clear_rearms_webhook_gate_for_fresh_breach() -> None:
    adapter = IBKRAdapter(host="127.0.0.1", port=7497, client_id=199)
    adapter.telemetry_gateway.shutdown()
    capture = _CaptureGateway()
    adapter.telemetry_gateway = capture
    adapter._webhook_url = "https://example.invalid/webhook"

    adapter._emit_circuit_breach_event("SYMBOL_DRIFT", "SNDL", 0.02, 1.0)
    assert len(_webhook_events(capture)) == 1

    adapter._circuit_breach_symbols = {"USD:SNDL"}
    adapter.positions_dict["SNDL"] = Position(symbol="SNDL", quantity=10.0, avg_entry_price=1.0)
    adapter._broker_position_snapshots["USD:SNDL"] = {"quantity": 10.0, "avg_cost": 1.0}

    assert adapter.operator_clear_circuit("manual reset") is True

    adapter._emit_circuit_breach_event("SYMBOL_DRIFT", "SNDL", 0.05, 5.0)
    assert len(_webhook_events(capture)) == 2

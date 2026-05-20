from __future__ import annotations

import json

import pytest


pytest.importorskip("ibapi")

from autotrader.execution.adapters import Order, OrderSide, OrderStatus, OrderType
from autotrader.execution.adapters.ibkr import IBKRAdapter


def test_write_last_gasp_envelope_persists_recent_events(tmp_path) -> None:
    adapter = IBKRAdapter(host="127.0.0.1", port=7497, client_id=195)
    adapter._last_gasp_path = tmp_path / "crash_diagnostics.json"
    adapter._reconciliation_state = "BREACHED"

    for idx in range(15):
        adapter._record_reconciliation_event("SNDL", f"event_{idx}", "test")

    try:
        raise RuntimeError("synthetic fatal")
    except RuntimeError as exc:
        adapter._write_last_gasp_envelope(exc, context="unit_test")

    payload = json.loads(adapter._last_gasp_path.read_text(encoding="utf-8"))
    assert payload["event_type"] == "LAST_GASP_DIAGNOSTIC"
    assert payload["context"] == "unit_test"
    assert payload["fatal_error"]["type"] == "RuntimeError"
    assert len(payload["recent_reconciliation_events"]) == 10
    assert payload["recent_reconciliation_events"][0]["event"] == "event_5"
    assert payload["recent_reconciliation_events"][-1]["event"] == "event_14"


@pytest.mark.asyncio
async def test_submit_order_failure_writes_last_gasp(tmp_path) -> None:
    adapter = IBKRAdapter(host="127.0.0.1", port=7497, client_id=196)
    adapter._last_gasp_path = tmp_path / "crash_diagnostics.json"
    adapter.connected_flag = True
    adapter.next_order_id = 1

    def _raise_place_order(*args, **kwargs):
        raise RuntimeError("placeOrder exploded")

    adapter.placeOrder = _raise_place_order

    order = Order(
        order_id="",
        symbol="SNDL",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=1.0,
        price=1.0,
        status=OrderStatus.PENDING,
    )

    with pytest.raises(RuntimeError, match="placeOrder exploded"):
        await adapter.submit_order(order)

    payload = json.loads(adapter._last_gasp_path.read_text(encoding="utf-8"))
    assert payload["context"] == "submit_order:SNDL"
    assert payload["fatal_error"]["message"] == "placeOrder exploded"

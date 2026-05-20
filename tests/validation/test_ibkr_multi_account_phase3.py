from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


pytest.importorskip("ibapi")

from autotrader.execution.adapters.ibkr import IBKRAdapter


def _contract(symbol: str, currency: str = "USD") -> SimpleNamespace:
    return SimpleNamespace(symbol=symbol, currency=currency)


def _webhook_dispatches(calls):
    events = []
    for call in calls:
        kwargs = call[1]
        if kwargs.get("event_type") == "WEBHOOK_DISPATCH":
            events.append(kwargs)
    return events


@pytest.mark.asyncio
async def test_cross_account_webhook_isolation_and_rearm() -> None:
    """Verify account-isolated webhooks fire independently and clear independently."""
    adapter = IBKRAdapter(host="127.0.0.1", port=7497, client_id=203)
    adapter._rehydration_complete = True
    adapter._webhook_url = "http://localhost:9999/webhook"
    adapter.telemetry_gateway = MagicMock()

    # 1. Trigger breach on Account A.
    adapter.position("U1111111", _contract("AMD"), 500.0, 100.0)
    calls = adapter.telemetry_gateway.publish.call_args_list
    webhook_dispatches = _webhook_dispatches(calls)
    assert len(webhook_dispatches) == 1

    # Nested payload path: kwargs['payload']['payload']['account_id']
    outer_payload = webhook_dispatches[0].get("payload", {})
    inner_payload = outer_payload.get("payload", {})
    assert inner_payload.get("account_id") == "U1111111"

    # 2. Trigger second consecutive breach on Account A (must be suppressed).
    adapter.position("U1111111", _contract("AMD"), 600.0, 100.0)
    calls_after_second = adapter.telemetry_gateway.publish.call_args_list
    webhook_dispatches_2 = _webhook_dispatches(calls_after_second)
    assert len(webhook_dispatches_2) == 1

    # 3. Trigger first breach on Account B (must fire despite Account A suppression).
    adapter.position("U2222222", _contract("NVDA"), 500.0, 100.0)
    calls_after_b = adapter.telemetry_gateway.publish.call_args_list
    webhook_dispatches_3 = _webhook_dispatches(calls_after_b)
    assert len(webhook_dispatches_3) == 2

    outer_payload_b = webhook_dispatches_3[1].get("payload", {})
    inner_payload_b = outer_payload_b.get("payload", {})
    assert inner_payload_b.get("account_id") == "U2222222"

    # 4. Clear Account A only; Account B latch must remain armed.
    adapter.operator_clear_circuit("U1111111")
    ctx_a = adapter._get_account_ctx("U1111111")
    ctx_b = adapter._get_account_ctx("U2222222")
    assert len(ctx_a["fired_breach_epochs"]) == 0
    assert len(ctx_b["fired_breach_epochs"]) == 1

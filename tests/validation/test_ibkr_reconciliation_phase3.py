from __future__ import annotations

from types import SimpleNamespace

import pytest


pytest.importorskip("ibapi")

from autotrader.execution.adapters import Order, OrderSide, OrderType, Position
from autotrader.execution.adapters.ibkr import IBKRAdapter


def _contract(symbol: str, currency: str = "USD") -> SimpleNamespace:
    return SimpleNamespace(symbol=symbol, currency=currency)


@pytest.fixture
def adapter() -> IBKRAdapter:
    a = IBKRAdapter(host="127.0.0.1", port=7497, client_id=192)
    a._rehydration_complete = True
    return a


def test_operator_clear_circuit_fails_with_unresolved_drift(adapter: IBKRAdapter) -> None:
    adapter.positions_dict["SNDL"] = Position(symbol="SNDL", quantity=10.0, avg_entry_price=1.0)
    adapter._broker_position_snapshots["USD:SNDL"] = {"quantity": 9.0, "avg_cost": 1.0}
    adapter._circuit_breach_symbols.add("USD:SNDL")
    adapter._reconciliation_circuit_open = True

    cleared = adapter.operator_clear_circuit("post-incident verification")

    assert cleared is False
    assert adapter._reconciliation_circuit_open is True
    assert "USD:SNDL" in adapter._circuit_breach_symbols


@pytest.mark.asyncio
async def test_operator_clear_circuit_succeeds_and_restores_submit_path(adapter: IBKRAdapter) -> None:
    adapter.positions_dict["SNDL"] = Position(symbol="SNDL", quantity=10.0, avg_entry_price=1.0)
    adapter._broker_position_snapshots["USD:SNDL"] = {"quantity": 10.0, "avg_cost": 1.0}
    adapter._circuit_breach_symbols.add("USD:SNDL")
    adapter._reconciliation_circuit_open = True
    adapter._set_reconciliation_lock("SNDL", "breach lock")

    cleared = adapter.operator_clear_circuit("manual reconciliation complete")

    assert cleared is True
    assert adapter._reconciliation_circuit_open is False
    assert adapter._circuit_breach_symbols == set()
    assert adapter._reconciliation_locks == set()

    adapter.connected_flag = True
    adapter.next_order_id = 1
    adapter.placeOrder = lambda *args, **kwargs: None

    order = Order(
        order_id="",
        symbol="SNDL",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=1.0,
        price=1.0,
    )

    submitted = await adapter.submit_order(order)
    assert submitted.order_id == "1"


def test_position_end_refreshes_bootstrap_and_global_state(adapter: IBKRAdapter) -> None:
    adapter._reconciliation_bootstrap_pending = True
    adapter._max_drift_pct = 0.01
    adapter.positions_dict["SNDL"] = Position(symbol="SNDL", quantity=10.0, avg_entry_price=1.0)
    adapter._broker_position_snapshots["USD:SNDL"] = {"quantity": 5.0, "avg_cost": 1.0}

    adapter.positionEnd()

    assert adapter._reconciliation_bootstrap_pending is False
    assert adapter._reconciliation_circuit_open is True
    assert adapter._reconciliation_state == "BREACHED"

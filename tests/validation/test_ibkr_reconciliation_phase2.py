from __future__ import annotations

from types import SimpleNamespace

import pytest


pytest.importorskip("ibapi")

from autotrader.execution.adapters import Order, OrderSide, OrderStatus, OrderType, Position
from autotrader.execution.adapters.ibkr import IBKRAdapter


def _contract(symbol: str, currency: str = "USD") -> SimpleNamespace:
    return SimpleNamespace(symbol=symbol, currency=currency)


@pytest.fixture
def adapter() -> IBKRAdapter:
    a = IBKRAdapter(host="127.0.0.1", port=7497, client_id=191)
    a._rehydration_complete = True
    return a


def test_position_circuit_breach_trips_global_interlock(adapter: IBKRAdapter) -> None:
    adapter._max_drift_pct = 0.01
    adapter.positions_dict["SNDL"] = Position(symbol="SNDL", quantity=10.0, avg_entry_price=1.0)

    adapter.position("DU123", _contract("SNDL"), 5.0, 1.0)

    assert adapter._reconciliation_circuit_open is True
    assert adapter._is_reconciliation_locked("SNDL") is True
    assert "USD:SNDL" in adapter._circuit_breach_symbols


def test_position_defers_when_drift_and_open_orders(adapter: IBKRAdapter) -> None:
    adapter._max_drift_pct = 1.0
    adapter.positions_dict["SNDL"] = Position(symbol="SNDL", quantity=10.0, avg_entry_price=1.0)
    order = Order(
        order_id="10",
        symbol="SNDL",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=1.0,
        price=1.0,
        status=OrderStatus.SUBMITTED,
    )
    adapter.orders[order.order_id] = order

    adapter.position("DU123", _contract("SNDL"), 9.0, 1.0)

    assert adapter._is_reconciliation_locked("SNDL") is True
    assert adapter.positions_dict["SNDL"].quantity == pytest.approx(10.0)


def test_position_force_sync_when_drift_without_open_orders(adapter: IBKRAdapter) -> None:
    adapter._max_drift_pct = 1.0
    adapter.positions_dict["SNDL"] = Position(symbol="SNDL", quantity=10.0, avg_entry_price=1.0)

    adapter.position("DU123", _contract("SNDL"), 9.0, 1.2)

    assert adapter._is_reconciliation_locked("SNDL") is False
    assert adapter.positions_dict["SNDL"].quantity == pytest.approx(9.0)
    assert adapter.positions_dict["SNDL"].avg_entry_price == pytest.approx(1.2)


def test_position_equilibrium_releases_existing_lock(adapter: IBKRAdapter) -> None:
    adapter._max_drift_pct = 1.0
    adapter.positions_dict["SNDL"] = Position(symbol="SNDL", quantity=4.0, avg_entry_price=1.0)
    adapter._set_reconciliation_lock("SNDL", "pre-existing lock")

    adapter.position("DU123", _contract("SNDL"), 4.0, 1.0)

    assert adapter._is_reconciliation_locked("SNDL") is False

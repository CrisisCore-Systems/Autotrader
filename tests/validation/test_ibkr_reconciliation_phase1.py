from __future__ import annotations

from datetime import datetime

import pytest


pytest.importorskip("ibapi")

from autotrader.execution.adapters import Order, OrderSide, OrderStatus, OrderType
from autotrader.execution.adapters.ibkr import IBKRAdapter


@pytest.fixture
def adapter() -> IBKRAdapter:
    return IBKRAdapter(host="127.0.0.1", port=7497, client_id=190)


def test_reconciliation_lock_key_normalization(adapter: IBKRAdapter) -> None:
    adapter._set_reconciliation_lock(" aapl ", "test lock")
    assert adapter._is_reconciliation_locked("AAPL") is True
    assert adapter._is_reconciliation_locked("aapl") is True


def test_reconciliation_unlock_when_no_working_orders(adapter: IBKRAdapter) -> None:
    adapter._set_reconciliation_lock("MSFT", "in-flight")
    adapter._clear_reconciliation_lock_if_safe("MSFT", "resolved")
    assert adapter._is_reconciliation_locked("MSFT") is False


@pytest.mark.asyncio
async def test_submit_order_blocked_when_circuit_open(adapter: IBKRAdapter) -> None:
    adapter._reconciliation_circuit_open = True
    adapter.connected_flag = True
    adapter.next_order_id = 1

    order = Order(
        order_id="",
        symbol="AAPL",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=1,
        price=100.0,
    )

    with pytest.raises(RuntimeError, match="circuit breaker"):
        await adapter.submit_order(order)


@pytest.mark.asyncio
async def test_submit_order_blocked_when_symbol_locked(adapter: IBKRAdapter) -> None:
    adapter._set_reconciliation_lock("AAPL", "in-flight convergence")
    adapter.connected_flag = True
    adapter.next_order_id = 1

    order = Order(
        order_id="",
        symbol="AAPL",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=1,
        price=100.0,
    )

    with pytest.raises(RuntimeError, match="Reconciliation lock active"):
        await adapter.submit_order(order)


def test_terminal_transition_unlocks_symbol(adapter: IBKRAdapter) -> None:
    order = Order(
        order_id="77",
        symbol="AAPL",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=1,
        price=100.0,
        status=OrderStatus.SUBMITTED,
    )
    order.submitted_at = datetime.now()
    adapter.orders[order.order_id] = order
    adapter.ib_to_our_order[77] = order.order_id
    adapter._set_reconciliation_lock("AAPL", "in-flight convergence")
    order.status = OrderStatus.CANCELLED

    adapter._record_runtime_transition(
        order=order,
        previous_status="Submitted",
        new_status=OrderStatus.CANCELLED,
        filled=0.0,
        remaining=1.0,
        failure_reason="test",
    )

    assert adapter._is_reconciliation_locked("AAPL") is False

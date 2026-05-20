from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


pytest.importorskip("ibapi")

from autotrader.execution.adapters import Order, OrderSide, OrderType
from autotrader.execution.adapters.ibkr import IBKRAdapter, _AdapterStateWALEngine


def _mk_order(order_id: str, symbol: str, side: OrderSide) -> Order:
    return Order(
        order_id=order_id,
        symbol=symbol,
        side=side,
        order_type=OrderType.LIMIT,
        quantity=1.0,
        price=100.0,
    )


def _mk_exec(order_id: int, exec_id: str, side: str, px: float) -> SimpleNamespace:
    return SimpleNamespace(
        orderId=order_id,
        execId=exec_id,
        side=side,
        price=px,
        shares=1.0,
        time="20260517  12:00:00",
        exchange="SMART",
    )


def test_exec_shortfall_buy_is_positive_for_worse_fill() -> None:
    adapter = IBKRAdapter(host="127.0.0.1", port=7497, client_id=207)
    adapter.wal_engine.append_execution_fingerprint = MagicMock(return_value=1)
    adapter.wal_engine.append_execution_shortfall = MagicMock(return_value=2)
    adapter._closed_order_ids.clear()
    adapter._seen_execution_fingerprints.clear()

    order = _mk_order("1", "AAPL", OrderSide.BUY)
    adapter.orders["1"] = order
    adapter.ib_to_our_order[1] = "1"
    adapter._active_order_benchmarks[1] = {
        "account_id": "U1111111",
        "symbol_key": "USD:AAPL",
        "side": OrderSide.BUY,
        "benchmark_mid": 100.0,
    }

    adapter.execDetails(0, SimpleNamespace(symbol="AAPL", currency="USD"), _mk_exec(1, "EX-BUY-1", "BOT", 100.2))

    kwargs = adapter.wal_engine.append_execution_shortfall.call_args.kwargs
    assert kwargs["slippage_bps"] == pytest.approx(20.0)
    assert kwargs["account_id"] == "U1111111"
    assert kwargs["symbol"] == "USD:AAPL"


def test_exec_shortfall_sell_is_positive_for_worse_fill() -> None:
    adapter = IBKRAdapter(host="127.0.0.1", port=7497, client_id=208)
    adapter.wal_engine.append_execution_fingerprint = MagicMock(return_value=1)
    adapter.wal_engine.append_execution_shortfall = MagicMock(return_value=2)
    adapter._closed_order_ids.clear()
    adapter._seen_execution_fingerprints.clear()

    order = _mk_order("2", "NVDA", OrderSide.SELL)
    adapter.orders["2"] = order
    adapter.ib_to_our_order[2] = "2"
    adapter._active_order_benchmarks[2] = {
        "account_id": "U2222222",
        "symbol_key": "USD:NVDA",
        "side": OrderSide.SELL,
        "benchmark_mid": 100.0,
    }

    adapter.execDetails(0, SimpleNamespace(symbol="NVDA", currency="USD"), _mk_exec(2, "EX-SELL-1", "SLD", 99.8))

    kwargs = adapter.wal_engine.append_execution_shortfall.call_args.kwargs
    assert kwargs["slippage_bps"] == pytest.approx(20.0)
    assert kwargs["account_id"] == "U2222222"
    assert kwargs["symbol"] == "USD:NVDA"


def test_shortfall_rows_roundtrip_in_wal_rehydration(tmp_path: Path) -> None:
    wal_path = tmp_path / "adapter_state_journal.wal"
    engine = _AdapterStateWALEngine(wal_path)

    seq = engine.append_execution_shortfall(
        order_id=11,
        exec_id="EX-SHORTFALL-1",
        account_id="U3333333",
        symbol="USD:MSFT",
        side="BUY",
        execution_price=101.25,
        execution_size=2.0,
        commission=0.5,
        benchmark_mid=101.0,
        execution_mid=101.1,
        slippage_bps=24.752475,
    )

    assert seq == 1

    trackers, fingerprints, repaired = engine.rehydrate_and_repair()

    assert repaired is False
    assert trackers == {}
    assert fingerprints == set()
    assert engine.current_sequence == 1

from __future__ import annotations

import pytest


pytest.importorskip("ibapi")

from autotrader.execution.adapters import Order, OrderSide, OrderType
from autotrader.execution.adapters.ibkr import IBKRAdapter


def _base_order(**kwargs) -> Order:
    return Order(
        order_id="",
        symbol=kwargs.get("symbol", "AAPL"),
        side=kwargs.get("side", OrderSide.BUY),
        order_type=kwargs.get("order_type", OrderType.LIMIT),
        quantity=kwargs.get("quantity", 10.0),
        price=kwargs.get("price", 100.0),
        metadata=kwargs.get("metadata", {}),
    )


def test_hidden_flag_maps_to_native_ib_order() -> None:
    adapter = IBKRAdapter(host="127.0.0.1", port=7497, client_id=209)
    order = _base_order(metadata={"is_hidden": True})

    ib_order = adapter._create_ib_order(order)

    assert getattr(ib_order, "hidden", False) is True


def test_display_size_maps_to_native_ib_order() -> None:
    adapter = IBKRAdapter(host="127.0.0.1", port=7497, client_id=210)
    order = _base_order(metadata={"display_size": 100})

    ib_order = adapter._create_ib_order(order)

    assert getattr(ib_order, "displaySize", None) == 100


def test_legacy_order_defaults_to_open_book() -> None:
    adapter = IBKRAdapter(host="127.0.0.1", port=7497, client_id=211)
    order = _base_order()

    ib_order = adapter._create_ib_order(order)

    assert bool(getattr(ib_order, "hidden", False)) is False
    display_size = getattr(ib_order, "displaySize", None)
    assert display_size in (None, 0)

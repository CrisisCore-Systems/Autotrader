from __future__ import annotations

from unittest.mock import MagicMock

import pytest


pytest.importorskip("ibapi")

from autotrader.execution.adapters.ibkr import IBKRAdapter


def test_nbbo_subscription_is_idempotent_per_symbol() -> None:
    adapter = IBKRAdapter(host="127.0.0.1", port=7497, client_id=204)
    adapter.reqMktData = MagicMock()

    contract = adapter._create_contract(symbol="AAPL", sec_type="STK", exchange="SMART", currency="USD")

    req_a = adapter._ensure_nbbo_subscription(contract)
    req_b = adapter._ensure_nbbo_subscription(contract)

    assert req_a == req_b
    assert adapter.reqMktData.call_count == 1


def test_tick_callbacks_update_nbbo_snapshot_and_mid() -> None:
    adapter = IBKRAdapter(host="127.0.0.1", port=7497, client_id=205)
    adapter.reqMktData = MagicMock()

    contract = adapter._create_contract(symbol="MSFT", sec_type="STK", exchange="SMART", currency="USD")
    req_id = adapter._ensure_nbbo_subscription(contract)

    adapter.tickPrice(req_id, 1, 100.0, None)  # bid
    adapter.tickPrice(req_id, 2, 100.2, None)  # ask
    adapter.tickSize(req_id, 0, 450.0)  # bid size
    adapter.tickSize(req_id, 3, 500.0)  # ask size

    snap = adapter.get_nbbo_snapshot("MSFT", "USD")
    assert snap["bid"] == 100.0
    assert snap["ask"] == 100.2
    assert snap["mid"] == pytest.approx(100.1)
    assert snap["bid_size"] == 450.0
    assert snap["ask_size"] == 500.0
    assert snap["last_update_ms"] > 0


def test_unknown_reqid_ticks_are_ignored() -> None:
    adapter = IBKRAdapter(host="127.0.0.1", port=7497, client_id=206)

    adapter.tickPrice(999_999, 1, 42.0, None)
    adapter.tickSize(999_999, 0, 10.0)

    # No symbol mapping should be created from unknown reqIds.
    assert adapter._nbbo_snapshots == {}

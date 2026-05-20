from __future__ import annotations

from types import SimpleNamespace

import pytest


pytest.importorskip("ibapi")

from autotrader.execution.adapters.ibkr import IBKRAdapter


def _contract(symbol: str, currency: str = "USD") -> SimpleNamespace:
    return SimpleNamespace(symbol=symbol, currency=currency)


def test_default_account_context_is_initialized() -> None:
    adapter = IBKRAdapter(host="127.0.0.1", port=7497, client_id=200, default_account_id="DU-DEFAULT")
    ctx = adapter._get_account_ctx(None)

    assert adapter._default_account_id == "DU-DEFAULT"
    assert "reconciliation_locks" in ctx
    assert "circuit_breach_symbols" in ctx
    assert "broker_position_snapshots" in ctx


def test_account_contexts_are_partitioned_for_position_snapshots() -> None:
    adapter = IBKRAdapter(host="127.0.0.1", port=7497, client_id=201, default_account_id="DU-DEFAULT")
    adapter._rehydration_complete = True

    adapter.position("DU-ALPHA", _contract("SNDL"), 1.0, 1.0)
    adapter.position("DU-BETA", _contract("AAPL"), 2.0, 150.0)

    alpha_ctx = adapter._get_account_ctx("DU-ALPHA")
    beta_ctx = adapter._get_account_ctx("DU-BETA")

    assert "USD:SNDL" in alpha_ctx["broker_position_snapshots"]
    assert "USD:AAPL" not in alpha_ctx["broker_position_snapshots"]
    assert "USD:AAPL" in beta_ctx["broker_position_snapshots"]
    assert "USD:SNDL" not in beta_ctx["broker_position_snapshots"]

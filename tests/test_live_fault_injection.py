"""Fault-injection tests for the Phase 5 live execution safety boundary."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from autotrader.execution.adapters.paper import PaperTradingAdapter
from autotrader.execution.live.contracts import PortfolioStateSnapshot, StateDivergenceException
from autotrader.execution.live.oms import LiveOMS
from autotrader.execution.live.reconciler import LiveReconciler


def _snapshot(
    *,
    positions: dict[str, float] | None = None,
    open_order_ids: list[str] | None = None,
    source: str = "test",
) -> PortfolioStateSnapshot:
    return PortfolioStateSnapshot(
        timestamp=datetime.now(timezone.utc),
        positions=dict(positions or {}),
        open_order_ids=list(open_order_ids or []),
        source=source,
    )


async def _create_live_oms() -> LiveOMS:
    adapter = PaperTradingAdapter(
        initial_balance=100_000.0,
        latency_ms=(0, 0),
        slippage_bps=0.0,
        commission_bps=0.0,
        fill_probability=1.0,
    )
    await adapter.connect()
    return LiveOMS(adapter=adapter, max_open_orders=10, order_timeout_seconds=30.0)


def test_fault_injection_heartbeat_starvation_triggers_emergency_kill():
    """When heartbeat is stale, the reconciler must kill trading immediately."""
    live_oms = asyncio.run(_create_live_oms())

    reconciler = LiveReconciler(
        oms=live_oms,
        local_snapshot_provider=lambda: _snapshot(source="local"),
        exchange_snapshot_provider=lambda: _snapshot(source="exchange"),
        interval_seconds=1.0,
        tolerance_qty=0.0,
        heartbeat_timeout_seconds=1.0,
    )

    reconciler.mark_heartbeat()
    # Force staleness without sleeping to keep the test deterministic.
    reconciler._last_heartbeat_at = datetime.now(timezone.utc) - timedelta(seconds=5)

    with pytest.raises(StateDivergenceException, match="Heartbeat stale"):
        asyncio.run(reconciler.audit_cycle())

    assert live_oms.kill_switch_engaged is True
    assert live_oms.kill_switch_reason is not None
    assert "Heartbeat stale" in live_oms.kill_switch_reason


def test_fault_injection_position_drift_triggers_emergency_kill():
    """A local/exchange position mismatch must trigger state-divergence kill."""
    live_oms = asyncio.run(_create_live_oms())

    local_state = _snapshot(positions={"BTC/USD": 1.0}, source="local")
    exchange_state = _snapshot(positions={"BTC/USD": 0.0}, source="exchange")

    reconciler = LiveReconciler(
        oms=live_oms,
        local_snapshot_provider=lambda: local_state,
        exchange_snapshot_provider=lambda: exchange_state,
        interval_seconds=1.0,
        tolerance_qty=0.0,
        heartbeat_timeout_seconds=30.0,
    )

    reconciler.mark_heartbeat()

    with pytest.raises(StateDivergenceException, match="diverged") as exc_info:
        asyncio.run(reconciler.audit_cycle())

    assert live_oms.kill_switch_engaged is True
    assert live_oms.kill_switch_reason is not None
    assert "diverged" in live_oms.kill_switch_reason
    assert len(exc_info.value.divergences) >= 1
    assert exc_info.value.divergences[0].symbol == "BTC/USD"


def test_fault_injection_open_order_drift_triggers_emergency_kill():
    """A mismatch in open-order IDs should also be treated as critical drift."""
    live_oms = asyncio.run(_create_live_oms())

    local_state = _snapshot(open_order_ids=["OID_LOCAL_1"], source="local")
    exchange_state = _snapshot(open_order_ids=["OID_EXCHANGE_9"], source="exchange")

    reconciler = LiveReconciler(
        oms=live_oms,
        local_snapshot_provider=lambda: local_state,
        exchange_snapshot_provider=lambda: exchange_state,
        interval_seconds=1.0,
        tolerance_qty=0.0,
        heartbeat_timeout_seconds=30.0,
    )

    reconciler.mark_heartbeat()

    with pytest.raises(StateDivergenceException) as exc_info:
        asyncio.run(reconciler.audit_cycle())

    assert live_oms.kill_switch_engaged is True
    assert len(exc_info.value.divergences) >= 1
    symbols = {item.symbol for item in exc_info.value.divergences}
    assert "__open_orders__" in symbols
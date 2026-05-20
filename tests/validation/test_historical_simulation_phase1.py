import pandas as pd
import pytest

from autotrader.backtesting.engine.historical import (
    DuckDBHistoricalDatasetConnector,
    HistoricalQuoteEvent,
    HistoricalSimulationEngine,
    StrategySignal,
)


class _FakeConn:
    def __init__(self, rows):
        self._rows = rows

    def execute(self, sql, params=None):
        _ = (sql, params)
        return self

    def fetchall(self):
        return self._rows

    def close(self):
        return None


class _DummyRouter:
    def __init__(self, should_reject=False):
        self.should_reject = should_reject
        self.calls = []

    async def route_order(self, **kwargs):
        self.calls.append(kwargs)
        if self.should_reject:
            raise RuntimeError("synthetic margin interlock reject")
        return ["OID-1", "OID-2"]


def test_duckdb_connector_emits_quote_events_from_rows():
    rows = [
        (pd.Timestamp("2026-05-01T09:30:00"), "AMD", 100.0, 100.1),
        (pd.Timestamp("2026-05-01T09:30:01"), "AMD", 100.1, 100.2),
    ]
    connector = DuckDBHistoricalDatasetConnector(
        dataset_glob="data/historical/US/EQUITIES/AMD/2026/05/*.parquet",
        connection_factory=lambda: _FakeConn(rows),
    )

    events = list(connector.iter_quotes("AMD"))

    assert len(events) == 2
    assert isinstance(events[0], HistoricalQuoteEvent)
    assert events[0].symbol == "AMD"
    assert events[0].mid == pytest.approx(100.05)


@pytest.mark.asyncio
async def test_simulation_engine_routes_signal_and_tracks_nbbo():
    rows = [
        (pd.Timestamp("2026-05-01T09:30:00"), "NVDA", 900.0, 900.1),
    ]
    connector = DuckDBHistoricalDatasetConnector(
        dataset_glob="data/historical/US/EQUITIES/NVDA/2026/05/*.parquet",
        connection_factory=lambda: _FakeConn(rows),
    )
    router = _DummyRouter(should_reject=False)

    def strategy_callback(event, nbbo_cache):
        _ = (event, nbbo_cache)
        return StrategySignal(
            symbol="NVDA",
            total_qty=1500,
            side="BUY",
            policy="FIXED_EQUAL",
            target_accounts=["U1111111", "U2222222"],
        )

    engine = HistoricalSimulationEngine(
        data_connector=connector,
        strategy_callback=strategy_callback,
        allocation_router=router,
    )

    summary = await engine.run("NVDA")

    assert summary.quote_events_processed == 1
    assert summary.signals_processed == 1
    assert summary.matched_orders == 1
    assert summary.routed_orders == 2
    assert summary.rejected_allocations == 0
    assert len(router.calls) == 1
    assert engine.nbbo_cache["NVDA"]["mid"] == pytest.approx(900.05)
    event_types = [evt.event_type for evt in engine.trace_events]
    assert "ALLOCATION_ROUTE_ACCEPT" in event_types
    assert "ALLOCATION_MATCHED" in event_types


@pytest.mark.asyncio
async def test_simulation_engine_records_allocation_reject_trace():
    rows = [
        (pd.Timestamp("2026-05-01T09:30:00"), "TSLA", 180.0, 180.2),
    ]
    connector = DuckDBHistoricalDatasetConnector(
        dataset_glob="data/historical/US/EQUITIES/TSLA/2026/05/*.parquet",
        connection_factory=lambda: _FakeConn(rows),
    )
    router = _DummyRouter(should_reject=True)

    def strategy_callback(event, nbbo_cache):
        _ = (event, nbbo_cache)
        return StrategySignal(
            symbol="TSLA",
            total_qty=500,
            side="BUY",
            policy="DYNAMIC_NLV",
            target_accounts=["U1111111", "U2222222"],
        )

    engine = HistoricalSimulationEngine(
        data_connector=connector,
        strategy_callback=strategy_callback,
        allocation_router=router,
    )

    summary = await engine.run("TSLA")

    assert summary.quote_events_processed == 1
    assert summary.signals_processed == 1
    assert summary.matched_orders == 0
    assert summary.routed_orders == 0
    assert summary.rejected_allocations == 1
    assert engine.trace_events[-1].event_type == "ALLOCATION_REJECT"
    assert "synthetic margin interlock reject" in engine.trace_events[-1].payload["reason"]

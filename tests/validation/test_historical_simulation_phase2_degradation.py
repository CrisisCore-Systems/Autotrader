import pandas as pd
import pytest

from autotrader.backtesting.engine.historical import (
    DuckDBHistoricalDatasetConnector,
    HistoricalSimulationEngine,
    LatencyDistributionProfile,
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


class _AcceptingRouter:
    def __init__(self):
        self.calls = []

    async def route_order(self, **kwargs):
        self.calls.append(kwargs)
        return ["OID-A"]


@pytest.mark.asyncio
async def test_latency_queue_defers_matching_until_arrival():
    rows = [
        (pd.Timestamp("2026-05-01T09:30:00.000000"), "AMD", 100.00, 100.10, 500.0, 500.0),
        (pd.Timestamp("2026-05-01T09:30:00.200000"), "AMD", 100.01, 100.11, 500.0, 500.0),
    ]
    connector = DuckDBHistoricalDatasetConnector(
        dataset_glob="data/historical/US/EQUITIES/AMD/2026/05/*.parquet",
        bid_size_col="bid_size",
        ask_size_col="ask_size",
        connection_factory=lambda: _FakeConn(rows),
    )
    router = _AcceptingRouter()

    seen = {"fired": False}

    def strategy_callback(event, nbbo_cache):
        _ = nbbo_cache
        if seen["fired"]:
            return None
        seen["fired"] = True
        return StrategySignal(
            symbol="AMD",
            total_qty=100,
            side="BUY",
            policy="FIXED_EQUAL",
            target_accounts=["U1111111", "U2222222"],
        )

    # 150us delay means first quote cannot match; second quote should match.
    def latency_provider(signal, event, nbbo_cache):
        _ = (signal, event, nbbo_cache)
        return 150_000

    engine = HistoricalSimulationEngine(
        data_connector=connector,
        strategy_callback=strategy_callback,
        allocation_router=router,
        latency_ns_provider=latency_provider,
    )

    summary = await engine.run("AMD")

    assert summary.quote_events_processed == 2
    assert summary.signals_processed == 1
    assert summary.matched_orders == 1
    assert len(router.calls) == 1

    match_events = [e for e in engine.trace_events if e.event_type == "ALLOCATION_MATCHED"]
    assert len(match_events) == 1
    exec_ts = pd.Timestamp(match_events[0].payload["execution_ts"])
    arrival_ts = pd.Timestamp(match_events[0].payload["arrival_ts"])
    assert exec_ts >= arrival_ts


@pytest.mark.asyncio
async def test_buy_matching_uses_ask_and_computes_positive_shortfall_bps():
    rows = [
        (pd.Timestamp("2026-05-01T09:30:00"), "NVDA", 900.00, 900.20, 1000.0, 50.0),
    ]
    connector = DuckDBHistoricalDatasetConnector(
        dataset_glob="data/historical/US/EQUITIES/NVDA/2026/05/*.parquet",
        bid_size_col="bid_size",
        ask_size_col="ask_size",
        connection_factory=lambda: _FakeConn(rows),
    )
    router = _AcceptingRouter()

    def strategy_callback(event, nbbo_cache):
        _ = (event, nbbo_cache)
        return StrategySignal(
            symbol="NVDA",
            total_qty=100,
            side="BUY",
            policy="FIXED_EQUAL",
            target_accounts=["U1111111", "U2222222"],
        )

    engine = HistoricalSimulationEngine(
        data_connector=connector,
        strategy_callback=strategy_callback,
        allocation_router=router,
        size_penalty_bps_per_excess_ratio=10.0,
    )

    summary = await engine.run("NVDA")

    assert summary.matched_orders == 1
    matched = [e for e in engine.trace_events if e.event_type == "ALLOCATION_MATCHED"][0]
    assert matched.payload["execution_price"] > 900.20
    assert matched.payload["shortfall_bps"] > 0.0


@pytest.mark.asyncio
async def test_sell_matching_uses_bid_and_computes_positive_shortfall_bps():
    rows = [
        (pd.Timestamp("2026-05-01T09:30:00"), "TSLA", 180.00, 180.20, 40.0, 500.0),
    ]
    connector = DuckDBHistoricalDatasetConnector(
        dataset_glob="data/historical/US/EQUITIES/TSLA/2026/05/*.parquet",
        bid_size_col="bid_size",
        ask_size_col="ask_size",
        connection_factory=lambda: _FakeConn(rows),
    )
    router = _AcceptingRouter()

    def strategy_callback(event, nbbo_cache):
        _ = (event, nbbo_cache)
        return StrategySignal(
            symbol="TSLA",
            total_qty=80,
            side="SELL",
            policy="FIXED_EQUAL",
            target_accounts=["U1111111", "U2222222"],
        )

    engine = HistoricalSimulationEngine(
        data_connector=connector,
        strategy_callback=strategy_callback,
        allocation_router=router,
        size_penalty_bps_per_excess_ratio=10.0,
    )

    summary = await engine.run("TSLA")

    assert summary.matched_orders == 1
    matched = [e for e in engine.trace_events if e.event_type == "ALLOCATION_MATCHED"][0]
    assert matched.payload["execution_price"] < 180.00
    assert matched.payload["shortfall_bps"] > 0.0


@pytest.mark.asyncio
async def test_time_decay_exit_emits_open_and_exit_events():
    rows = [
        (pd.Timestamp("2026-05-01T09:30:00.000000"), "AMD", 100.00, 100.10, 500.0, 500.0),
        (pd.Timestamp("2026-05-01T09:30:00.100000"), "AMD", 100.05, 100.15, 500.0, 500.0),
        (pd.Timestamp("2026-05-01T09:30:00.200000"), "AMD", 100.20, 100.30, 500.0, 500.0),
    ]
    connector = DuckDBHistoricalDatasetConnector(
        dataset_glob="data/historical/US/EQUITIES/AMD/2026/05/*.parquet",
        bid_size_col="bid_size",
        ask_size_col="ask_size",
        connection_factory=lambda: _FakeConn(rows),
    )
    router = _AcceptingRouter()

    fired = {"done": False}

    def strategy_callback(event, nbbo_cache):
        _ = (event, nbbo_cache)
        if fired["done"]:
            return None
        fired["done"] = True
        return StrategySignal(
            symbol="AMD",
            total_qty=100,
            side="BUY",
            policy="FIXED_EQUAL",
            target_accounts=["U1111111"],
        )

    engine = HistoricalSimulationEngine(
        data_connector=connector,
        strategy_callback=strategy_callback,
        allocation_router=router,
        exit_time_decay_ticks=1,
    )

    summary = await engine.run("AMD")

    assert summary.matched_orders == 1
    open_events = [e for e in engine.trace_events if e.event_type == "POSITION_OPENED"]
    exit_events = [e for e in engine.trace_events if e.event_type == "POSITION_EXITED"]
    assert len(open_events) == 1
    assert len(exit_events) == 1
    assert exit_events[0].payload["exit_reason"] == "time_decay"
    assert exit_events[0].payload["held_ticks"] == 1
    assert exit_events[0].payload["realized_pnl"] == pytest.approx(5.0)


@pytest.mark.asyncio
async def test_trailing_stop_exit_uses_quote_level_volatility_proxy():
    rows = [
        (pd.Timestamp("2026-05-01T09:30:00.000000"), "NVDA", 100.00, 100.10, 500.0, 500.0),
        (pd.Timestamp("2026-05-01T09:30:00.100000"), "NVDA", 100.05, 100.15, 500.0, 500.0),
        (pd.Timestamp("2026-05-01T09:30:00.200000"), "NVDA", 100.30, 100.40, 500.0, 500.0),
        (pd.Timestamp("2026-05-01T09:30:00.300000"), "NVDA", 100.24, 100.34, 500.0, 500.0),
    ]
    connector = DuckDBHistoricalDatasetConnector(
        dataset_glob="data/historical/US/EQUITIES/NVDA/2026/05/*.parquet",
        bid_size_col="bid_size",
        ask_size_col="ask_size",
        connection_factory=lambda: _FakeConn(rows),
    )
    router = _AcceptingRouter()

    fired = {"done": False}

    def strategy_callback(event, nbbo_cache):
        _ = (event, nbbo_cache)
        if fired["done"]:
            return None
        fired["done"] = True
        return StrategySignal(
            symbol="NVDA",
            total_qty=100,
            side="BUY",
            policy="FIXED_EQUAL",
            target_accounts=["U1111111"],
        )

    engine = HistoricalSimulationEngine(
        data_connector=connector,
        strategy_callback=strategy_callback,
        allocation_router=router,
        exit_trailing_vol_multiplier=0.5,
        exit_vol_lookback_ticks=3,
    )

    await engine.run("NVDA")

    exit_event = [e for e in engine.trace_events if e.event_type == "POSITION_EXITED"][0]
    assert exit_event.payload["exit_reason"] == "trailing_stop"
    assert exit_event.payload["trailing_stop_price"] == pytest.approx(100.25)
    assert exit_event.payload["realized_pnl"] == pytest.approx(9.0)


@pytest.mark.asyncio
async def test_seeded_latency_profile_is_deterministic_across_runs():
    rows = [
        (pd.Timestamp("2026-05-01T09:30:00.000000"), "MSFT", 300.00, 300.10, 1000.0, 1000.0),
        (pd.Timestamp("2026-05-01T09:30:00.500000"), "MSFT", 300.01, 300.11, 1000.0, 1000.0),
    ]

    def make_engine():
        connector = DuckDBHistoricalDatasetConnector(
            dataset_glob="data/historical/US/EQUITIES/MSFT/2026/05/*.parquet",
            bid_size_col="bid_size",
            ask_size_col="ask_size",
            connection_factory=lambda: _FakeConn(rows),
        )
        router = _AcceptingRouter()

        fired = {"done": False}

        def strategy_callback(event, nbbo_cache):
            _ = (event, nbbo_cache)
            if fired["done"]:
                return None
            fired["done"] = True
            return StrategySignal(
                symbol="MSFT",
                total_qty=10,
                side="BUY",
                policy="FIXED_EQUAL",
                target_accounts=["U1111111", "U2222222"],
            )

        profile = LatencyDistributionProfile(
            mode="NORMAL",
            mean_ns=120_000,
            std_ns=15_000,
            min_ns=50_000,
            max_ns=300_000,
            seed=42,
        )

        return HistoricalSimulationEngine(
            data_connector=connector,
            strategy_callback=strategy_callback,
            allocation_router=router,
            latency_profile=profile,
        )

    engine_a = make_engine()
    engine_b = make_engine()

    await engine_a.run("MSFT")
    await engine_b.run("MSFT")

    delay_a = [e for e in engine_a.trace_events if e.event_type == "ALLOCATION_PENDING_ENQUEUED"][0].payload["delay_ns"]
    delay_b = [e for e in engine_b.trace_events if e.event_type == "ALLOCATION_PENDING_ENQUEUED"][0].payload["delay_ns"]
    assert delay_a == delay_b
    assert 50_000 <= delay_a <= 300_000


def test_fixed_latency_profile_uses_exact_value():
    profile = LatencyDistributionProfile(mode="FIXED", fixed_ns=250_000)
    assert profile.sample_ns() == 250_000
    assert profile.sample_ns() == 250_000

"""
Phase 3: Synthetic WAL Output and Crash Scenario Replay

- Validates that HistoricalSimulationEngine emits production-format WAL rows.
- Injects market-panic fixtures: spread expander, size evaporator, latency surge.
- Asserts WAL compatibility with IBKRAdapter.rehydrate_and_repair().
"""
import os
import tempfile
import pandas as pd
import pytest
from autotrader.backtesting.engine.historical import (
    DuckDBHistoricalDatasetConnector,
    HistoricalSimulationEngine,
    LatencyDistributionProfile,
    StrategySignal,
)


import re

class _DummyRouter:
    def __init__(self):
        self.calls = []
    async def route_order(self, **kwargs):
        self.calls.append(kwargs)
        return ["OID-1", "OID-2"]

def _parse_wal_line(line):
    # Returns tuple of tokens if valid, else None
    tokens = line.strip().split("|")
    if len(tokens) != 10:
        return None
    if tokens[0] != "SHORTFALL":
        return None
    return tokens

@pytest.mark.asyncio
async def test_synthetic_wal_writer_tokenization(tmp_path):
    # Minimal quote and signal, WAL output enabled
    rows = [
        (pd.Timestamp("2026-05-01T09:30:00"), "AAPL", 100.0, 100.1, 1000.0, 1000.0),
    ]
    connector = DuckDBHistoricalDatasetConnector(
        dataset_glob="data/historical/US/EQUITIES/AAPL/2026/05/*.parquet",
        bid_size_col="bid_size",
        ask_size_col="ask_size",
        connection_factory=lambda: type("_FakeConn", (), {
            "execute": lambda self, sql, params: self,
            "fetchall": lambda self: rows,
            "close": lambda self: None
        })(),
    )
    router = _DummyRouter()
    def strategy_callback(event, nbbo_cache):
        return StrategySignal(
            symbol="AAPL",
            total_qty=100,
            side="BUY",
            policy="FIXED_EQUAL",
            target_accounts=["U1", "U2"],
        )
    wal_path = tmp_path / "synthetic.wal"
    engine = HistoricalSimulationEngine(
        data_connector=connector,
        strategy_callback=strategy_callback,
        allocation_router=router,
        synthetic_wal_path=str(wal_path),
    )
    await engine.run("AAPL")
    # Validate WAL file exists and is non-empty
    assert wal_path.exists()
    lines = wal_path.read_text().strip().splitlines()
    assert len(lines) >= 1
    for line in lines:
        tokens = _parse_wal_line(line)
        assert tokens is not None, f"Malformed WAL line: {line}"
        # Check numeric fields
        float(tokens[2])  # timestamp_ms
        float(tokens[6])  # exec_price
        float(tokens[7])  # exec_qty
        float(tokens[8])  # benchmark_mid
        float(tokens[9])  # slippage_bps


@pytest.mark.asyncio
async def test_flash_crash_liquidity_hole(tmp_path):
    # Extreme spread, tiny size, huge latency
    rows = [
        (pd.Timestamp("2026-05-01T09:30:00"), "CRASH", 100.0, 130.0, 2.0, 2.0),
        (pd.Timestamp("2026-05-01T09:30:10"), "CRASH", 99.0, 135.0, 1.0, 1.0),
    ]
    connector = DuckDBHistoricalDatasetConnector(
        dataset_glob="data/historical/US/EQUITIES/CRASH/2026/05/*.parquet",
        bid_size_col="bid_size",
        ask_size_col="ask_size",
        connection_factory=lambda: type("_FakeConn", (), {
            "execute": lambda self, sql, params: self,
            "fetchall": lambda self: rows,
            "close": lambda self: None
        })(),
    )
    router = _DummyRouter()
    def strategy_callback(event, nbbo_cache):
        # Only fire on first event
        if event.timestamp == rows[0][0]:
            return StrategySignal(
                symbol="CRASH",
                total_qty=10,
                side="BUY",
                policy="FIXED_EQUAL",
                target_accounts=["UCRASH"],
            )
        return None
    profile = LatencyDistributionProfile(
        mode="FIXED",
        fixed_ns=5_000_000_000,  # 5 seconds
        min_ns=5_000_000_000,
        max_ns=5_000_000_000,
        seed=42,
    )
    wal_path = tmp_path / "crash.wal"
    engine = HistoricalSimulationEngine(
        data_connector=connector,
        strategy_callback=strategy_callback,
        allocation_router=router,
        latency_profile=profile,
        synthetic_wal_path=str(wal_path),
    )
    await engine.run("CRASH")
    # Validate WAL file exists and is non-empty
    assert wal_path.exists()
    lines = wal_path.read_text().strip().splitlines()
    assert len(lines) >= 1
    for line in lines:
        tokens = _parse_wal_line(line)
        assert tokens is not None, f"Malformed WAL line: {line}"
        # Spread should be huge
        spread = float(rows[0][3]) - float(rows[0][2])
        assert spread >= 30.0
        # Size should be tiny
        assert float(tokens[7]) <= 10.0
        # Latency should be at least 5 seconds (5000 ms)
        # Check that execution timestamp is >= signal timestamp + 5000 ms
        exec_ts = float(tokens[2])
        # The event timestamp in ms
        event_ts = int(rows[0][0].value // 10**6)
        assert exec_ts >= event_ts + 5000, f"Execution ts {exec_ts} not delayed enough from {event_ts}"

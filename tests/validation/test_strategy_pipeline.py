from __future__ import annotations

import pandas as pd

from autotrader.strategy.bars import TickToBarAggregator


def test_tick_to_bar_aggregator_does_not_emit_before_bar_close():
    aggregator = TickToBarAggregator(bar_frequency="1m")

    emitted = aggregator.update(
        symbol="EUR/USD",
        timestamp=pd.Timestamp("2024-10-21T12:00:10Z"),
        bid=1.0850,
        ask=1.0852,
        bid_size=100.0,
        ask_size=80.0,
    )

    assert emitted == []

    emitted = aggregator.update(
        symbol="EUR/USD",
        timestamp=pd.Timestamp("2024-10-21T12:00:50Z"),
        bid=1.0851,
        ask=1.0853,
        bid_size=120.0,
        ask_size=90.0,
    )

    assert emitted == []


def test_tick_to_bar_aggregator_emits_finalized_bar_on_boundary_cross():
    aggregator = TickToBarAggregator(bar_frequency="1m")

    aggregator.update(
        symbol="EUR/USD",
        timestamp=pd.Timestamp("2024-10-21T12:00:10Z"),
        bid=1.0850,
        ask=1.0852,
        bid_size=100.0,
        ask_size=80.0,
    )
    aggregator.update(
        symbol="EUR/USD",
        timestamp=pd.Timestamp("2024-10-21T12:00:50Z"),
        bid=1.0852,
        ask=1.0854,
        bid_size=140.0,
        ask_size=110.0,
    )

    emitted = aggregator.update(
        symbol="EUR/USD",
        timestamp=pd.Timestamp("2024-10-21T12:01:05Z"),
        bid=1.0853,
        ask=1.0855,
        bid_size=150.0,
        ask_size=120.0,
    )

    assert len(emitted) == 1
    bar = emitted[0]
    assert bar["bar_start_ts"] == pd.Timestamp("2024-10-21T12:00:00Z")
    assert bar["bar_end_ts"] == pd.Timestamp("2024-10-21T12:01:00Z")
    assert bar["open_bid"] == 1.0850
    assert bar["close_bid"] == 1.0852
    assert bar["high_ask"] == 1.0854
    assert bar["low_bid"] == 1.0850
    assert bar["tick_count"] == 2
    assert bar["empty_bar"] is False


def test_tick_to_bar_aggregator_emits_empty_gap_bars_without_future_leak():
    aggregator = TickToBarAggregator(bar_frequency="1m")

    aggregator.update(
        symbol="EUR/USD",
        timestamp=pd.Timestamp("2024-10-21T12:00:10Z"),
        bid=1.0850,
        ask=1.0852,
        bid_size=100.0,
        ask_size=80.0,
    )

    emitted = aggregator.update(
        symbol="EUR/USD",
        timestamp=pd.Timestamp("2024-10-21T12:03:05Z"),
        bid=1.0860,
        ask=1.0862,
        bid_size=150.0,
        ask_size=120.0,
    )

    assert [bar["bar_start_ts"] for bar in emitted] == [
        pd.Timestamp("2024-10-21T12:00:00Z"),
        pd.Timestamp("2024-10-21T12:01:00Z"),
        pd.Timestamp("2024-10-21T12:02:00Z"),
    ]

    first_gap_bar = emitted[1]
    second_gap_bar = emitted[2]
    assert first_gap_bar["empty_bar"] is True
    assert second_gap_bar["empty_bar"] is True
    assert first_gap_bar["tick_count"] == 0
    assert second_gap_bar["tick_count"] == 0
    assert first_gap_bar["close_bid"] == emitted[0]["close_bid"]
    assert second_gap_bar["close_bid"] == emitted[0]["close_bid"]
    assert second_gap_bar["bar_end_ts"] == pd.Timestamp("2024-10-21T12:03:00Z")


def test_tick_to_bar_aggregator_flushes_active_bar_only_on_explicit_flush():
    aggregator = TickToBarAggregator(bar_frequency="5m")

    aggregator.update(
        symbol="EUR/USD",
        timestamp=pd.Timestamp("2024-10-21T12:00:10Z"),
        bid=1.0850,
        ask=1.0852,
        bid_size=100.0,
        ask_size=80.0,
    )

    emitted = aggregator.flush("EUR/USD")

    assert len(emitted) == 1
    assert emitted[0]["bar_start_ts"] == pd.Timestamp("2024-10-21T12:00:00Z")
    assert emitted[0]["bar_end_ts"] == pd.Timestamp("2024-10-21T12:05:00Z")
from __future__ import annotations

import pandas as pd

from autotrader.execution.adapters import OrderSide
from autotrader.execution.oms import MockStructuralTrapDetector


def _bar(
    *,
    symbol: str,
    start: str,
    end: str,
    mid_low: float,
    mid_high: float,
    mid_close: float,
    volume_proxy: float,
) -> dict:
    return {
        "symbol": symbol,
        "bar_start_ts": pd.Timestamp(start),
        "bar_end_ts": pd.Timestamp(end),
        "mid_low": mid_low,
        "mid_high": mid_high,
        "mid_close": mid_close,
        "volume_proxy": volume_proxy,
    }


def test_mock_structural_trap_detector_emits_buy_signal_from_swing_failure():
    detector = MockStructuralTrapDetector(lookback_bars=3, min_breach_bps=5.0, total_size=2.0)
    bars = [
        _bar(symbol="BTCUSDT", start="2024-10-21T12:00:00Z", end="2024-10-21T12:01:00Z", mid_low=100.0, mid_high=101.0, mid_close=100.4, volume_proxy=100.0),
        _bar(symbol="BTCUSDT", start="2024-10-21T12:01:00Z", end="2024-10-21T12:02:00Z", mid_low=100.2, mid_high=101.2, mid_close=100.6, volume_proxy=110.0),
        _bar(symbol="BTCUSDT", start="2024-10-21T12:02:00Z", end="2024-10-21T12:03:00Z", mid_low=100.1, mid_high=101.1, mid_close=100.5, volume_proxy=90.0),
        _bar(symbol="BTCUSDT", start="2024-10-21T12:03:00Z", end="2024-10-21T12:04:00Z", mid_low=99.8, mid_high=100.9, mid_close=100.3, volume_proxy=250.0),
    ]

    signals = detector.detect(bars)

    assert len(signals) == 1
    signal = signals[0]
    assert signal.side == OrderSide.BUY
    assert signal.structural_price == 100.0
    assert signal.breach_price == 99.8
    assert signal.total_size == 2.0
    assert signal.liquidity_score > 2.0
    assert signal.node_density > 0.0


def test_mock_structural_trap_detector_emits_sell_signal_from_swing_failure():
    detector = MockStructuralTrapDetector(lookback_bars=3, min_breach_bps=5.0)
    bars = [
        _bar(symbol="BTCUSDT", start="2024-10-21T12:00:00Z", end="2024-10-21T12:01:00Z", mid_low=99.5, mid_high=100.0, mid_close=99.8, volume_proxy=100.0),
        _bar(symbol="BTCUSDT", start="2024-10-21T12:01:00Z", end="2024-10-21T12:02:00Z", mid_low=99.6, mid_high=100.2, mid_close=99.9, volume_proxy=105.0),
        _bar(symbol="BTCUSDT", start="2024-10-21T12:02:00Z", end="2024-10-21T12:03:00Z", mid_low=99.7, mid_high=100.1, mid_close=99.95, volume_proxy=110.0),
        _bar(symbol="BTCUSDT", start="2024-10-21T12:03:00Z", end="2024-10-21T12:04:00Z", mid_low=99.4, mid_high=100.4, mid_close=99.9, volume_proxy=220.0),
    ]

    signals = detector.detect(bars)

    assert len(signals) == 1
    signal = signals[0]
    assert signal.side == OrderSide.SELL
    assert signal.structural_price == 100.2
    assert signal.breach_price == 100.4
    assert signal.invalidation_price > signal.breach_price


def test_mock_structural_trap_detector_suppresses_duplicate_signal_for_same_bar():
    detector = MockStructuralTrapDetector(lookback_bars=3, min_breach_bps=5.0)
    bars = [
        _bar(symbol="BTCUSDT", start="2024-10-21T12:00:00Z", end="2024-10-21T12:01:00Z", mid_low=100.0, mid_high=101.0, mid_close=100.4, volume_proxy=100.0),
        _bar(symbol="BTCUSDT", start="2024-10-21T12:01:00Z", end="2024-10-21T12:02:00Z", mid_low=100.2, mid_high=101.2, mid_close=100.6, volume_proxy=110.0),
        _bar(symbol="BTCUSDT", start="2024-10-21T12:02:00Z", end="2024-10-21T12:03:00Z", mid_low=100.1, mid_high=101.1, mid_close=100.5, volume_proxy=90.0),
        _bar(symbol="BTCUSDT", start="2024-10-21T12:03:00Z", end="2024-10-21T12:04:00Z", mid_low=99.8, mid_high=100.9, mid_close=100.3, volume_proxy=250.0),
    ]

    first = detector.detect(bars)
    second = detector.detect(bars)

    assert len(first) == 1
    assert second == []


def test_mock_structural_trap_detector_requires_enough_history():
    detector = MockStructuralTrapDetector(lookback_bars=3)
    bars = [
        _bar(symbol="BTCUSDT", start="2024-10-21T12:00:00Z", end="2024-10-21T12:01:00Z", mid_low=100.0, mid_high=101.0, mid_close=100.4, volume_proxy=100.0),
        _bar(symbol="BTCUSDT", start="2024-10-21T12:01:00Z", end="2024-10-21T12:02:00Z", mid_low=100.2, mid_high=101.2, mid_close=100.6, volume_proxy=110.0),
    ]

    assert detector.detect(bars) == []
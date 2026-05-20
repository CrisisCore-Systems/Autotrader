from __future__ import annotations

import pytest

from autotrader.execution.oms import VolumeProfileDetector


def _bar(*, low: float, high: float, volume: float, close: float | None = None) -> dict:
    return {
        "symbol": "BTCUSDT",
        "mid_low": low,
        "mid_high": high,
        "mid_close": close if close is not None else (low + high) / 2.0,
        "volume_proxy": volume,
    }


def test_volume_profile_detector_allocates_single_bar_uniformly_across_touched_bins():
    detector = VolumeProfileDetector(bin_size=0.5, lookback_bars=5)

    profile = detector.build_profile([_bar(low=100.0, high=101.0, volume=9.0)])

    assert profile == pytest.approx({100.0: 3.0, 100.5: 3.0, 101.0: 3.0})


def test_volume_profile_detector_accumulates_across_multiple_bars():
    detector = VolumeProfileDetector(bin_size=0.5, lookback_bars=5)
    bars = [
        _bar(low=100.0, high=101.0, volume=9.0),
        _bar(low=100.5, high=101.0, volume=4.0),
    ]

    profile = detector.build_profile(bars)

    assert profile == pytest.approx({100.0: 3.0, 100.5: 5.0, 101.0: 5.0})


def test_volume_profile_detector_evicts_bars_outside_rolling_window():
    detector = VolumeProfileDetector(bin_size=0.5, lookback_bars=2)
    bars = [
        _bar(low=100.0, high=100.5, volume=4.0),
        _bar(low=100.5, high=101.0, volume=4.0),
        _bar(low=101.0, high=101.5, volume=4.0),
    ]

    profile = detector.build_profile(bars)

    assert profile == pytest.approx({100.5: 2.0, 101.0: 4.0, 101.5: 2.0})


def test_volume_profile_detector_includes_exact_bin_boundaries():
    detector = VolumeProfileDetector(bin_size=0.5, lookback_bars=5)

    profile = detector.build_profile([_bar(low=100.0, high=100.5, volume=4.0)])

    assert profile == pytest.approx({100.0: 2.0, 100.5: 2.0})


def test_volume_profile_detector_exports_sorted_profile_and_ranked_bins():
    detector = VolumeProfileDetector(bin_size=0.5, lookback_bars=5)
    bars = [
        _bar(low=100.0, high=101.0, volume=9.0),
        _bar(low=100.5, high=101.0, volume=4.0),
    ]

    detector.detect(bars)

    assert detector.export_profile() == [(100.0, 3.0), (100.5, 5.0), (101.0, 5.0)]
    assert detector.top_k_bins(2) == [(100.5, 5.0), (101.0, 5.0)]
    assert detector.bottom_k_bins(1) == [(100.0, 3.0)]


def test_volume_profile_detector_smooths_profile_with_centered_moving_average():
    detector = VolumeProfileDetector(bin_size=0.5, lookback_bars=10)
    bars = [
        _bar(low=100.0, high=100.0, volume=2.0),
        _bar(low=100.5, high=100.5, volume=8.0),
        _bar(low=101.0, high=101.0, volume=2.0),
        _bar(low=101.5, high=101.5, volume=8.0),
        _bar(low=102.0, high=102.0, volume=2.0),
    ]

    detector.detect(bars)

    assert detector.smoothed_profile(window_size=3) == pytest.approx(
        [(100.0, 5.0), (100.5, 4.0), (101.0, 6.0), (101.5, 4.0), (102.0, 5.0)]
    )


def test_volume_profile_detector_extracts_hvns_and_lvns_with_prominence_threshold():
    detector = VolumeProfileDetector(bin_size=0.5, lookback_bars=10)
    bars = [
        _bar(low=100.0, high=100.0, volume=1.0),
        _bar(low=100.5, high=100.5, volume=5.0),
        _bar(low=101.0, high=101.0, volume=1.0),
        _bar(low=101.5, high=101.5, volume=5.0),
        _bar(low=102.0, high=102.0, volume=1.0),
    ]

    nodes = detector.extract_nodes(bars, window_size=1, min_prominence=3.0)

    assert [(node.price_bin, node.volume, node.prominence) for node in nodes["hvns"]] == [
        (100.5, 5.0, 4.0),
        (101.5, 5.0, 4.0),
    ]
    assert [(node.price_bin, node.volume, node.prominence) for node in nodes["lvns"]] == [
        (101.0, 1.0, 4.0),
    ]


def test_volume_profile_detector_rejects_even_smoothing_window():
    detector = VolumeProfileDetector(bin_size=0.5, lookback_bars=5)

    with pytest.raises(ValueError, match="window_size must be odd"):
        detector.smoothed_profile(window_size=2)


def test_volume_profile_detector_point_of_control_uses_raw_profile_and_lower_price_tie_break():
    detector = VolumeProfileDetector(bin_size=0.5, lookback_bars=10)
    bars = [
        _bar(low=100.0, high=100.0, volume=5.0),
        _bar(low=100.5, high=100.5, volume=1.0),
        _bar(low=101.0, high=101.0, volume=5.0),
    ]

    detector.detect(bars)

    assert detector.point_of_control() == (100.0, 5.0)


def test_volume_profile_detector_value_area_expands_from_poc_by_higher_adjacent_volume():
    detector = VolumeProfileDetector(bin_size=0.5, lookback_bars=10)
    bars = [
        _bar(low=100.0, high=100.0, volume=1.0),
        _bar(low=100.5, high=100.5, volume=3.0),
        _bar(low=101.0, high=101.0, volume=5.0),
        _bar(low=101.5, high=101.5, volume=2.0),
        _bar(low=102.0, high=102.0, volume=1.0),
    ]

    value_area = detector.value_area(bars, value_area_pct=0.70)

    assert value_area is not None
    assert value_area.point_of_control == 101.0
    assert value_area.value_area_low == 100.5
    assert value_area.value_area_high == 101.5
    assert value_area.covered_volume == pytest.approx(10.0)


def test_volume_profile_detector_value_area_uses_lower_price_tie_break_on_equal_adjacency():
    detector = VolumeProfileDetector(bin_size=0.5, lookback_bars=10)
    bars = [
        _bar(low=100.0, high=100.0, volume=1.0),
        _bar(low=100.5, high=100.5, volume=2.0),
        _bar(low=101.0, high=101.0, volume=5.0),
        _bar(low=101.5, high=101.5, volume=2.0),
        _bar(low=102.0, high=102.0, volume=1.0),
    ]

    value_area = detector.value_area(bars, value_area_pct=0.60)

    assert value_area is not None
    assert value_area.value_area_low == 100.5
    assert value_area.value_area_high == 101.0


def test_volume_profile_detector_rejects_invalid_value_area_pct():
    detector = VolumeProfileDetector(bin_size=0.5, lookback_bars=5)

    with pytest.raises(ValueError, match=r"value_area_pct must be in the interval \(0, 1\]"):
        detector.value_area(value_area_pct=0.0)


def test_volume_profile_detector_extracts_long_value_edge_rejection_zone_after_breach_and_reentry():
    detector = VolumeProfileDetector(bin_size=1.0, lookback_bars=6)
    bars = [
        _bar(low=100.0, high=100.0, close=100.0, volume=4.0),
        _bar(low=101.0, high=101.0, close=101.0, volume=4.0),
        _bar(low=102.0, high=102.0, close=102.0, volume=4.0),
        _bar(low=103.0, high=103.0, close=103.0, volume=4.0),
        _bar(low=99.0, high=100.0, close=99.5, volume=2.0),
        _bar(low=100.0, high=101.0, close=100.5, volume=2.0),
    ]

    zones = detector.extract_zones(bars)

    assert [(zone.zone_kind, zone.directional_bias) for zone in zones] == [
        ("value_edge_rejection", "long_reversion"),
    ]
    assert zones[0].reference_price == pytest.approx(100.0)
    assert zones[0].source_levels["value_area_low"] == pytest.approx(100.0)


def test_volume_profile_detector_extracts_short_value_edge_rejection_zone_after_breach_and_reentry():
    detector = VolumeProfileDetector(bin_size=1.0, lookback_bars=6)
    bars = [
        _bar(low=100.0, high=100.0, close=100.0, volume=4.0),
        _bar(low=101.0, high=101.0, close=101.0, volume=4.0),
        _bar(low=102.0, high=102.0, close=102.0, volume=4.0),
        _bar(low=103.0, high=103.0, close=103.0, volume=4.0),
        _bar(low=103.0, high=104.0, close=103.5, volume=2.0),
        _bar(low=102.0, high=103.0, close=102.5, volume=2.0),
    ]

    zones = detector.extract_zones(bars)

    assert [(zone.zone_kind, zone.directional_bias) for zone in zones] == [
        ("value_edge_rejection", "short_reversion"),
    ]
    assert zones[0].reference_price == pytest.approx(103.0)
    assert zones[0].source_levels["value_area_high"] == pytest.approx(103.0)


def test_volume_profile_detector_does_not_create_value_edge_zone_on_touch_without_breach():
    detector = VolumeProfileDetector(bin_size=1.0, lookback_bars=6)
    bars = [
        _bar(low=100.0, high=100.0, close=100.0, volume=4.0),
        _bar(low=101.0, high=101.0, close=101.0, volume=4.0),
        _bar(low=102.0, high=102.0, close=102.0, volume=4.0),
        _bar(low=103.0, high=103.0, close=103.0, volume=4.0),
        _bar(low=100.0, high=100.5, close=100.25, volume=2.0),
        _bar(low=100.25, high=101.0, close=100.75, volume=2.0),
    ]

    zones = detector.extract_zones(bars)

    assert zones == []


def test_volume_profile_detector_extracts_long_poc_reversion_zone_after_rotation_toward_poc():
    detector = VolumeProfileDetector(bin_size=1.0, lookback_bars=6, min_poc_reversion_distance_bps=50.0)
    bars = [
        _bar(low=101.0, high=101.0, close=101.0, volume=3.0),
        _bar(low=102.0, high=102.0, close=102.0, volume=6.0),
        _bar(low=103.0, high=103.0, close=103.0, volume=3.0),
        _bar(low=104.0, high=104.0, close=104.0, volume=1.0),
        _bar(low=101.0, high=101.0, close=101.0, volume=1.0),
        _bar(low=101.0, high=102.0, close=101.8, volume=1.0),
    ]

    zones = detector.extract_zones(bars)

    assert [(zone.zone_kind, zone.directional_bias) for zone in zones] == [
        ("poc_reversion", "long_reversion"),
    ]
    assert zones[0].reference_price == pytest.approx(102.0)
    assert zones[0].metadata["distance_from_poc_bps"] > 50.0


def test_volume_profile_detector_rejects_poc_reversion_when_displacement_is_too_small():
    detector = VolumeProfileDetector(bin_size=1.0, lookback_bars=6, min_poc_reversion_distance_bps=50.0)
    bars = [
        _bar(low=100.0, high=100.0, close=100.0, volume=3.0),
        _bar(low=101.0, high=101.0, close=101.0, volume=6.0),
        _bar(low=102.0, high=102.0, close=102.0, volume=3.0),
        _bar(low=103.0, high=103.0, close=103.0, volume=1.0),
        _bar(low=100.8, high=101.0, close=100.95, volume=1.0),
        _bar(low=100.9, high=101.1, close=101.0, volume=1.0),
    ]

    zones = detector.extract_zones(bars)

    assert zones == []


def test_volume_profile_detector_detect_remains_non_emitting_after_zone_extraction():
    detector = VolumeProfileDetector(bin_size=1.0, lookback_bars=6)
    bars = [
        _bar(low=100.0, high=100.0, close=100.0, volume=4.0),
        _bar(low=101.0, high=101.0, close=101.0, volume=4.0),
        _bar(low=102.0, high=102.0, close=102.0, volume=4.0),
        _bar(low=103.0, high=103.0, close=103.0, volume=4.0),
        _bar(low=99.0, high=100.0, close=99.5, volume=2.0),
        _bar(low=100.0, high=101.0, close=100.5, volume=2.0),
    ]

    assert detector.detect(bars) == []
    assert [(zone.zone_kind, zone.directional_bias) for zone in detector.export_zones()] == [
        ("value_edge_rejection", "long_reversion"),
    ]
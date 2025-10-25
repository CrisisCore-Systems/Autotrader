"""
Contract tests for feature extraction.

Ensures API stability and prevents schema drift:
- Feature names remain stable (no accidental renames)
- Return types are consistent
- Feature counts match expectations
- No duplicate feature names
"""

import pytest
import pandas as pd
import numpy as np

from autotrader.data_prep.features import (
    TechnicalFeatureExtractor,
    RollingFeatureExtractor,
    TemporalFeatureExtractor,
    FeatureFactory,
    FeatureConfig
)


def test_technical_feature_names(bars_1h_100):
    """Technical extractor produces exactly 7 features with stable names."""
    extractor = TechnicalFeatureExtractor()
    features = extractor.extract_all(bars_1h_100)
    
    expected_names = [
        "rsi",
        "macd_line",
        "macd_signal",
        "macd_histogram",
        "bb_upper_pct",
        "bb_lower_pct",
        "atr"
    ]
    
    assert list(features.columns) == expected_names
    assert len(features.columns) == 7


def test_rolling_feature_names_default():
    """Rolling extractor with default windows produces 18 features."""
    extractor = RollingFeatureExtractor()  # Default: [20, 50, 200]
    
    expected_count = 3 * 6  # 3 windows × 6 features per window
    expected_names = extractor.get_feature_names()
    
    assert len(expected_names) == expected_count
    
    # Check naming pattern
    for window in [20, 50, 200]:
        assert f"roll_{window}_log_return" in expected_names
        assert f"roll_{window}_volatility" in expected_names
        assert f"roll_{window}_zscore" in expected_names


def test_rolling_feature_names_custom():
    """Rolling extractor respects custom window configuration."""
    extractor = RollingFeatureExtractor(windows=[10, 30])
    
    expected_count = 2 * 6  # 2 windows × 6 features
    expected_names = extractor.get_feature_names()
    
    assert len(expected_names) == expected_count
    assert "roll_10_log_return" in expected_names
    assert "roll_30_log_return" in expected_names
    assert "roll_50_log_return" not in expected_names  # Not in custom config


def test_temporal_feature_names(bars_1h_100):
    """Temporal extractor produces exactly 11 features."""
    extractor = TemporalFeatureExtractor()
    features = extractor.extract_all(bars_1h_100)
    
    expected_names = [
        "hour_sin",
        "hour_cos",
        "minute_sin",
        "minute_cos",
        "day_of_week_sin",
        "day_of_week_cos",
        "is_market_open",
        "is_morning",
        "is_afternoon",
        "is_close",
        "is_weekend"
    ]
    
    assert list(features.columns) == expected_names
    assert len(features.columns) == 11


def test_feature_factory_return_type(bars_1h_100):
    """FeatureFactory always returns a DataFrame."""
    factory = FeatureFactory()
    features = factory.extract_all(bars_1h_100)
    
    assert isinstance(features, pd.DataFrame)
    assert len(features) == len(bars_1h_100)


def test_feature_factory_balanced_preset(bars_1h_100):
    """Balanced preset produces expected feature count."""
    config = FeatureConfig.balanced()
    factory = FeatureFactory(config=config)
    
    features = factory.extract_all(bars_1h_100)
    
    # Technical: 7
    # Rolling (3 windows): 18
    # Temporal: 11
    # Total: 36
    assert len(features.columns) == 36


def test_feature_factory_conservative_preset(bars_1h_100):
    """Conservative preset uses fewer features (longer windows)."""
    config = FeatureConfig.conservative()
    factory = FeatureFactory(config=config)
    
    features = factory.extract_all(bars_1h_100)
    
    # Technical: 7
    # Rolling (2 windows: 50, 200): 12
    # Temporal: 11
    # Total: 30
    assert len(features.columns) == 30


def test_feature_factory_aggressive_preset(bars_1h_100):
    """Aggressive preset uses more features (shorter windows)."""
    config = FeatureConfig.aggressive()
    factory = FeatureFactory(config=config)
    
    features = factory.extract_all(bars_1h_100)
    
    # Technical: 7
    # Rolling (3 windows: 10, 20, 50): 18
    # Temporal: 11
    # Total: 36
    assert len(features.columns) == 36


def test_no_duplicate_feature_names(bars_1h_100):
    """FeatureFactory produces no duplicate feature names."""
    factory = FeatureFactory()
    features = factory.extract_all(bars_1h_100)
    
    feature_names = list(features.columns)
    unique_names = set(feature_names)
    
    assert len(feature_names) == len(unique_names)


def test_feature_names_deterministic(bars_1h_100):
    """Feature names are deterministic (same config → same names)."""
    config = FeatureConfig.balanced()
    
    factory1 = FeatureFactory(config=config)
    features1 = factory1.extract_all(bars_1h_100)
    
    factory2 = FeatureFactory(config=config)
    features2 = factory2.extract_all(bars_1h_100)
    
    assert list(features1.columns) == list(features2.columns)


def test_index_alignment(bars_1h_100):
    """Features preserve input DataFrame index."""
    factory = FeatureFactory()
    features = factory.extract_all(bars_1h_100)
    
    assert features.index.equals(bars_1h_100.index)


def test_config_serialization():
    """FeatureConfig can be serialized to dict."""
    config = FeatureConfig.balanced()
    
    config_dict = {
        "enable_technical": config.enable_technical,
        "enable_rolling": config.enable_rolling,
        "rolling_windows": config.rolling_windows,
        "rsi_period": config.rsi_period
    }
    
    # Should not raise
    assert isinstance(config_dict, dict)
    assert config_dict["enable_technical"] is True


def test_selective_extractors():
    """FeatureFactory respects extractor enable flags."""
    # Only technical features
    config = FeatureConfig(
        enable_technical=True,
        enable_rolling=False,
        enable_temporal=False
    )
    factory = FeatureFactory(config=config)
    
    feature_names = factory.get_feature_names()
    
    assert len(feature_names) == 7  # Only technical
    assert "rsi" in feature_names
    assert "roll_20_log_return" not in feature_names
    assert "hour_sin" not in feature_names

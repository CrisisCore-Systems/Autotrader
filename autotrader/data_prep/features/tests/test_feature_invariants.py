"""
Invariant tests for feature extraction.

Validates mathematical properties and constraints:
- Features are finite (no inf/NaN in valid regions)
- Features respect expected ranges (e.g., RSI in [0, 100])
- NaN handling is consistent
- Features respond correctly to input changes
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


def test_rsi_range(bars_1h_100):
    """RSI values are in [0, 100] range."""
    extractor = TechnicalFeatureExtractor()
    features = extractor.extract_all(bars_1h_100)
    
    rsi = features["rsi"].dropna()
    
    assert (rsi >= 0).all()
    assert (rsi <= 100).all()


def test_bollinger_bands_range(bars_1h_100):
    """Bollinger Band percentiles are in [0, 1] range."""
    extractor = TechnicalFeatureExtractor()
    features = extractor.extract_all(bars_1h_100)
    
    bb_upper = features["bb_upper_pct"].dropna()
    bb_lower = features["bb_lower_pct"].dropna()
    
    assert (bb_upper >= 0).all()
    assert (bb_upper <= 1).all()
    assert (bb_lower >= 0).all()
    assert (bb_lower <= 1).all()


def test_atr_non_negative(bars_1h_100):
    """ATR is always non-negative."""
    extractor = TechnicalFeatureExtractor()
    features = extractor.extract_all(bars_1h_100)
    
    atr = features["atr"].dropna()
    
    assert (atr >= 0).all()


def test_percentile_rank_range(bars_1h_100):
    """Percentile ranks are in [0, 1] range."""
    extractor = RollingFeatureExtractor(windows=[20])
    features = extractor.extract_all(bars_1h_100)
    
    percentile = features["roll_20_percentile"].dropna()
    
    assert (percentile >= 0).all()
    assert (percentile <= 1).all()


def test_volatility_non_negative(bars_1h_100):
    """Volatility is always non-negative."""
    extractor = RollingFeatureExtractor(windows=[20, 50])
    features = extractor.extract_all(bars_1h_100)
    
    vol_20 = features["roll_20_volatility"].dropna()
    vol_50 = features["roll_50_volatility"].dropna()
    
    assert (vol_20 >= 0).all()
    assert (vol_50 >= 0).all()


def test_parkinson_volatility_non_negative(bars_1h_100):
    """Parkinson volatility is always non-negative."""
    extractor = RollingFeatureExtractor(windows=[20])
    features = extractor.extract_all(bars_1h_100)
    
    parkinson_vol = features["roll_20_parkinson_vol"].dropna()
    
    assert (parkinson_vol >= 0).all()


def test_temporal_cyclical_range(bars_1h_100):
    """Cyclical temporal features are in [-1, 1] range."""
    extractor = TemporalFeatureExtractor()
    features = extractor.extract_all(bars_1h_100)
    
    cyclical_features = [
        "hour_sin", "hour_cos",
        "minute_sin", "minute_cos",
        "day_of_week_sin", "day_of_week_cos"
    ]
    
    for feature in cyclical_features:
        values = features[feature]
        assert (values >= -1).all()
        assert (values <= 1).all()


def test_temporal_binary_range(bars_1h_100):
    """Binary temporal features are in {0, 1}."""
    extractor = TemporalFeatureExtractor()
    features = extractor.extract_all(bars_1h_100)
    
    binary_features = [
        "is_market_open",
        "is_morning",
        "is_afternoon",
        "is_close",
        "is_weekend"
    ]
    
    for feature in binary_features:
        values = features[feature].unique()
        assert set(values).issubset({0.0, 1.0})


def test_no_inf_values(bars_1h_100):
    """No features produce inf values on valid data."""
    factory = FeatureFactory()
    features = factory.extract_all(bars_1h_100)
    
    # After forward fill, no inf should remain
    assert not np.isinf(features).any().any()


def test_forward_fill_reduces_nans(bars_with_gaps):
    """Forward fill reduces NaN count."""
    config = FeatureConfig(fill_method="forward")
    factory = FeatureFactory(config=config)
    
    features = factory.extract_all(bars_with_gaps)
    
    # Should have NaNs only at the start (before min_periods)
    # Not throughout the entire DataFrame
    nan_pct = features.isna().mean().mean()
    assert nan_pct < 0.5  # Less than 50% NaN overall


def test_zero_fill_eliminates_nans(bars_1h_100):
    """Zero fill eliminates all NaN values."""
    config = FeatureConfig(fill_method="zero")
    factory = FeatureFactory(config=config)
    
    features = factory.extract_all(bars_1h_100)
    
    # No NaN should remain
    assert not features.isna().any().any()


def test_flat_prices_no_crash(bars_flat):
    """Feature extraction doesn't crash on flat prices (edge case)."""
    factory = FeatureFactory()
    
    # Should not raise division by zero or other errors
    features = factory.extract_all(bars_flat)
    
    assert isinstance(features, pd.DataFrame)
    assert len(features) == len(bars_flat)


def test_high_volatility_stability(bars_volatile):
    """Features remain finite under high volatility."""
    factory = FeatureFactory()
    features = factory.extract_all(bars_volatile)
    
    # Check all features are finite (after forward fill)
    for col in features.columns:
        valid_values = features[col].dropna()
        if len(valid_values) > 0:
            assert np.isfinite(valid_values).all(), f"Feature {col} has non-finite values"


def test_rsi_responds_to_trend(bars_1h_100):
    """RSI increases on uptrend."""
    extractor = TechnicalFeatureExtractor(rsi_period=14)
    features = extractor.extract_all(bars_1h_100)
    
    # bars_1h_100 has upward drift
    rsi = features["rsi"].dropna()
    
    # RSI should be mostly above 50 (bullish)
    median_rsi = rsi.median()
    assert median_rsi > 45  # Allow some variance


def test_volatility_increases_with_variance():
    """Higher price variance → higher volatility."""
    np.random.seed(42)
    
    # Low volatility bars
    low_vol_prices = 100 + np.cumsum(np.random.normal(0, 0.001, 100))
    low_vol_bars = pd.DataFrame({
        "timestamp_utc": pd.date_range("2024-01-01", periods=100, freq="1h"),
        "open": low_vol_prices,
        "high": low_vol_prices * 1.001,
        "low": low_vol_prices * 0.999,
        "close": low_vol_prices,
        "volume": [1000] * 100
    })
    
    # High volatility bars
    high_vol_prices = 100 + np.cumsum(np.random.normal(0, 0.05, 100))
    high_vol_bars = pd.DataFrame({
        "timestamp_utc": pd.date_range("2024-01-01", periods=100, freq="1h"),
        "open": high_vol_prices,
        "high": high_vol_prices * 1.01,
        "low": high_vol_prices * 0.99,
        "close": high_vol_prices,
        "volume": [1000] * 100
    })
    
    extractor = RollingFeatureExtractor(windows=[20])
    
    low_vol_features = extractor.extract_all(low_vol_bars)
    high_vol_features = extractor.extract_all(high_vol_bars)
    
    low_vol_median = low_vol_features["roll_20_volatility"].dropna().median()
    high_vol_median = high_vol_features["roll_20_volatility"].dropna().median()
    
    assert high_vol_median > low_vol_median * 2  # Significantly higher


def test_zscore_standardization(bars_1h_100):
    """Z-scores are centered around zero."""
    extractor = RollingFeatureExtractor(windows=[50])
    features = extractor.extract_all(bars_1h_100)
    
    zscore = features["roll_50_zscore"].dropna()
    
    # Mean should be close to 0
    mean_zscore = zscore.mean()
    assert abs(mean_zscore) < 0.5  # Within reasonable tolerance

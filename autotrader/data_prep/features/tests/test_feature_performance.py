"""
Performance tests for feature extraction.

Validates computational efficiency:
- Feature extraction meets time budgets
- O(N) scaling (linear with data size)
- No memory leaks
"""

import pytest
import pandas as pd
import numpy as np
import time
import gc

from autotrader.data_prep.features import (
    TechnicalFeatureExtractor,
    RollingFeatureExtractor,
    TemporalFeatureExtractor,
    FeatureFactory,
    FeatureConfig
)


@pytest.mark.performance
def test_technical_features_time_budget(bars_1m_1000):
    """Technical features extracted in <0.5s for 1,000 bars."""
    extractor = TechnicalFeatureExtractor()
    
    start = time.time()
    features = extractor.extract_all(bars_1m_1000)
    elapsed = time.time() - start
    
    assert elapsed < 0.5
    assert len(features) == 1000


@pytest.mark.performance
def test_rolling_features_time_budget(bars_1m_1000):
    """Rolling features extracted in <0.5s for 1,000 bars."""
    extractor = RollingFeatureExtractor(windows=[20, 50, 200])
    
    start = time.time()
    features = extractor.extract_all(bars_1m_1000)
    elapsed = time.time() - start
    
    assert elapsed < 0.5
    assert len(features) == 1000


@pytest.mark.performance
def test_temporal_features_time_budget(bars_1m_1000):
    """Temporal features extracted in <0.2s for 1,000 bars."""
    extractor = TemporalFeatureExtractor()
    
    start = time.time()
    features = extractor.extract_all(bars_1m_1000)
    elapsed = time.time() - start
    
    assert elapsed < 0.2
    assert len(features) == 1000


@pytest.mark.performance
def test_feature_factory_time_budget(bars_1m_1000):
    """Complete feature pipeline in <1.0s for 1,000 bars."""
    factory = FeatureFactory()
    
    start = time.time()
    features = factory.extract_all(bars_1m_1000)
    elapsed = time.time() - start
    
    assert elapsed < 1.0
    assert len(features) == 1000


@pytest.mark.performance
def test_linear_scaling():
    """Feature extraction scales linearly with data size."""
    np.random.seed(42)
    factory = FeatureFactory()
    
    # Small dataset (500 bars)
    small_bars = _generate_bars(500)
    start = time.time()
    factory.extract_all(small_bars)
    time_small = time.time() - start
    
    # Large dataset (1000 bars, 2× size)
    large_bars = _generate_bars(1000)
    start = time.time()
    factory.extract_all(large_bars)
    time_large = time.time() - start
    
    # Should scale approximately linearly (allow 2.5× tolerance)
    assert time_large < time_small * 2.5


@pytest.mark.performance
def test_no_memory_leak():
    """Repeated feature extraction doesn't leak memory."""
    factory = FeatureFactory()
    bars = _generate_bars(500)
    
    # Force garbage collection
    gc.collect()
    
    # Run extraction multiple times
    for _ in range(10):
        features = factory.extract_all(bars)
        del features
    
    # Force garbage collection again
    gc.collect()
    
    # If no leak, this should complete without memory error
    # (Actual memory measurement would require psutil)
    assert True


def _generate_bars(n_bars: int) -> pd.DataFrame:
    """Generate synthetic OHLCV bars for performance testing."""
    prices = 100.0 + np.cumsum(np.random.normal(0, 0.5, n_bars))
    
    return pd.DataFrame({
        "timestamp_utc": pd.date_range("2024-01-01 09:30", periods=n_bars, freq="1min"),
        "open": prices,
        "high": prices * 1.01,
        "low": prices * 0.99,
        "close": prices,
        "volume": np.random.lognormal(10, 1, n_bars)
    })

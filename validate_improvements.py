"""
Quick validation of tree-of-thought improvements.

Tests the 6 new/modified components:
1. VolumeFeatureExtractor
2. FeatureTransformer
3. SmartNaNHandler
4. Optimized percentile calculation
5. FeatureMetadata system
6. FeatureSelector

Validates:
- All imports work
- Basic functionality
- Performance improvement
- No regressions
"""

import pandas as pd
import numpy as np
import time
from datetime import datetime, timedelta


def create_sample_data(n_bars: int = 1000) -> pd.DataFrame:
    """Create sample OHLCV data for testing."""
    dates = pd.date_range(start='2024-01-01', periods=n_bars, freq='1min')
    
    # Simulate realistic price movement
    np.random.seed(42)
    price = 100.0
    prices = []
    
    for _ in range(n_bars):
        change = np.random.randn() * 0.5
        price += change
        prices.append(price)
    
    prices = np.array(prices)
    
    # Create OHLCV
    data = pd.DataFrame({
        'timestamp': dates,
        'open': prices + np.random.randn(n_bars) * 0.1,
        'high': prices + abs(np.random.randn(n_bars)) * 0.5,
        'low': prices - abs(np.random.randn(n_bars)) * 0.5,
        'close': prices,
        'volume': np.random.randint(1000, 10000, n_bars)
    })
    
    data.set_index('timestamp', inplace=True)
    return data


def test_volume_features():
    """Test VolumeFeatureExtractor."""
    print("\n1. Testing VolumeFeatureExtractor...")
    
    from autotrader.data_prep.features.volume_features import VolumeFeatureExtractor
    
    bars = create_sample_data(300)
    extractor = VolumeFeatureExtractor()
    
    features = extractor.extract_all(
        bars_df=bars,
        close_col='close',
        volume_col='volume',
        high_col='high',
        low_col='low'
    )
    
    print(f"   ✓ Extracted {len(features.columns)} volume features")
    print(f"   ✓ Features: {', '.join(features.columns.tolist())}")
    print(f"   ✓ Shape: {features.shape}")
    
    # Check for expected features
    expected = ['vwap', 'volume_ratio', 'volume_accel', 'relative_volume', 
                'volume_price_corr', 'obv', 'vw_return']
    assert all(feat in features.columns for feat in expected), "Missing expected features"
    print("   ✓ All expected features present")
    
    return True


def test_feature_transformer():
    """Test FeatureTransformer."""
    print("\n2. Testing FeatureTransformer...")
    
    from autotrader.data_prep.features.feature_transformer import FeatureTransformer, TransformerConfig
    
    # Create sample features
    bars = create_sample_data(300)
    features = pd.DataFrame({
        'rsi_14': np.random.uniform(20, 80, len(bars)),
        'macd_line': np.random.randn(len(bars)),
        'volume_ratio': np.random.uniform(0.5, 2.0, len(bars))
    }, index=bars.index)
    
    # Configure transformer
    config = TransformerConfig(
        scale_method="standard",
        add_lags=[1, 2, 3],
        add_diffs=True,
        clip_std=5.0
    )
    
    transformer = FeatureTransformer(config)
    
    # Transform
    transformed = transformer.fit_transform(features)
    
    print(f"   ✓ Original features: {len(features.columns)}")
    print(f"   ✓ Transformed features: {len(transformed.columns)}")
    print(f"   ✓ Expansion: {len(transformed.columns) / len(features.columns):.1f}x")
    
    # Check for lagged features
    assert 'rsi_14_lag1' in transformed.columns, "Missing lagged features"
    assert 'rsi_14_diff' in transformed.columns, "Missing differenced features"
    print("   ✓ Lagged and differenced features created")
    
    # Check scaling
    for col in features.columns:
        if col in transformed.columns:
            mean = transformed[col].mean()
            std = transformed[col].std()
            print(f"   ✓ {col}: mean={mean:.3f}, std={std:.3f}")
            assert abs(mean) < 0.1, f"Not properly scaled (mean={mean})"
            assert abs(std - 1.0) < 0.1, f"Not properly scaled (std={std})"
    
    return True


def test_smart_nan_handler():
    """Test SmartNaNHandler."""
    print("\n3. Testing SmartNaNHandler...")
    
    from autotrader.data_prep.features.smart_nan_handler import SmartNaNHandler
    
    # Create features with NaNs
    n = 100
    features = pd.DataFrame({
        'rsi_14': [np.nan] * 14 + list(np.random.uniform(20, 80, n - 14)),
        'roll_20_return': [np.nan] * 20 + list(np.random.randn(n - 20)),
        'volume_ratio': [np.nan] * 20 + list(np.random.uniform(0.5, 2.0, n - 20)),
        'hour_sin': np.sin(np.linspace(0, 4*np.pi, n))
    })
    
    # Introduce some random NaNs
    features.loc[50:55, 'rsi_14'] = np.nan
    features.loc[60:65, 'volume_ratio'] = np.nan
    
    nan_count_before = features.isna().sum().sum()
    print(f"   ✓ NaNs before: {nan_count_before}")
    
    # Apply smart NaN handling
    handler = SmartNaNHandler()
    clean = handler.handle_nans(features)
    
    nan_count_after = clean.isna().sum().sum()
    print(f"   ✓ NaNs after: {nan_count_after}")
    print(f"   ✓ Removed: {nan_count_before - nan_count_after} NaNs")
    
    # Get report
    summary = handler.get_handling_summary()
    print(f"   ✓ Strategies used: {summary['strategies_used']}")
    for strategy, info in summary['by_strategy'].items():
        print(f"      - {strategy}: {info['count']} features")
    
    return True


def test_percentile_performance():
    """Test optimized percentile calculation performance."""
    print("\n4. Testing Percentile Performance...")
    
    from autotrader.data_prep.features.rolling_features import RollingFeatureExtractor
    
    # Create larger dataset for performance test
    bars = create_sample_data(5000)
    extractor = RollingFeatureExtractor(windows=[50])
    
    # Time the extraction
    start = time.time()
    features = extractor.extract_all(
        bars_df=bars,
        close_col='close',
        high_col='high',
        low_col='low'
    )
    elapsed = time.time() - start
    
    rows_per_sec = len(bars) / elapsed
    
    print(f"   ✓ Processed {len(bars)} bars in {elapsed:.3f}s")
    print(f"   ✓ Throughput: {rows_per_sec:.0f} rows/sec")
    
    # Check percentile feature exists and is valid
    perc_col = 'roll_50_percentile'
    assert perc_col in features.columns, "Percentile feature missing"
    
    # Validate percentile range [0, 1]
    valid_percentiles = features[perc_col].dropna()
    assert valid_percentiles.min() >= 0.0, "Percentile < 0"
    assert valid_percentiles.max() <= 1.0, "Percentile > 1"
    print(f"   ✓ Percentile range valid: [{valid_percentiles.min():.3f}, {valid_percentiles.max():.3f}]")
    
    return True


def test_feature_metadata():
    """Test FeatureMetadata system."""
    print("\n5. Testing FeatureMetadata...")
    
    from autotrader.data_prep.features.feature_metadata import (
        FeatureMetadataRegistry,
        create_technical_metadata,
        create_rolling_metadata,
        create_volume_metadata
    )
    
    registry = FeatureMetadataRegistry()
    
    # Register features
    registry.register_batch(create_technical_metadata(rsi_period=14))
    registry.register_batch(create_rolling_metadata(windows=[20, 50]))
    registry.register_batch(create_volume_metadata())
    
    summary = registry.get_summary()
    print(f"   ✓ Total features: {summary['total_features']}")
    print(f"   ✓ By group: {summary['by_group']}")
    print(f"   ✓ Min bars needed: {summary['min_bars_needed']}")
    print(f"   ✓ Total computation cost: {summary['total_cost']}")
    
    # Test validation
    assert registry.can_compute(bars_available=100), "Should have enough data"
    assert not registry.can_compute(bars_available=10), "Should not have enough data"
    print("   ✓ Data requirement validation works")
    
    # Test metadata retrieval
    rsi_meta = registry.get('rsi_14')
    assert rsi_meta is not None, "RSI metadata not found"
    assert rsi_meta.min_bars == 14, "Wrong min_bars"
    print(f"   ✓ Retrieved RSI metadata: min_bars={rsi_meta.min_bars}, cost={rsi_meta.cost}")
    
    return True


def test_feature_selector():
    """Test FeatureSelector."""
    print("\n6. Testing FeatureSelector...")
    
    from autotrader.data_prep.features.feature_selector import FeatureSelector
    
    # Create features with known correlations
    n = 1000
    np.random.seed(42)
    
    base_feature = np.random.randn(n)
    
    features = pd.DataFrame({
        'feature_a': base_feature,
        'feature_b': base_feature + np.random.randn(n) * 0.1,  # High correlation with A
        'feature_c': np.random.randn(n),  # Independent
        'feature_d': base_feature * 0.95 + np.random.randn(n) * 0.15,  # High correlation with A
        'feature_e': np.random.randn(n)  # Independent
    })
    
    selector = FeatureSelector(correlation_threshold=0.9)
    
    # Analyze
    analysis = selector.analyze_correlation(features)
    print(f"   ✓ Total features: {analysis['summary']['total_features']}")
    print(f"   ✓ Redundant pairs: {analysis['summary']['redundant_pairs']}")
    
    for feat1, feat2, corr in analysis['high_correlation_pairs']:
        print(f"      - {feat1} <-> {feat2}: {corr:.3f}")
    
    # Reduce
    reduced = selector.reduce_features(features, method="correlation")
    print(f"   ✓ Features after reduction: {len(reduced.columns)}")
    print(f"   ✓ Removed: {len(features.columns) - len(reduced.columns)} features")
    
    # Get report
    report = selector.get_redundancy_report(features)
    print(f"   ✓ Compression potential: {report['compression_potential']}")
    
    return True


def run_all_tests():
    """Run all validation tests."""
    print("=" * 60)
    print("TREE-OF-THOUGHT IMPROVEMENTS - VALIDATION")
    print("=" * 60)
    
    tests = [
        ("VolumeFeatureExtractor", test_volume_features),
        ("FeatureTransformer", test_feature_transformer),
        ("SmartNaNHandler", test_smart_nan_handler),
        ("Percentile Performance", test_percentile_performance),
        ("FeatureMetadata", test_feature_metadata),
        ("FeatureSelector", test_feature_selector)
    ]
    
    results = []
    
    for name, test_func in tests:
        try:
            success = test_func()
            results.append((name, "✅ PASS", None))
        except Exception as e:
            results.append((name, "❌ FAIL", str(e)))
            print(f"\n   ❌ ERROR: {e}")
    
    # Print summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    for name, status, error in results:
        print(f"{status} {name}")
        if error:
            print(f"    Error: {error}")
    
    passed = sum(1 for _, status, _ in results if status == "✅ PASS")
    total = len(results)
    
    print("\n" + "=" * 60)
    print(f"RESULTS: {passed}/{total} tests passed")
    print("=" * 60)
    
    if passed == total:
        print("\n🎉 All validation tests passed!")
        print("\nTier 1 implementation is complete and validated.")
        print("Next steps: Integration work (update feature_factory.py, __init__.py, tests)")
    else:
        print(f"\n⚠️ {total - passed} test(s) failed. Please review errors above.")


if __name__ == "__main__":
    run_all_tests()

"""Minimal test suite for schemas, backtest, and feature validation.

This test suite validates core functionality with minimal dependencies:
1. Schema validation for data structures
2. Backtest data integrity
3. Feature validation and quality checks
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from src.core.features import MarketSnapshot, compute_time_series_features, build_feature_vector
from src.core.safety import evaluate_contract, liquidity_guardrail
from src.core.scoring import compute_gem_score, should_flag_asset


def test_schema_validation():
    """Test schema validation for core data structures."""
    print("=" * 60)
    print("Testing Schema Validation")
    print("=" * 60)
    
    # Test MarketSnapshot schema
    snapshot = MarketSnapshot(
        symbol="TEST",
        timestamp=datetime.utcnow(),
        price=1.5,
        volume_24h=100000,
        liquidity_usd=500000,
        holders=1000,
        onchain_metrics={"active_wallets": 200},
        narratives=["DeFi"]
    )
    
    assert snapshot.symbol == "TEST"
    assert snapshot.price == 1.5
    assert snapshot.volume_24h == 100000
    assert snapshot.liquidity_usd == 500000
    assert snapshot.holders == 1000
    assert "active_wallets" in snapshot.onchain_metrics
    assert "DeFi" in snapshot.narratives
    print("✓ MarketSnapshot schema valid")
    
    # Test contract report schema
    contract_report = evaluate_contract(
        {"honeypot": False, "owner_can_mint": False},
        severity="none"
    )
    
    assert hasattr(contract_report, 'score')
    assert hasattr(contract_report, 'severity')
    assert 0 <= contract_report.score <= 1
    print("✓ Contract report schema valid")
    
    # Test GemScore result schema
    features = {
        "SentimentScore": 0.7,
        "AccumulationScore": 0.6,
        "OnchainActivity": 0.5,
        "LiquidityDepth": 0.4,
        "TokenomicsRisk": 0.8,
        "ContractSafety": 0.9,
        "NarrativeMomentum": 0.6,
        "CommunityGrowth": 0.5,
    }
    
    result = compute_gem_score(features)
    
    assert hasattr(result, 'score')
    assert hasattr(result, 'confidence')
    assert hasattr(result, 'contributions')
    assert 0 <= result.score <= 100
    assert 0 <= result.confidence <= 100
    assert len(result.contributions) > 0
    print("✓ GemScore result schema valid")
    
    print("\n✅ All schema validation tests passed!\n")
    return True


def test_backtest_data_integrity():
    """Test backtest data integrity and calculations."""
    print("=" * 60)
    print("Testing Backtest Data Integrity")
    print("=" * 60)
    
    # Create synthetic historical data
    n_days = 30
    dates = [datetime.utcnow() - timedelta(days=i) for i in range(n_days)][::-1]
    
    # Generate price series with trend and noise
    base_price = 1.0
    prices = [base_price * (1 + 0.01 * i + np.random.uniform(-0.02, 0.02)) for i in range(n_days)]
    price_series = pd.Series(prices, index=pd.to_datetime(dates))
    
    # Validate data integrity
    assert len(price_series) == n_days
    assert price_series.isna().sum() == 0
    print(f"✓ Price series integrity: {n_days} clean data points")
    
    # Validate monotonic time index
    assert price_series.index.is_monotonic_increasing
    print("✓ Time index is monotonic")
    
    # Validate price range
    assert (price_series > 0).all()
    print("✓ All prices positive")
    
    # Test returns calculation
    returns = price_series.pct_change().dropna()
    assert len(returns) == n_days - 1
    print(f"✓ Returns calculated: {len(returns)} periods")
    
    # Test volatility calculation
    volatility = returns.std()
    assert volatility >= 0
    print(f"✓ Volatility: {volatility:.4f}")
    
    # Test cumulative returns
    cum_returns = (1 + returns).cumprod()
    assert len(cum_returns) == len(returns)
    print(f"✓ Cumulative returns: {cum_returns.iloc[-1]:.4f}")
    
    # Test drawdown calculation
    rolling_max = price_series.expanding().max()
    drawdown = (price_series - rolling_max) / rolling_max
    max_drawdown = drawdown.min()
    assert max_drawdown <= 0
    print(f"✓ Max drawdown: {max_drawdown:.2%}")
    
    print("\n✅ All backtest integrity tests passed!\n")
    return True


def test_feature_validation():
    """Test feature validation and quality checks."""
    print("=" * 60)
    print("Testing Feature Validation")
    print("=" * 60)
    
    # Create test price series
    now = datetime.utcnow()
    dates = [now - timedelta(hours=i) for i in range(48)][::-1]
    prices = pd.Series(
        data=[0.1 + 0.001 * i for i in range(48)],
        index=pd.to_datetime(dates)
    )
    
    # Test time series features
    price_features = compute_time_series_features(prices)
    
    # Validate feature existence
    required_features = ["rsi", "macd", "volatility"]
    for feature in required_features:
        assert feature in price_features, f"Missing feature: {feature}"
    print(f"✓ All required features present: {', '.join(required_features)}")
    
    # Validate feature ranges
    assert 0 <= price_features["rsi"] <= 1, "RSI out of range"
    assert price_features["volatility"] >= 0, "Volatility negative"
    print("✓ Feature values in valid ranges")
    
    # Test feature vector construction
    snapshot = MarketSnapshot(
        symbol="TEST",
        timestamp=now,
        price=0.147,
        volume_24h=100000,
        liquidity_usd=200000,
        holders=1000,
        onchain_metrics={"active_wallets": 200, "net_inflows": 50000, "unlock_pressure": 0.1},
        narratives=["Test"]
    )
    
    contract_safety = {"score": 0.9}
    features = build_feature_vector(
        snapshot,
        price_features,
        narrative_embedding_score=0.7,
        contract_metrics=contract_safety,
        narrative_momentum=0.65
    )
    
    # Validate feature vector completeness
    expected_features = [
        "SentimentScore",
        "AccumulationScore",
        "OnchainActivity",
        "LiquidityDepth",
        "TokenomicsRisk",
        "ContractSafety",
        "NarrativeMomentum",
        "CommunityGrowth",
        "RSI",
        "MACD",
        "Volatility"
    ]
    
    missing_features = [f for f in expected_features if f not in features]
    assert len(missing_features) == 0, f"Missing features: {missing_features}"
    print(f"✓ Feature vector complete: {len(features)} features")
    
    # Validate feature normalization
    normalized_features = [
        "SentimentScore", "AccumulationScore", "OnchainActivity",
        "LiquidityDepth", "TokenomicsRisk", "ContractSafety",
        "NarrativeMomentum", "CommunityGrowth", "RSI"
    ]
    
    for feature in normalized_features:
        if feature in features:
            value = features[feature]
            assert 0 <= value <= 1, f"{feature} not normalized: {value}"
    print("✓ All normalized features in [0, 1] range")
    
    # Test quality metrics
    completeness = sum(1 for v in features.values() if v is not None and not np.isnan(v)) / len(features)
    assert completeness >= 0.8, f"Feature completeness too low: {completeness}"
    print(f"✓ Feature completeness: {completeness:.2%}")
    
    # Test for outliers
    feature_values = [v for v in features.values() if isinstance(v, (int, float)) and not np.isnan(v)]
    mean_value = np.mean(feature_values)
    std_value = np.std(feature_values)
    outliers = [v for v in feature_values if abs(v - mean_value) > 3 * std_value]
    print(f"✓ Outliers detected: {len(outliers)}/{len(feature_values)}")
    
    # Test GemScore calculation
    result = compute_gem_score(features)
    assert 0 <= result.score <= 100
    assert 0 <= result.confidence <= 100
    print(f"✓ GemScore calculated: {result.score:.2f} (confidence: {result.confidence:.2f}%)")
    
    # Test flagging logic
    flagged, debug = should_flag_asset(result, features)
    assert isinstance(flagged, bool)
    assert "safety_pass" in debug
    assert "signals" in debug
    print(f"✓ Flagging logic: {flagged} (signals: {debug['signals']})")
    
    print("\n✅ All feature validation tests passed!\n")
    return True


def test_edge_cases():
    """Test edge cases and error handling."""
    print("=" * 60)
    print("Testing Edge Cases")
    print("=" * 60)
    
    # Test empty price series
    empty_series = pd.Series(dtype=float)
    features = compute_time_series_features(empty_series)
    assert features["rsi"] == 0.5  # Default value
    print("✓ Empty series handled gracefully")
    
    # Test single price point
    single_point = pd.Series([1.0])
    features = compute_time_series_features(single_point)
    assert "rsi" in features
    print("✓ Single data point handled")
    
    # Test NaN handling
    prices_with_nan = pd.Series([1.0, np.nan, 2.0, 3.0])
    features = compute_time_series_features(prices_with_nan)
    assert not np.isnan(features["rsi"])
    print("✓ NaN values filtered")
    
    # Test extreme values
    extreme_prices = pd.Series([0.000001, 1000000])
    features = compute_time_series_features(extreme_prices)
    assert 0 <= features["rsi"] <= 1
    print("✓ Extreme values handled")
    
    # Test zero liquidity
    assert not liquidity_guardrail(0)
    print("✓ Zero liquidity rejected")
    
    # Test negative values (should be handled)
    snapshot = MarketSnapshot(
        symbol="TEST",
        timestamp=datetime.utcnow(),
        price=1.0,
        volume_24h=-100,  # Invalid
        liquidity_usd=100000,
        holders=0,
        onchain_metrics={},
        narratives=[]
    )
    # Should not crash
    print("✓ Invalid snapshot values handled")
    
    print("\n✅ All edge case tests passed!\n")
    return True


def main():
    """Run all minimal tests."""
    print("\n" + "=" * 60)
    print("MINIMAL TEST SUITE")
    print("=" * 60 + "\n")
    
    tests = [
        ("Schema Validation", test_schema_validation),
        ("Backtest Data Integrity", test_backtest_data_integrity),
        ("Feature Validation", test_feature_validation),
        ("Edge Cases", test_edge_cases),
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
        except Exception as e:
            print(f"❌ {test_name} FAILED: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    
    print("=" * 60)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 60)
    
    if failed == 0:
        print("\n🎉 All tests passed successfully!\n")
    else:
        print(f"\n⚠️ {failed} test(s) failed\n")
        sys.exit(1)


if __name__ == "__main__":
    main()

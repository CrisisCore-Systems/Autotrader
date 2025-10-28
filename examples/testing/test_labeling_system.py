"""
Test script for cost-aware labeling system.

Tests classification and regression labeling with horizon optimization
on synthetic and real bar data.
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Add project to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from autotrader.data_prep.labeling import (
    CostModel,
    ClassificationLabeler,
    RegressionLabeler,
    HorizonOptimizer,
    LabelFactory,
)


def create_synthetic_bars(n_bars: int = 1000, seed: int = 42) -> pd.DataFrame:
    """
    Create synthetic bar data with realistic properties.
    
    Simulates trending + mean-reverting behavior with bid/ask spread.
    """
    np.random.seed(seed)
    
    # Generate timestamps (1-minute bars)
    start_time = datetime(2024, 1, 1, 9, 30)
    timestamps = [start_time + timedelta(minutes=i) for i in range(n_bars)]
    
    # Generate price series with trend + noise
    trend = np.linspace(0, 10, n_bars)  # 10 bps trend over period
    noise = np.random.randn(n_bars) * 5  # 5 bps volatility
    mid_price = 1.0800 + (trend + noise) / 10_000  # Start at 1.0800
    
    # Generate bid/ask with spread
    spread_bps = 1.0  # 1 bps spread
    bid = mid_price - spread_bps / 2 / 10_000
    ask = mid_price + spread_bps / 2 / 10_000
    
    # Close price (alternates between bid and ask)
    close = np.where(np.random.rand(n_bars) > 0.5, bid, ask)
    
    # Generate volumes (with some variation)
    volume = np.random.randint(100_000, 500_000, n_bars)
    bid_volume = volume * np.random.uniform(0.4, 0.6, n_bars)
    ask_volume = volume - bid_volume
    
    # OHLC
    high = mid_price + np.abs(np.random.randn(n_bars)) * 3 / 10_000
    low = mid_price - np.abs(np.random.randn(n_bars)) * 3 / 10_000
    open_price = mid_price + np.random.randn(n_bars) * 2 / 10_000
    
    bars = pd.DataFrame({
        "timestamp": timestamps,
        "open": open_price,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
        "bid": bid,
        "ask": ask,
        "bid_volume": bid_volume,
        "ask_volume": ask_volume,
    })
    
    return bars


def test_classification_labeling():
    """Test cost-aware classification labeling."""
    print("\n" + "="*100)
    print("TEST 1: CLASSIFICATION LABELING")
    print("="*100)
    
    # Create synthetic data
    bars = create_synthetic_bars(n_bars=500)
    print(f"\nCreated {len(bars)} synthetic bars")
    print(f"Price range: {bars['close'].min():.5f} - {bars['close'].max():.5f}")
    
    # Create cost model
    cost_model = CostModel(
        maker_fee=0.02,
        taker_fee=0.04,
        spread_cost=0.5,
        slippage_bps=0.5,
        min_profit_bps=1.0,
    )
    
    print(f"\nCost model:")
    print(f"  Round-trip (maker): {cost_model.round_trip_cost_bps(is_maker=True):.2f} bps")
    print(f"  Profitable threshold (maker): {cost_model.profitable_threshold_bps(is_maker=True):.2f} bps")
    
    # Create labeler
    labeler = ClassificationLabeler(
        cost_model=cost_model,
        horizon_seconds=60,
        is_maker=True,
        use_microprice=True,
    )
    
    # Generate labels
    print("\nGenerating labels...")
    labeled_data = labeler.generate_labels(bars)
    
    # Get statistics
    stats = labeler.get_label_statistics(labeled_data)
    
    print(f"\nLabel distribution:")
    print(f"  BUY (+1): {stats['label_distribution']['buy_count']} ({stats['label_distribution']['buy_pct']:.1f}%)")
    print(f"  SELL (-1): {stats['label_distribution']['sell_count']} ({stats['label_distribution']['sell_pct']:.1f}%)")
    print(f"  HOLD (0): {stats['label_distribution']['hold_count']} ({stats['label_distribution']['hold_pct']:.1f}%)")
    
    print(f"\nPerformance:")
    print(f"  Buy hit rate: {stats['performance']['buy_hit_rate']:.2f}%")
    print(f"  Sell hit rate: {stats['performance']['sell_hit_rate']:.2f}%")
    print(f"  Overall hit rate: {stats['performance']['overall_hit_rate']:.2f}%")
    
    print(f"\nReturn statistics:")
    print(f"  Mean return: {stats['return_statistics']['mean_return_bps']:.2f} bps")
    print(f"  Std return: {stats['return_statistics']['std_return_bps']:.2f} bps")
    
    # Validate
    assert len(labeled_data) == len(bars), "Label count mismatch"
    assert "label" in labeled_data.columns, "Missing label column"
    assert labeled_data["label"].isin([-1, 0, 1]).all(), "Invalid label values"
    
    print("\n✓ Classification labeling test PASSED")


def test_regression_labeling():
    """Test regression labeling with microprice returns."""
    print("\n" + "="*100)
    print("TEST 2: REGRESSION LABELING")
    print("="*100)
    
    # Create synthetic data
    bars = create_synthetic_bars(n_bars=500)
    print(f"\nCreated {len(bars)} synthetic bars")
    
    # Create cost model
    cost_model = CostModel(
        maker_fee=0.02,
        taker_fee=0.04,
        spread_cost=0.5,
        slippage_bps=0.5,
        min_profit_bps=1.0,
    )
    
    # Create labeler
    labeler = RegressionLabeler(
        cost_model=cost_model,
        horizon_seconds=60,
        clip_percentiles=(5.0, 95.0),
        subtract_costs=True,
        use_microprice=True,
    )
    
    # Generate labels
    print("\nGenerating labels...")
    labeled_data = labeler.generate_labels(bars)
    
    # Get statistics
    stats = labeler.get_label_statistics(labeled_data)
    
    print(f"\nLabel statistics:")
    print(f"  Mean: {stats['label_statistics']['mean']:.2f} bps")
    print(f"  Std: {stats['label_statistics']['std']:.2f} bps")
    print(f"  Min: {stats['label_statistics']['min']:.2f} bps")
    print(f"  Max: {stats['label_statistics']['max']:.2f} bps")
    print(f"  Median: {stats['label_statistics']['median']:.2f} bps")
    
    print(f"\nClipping impact:")
    print(f"  Clipped at lower bound: {stats['clipping_impact']['pct_clipped_lower']:.2f}%")
    print(f"  Clipped at upper bound: {stats['clipping_impact']['pct_clipped_upper']:.2f}%")
    
    print(f"\nCost adjustment:")
    print(f"  Mean cost impact: {stats['cost_adjustment']['mean_cost_impact_bps']:.2f} bps")
    
    print(f"\nPerformance:")
    print(f"  Sharpe ratio: {stats['performance']['sharpe_ratio_annual']:.2f}")
    print(f"  Information ratio: {stats['performance']['information_ratio']:.4f}")
    
    print(f"\nDirection distribution:")
    print(f"  Positive: {stats['direction_distribution']['positive_pct']:.1f}%")
    print(f"  Negative: {stats['direction_distribution']['negative_pct']:.1f}%")
    print(f"  Zero: {stats['direction_distribution']['zero_pct']:.1f}%")
    
    # Validate
    assert len(labeled_data) == len(bars), "Label count mismatch"
    assert "label" in labeled_data.columns, "Missing label column"
    assert labeled_data["label"].notna().sum() > 0, "No valid labels"
    
    print("\n✓ Regression labeling test PASSED")


def test_horizon_optimization():
    """Test horizon optimization with grid search."""
    print("\n" + "="*100)
    print("TEST 3: HORIZON OPTIMIZATION")
    print("="*100)
    
    # Create synthetic data (more bars for optimization)
    bars = create_synthetic_bars(n_bars=1000)
    print(f"\nCreated {len(bars)} synthetic bars for optimization")
    
    # Create optimizer
    optimizer = HorizonOptimizer(
        horizons_seconds=[10, 30, 60, 120, 180],  # Shorter grid for testing
        labeling_method="classification",
        max_participation_rate=0.02,
    )
    
    # Run optimization
    best_result, all_results, results_df = optimizer.optimize(
        bars,
        symbol="TEST/USD",
    )
    
    # Generate report
    print("\n" + "="*100)
    report = optimizer.generate_report(results_df, "TEST/USD")
    print(report)
    
    # Validate
    assert len(all_results) > 0, "No optimization results"
    assert best_result.information_ratio > 0, "Invalid information ratio"
    assert len(results_df) == len(all_results), "Results DataFrame mismatch"
    
    print("\n✓ Horizon optimization test PASSED")


def test_label_factory():
    """Test unified label factory interface."""
    print("\n" + "="*100)
    print("TEST 4: LABEL FACTORY")
    print("="*100)
    
    # Create synthetic data
    bars = create_synthetic_bars(n_bars=300)
    print(f"\nCreated {len(bars)} synthetic bars")
    
    # Test classification
    print("\nGenerating classification labels via factory...")
    class_labels = LabelFactory.create(
        bars,
        method="classification",
        horizon_seconds=60,
    )
    
    print(f"  Generated {len(class_labels)} classification labels")
    print(f"  Label distribution: {class_labels['label'].value_counts().to_dict()}")
    
    # Test regression
    print("\nGenerating regression labels via factory...")
    reg_labels = LabelFactory.create(
        bars,
        method="regression",
        horizon_seconds=60,
    )
    
    print(f"  Generated {len(reg_labels)} regression labels")
    print(f"  Mean label: {reg_labels['label'].mean():.2f} bps")
    print(f"  Std label: {reg_labels['label'].std():.2f} bps")
    
    # Test statistics
    print("\nGetting statistics via factory...")
    stats = LabelFactory.get_statistics(class_labels, method="classification")
    print(f"  Overall hit rate: {stats['performance']['overall_hit_rate']:.2f}%")
    
    # Validate
    assert len(class_labels) == len(bars), "Classification label count mismatch"
    assert len(reg_labels) == len(bars), "Regression label count mismatch"
    assert "label" in class_labels.columns, "Missing label column (classification)"
    assert "label" in reg_labels.columns, "Missing label column (regression)"
    
    print("\n✓ Label factory test PASSED")


def main():
    """Run all labeling tests."""
    print("\n" + "="*100)
    print("COST-AWARE LABELING TEST SUITE")
    print("="*100)
    print(f"Start time: {datetime.now()}")
    
    try:
        # Run tests
        test_classification_labeling()
        test_regression_labeling()
        test_horizon_optimization()
        test_label_factory()
        
        # Summary
        print("\n" + "="*100)
        print("ALL TESTS PASSED ✓")
        print("="*100)
        print(f"End time: {datetime.now()}")
        
        print("\nSummary:")
        print("  ✓ Classification labeling: Cost-aware {-1, 0, +1} labels")
        print("  ✓ Regression labeling: Microprice returns with robust clipping")
        print("  ✓ Horizon optimization: Grid search for optimal prediction window")
        print("  ✓ Label factory: Unified API for all labeling methods")
        print("\nLabeling system ready for production use!")
        
    except Exception as e:
        print(f"\n✗ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

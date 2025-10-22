"""Example demonstrating extended backtest metrics and time-sliced evaluation.

This example shows how to use:
1. ROC/AUC and PR curve metrics for classification performance
2. Time-sliced evaluation for temporal performance analysis
3. Experiment configuration for reproducibility
"""

from __future__ import annotations

import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dataclasses import dataclass
from typing import Dict
import numpy as np
import pandas as pd

from backtest.extended_metrics import (
    calculate_classification_metrics,
    calculate_extended_metrics,
)


@dataclass
class TokenSnapshot:
    """Token snapshot for backtest evaluation."""
    
    token: str
    date: pd.Timestamp
    features: Dict[str, float]
    future_return_7d: float


def create_sample_data_single_period() -> list[TokenSnapshot]:
    """Create sample data for a single period."""
    snapshots = []
    
    # Create 20 token snapshots with varying performance
    tokens = ["TOKEN" + str(i) for i in range(20)]
    base_date = pd.Timestamp("2024-01-15")
    
    np.random.seed(42)
    
    for i, token in enumerate(tokens):
        # Create features
        features = {
            "MarketCap": np.random.uniform(1_000_000, 10_000_000),
            "PriceChange7d": np.random.uniform(-0.2, 0.3),
            "Volume24h": np.random.uniform(100_000, 1_000_000),
        }
        
        # Future return correlated with features but with noise
        future_return = (
            0.02 * features["PriceChange7d"] + 
            np.random.normal(0, 0.05)
        )
        
        snapshot = TokenSnapshot(
            token=token,
            date=base_date,
            features=features,
            future_return_7d=future_return,
        )
        snapshots.append(snapshot)
    
    return snapshots


def create_sample_data_multiple_periods() -> list[TokenSnapshot]:
    """Create sample data across multiple time periods."""
    snapshots = []
    
    # Create 4 months of data
    for month in range(1, 5):
        base_date = pd.Timestamp(f"2024-{month:02d}-15")
        
        # Create 10 snapshots per month
        for i in range(10):
            token = f"TOKEN{i}"
            
            features = {
                "MarketCap": np.random.uniform(1_000_000, 10_000_000),
                "PriceChange7d": np.random.uniform(-0.2, 0.3),
                "Volume24h": np.random.uniform(100_000, 1_000_000),
            }
            
            # Add some temporal variation
            trend = 0.01 * month
            future_return = (
                0.02 * features["PriceChange7d"] + 
                trend +
                np.random.normal(0, 0.05)
            )
            
            snapshot = TokenSnapshot(
                token=token,
                date=base_date + pd.Timedelta(days=i),
                features=features,
                future_return_7d=future_return,
            )
            snapshots.append(snapshot)
    
    return snapshots


def example_1_classification_metrics():
    """Example 1: ROC/AUC and PR curve metrics."""
    print("=" * 70)
    print("EXAMPLE 1: Classification Metrics (ROC/AUC, PR Curves)")
    print("=" * 70)
    print()
    
    # Create sample data
    snapshots = create_sample_data_single_period()
    
    # Generate predictions (scores for each token)
    np.random.seed(42)
    predictions = np.array([
        snap.features["PriceChange7d"] + np.random.normal(0, 0.1)
        for snap in snapshots
    ])
    
    # Calculate classification metrics
    actuals = np.array([snap.future_return_7d for snap in snapshots])
    metrics = calculate_classification_metrics(predictions, actuals)
    
    print("Classification Performance:")
    print(f"  ROC AUC:           {metrics.roc_auc:.4f}")
    print(f"  PR AUC:            {metrics.pr_auc:.4f}")
    print(f"  Baseline Accuracy: {metrics.baseline_accuracy:.2%}")
    print(f"  Sample Size:       {metrics.sample_size}")
    print()
    
    print("Interpretation:")
    if metrics.roc_auc > 0.7:
        print("  ✅ Strong classification performance (ROC AUC > 0.7)")
    elif metrics.roc_auc > 0.6:
        print("  ⚠️  Moderate classification performance (0.6 < ROC AUC < 0.7)")
    elif metrics.roc_auc > 0.5:
        print("  ⚠️  Weak classification performance (0.5 < ROC AUC < 0.6)")
    else:
        print("  ❌ Poor classification performance (ROC AUC < 0.5)")
    
    print()
    print("ROC Curve Summary:")
    print(f"  FPR range: [{metrics.roc_curve_fpr.min():.3f}, {metrics.roc_curve_fpr.max():.3f}]")
    print(f"  TPR range: [{metrics.roc_curve_tpr.min():.3f}, {metrics.roc_curve_tpr.max():.3f}]")
    print(f"  Points:    {len(metrics.roc_curve_fpr)}")
    print()


def example_2_extended_metrics_with_classification():
    """Example 2: Full extended metrics including classification."""
    print("=" * 70)
    print("EXAMPLE 2: Extended Metrics with Classification")
    print("=" * 70)
    print()
    
    snapshots = create_sample_data_single_period()
    
    # Generate predictions
    np.random.seed(42)
    predictions = np.array([
        snap.features["PriceChange7d"] + np.random.normal(0, 0.1)
        for snap in snapshots
    ])
    
    # Calculate all extended metrics including classification
    metrics = calculate_extended_metrics(
        snapshots=snapshots,
        predictions=predictions,
        top_k=10,
        include_classification=True,
    )
    
    # Display summary
    print(metrics.summary_string())
    print()


def example_3_experiment_reproducibility():
    """Example 3: Experiment configuration for reproducibility."""
    print("=" * 70)
    print("EXAMPLE 3: Experiment Configuration for Reproducibility")
    print("=" * 70)
    print()
    
    # Demonstrate config structure without importing full harness
    config_dict = {
        'top_k': 10,
        'compare_baselines': True,
        'extended_metrics': True,
        'seed': 42,
        'data_path': '/path/to/backtest_data.csv',
        'timestamp': datetime.now().isoformat(),
    }
    
    print("Experiment Configuration:")
    for key, value in config_dict.items():
        print(f"  {key}: {value}")
    print()
    
    # Demonstrate result structure with config
    result_dict = {
        'precision_at_k': 0.7,
        'average_return_at_k': 0.05,
        'flagged_assets': ['TOKEN1', 'TOKEN2', 'TOKEN3'],
        'config': config_dict,
    }
    
    # Export to JSON for reproducibility
    import json
    json_str = json.dumps(result_dict, indent=2)
    
    print("JSON Export:")
    print(json_str)
    print()
    
    print("✅ Configuration stored with results for full reproducibility")
    print()
    print("The experiment config includes:")
    print("  - All hyperparameters (top_k, seed, etc.)")
    print("  - Data source path")
    print("  - Timestamp for tracking")
    print("  - Feature flags (baselines, extended metrics)")
    print()


def example_4_time_sliced_concept():
    """Example 4: Time-sliced evaluation concept."""
    print("=" * 70)
    print("EXAMPLE 4: Time-Sliced Evaluation Concept")
    print("=" * 70)
    print()
    
    snapshots = create_sample_data_multiple_periods()
    
    print(f"Total snapshots: {len(snapshots)}")
    print(f"Date range: {min(s.date for s in snapshots)} to {max(s.date for s in snapshots)}")
    print()
    
    # Group by month
    df = pd.DataFrame([
        {'date': s.date, 'token': s.token, 'return': s.future_return_7d}
        for s in snapshots
    ])
    df['month'] = df['date'].dt.to_period('M')
    
    print("Per-Month Statistics:")
    for month, group in df.groupby('month'):
        mean_return = group['return'].mean()
        std_return = group['return'].std()
        positive_pct = (group['return'] > 0).mean()
        
        print(f"\n  {month}:")
        print(f"    Snapshots:     {len(group)}")
        print(f"    Mean Return:   {mean_return:.4f}")
        print(f"    Std Return:    {std_return:.4f}")
        print(f"    Positive Rate: {positive_pct:.2%}")
    
    print()
    print("📊 Time-sliced evaluation helps identify:")
    print("   - Temporal performance trends")
    print("   - Regime changes in market conditions")
    print("   - Stability of prediction performance")
    print()
    
    print("To use time-sliced evaluation in the harness:")
    print("  python backtest/harness.py data.csv --time-sliced --slice-by month")
    print()


def example_5_comparison_with_without_classification():
    """Example 5: Compare metrics with and without classification."""
    print("=" * 70)
    print("EXAMPLE 5: Metrics Comparison (With vs Without Classification)")
    print("=" * 70)
    print()
    
    snapshots = create_sample_data_single_period()
    
    np.random.seed(42)
    predictions = np.array([
        snap.features["PriceChange7d"] + np.random.normal(0, 0.1)
        for snap in snapshots
    ])
    
    # Calculate without classification
    metrics_without = calculate_extended_metrics(
        snapshots=snapshots,
        predictions=predictions,
        include_classification=False,
    )
    
    # Calculate with classification
    metrics_with = calculate_extended_metrics(
        snapshots=snapshots,
        predictions=predictions,
        include_classification=True,
    )
    
    print("Standard Metrics (always included):")
    print(f"  IC (Pearson):    {metrics_with.ic_metrics.ic_pearson:.4f}")
    print(f"  Sharpe Ratio:    {metrics_with.risk_metrics.sharpe_ratio:.4f}")
    print(f"  Sortino Ratio:   {metrics_with.risk_metrics.sortino_ratio:.4f}")
    print()
    
    print("Classification Metrics (optional):")
    if metrics_with.classification_metrics:
        print(f"  ROC AUC:         {metrics_with.classification_metrics.roc_auc:.4f}")
        print(f"  PR AUC:          {metrics_with.classification_metrics.pr_auc:.4f}")
    print()
    
    print("When to use classification metrics:")
    print("  ✅ When treating returns as binary outcome (positive/negative)")
    print("  ✅ When comparing against classification-based models")
    print("  ✅ When visualizing ROC/PR curves for model selection")
    print()


def main():
    """Run all examples."""
    print()
    print("╔" + "═" * 68 + "╗")
    print("║" + " " * 12 + "EXTENDED BACKTEST METRICS EXAMPLES" + " " * 22 + "║")
    print("╚" + "═" * 68 + "╝")
    print()
    
    # Run examples
    example_1_classification_metrics()
    print()
    
    example_2_extended_metrics_with_classification()
    print()
    
    example_3_experiment_reproducibility()
    print()
    
    example_4_time_sliced_concept()
    print()
    
    example_5_comparison_with_without_classification()
    print()
    
    print("=" * 70)
    print("All examples completed successfully!")
    print()
    print("Next steps:")
    print("  1. Run harness with --extended-metrics to get IC and risk metrics")
    print("  2. Add --time-sliced to enable temporal evaluation")
    print("  3. Use --json-output to save results with full config")
    print("=" * 70)


if __name__ == "__main__":
    main()

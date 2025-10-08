"""Example usage of baseline strategy comparators.

This script demonstrates how to use baseline strategies to evaluate
GemScore performance in backtests.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dataclasses import dataclass
from typing import Dict

from backtest.baseline_strategies import (
    BaselineResult,
    CapWeightedStrategy,
    RandomStrategy,
    SimpleMomentumStrategy,
    compare_to_baselines,
    evaluate_all_baselines,
    format_baseline_comparison,
)


@dataclass
class TokenSnapshot:
    """Token snapshot for baseline evaluation."""
    
    token: str
    features: Dict[str, float]
    future_return_7d: float


def create_sample_snapshots() -> list[TokenSnapshot]:
    """Create sample token snapshots for demonstration."""
    return [
        TokenSnapshot(
            token="PEPE",
            features={
                "MarketCap": 5_000_000_000,
                "PriceChange7d": 0.15,
                "volume_24h_usd": 500_000_000,
            },
            future_return_7d=0.25,
        ),
        TokenSnapshot(
            token="WIF",
            features={
                "MarketCap": 2_000_000_000,
                "PriceChange7d": 0.08,
                "volume_24h_usd": 200_000_000,
            },
            future_return_7d=0.12,
        ),
        TokenSnapshot(
            token="BONK",
            features={
                "MarketCap": 1_000_000_000,
                "PriceChange7d": 0.20,
                "volume_24h_usd": 150_000_000,
            },
            future_return_7d=0.18,
        ),
        TokenSnapshot(
            token="FLOKI",
            features={
                "MarketCap": 3_000_000_000,
                "PriceChange7d": -0.05,
                "volume_24h_usd": 100_000_000,
            },
            future_return_7d=-0.08,
        ),
        TokenSnapshot(
            token="SHIB",
            features={
                "MarketCap": 10_000_000_000,
                "PriceChange7d": 0.03,
                "volume_24h_usd": 800_000_000,
            },
            future_return_7d=0.05,
        ),
        TokenSnapshot(
            token="DOGE",
            features={
                "MarketCap": 15_000_000_000,
                "PriceChange7d": 0.10,
                "volume_24h_usd": 1_000_000_000,
            },
            future_return_7d=0.08,
        ),
        TokenSnapshot(
            token="MEME",
            features={
                "MarketCap": 500_000_000,
                "PriceChange7d": 0.30,
                "volume_24h_usd": 50_000_000,
            },
            future_return_7d=0.35,
        ),
        TokenSnapshot(
            token="WOJAK",
            features={
                "MarketCap": 300_000_000,
                "PriceChange7d": -0.10,
                "volume_24h_usd": 20_000_000,
            },
            future_return_7d=-0.15,
        ),
    ]


def example_1_individual_strategies():
    """Example 1: Evaluate individual baseline strategies."""
    print("=" * 70)
    print("EXAMPLE 1: Individual Strategy Evaluation")
    print("=" * 70)
    print()
    
    snapshots = create_sample_snapshots()
    top_k = 3
    
    # Test Random strategy
    print("Random Strategy:")
    random_strategy = RandomStrategy()
    random_result = random_strategy.evaluate(snapshots, top_k, seed=42)
    print(f"  Precision@{top_k}: {random_result.precision_at_k:.3f}")
    print(f"  Avg Return: {random_result.average_return_at_k:.4f}")
    print(f"  Selected: {', '.join(random_result.selected_assets)}")
    print()
    
    # Test Cap-Weighted strategy
    print("Cap-Weighted Strategy:")
    cap_strategy = CapWeightedStrategy()
    cap_result = cap_strategy.evaluate(snapshots, top_k)
    print(f"  Precision@{top_k}: {cap_result.precision_at_k:.3f}")
    print(f"  Avg Return: {cap_result.average_return_at_k:.4f}")
    print(f"  Selected: {', '.join(cap_result.selected_assets)}")
    print()
    
    # Test Momentum strategy
    print("Simple Momentum Strategy:")
    momentum_strategy = SimpleMomentumStrategy()
    momentum_result = momentum_strategy.evaluate(snapshots, top_k)
    print(f"  Precision@{top_k}: {momentum_result.precision_at_k:.3f}")
    print(f"  Avg Return: {momentum_result.average_return_at_k:.4f}")
    print(f"  Selected: {', '.join(momentum_result.selected_assets)}")
    print()


def example_2_batch_evaluation():
    """Example 2: Batch evaluation of all baselines."""
    print("=" * 70)
    print("EXAMPLE 2: Batch Baseline Evaluation")
    print("=" * 70)
    print()
    
    snapshots = create_sample_snapshots()
    top_k = 3
    
    # Evaluate all baselines at once
    baseline_results = evaluate_all_baselines(snapshots, top_k, seed=42)
    
    print(f"Evaluated {len(baseline_results)} baseline strategies:")
    print()
    
    for name, result in baseline_results.items():
        print(f"{name.replace('_', ' ').title()}:")
        print(f"  Precision@{top_k}: {result.precision_at_k:.3f}")
        print(f"  Avg Return: {result.average_return_at_k:.4f}")
        print(f"  Selected: {', '.join(result.selected_assets)}")
        print()


def example_3_gemscore_comparison():
    """Example 3: Compare GemScore against baselines."""
    print("=" * 70)
    print("EXAMPLE 3: GemScore vs Baseline Comparison")
    print("=" * 70)
    print()
    
    snapshots = create_sample_snapshots()
    top_k = 3
    
    # Evaluate baselines
    baseline_results = evaluate_all_baselines(snapshots, top_k, seed=42)
    
    # Simulated GemScore performance (in real usage, compute from actual GemScore)
    gem_score_precision = 0.667  # 2/3 positive returns
    gem_score_return = 0.200     # Avg return of 20%
    
    # Compare
    comparisons = compare_to_baselines(
        gem_score_precision,
        gem_score_return,
        baseline_results
    )
    
    print(f"GemScore Performance:")
    print(f"  Precision@{top_k}: {gem_score_precision:.3f}")
    print(f"  Avg Return: {gem_score_return:.4f}")
    print()
    
    print("Comparison to Baselines:")
    print()
    
    for name, comp in comparisons.items():
        baseline = baseline_results[name]
        status = "✅ Outperforms" if comp['outperforms'] else "❌ Underperforms"
        
        print(f"{name.replace('_', ' ').title()}: {status}")
        print(f"  Baseline Precision: {baseline.precision_at_k:.3f}")
        print(f"  Improvement: {comp['precision_improvement']:+.3f} ({comp['precision_pct']:+.1f}%)")
        print(f"  Baseline Return: {baseline.average_return_at_k:.4f}")
        print(f"  Improvement: {comp['return_improvement']:+.4f} ({comp['return_pct']:+.1f}%)")
        print()


def example_4_formatted_output():
    """Example 4: Use formatted comparison output."""
    print("=" * 70)
    print("EXAMPLE 4: Formatted Comparison Output")
    print("=" * 70)
    print()
    
    snapshots = create_sample_snapshots()
    top_k = 3
    
    # Evaluate baselines
    baseline_results = evaluate_all_baselines(snapshots, top_k, seed=42)
    
    # Simulated GemScore
    gem_score_result = {
        'precision': 0.667,
        'return': 0.200,
    }
    
    # Print formatted comparison
    output = format_baseline_comparison(gem_score_result, baseline_results)
    print(output)


def example_5_custom_baseline():
    """Example 5: Create and use custom baseline strategy."""
    print("=" * 70)
    print("EXAMPLE 5: Custom Baseline Strategy")
    print("=" * 70)
    print()
    
    from backtest.baseline_strategies import BaselineStrategy
    
    class VolumeWeightedStrategy(BaselineStrategy):
        """Select assets by 24h trading volume."""
        
        def get_name(self) -> str:
            return "volume_weighted"
        
        def select_assets(self, snapshots, top_k, seed=None):
            def get_volume(snap):
                return snap.features.get('volume_24h_usd', 0.0)
            
            sorted_snaps = sorted(snapshots, key=get_volume, reverse=True)
            return sorted_snaps[:top_k]
    
    snapshots = create_sample_snapshots()
    top_k = 3
    
    # Use custom strategy
    volume_strategy = VolumeWeightedStrategy()
    result = volume_strategy.evaluate(snapshots, top_k)
    
    print("Volume-Weighted Strategy:")
    print(f"  Precision@{top_k}: {result.precision_at_k:.3f}")
    print(f"  Avg Return: {result.average_return_at_k:.4f}")
    print(f"  Selected: {', '.join(result.selected_assets)}")
    print()
    
    # Evaluate with custom + standard baselines
    from backtest.baseline_strategies import evaluate_all_baselines
    
    custom_strategies = [
        RandomStrategy(),
        CapWeightedStrategy(),
        VolumeWeightedStrategy(),
    ]
    
    results = evaluate_all_baselines(snapshots, top_k, seed=42, strategies=custom_strategies)
    
    print("All strategies evaluated:")
    for name, result in results.items():
        print(f"  {name}: Precision={result.precision_at_k:.3f}, Return={result.average_return_at_k:.4f}")


def main():
    """Run all examples."""
    print()
    print("╔" + "═" * 68 + "╗")
    print("║" + " " * 15 + "BASELINE STRATEGY EXAMPLES" + " " * 27 + "║")
    print("╚" + "═" * 68 + "╝")
    print()
    
    # Run examples
    example_1_individual_strategies()
    print()
    
    example_2_batch_evaluation()
    print()
    
    example_3_gemscore_comparison()
    print()
    
    example_4_formatted_output()
    print()
    
    example_5_custom_baseline()
    print()
    
    print("=" * 70)
    print("All examples completed successfully!")
    print("=" * 70)


if __name__ == "__main__":
    main()

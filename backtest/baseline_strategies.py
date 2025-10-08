"""Baseline strategy comparators for backtest evaluation.

Provides reference strategies to compare against GemScore:
- Random: Random selection baseline
- CapWeighted: Market cap weighted selection
- SimpleMomentum: Price momentum based selection

These baselines help contextualize GemScore performance.
"""

from __future__ import annotations

import random
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, List, Protocol

import pandas as pd


class TokenSnapshot(Protocol):
    """Protocol for token snapshot with minimal required fields."""
    
    token: str
    features: Dict[str, float]
    future_return_7d: float


@dataclass
class BaselineResult:
    """Result from a baseline strategy evaluation."""
    
    strategy_name: str
    precision_at_k: float
    average_return_at_k: float
    selected_assets: List[str]
    metadata: Dict[str, float] | None = None


class BaselineStrategy(ABC):
    """Abstract base class for baseline strategies."""
    
    @abstractmethod
    def select_assets(
        self,
        snapshots: List[TokenSnapshot],
        top_k: int,
        seed: int | None = None
    ) -> List[TokenSnapshot]:
        """Select top K assets according to strategy.
        
        Args:
            snapshots: List of token snapshots to select from
            top_k: Number of assets to select
            seed: Random seed for reproducibility
        
        Returns:
            List of selected token snapshots
        """
        pass
    
    @abstractmethod
    def get_name(self) -> str:
        """Get strategy name."""
        pass
    
    def evaluate(
        self,
        snapshots: List[TokenSnapshot],
        top_k: int,
        seed: int | None = None
    ) -> BaselineResult:
        """Evaluate strategy performance.
        
        Args:
            snapshots: List of token snapshots
            top_k: Number of assets to select
            seed: Random seed
        
        Returns:
            BaselineResult with performance metrics
        """
        selected = self.select_assets(snapshots, top_k, seed)
        
        if not selected:
            return BaselineResult(
                strategy_name=self.get_name(),
                precision_at_k=0.0,
                average_return_at_k=0.0,
                selected_assets=[],
            )
        
        returns = [snap.future_return_7d for snap in selected]
        positives = [r for r in returns if r > 0]
        
        precision_at_k = len(positives) / max(1, len(selected))
        average_return_at_k = float(pd.Series(returns).mean()) if returns else 0.0
        
        return BaselineResult(
            strategy_name=self.get_name(),
            precision_at_k=precision_at_k,
            average_return_at_k=average_return_at_k,
            selected_assets=[snap.token for snap in selected],
        )


class RandomStrategy(BaselineStrategy):
    """Random selection baseline.
    
    Selects assets uniformly at random. This represents the null hypothesis -
    performance below random indicates the model is harmful.
    """
    
    def get_name(self) -> str:
        return "random"
    
    def select_assets(
        self,
        snapshots: List[TokenSnapshot],
        top_k: int,
        seed: int | None = None
    ) -> List[TokenSnapshot]:
        """Select K random assets."""
        if seed is not None:
            random.seed(seed)
        
        k = min(top_k, len(snapshots))
        return random.sample(snapshots, k)


class CapWeightedStrategy(BaselineStrategy):
    """Market capitalization weighted selection.
    
    Selects assets with highest market cap. This represents the "buy large caps"
    passive strategy common in traditional markets.
    
    Requires 'MarketCap' or 'market_cap_usd' in features.
    """
    
    def get_name(self) -> str:
        return "cap_weighted"
    
    def select_assets(
        self,
        snapshots: List[TokenSnapshot],
        top_k: int,
        seed: int | None = None
    ) -> List[TokenSnapshot]:
        """Select K assets with highest market cap."""
        # Try different possible feature names for market cap
        def get_market_cap(snap: TokenSnapshot) -> float:
            for key in ['MarketCap', 'market_cap_usd', 'MarketCapUSD', 'marketcap']:
                if key in snap.features:
                    return snap.features[key]
            
            # Fallback: use volume as proxy if market cap not available
            for key in ['volume_24h_usd', 'Volume24h', 'volume']:
                if key in snap.features:
                    return snap.features[key]
            
            # Last resort: return 0
            return 0.0
        
        # Sort by market cap descending
        sorted_snaps = sorted(snapshots, key=get_market_cap, reverse=True)
        k = min(top_k, len(sorted_snaps))
        return sorted_snaps[:k]


class SimpleMomentumStrategy(BaselineStrategy):
    """Simple price momentum baseline.
    
    Selects assets with highest recent price momentum. This represents a
    basic technical trading strategy.
    
    Requires 'PriceChange7d', 'price_change_7d', or similar momentum feature.
    """
    
    def get_name(self) -> str:
        return "simple_momentum"
    
    def select_assets(
        self,
        snapshots: List[TokenSnapshot],
        top_k: int,
        seed: int | None = None
    ) -> List[TokenSnapshot]:
        """Select K assets with highest price momentum."""
        def get_momentum(snap: TokenSnapshot) -> float:
            # Try different possible momentum feature names
            for key in ['PriceChange7d', 'price_change_7d', 'momentum_7d', 
                       'PriceChange24h', 'price_change_24h', 'return_7d']:
                if key in snap.features:
                    return snap.features[key]
            
            # Fallback: try to compute from price features
            if 'price_usd' in snap.features and 'price_usd_7d_ago' in snap.features:
                current = snap.features['price_usd']
                past = snap.features['price_usd_7d_ago']
                if past > 0:
                    return (current - past) / past
            
            # Last resort: return 0
            return 0.0
        
        # Sort by momentum descending
        sorted_snaps = sorted(snapshots, key=get_momentum, reverse=True)
        k = min(top_k, len(sorted_snaps))
        return sorted_snaps[:k]


def evaluate_all_baselines(
    snapshots: List[TokenSnapshot],
    top_k: int,
    seed: int | None = None,
    strategies: List[BaselineStrategy] | None = None
) -> Dict[str, BaselineResult]:
    """Evaluate all baseline strategies.
    
    Args:
        snapshots: List of token snapshots
        top_k: Number of assets to select
        seed: Random seed for reproducibility
        strategies: Optional list of strategies to evaluate (defaults to all)
    
    Returns:
        Dictionary mapping strategy name to BaselineResult
    """
    if strategies is None:
        strategies = [
            RandomStrategy(),
            CapWeightedStrategy(),
            SimpleMomentumStrategy(),
        ]
    
    results = {}
    for strategy in strategies:
        result = strategy.evaluate(snapshots, top_k, seed)
        results[strategy.get_name()] = result
    
    return results


def compare_to_baselines(
    gem_score_precision: float,
    gem_score_return: float,
    baseline_results: Dict[str, BaselineResult]
) -> Dict[str, Dict[str, float]]:
    """Compare GemScore performance to baseline strategies.
    
    Args:
        gem_score_precision: GemScore precision@K
        gem_score_return: GemScore average return@K
        baseline_results: Results from baseline strategies
    
    Returns:
        Dictionary with comparison metrics (improvement over each baseline)
    """
    comparisons = {}
    
    for name, result in baseline_results.items():
        precision_improvement = gem_score_precision - result.precision_at_k
        return_improvement = gem_score_return - result.average_return_at_k
        
        # Calculate relative improvement (percentage)
        precision_pct = (
            (precision_improvement / result.precision_at_k * 100)
            if result.precision_at_k > 0
            else 0.0
        )
        return_pct = (
            (return_improvement / result.average_return_at_k * 100)
            if result.average_return_at_k > 0
            else 0.0
        )
        
        comparisons[name] = {
            "precision_improvement": round(precision_improvement, 4),
            "return_improvement": round(return_improvement, 4),
            "precision_pct": round(precision_pct, 2),
            "return_pct": round(return_pct, 2),
            "outperforms": precision_improvement > 0 and return_improvement > 0,
        }
    
    return comparisons


def format_baseline_comparison(
    gem_score_result: Dict[str, float],
    baseline_results: Dict[str, BaselineResult]
) -> str:
    """Format baseline comparison as human-readable string.
    
    Args:
        gem_score_result: Dict with 'precision' and 'return' keys
        baseline_results: Results from baseline strategies
    
    Returns:
        Formatted string with comparison
    """
    lines = []
    lines.append("=" * 60)
    lines.append("BASELINE COMPARISONS")
    lines.append("=" * 60)
    
    lines.append(f"\nGemScore Performance:")
    lines.append(f"  Precision@K: {gem_score_result['precision']:.3f}")
    lines.append(f"  Avg Return:  {gem_score_result['return']:.4f}")
    
    comparisons = compare_to_baselines(
        gem_score_result['precision'],
        gem_score_result['return'],
        baseline_results
    )
    
    lines.append(f"\nBaseline Comparisons:")
    for name, result in baseline_results.items():
        comp = comparisons[name]
        lines.append(f"\n  {name.replace('_', ' ').title()}:")
        lines.append(f"    Precision: {result.precision_at_k:.3f} "
                    f"({comp['precision_improvement']:+.3f}, {comp['precision_pct']:+.1f}%)")
        lines.append(f"    Return:    {result.average_return_at_k:.4f} "
                    f"({comp['return_improvement']:+.4f}, {comp['return_pct']:+.1f}%)")
        lines.append(f"    Status:    {'✅ Outperforms' if comp['outperforms'] else '❌ Underperforms'}")
    
    lines.append("\n" + "=" * 60)
    
    return "\n".join(lines)

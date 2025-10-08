# Baseline Strategy Comparators for Backtests

This document describes the baseline strategy comparators implemented for validating GemScore performance in backtests.

## Overview

Baseline strategies provide reference points to contextualize GemScore performance. By comparing against naive strategies, we can determine whether GemScore adds value beyond simple heuristics.

## Available Strategies

### 1. Random Strategy

**Description:** Selects assets uniformly at random.

**Purpose:** Represents the null hypothesis. Performance below random indicates harmful predictions.

**Usage:**
```python
from backtest.baseline_strategies import RandomStrategy

strategy = RandomStrategy()
selected = strategy.select_assets(snapshots, top_k=10, seed=42)
```

**Interpretation:**
- GemScore should **significantly outperform** random selection
- If GemScore ≈ Random → Model provides no value
- If GemScore < Random → Model is harmful (anti-correlated)

### 2. Cap-Weighted Strategy

**Description:** Selects assets with highest market capitalization.

**Purpose:** Represents the "buy large caps" passive strategy common in traditional markets.

**Features Used:**
- `MarketCap` or `market_cap_usd` (primary)
- Falls back to `volume_24h_usd` if market cap unavailable

**Usage:**
```python
from backtest.baseline_strategies import CapWeightedStrategy

strategy = CapWeightedStrategy()
selected = strategy.select_assets(snapshots, top_k=10)
```

**Interpretation:**
- Large caps are typically more stable but offer lower upside
- GemScore should outperform if it successfully identifies undervalued small/mid caps
- If CapWeighted > GemScore → Model may have size bias issues

### 3. Simple Momentum Strategy

**Description:** Selects assets with highest recent price momentum.

**Purpose:** Represents basic technical trading strategy (trend following).

**Features Used:**
- `PriceChange7d` or `price_change_7d` (primary)
- Falls back to computed momentum from `price_usd` and `price_usd_7d_ago`

**Usage:**
```python
from backtest.baseline_strategies import SimpleMomentumStrategy

strategy = SimpleMomentumStrategy()
selected = strategy.select_assets(snapshots, top_k=10)
```

**Interpretation:**
- Momentum strategies exploit "hot hand" effect
- GemScore should outperform by identifying assets before momentum starts
- If Momentum > GemScore → Model may be lagging indicator

## Running Baseline Comparisons

### Command-Line Interface

#### Basic Backtest (No Baselines)
```bash
python backtest/harness.py data.csv --top-k 10
```

#### With Baseline Comparisons
```bash
python backtest/harness.py data.csv --top-k 10 --compare-baselines --seed 42
```

#### Walk-Forward Backtest with Baselines
```bash
python -m src.pipeline.backtest \
  --start 2024-01-01 \
  --end 2024-12-31 \
  --walk 30d \
  --k 10 \
  --compare-baselines \
  --seed 42
```

### Programmatic Usage

```python
from backtest.baseline_strategies import evaluate_all_baselines

# Evaluate all baseline strategies
baseline_results = evaluate_all_baselines(snapshots, top_k=10, seed=42)

# Access individual results
random_result = baseline_results["random"]
print(f"Random Precision@10: {random_result.precision_at_k:.3f}")
print(f"Random Return: {random_result.average_return_at_k:.4f}")

# Compare to GemScore
from backtest.baseline_strategies import compare_to_baselines

comparisons = compare_to_baselines(
    gem_score_precision=0.65,
    gem_score_return=0.045,
    baseline_results=baseline_results
)

print(f"Improvement over Random: {comparisons['random']['precision_improvement']:.3f}")
```

## Output Format

### Console Output (with --compare-baselines)

```
============================================================
GEMSCORE PERFORMANCE
============================================================
Precision@K: 0.650
Average Return@K: 0.0450
Flagged Assets: TOKEN1, TOKEN2, TOKEN3, ...

============================================================
BASELINE COMPARISONS
============================================================

GemScore Performance:
  Precision@K: 0.650
  Avg Return:  0.0450

Baseline Comparisons:

  Random:
    Precision: 0.330 (+0.320, +97.0%)
    Return:    0.0100 (+0.0350, +350.0%)
    Status:    ✅ Outperforms

  Cap Weighted:
    Precision: 0.450 (+0.200, +44.4%)
    Return:    0.0250 (+0.0200, +80.0%)
    Status:    ✅ Outperforms

  Simple Momentum:
    Precision: 0.480 (+0.170, +35.4%)
    Return:    0.0300 (+0.0150, +50.0%)
    Status:    ✅ Outperforms

============================================================
```

### JSON Output (summary.json)

```json
{
  "config": {
    "compare_baselines": true,
    "k": 10,
    "seed": 42,
    "start": "2024-01-01",
    "end": "2024-12-31",
    "walk_days": 30,
    "windows": 12
  },
  "metrics": {
    "gem_score": {
      "precision_at_k": {
        "mean": 0.6500,
        "best": 0.7200,
        "worst": 0.5800
      },
      "forward_return": {
        "median": 0.0450
      }
    },
    "baselines": {
      "random": {
        "precision_at_k": {
          "mean": 0.3300,
          "improvement_over_baseline": 0.3200
        },
        "forward_return": {
          "median": 0.0100,
          "improvement_over_baseline": 0.0350
        },
        "outperforms": true
      },
      "cap_weighted": {
        "precision_at_k": {
          "mean": 0.4500,
          "improvement_over_baseline": 0.2000
        },
        "forward_return": {
          "median": 0.0250,
          "improvement_over_baseline": 0.0200
        },
        "outperforms": true
      },
      "simple_momentum": {
        "precision_at_k": {
          "mean": 0.4800,
          "improvement_over_baseline": 0.1700
        },
        "forward_return": {
          "median": 0.0300,
          "improvement_over_baseline": 0.0150
        },
        "outperforms": true
      }
    }
  }
}
```

### CSV Output (windows.csv)

```csv
train_start,train_end,test_start,test_end,precision_at_k,forward_return,max_drawdown,sharpe,random_precision,random_return,cap_weighted_precision,cap_weighted_return,momentum_precision,momentum_return
2024-01-01,2024-01-31,2024-01-31,2024-02-29,0.650,0.0450,0.120,1.20,0.330,0.0100,0.450,0.0250,0.480,0.0300
2024-02-01,2024-02-29,2024-02-29,2024-03-31,0.670,0.0470,0.125,1.25,0.340,0.0105,0.460,0.0260,0.490,0.0310
...
```

## Interpretation Guide

### Scenario 1: GemScore Dominates All Baselines

```
GemScore:     Precision 0.70, Return 0.05
Random:       Precision 0.33, Return 0.01
CapWeighted:  Precision 0.45, Return 0.025
Momentum:     Precision 0.48, Return 0.03
```

**Analysis:** ✅ **Excellent** - Model adds significant value beyond naive strategies.

**Action:** Deploy with confidence. Model has predictive power.

### Scenario 2: GemScore Slightly Better

```
GemScore:     Precision 0.52, Return 0.032
Random:       Precision 0.33, Return 0.01
CapWeighted:  Precision 0.50, Return 0.030
Momentum:     Precision 0.51, Return 0.031
```

**Analysis:** ⚠️ **Marginal** - Model barely beats simple baselines.

**Action:** Investigate feature engineering, model tuning. May not justify complexity.

### Scenario 3: GemScore Loses to Momentum

```
GemScore:     Precision 0.48, Return 0.028
Random:       Precision 0.33, Return 0.01
CapWeighted:  Precision 0.45, Return 0.025
Momentum:     Precision 0.55, Return 0.035
```

**Analysis:** ❌ **Lagging Indicator** - Model is too slow to capture trends.

**Action:** Add momentum features, reduce feature lag, investigate data freshness.

### Scenario 4: GemScore Loses to Everything

```
GemScore:     Precision 0.30, Return 0.005
Random:       Precision 0.33, Return 0.01
CapWeighted:  Precision 0.45, Return 0.025
Momentum:     Precision 0.48, Return 0.03
```

**Analysis:** 🚫 **Harmful Model** - Worse than random selection.

**Action:** Do NOT deploy. Major issues with features, labels, or model architecture.

## Best Practices

### 1. Always Compare Against Baselines

Never evaluate GemScore in isolation. Context matters:
- Is 0.55 precision good? Depends on baseline (0.33 vs 0.52).

### 2. Use Consistent Seeds

Set `seed` parameter for reproducible comparisons:
```python
baseline_results = evaluate_all_baselines(snapshots, top_k=10, seed=42)
```

### 3. Check Multiple Metrics

Don't optimize for single metric:
- **Precision@K:** Hit rate of positive returns
- **Average Return:** Magnitude of returns
- Both must beat baselines for valid model

### 4. Validate Across Time Windows

Single-window performance can be misleading:
- Use walk-forward with multiple windows
- Check consistency across market regimes

### 5. Understand Feature Dependencies

Each baseline requires specific features:
- **CapWeighted:** Needs `MarketCap` or `volume_24h_usd`
- **Momentum:** Needs `PriceChange7d` or price history

Ensure your data includes these features.

## Custom Baselines

You can create custom baseline strategies:

```python
from backtest.baseline_strategies import BaselineStrategy, BaselineResult
from typing import List

class MyCustomStrategy(BaselineStrategy):
    """Custom baseline strategy."""
    
    def get_name(self) -> str:
        return "my_custom"
    
    def select_assets(
        self,
        snapshots: List[TokenSnapshot],
        top_k: int,
        seed: int | None = None
    ) -> List[TokenSnapshot]:
        # Implement selection logic
        # Example: Select by custom score
        scored = [(snap, self._compute_score(snap)) for snap in snapshots]
        scored.sort(key=lambda x: x[1], reverse=True)
        return [snap for snap, _ in scored[:top_k]]
    
    def _compute_score(self, snapshot) -> float:
        # Custom scoring logic
        return snapshot.features.get("my_metric", 0.0)

# Use custom strategy
from backtest.baseline_strategies import evaluate_all_baselines

strategies = [
    RandomStrategy(),
    CapWeightedStrategy(),
    MyCustomStrategy(),
]

results = evaluate_all_baselines(snapshots, top_k=10, strategies=strategies)
```

## Troubleshooting

### Issue: "KeyError: 'MarketCap'"

**Cause:** CapWeighted strategy can't find market cap feature.

**Solution:** 
1. Add `MarketCap` or `market_cap_usd` to your features
2. Or provide `volume_24h_usd` as fallback
3. Or use only Random and Momentum strategies

### Issue: Baselines all show 0.0 precision

**Cause:** No snapshots have positive `future_return_7d`.

**Solution:** Check your labeling process. Ensure `future_return_7d` is correctly computed.

### Issue: All strategies perform identically

**Cause:** Insufficient variation in features or small sample size.

**Solution:**
1. Increase sample size
2. Ensure feature diversity
3. Check for data quality issues

## API Reference

### `BaselineStrategy` (Abstract Base Class)

```python
class BaselineStrategy(ABC):
    @abstractmethod
    def select_assets(
        self,
        snapshots: List[TokenSnapshot],
        top_k: int,
        seed: int | None = None
    ) -> List[TokenSnapshot]:
        """Select top K assets according to strategy."""
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
        """Evaluate strategy performance."""
        pass
```

### `evaluate_all_baselines()`

```python
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
        strategies: Optional list of strategies (defaults to all)
    
    Returns:
        Dictionary mapping strategy name to BaselineResult
    """
```

### `compare_to_baselines()`

```python
def compare_to_baselines(
    gem_score_precision: float,
    gem_score_return: float,
    baseline_results: Dict[str, BaselineResult]
) -> Dict[str, Dict[str, float]]:
    """Compare GemScore performance to baseline strategies.
    
    Returns:
        Dictionary with comparison metrics (improvement over each baseline)
    """
```

### `format_baseline_comparison()`

```python
def format_baseline_comparison(
    gem_score_result: Dict[str, float],
    baseline_results: Dict[str, BaselineResult]
) -> str:
    """Format baseline comparison as human-readable string."""
```

## Related Documentation

- [Backtest Harness](../backtest/harness.py) - Single-period backtest evaluation
- [Pipeline Backtest](../src/pipeline/backtest.py) - Walk-forward backtest framework
- [GemScore Computation](../src/core/scoring.py) - Feature scoring logic
- [Feature Validation](../docs/FEATURE_VALIDATION.md) - Feature quality checks

## Contributing

To add new baseline strategies:

1. Subclass `BaselineStrategy`
2. Implement `get_name()` and `select_assets()`
3. Add tests in `tests/test_baseline_strategies.py`
4. Update this documentation

Example:
```python
class EqualWeightedStrategy(BaselineStrategy):
    """Equal-weighted portfolio baseline."""
    
    def get_name(self) -> str:
        return "equal_weighted"
    
    def select_assets(self, snapshots, top_k, seed=None):
        # Select first K assets (equal weight)
        return snapshots[:top_k]
```

## Changelog

### v1.0.0 (2025-01-XX)
- Initial implementation
- Three baseline strategies: Random, CapWeighted, SimpleMomentum
- CLI integration for harness and pipeline backtests
- Comprehensive test coverage (23 tests)
- JSON and CSV output formats

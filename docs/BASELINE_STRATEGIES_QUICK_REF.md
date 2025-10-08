# Baseline Strategies Quick Reference

Quick guide for using baseline strategy comparators in backtests.

## TL;DR

```bash
# Run backtest with baseline comparisons
python backtest/harness.py data.csv --top-k 10 --compare-baselines --seed 42

# Walk-forward with baselines
python -m src.pipeline.backtest \
  --start 2024-01-01 --end 2024-12-31 --walk 30d \
  --k 10 --compare-baselines --seed 42
```

## Available Strategies

| Strategy | Description | Purpose |
|----------|-------------|---------|
| **Random** | Random selection | Null hypothesis (should beat this!) |
| **CapWeighted** | Largest market cap | Passive large-cap strategy |
| **SimpleMomentum** | Highest price momentum | Basic trend-following |

## Interpretation

### ✅ Good Performance
```
GemScore beats all baselines by >20% precision AND >50% return
```
→ Deploy confidently

### ⚠️ Marginal Performance
```
GemScore barely beats baselines (<10% improvement)
```
→ Investigate feature engineering

### ❌ Poor Performance
```
GemScore loses to momentum or worse than random
```
→ Do NOT deploy, fix model

## Programmatic Usage

```python
from backtest.baseline_strategies import evaluate_all_baselines, compare_to_baselines

# Evaluate baselines
baseline_results = evaluate_all_baselines(snapshots, top_k=10, seed=42)

# Compare to GemScore
comparisons = compare_to_baselines(
    gem_score_precision=0.65,
    gem_score_return=0.045,
    baseline_results=baseline_results
)

# Check if outperforms
for name, comp in comparisons.items():
    if comp['outperforms']:
        print(f"✅ Beats {name}: +{comp['precision_improvement']:.3f} precision")
    else:
        print(f"❌ Loses to {name}: {comp['precision_improvement']:.3f} precision")
```

## Output Files

| File | Content |
|------|---------|
| `summary.json` | Overall metrics with baseline comparisons |
| `windows.csv` | Per-window results for all strategies |

## Required Features

| Strategy | Required Features |
|----------|------------------|
| Random | None |
| CapWeighted | `MarketCap` or `market_cap_usd` (fallback: `volume_24h_usd`) |
| SimpleMomentum | `PriceChange7d` or `price_change_7d` |

## Key Metrics

- **Precision@K**: Percentage of selected assets with positive returns
- **Average Return@K**: Mean return of selected assets
- **Improvement**: Absolute difference vs baseline
- **Improvement %**: Relative percentage improvement

## Common Issues

**"No baselines shown"**
→ Add `--compare-baselines` flag

**"KeyError: MarketCap"**
→ Ensure data includes market cap or volume features

**"All baselines = 0.0"**
→ Check `future_return_7d` labeling

## Custom Baselines

```python
from backtest.baseline_strategies import BaselineStrategy

class MyStrategy(BaselineStrategy):
    def get_name(self) -> str:
        return "my_strategy"
    
    def select_assets(self, snapshots, top_k, seed=None):
        # Your selection logic
        return sorted(snapshots, key=lambda x: x.features['my_score'])[:top_k]
```

## Full Documentation

See [BASELINE_STRATEGIES.md](./BASELINE_STRATEGIES.md) for comprehensive guide.

## Tests

```bash
# Run baseline strategy tests
pytest tests/test_baseline_strategies.py -v

# Expected: 23 passed
```

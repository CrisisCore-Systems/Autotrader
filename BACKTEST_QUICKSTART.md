# Backtest Extended Metrics - Quick Start Guide

This guide shows you how to use the newly implemented backtest metrics features.

## What's New

1. **ROC/AUC and PR Curves**: Binary classification metrics for return prediction
2. **Time-Sliced Evaluation**: Analyze performance across different time periods
3. **Experiment Tracking**: Full reproducibility with configuration storage

## Quick Examples

### 1. Basic Backtest with Extended Metrics

```bash
# Run backtest with all extended metrics (IC, Sharpe, Sortino, ROC/AUC)
python backtest/harness.py data.csv --extended-metrics
```

**Output includes:**
- Information Coefficient (Pearson, Spearman, Kendall)
- Risk-adjusted metrics (Sharpe, Sortino, Calmar)
- ROC AUC and PR AUC scores
- Hit rate and statistical significance

### 2. Compare Against Baselines

```bash
# Compare your strategy against random, cap-weighted, and momentum baselines
python backtest/harness.py data.csv \
    --compare-baselines \
    --extended-metrics \
    --seed 42
```

**Shows comparison with:**
- Random selection baseline
- Market-cap weighted baseline
- Simple momentum baseline

### 3. Time-Sliced Evaluation

```bash
# Evaluate performance month-by-month
python backtest/harness.py data.csv \
    --time-sliced \
    --slice-by month \
    --extended-metrics
```

**Provides:**
- Per-period precision and returns
- Aggregate statistics (mean, std, min, max)
- Temporal performance trends

### 4. Full Analysis with Export

```bash
# Run complete analysis and save results
python backtest/harness.py data.csv \
    --top-k 15 \
    --compare-baselines \
    --extended-metrics \
    --time-sliced \
    --slice-by quarter \
    --seed 123 \
    --json-output results.json
```

**Exports JSON with:**
- All metrics (precision, returns, IC, Sharpe, ROC/AUC)
- Baseline comparisons
- Time-sliced results
- Full experiment configuration for reproducibility

## CLI Options Reference

| Option | Description |
|--------|-------------|
| `--extended-metrics` | Calculate IC, Sharpe, Sortino, ROC/AUC, PR curves |
| `--compare-baselines` | Compare against random, cap-weighted, momentum |
| `--time-sliced` | Enable time-sliced evaluation |
| `--slice-by {week,month,quarter}` | Time slice granularity |
| `--seed SEED` | Random seed for reproducibility |
| `--json-output PATH` | Export results as JSON |
| `--top-k K` | Number of top assets to evaluate (default: 10) |

## Understanding the Metrics

### ROC AUC (Receiver Operating Characteristic)
- **Range**: 0 to 1
- **Interpretation**:
  - > 0.7: Strong classification performance
  - 0.6-0.7: Moderate performance
  - 0.5-0.6: Weak performance
  - 0.5: Random baseline
  - < 0.5: Worse than random

### PR AUC (Precision-Recall)
- **Range**: 0 to 1
- **Use**: Better for imbalanced datasets
- **Interpretation**: Higher is better

### Information Coefficient (IC)
- **Range**: -1 to 1
- **Interpretation**:
  - > 0.05: Strong predictive power
  - 0.02-0.05: Moderate predictive power
  - < 0.02: Weak predictive power

### Sharpe Ratio
- **Range**: Unbounded
- **Interpretation**:
  - > 2: Excellent risk-adjusted returns
  - 1-2: Good risk-adjusted returns
  - 0.5-1: Acceptable risk-adjusted returns
  - < 0.5: Poor risk-adjusted returns

## Python API Examples

### Example 1: Calculate Classification Metrics

```python
from backtest.extended_metrics import calculate_classification_metrics
import numpy as np

# Your predictions and actual returns
predictions = np.array([0.9, 0.7, 0.3, 0.8, 0.5])
actuals = np.array([0.05, 0.03, -0.02, 0.04, 0.01])

# Calculate metrics
metrics = calculate_classification_metrics(predictions, actuals)

print(f"ROC AUC: {metrics.roc_auc:.4f}")
print(f"PR AUC: {metrics.pr_auc:.4f}")
print(f"Baseline Accuracy: {metrics.baseline_accuracy:.2%}")
```

### Example 2: Full Extended Metrics

```python
from backtest.extended_metrics import calculate_extended_metrics

# Your snapshots and predictions
metrics = calculate_extended_metrics(
    snapshots=snapshots,
    predictions=predictions,
    top_k=10,
    include_classification=True,
)

# Print comprehensive summary
print(metrics.summary_string())
```

### Example 3: Time-Sliced Evaluation

```python
from backtest.harness import evaluate_time_sliced

result = evaluate_time_sliced(
    snapshots=snapshots,
    top_k=10,
    slice_by="month",
    compare_baselines=True,
    extended_metrics=True,
    seed=42,
)

# Access per-period results
for ts in result.time_slices:
    print(f"Period {ts.period_id}: Precision={ts.result.precision_at_k:.3f}")
```

## Example Workflow

1. **Prepare your data** with required columns:
   - `token`: Asset identifier
   - `date`: Timestamp
   - `f_*`: Feature columns (prefixed with `f_`)
   - `future_return_7d`: 7-day forward return

2. **Run basic backtest:**
   ```bash
   python backtest/harness.py data.csv --top-k 10
   ```

3. **Add extended metrics:**
   ```bash
   python backtest/harness.py data.csv --extended-metrics
   ```

4. **Compare with baselines:**
   ```bash
   python backtest/harness.py data.csv --compare-baselines --extended-metrics
   ```

5. **Add temporal analysis:**
   ```bash
   python backtest/harness.py data.csv \
       --extended-metrics \
       --time-sliced \
       --slice-by month
   ```

6. **Export for reproducibility:**
   ```bash
   python backtest/harness.py data.csv \
       --extended-metrics \
       --compare-baselines \
       --time-sliced \
       --seed 42 \
       --json-output experiment_001.json
   ```

## Running the Examples

```bash
# Run comprehensive examples
python examples/extended_backtest_example.py

# Run baseline strategies example (existing)
python examples/baseline_strategies_example.py
```

## Full Documentation

For complete documentation, see:
- **Extended Metrics Guide**: [`docs/BACKTEST_EXTENDED_METRICS.md`](docs/BACKTEST_EXTENDED_METRICS.md)
- **API Reference**: See docstrings in `backtest/extended_metrics.py`
- **Examples**: See `examples/extended_backtest_example.py`

## Testing

Run the test suite:
```bash
# Test classification metrics
pytest tests/test_classification_metrics.py -v

# Test time-sliced evaluation
pytest tests/test_time_sliced_evaluation.py -v

# Test all backtest features
pytest tests/test_extended_metrics.py \
       tests/test_baseline_strategies.py \
       tests/test_classification_metrics.py \
       tests/test_time_sliced_evaluation.py -v
```

## Next Steps

1. Try the examples with your own backtest data
2. Experiment with different time slice granularities
3. Compare your strategy against baselines
4. Export results and track experiments over time
5. Use ROC/PR curves to tune prediction thresholds

## Support

For issues or questions:
- Check the full documentation in `docs/BACKTEST_EXTENDED_METRICS.md`
- Review examples in `examples/extended_backtest_example.py`
- Run tests to verify functionality

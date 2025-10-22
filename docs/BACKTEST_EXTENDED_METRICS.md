# Extended Backtest Metrics and Time-Sliced Evaluation

This document describes the extended backtest metrics framework, including ROC/AUC analysis, PR curves, time-sliced evaluation, and experiment reproducibility features.

## Overview

The backtest harness has been enhanced with:

1. **Classification Metrics**: ROC/AUC and Precision-Recall curves for binary classification performance
2. **Time-Sliced Evaluation**: Temporal performance analysis across different time periods
3. **Experiment Configuration**: Full reproducibility tracking for all backtest experiments

## Features

### 1. Classification Metrics (ROC/AUC, PR Curves)

Treat the prediction task as binary classification: predicting whether returns will be positive (1) or negative/zero (0).

**Metrics Included:**
- **ROC AUC**: Area under the Receiver Operating Characteristic curve
- **PR AUC**: Area under the Precision-Recall curve (Average Precision)
- **Baseline Accuracy**: Majority class baseline for comparison
- **ROC Curve**: Full FPR/TPR curve data
- **PR Curve**: Full Precision/Recall curve data

**When to Use:**
- When comparing against classification-based models
- When visualizing model selection decisions
- When treating returns as binary outcomes (positive/negative)
- When assessing the trade-off between precision and recall

**Example:**
```python
from backtest.extended_metrics import calculate_classification_metrics
import numpy as np

predictions = np.array([0.9, 0.7, 0.3, 0.8, 0.5])
actuals = np.array([0.05, 0.03, -0.02, 0.04, 0.01])

metrics = calculate_classification_metrics(predictions, actuals)
print(f"ROC AUC: {metrics.roc_auc:.4f}")
print(f"PR AUC: {metrics.pr_auc:.4f}")
```

**Interpretation:**
- **ROC AUC > 0.7**: Strong classification performance
- **0.6 < ROC AUC < 0.7**: Moderate performance
- **0.5 < ROC AUC < 0.6**: Weak performance
- **ROC AUC < 0.5**: Poor performance (worse than random)
- **ROC AUC = 0.5**: Random classifier baseline

### 2. Time-Sliced Evaluation

Evaluate backtest performance across different time periods to identify:
- Temporal performance trends
- Regime changes in market conditions
- Stability of prediction performance
- Seasonal or cyclical patterns

**Supported Time Slices:**
- **Week**: `--slice-by week`
- **Month**: `--slice-by month` (default)
- **Quarter**: `--slice-by quarter`

**Usage:**
```bash
# Monthly time-sliced evaluation
python backtest/harness.py data.csv --time-sliced --slice-by month

# Quarterly evaluation with baselines and extended metrics
python backtest/harness.py data.csv \
    --time-sliced \
    --slice-by quarter \
    --compare-baselines \
    --extended-metrics \
    --seed 42 \
    --json-output results.json
```

**Output Includes:**
- Per-period precision and returns
- Aggregate statistics (mean, std, min, max)
- Full time slice details in JSON export

**Example Output:**
```
TIME-SLICED EVALUATION
Total Periods: 4

Per-Period Performance:
  Period 0 (2024-01-01 to 2024-01-31):
    Precision@K: 0.700
    Avg Return:  0.0350
  Period 1 (2024-02-01 to 2024-02-29):
    Precision@K: 0.600
    Avg Return:  0.0080
  ...

Aggregate Statistics:
  Mean Precision:   0.675 ± 0.050
  Mean Return:      0.0379 ± 0.0121
  Min Precision:    0.600
  Max Precision:    0.800
```

### 3. Experiment Configuration & Reproducibility

Every backtest result now includes full experiment configuration for complete reproducibility.

**Configuration Includes:**
- `top_k`: Number of top assets evaluated
- `compare_baselines`: Whether baselines were evaluated
- `extended_metrics`: Whether extended metrics were calculated
- `seed`: Random seed for reproducibility
- `data_path`: Path to input data
- `timestamp`: Experiment timestamp

**Usage:**
```bash
# Run backtest with all features and save config
python backtest/harness.py data.csv \
    --top-k 10 \
    --compare-baselines \
    --extended-metrics \
    --time-sliced \
    --seed 42 \
    --json-output experiment_results.json
```

**JSON Output Structure:**
```json
{
  "precision_at_k": 0.7,
  "average_return_at_k": 0.05,
  "flagged_assets": ["TOKEN1", "TOKEN2", "TOKEN3"],
  "config": {
    "top_k": 10,
    "compare_baselines": true,
    "extended_metrics": true,
    "seed": 42,
    "data_path": "/path/to/data.csv",
    "timestamp": "2024-01-01T00:00:00"
  },
  "baseline_results": { ... },
  "extended_metrics": { ... },
  "time_slices": [ ... ]
}
```

## CLI Reference

### Basic Usage
```bash
python backtest/harness.py <data.csv> [OPTIONS]
```

### Options

| Option | Description | Default |
|--------|-------------|---------|
| `--top-k K` | Number of top assets to evaluate | 10 |
| `--compare-baselines` | Compare against baseline strategies | False |
| `--extended-metrics` | Calculate IC and risk-adjusted metrics | False |
| `--time-sliced` | Enable time-sliced evaluation | False |
| `--slice-by {week,month,quarter}` | Time slice granularity | month |
| `--seed SEED` | Random seed for reproducibility | None |
| `--json-output PATH` | Export results as JSON | None |

### Examples

**1. Basic backtest:**
```bash
python backtest/harness.py backtest_data.csv --top-k 10
```

**2. With baselines and extended metrics:**
```bash
python backtest/harness.py backtest_data.csv \
    --top-k 20 \
    --compare-baselines \
    --extended-metrics
```

**3. Time-sliced with reproducibility:**
```bash
python backtest/harness.py backtest_data.csv \
    --time-sliced \
    --slice-by month \
    --seed 42 \
    --json-output monthly_results.json
```

**4. Full analysis:**
```bash
python backtest/harness.py backtest_data.csv \
    --top-k 15 \
    --compare-baselines \
    --extended-metrics \
    --time-sliced \
    --slice-by quarter \
    --seed 123 \
    --json-output full_analysis.json
```

## API Reference

### Classification Metrics

```python
from backtest.extended_metrics import calculate_classification_metrics

metrics = calculate_classification_metrics(
    predictions: np.ndarray,  # Predicted scores
    actuals: np.ndarray,      # Actual returns
) -> ClassificationMetrics
```

**Returns:**
- `roc_auc`: Area under ROC curve
- `pr_auc`: Area under PR curve
- `roc_curve_fpr`: False positive rates
- `roc_curve_tpr`: True positive rates
- `pr_curve_precision`: Precision values
- `pr_curve_recall`: Recall values
- `baseline_accuracy`: Majority class baseline
- `sample_size`: Number of observations

### Extended Metrics

```python
from backtest.extended_metrics import calculate_extended_metrics

metrics = calculate_extended_metrics(
    snapshots: List[TokenSnapshot],
    predictions: np.ndarray,
    top_k: Optional[int] = None,
    risk_free_rate: float = 0.0,
    periods_per_year: int = 52,
    periods: Optional[List[int]] = None,
    include_classification: bool = True,
) -> ExtendedBacktestMetrics
```

**Returns:**
- `ic_metrics`: Information Coefficient metrics
- `risk_metrics`: Risk-adjusted performance metrics
- `classification_metrics`: ROC/AUC and PR metrics (if enabled)
- `metadata`: Experiment metadata

### Time-Sliced Evaluation

```python
from backtest.harness import evaluate_time_sliced

result = evaluate_time_sliced(
    snapshots: List[TokenSnapshot],
    top_k: int = 10,
    slice_by: str = "month",  # "week", "month", or "quarter"
    compare_baselines: bool = False,
    extended_metrics: bool = False,
    seed: int | None = None,
) -> BacktestResult
```

**Returns:**
- Overall metrics (mean across periods)
- `time_slices`: List of TimeSlice objects with per-period results
- Optional baseline and extended metrics

## Examples

See [`examples/extended_backtest_example.py`](../examples/extended_backtest_example.py) for comprehensive usage examples:

1. **Classification Metrics**: ROC/AUC and PR curve analysis
2. **Extended Metrics**: Full metrics with classification
3. **Experiment Reproducibility**: Configuration tracking
4. **Time-Sliced Evaluation**: Temporal performance analysis
5. **Comparison**: With vs without classification metrics

Run the example:
```bash
python examples/extended_backtest_example.py
```

## Integration with Existing Features

The extended metrics seamlessly integrate with existing backtest features:

- **Baseline Strategies**: Random, Cap-Weighted, Momentum (already implemented)
- **Information Coefficient**: Pearson, Spearman, Kendall correlations
- **Risk Metrics**: Sharpe, Sortino, Calmar ratios, Max Drawdown
- **JSON Export**: Full experiment serialization

## Performance Considerations

- **Classification metrics** add minimal overhead (~10ms per evaluation)
- **Time-sliced evaluation** scales linearly with number of periods
- **ROC/PR curves** store full curve data for visualization (can be large for many predictions)
- Use `include_classification=False` to disable if not needed

## Testing

Comprehensive test coverage:
- `tests/test_classification_metrics.py`: 15 tests for ROC/AUC and PR curves
- `tests/test_time_sliced_evaluation.py`: 16 tests for temporal evaluation
- `tests/test_extended_metrics.py`: 29 existing tests for IC and risk metrics
- `tests/test_baseline_strategies.py`: 23 existing tests for baselines

Run tests:
```bash
pytest tests/test_classification_metrics.py -v
pytest tests/test_time_sliced_evaluation.py -v
```

## Future Enhancements

Potential future additions:
- Interactive ROC/PR curve visualization
- Statistical significance tests for time-sliced results
- Walk-forward optimization integration
- Cross-validation support
- Multi-asset portfolio backtesting

## References

- **ROC AUC**: Fawcett, T. (2006). "An introduction to ROC analysis"
- **Precision-Recall**: Davis & Goadrich (2006). "The relationship between Precision-Recall and ROC curves"
- **Information Coefficient**: Grinold & Kahn (1999). "Active Portfolio Management"
- **Walk-Forward**: Pardo, R. (2008). "The Evaluation and Optimization of Trading Strategies"

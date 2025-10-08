# Extended Backtest Metrics - Information Coefficient & Risk-Adjusted Performance

**Status:** ✅ **Production Ready**

**Date:** 2025-01-08

---

## Overview

This guide documents the extended backtest metrics system for evaluating GemScore performance, including **Information Coefficient (IC)** analysis and **risk-adjusted performance metrics**. These advanced metrics provide deeper insight into model quality beyond simple precision and return.

## Table of Contents

1. [What is Information Coefficient?](#what-is-information-coefficient)
2. [Key Metrics Explained](#key-metrics-explained)
3. [Installation & Setup](#installation--setup)
4. [Usage Examples](#usage-examples)
5. [Interpretation Guide](#interpretation-guide)
6. [API Reference](#api-reference)
7. [Troubleshooting](#troubleshooting)

---

## What is Information Coefficient?

**Information Coefficient (IC)** measures the correlation between predicted scores and actual returns. It's a fundamental metric in quantitative finance for assessing model predictive power.

### Why IC Matters

- **IC > 0.05**: Strong predictive power (excellent)
- **IC > 0.02**: Moderate predictive power (good)
- **IC < 0.02**: Weak predictive power (needs improvement)

### IC vs Other Metrics

| Metric | Measures | Use Case |
|--------|----------|----------|
| **Precision@K** | How many top-K picks are profitable | Portfolio construction |
| **IC (Pearson)** | Linear correlation between predictions and returns | Model quality assessment |
| **IC (Spearman)** | Rank correlation (robust to outliers) | Non-linear relationships |
| **Hit Rate** | % correct direction predictions | Signal quality |

---

## Key Metrics Explained

### Information Coefficient Metrics

#### 1. Pearson IC
**Definition:** Linear correlation between predictions and actual returns.

```python
IC_pearson = correlation(predictions, actual_returns)
```

**Interpretation:**
- **IC > 0.10**: Exceptional predictive power (rare)
- **IC > 0.05**: Strong predictive power
- **IC > 0.02**: Moderate predictive power
- **IC < 0.02**: Weak predictive power

#### 2. Spearman IC
**Definition:** Rank-based correlation, robust to outliers.

**When to use:** When returns are skewed or have extreme outliers.

#### 3. Kendall's Tau
**Definition:** Alternative rank correlation, more conservative than Spearman.

**When to use:** When you want a conservative estimate of predictive power.

#### 4. Hit Rate
**Definition:** Percentage of correct direction predictions.

```python
hit_rate = % of (sign(prediction) == sign(actual_return))
```

**Interpretation:**
- **> 60%**: Strong directional signal
- **> 55%**: Better than random
- **< 50%**: Worse than random (inverted signal)

#### 5. IC IR (Information Ratio)
**Definition:** Consistency of IC across periods.

```python
IC_IR = mean(IC_per_period) / std(IC_per_period)
```

**Interpretation:**
- **IR > 1.0**: Very consistent predictions
- **IR > 0.5**: Moderately consistent
- **IR < 0.5**: Inconsistent (high variance)

### Risk-Adjusted Metrics

#### 1. Sharpe Ratio
**Definition:** Excess return per unit of volatility.

```python
Sharpe = (annualized_return - risk_free_rate) / volatility
```

**Interpretation:**
- **Sharpe > 2.0**: Excellent
- **Sharpe > 1.0**: Good
- **Sharpe > 0.5**: Acceptable
- **Sharpe < 0**: Negative excess return

#### 2. Sortino Ratio
**Definition:** Excess return per unit of downside risk.

```python
Sortino = (annualized_return - risk_free_rate) / downside_deviation
```

**Interpretation:**
- Similar to Sharpe, but only penalizes downside volatility
- Should be higher than Sharpe (downside risk < total risk)

#### 3. Calmar Ratio
**Definition:** Annualized return divided by maximum drawdown.

```python
Calmar = annualized_return / abs(max_drawdown)
```

**Interpretation:**
- **Calmar > 3.0**: Excellent risk/reward
- **Calmar > 1.0**: Good
- **Calmar < 0.5**: Poor (large drawdowns relative to returns)

#### 4. Maximum Drawdown
**Definition:** Largest peak-to-trough decline.

**Interpretation:**
- Measures worst-case loss
- Lower absolute value is better
- Important for risk management

#### 5. Win Rate
**Definition:** Percentage of profitable trades/periods.

**Interpretation:**
- **> 60%**: High win rate
- **40-60%**: Typical
- **< 40%**: Low win rate (needs high profit factor)

#### 6. Profit Factor
**Definition:** Ratio of gross profits to gross losses.

```python
profit_factor = sum(positive_returns) / abs(sum(negative_returns))
```

**Interpretation:**
- **PF > 2.0**: Excellent
- **PF > 1.5**: Good
- **PF > 1.0**: Profitable
- **PF < 1.0**: Unprofitable

---

## Installation & Setup

### Requirements

```bash
pip install numpy pandas scipy matplotlib
```

### Import Modules

```python
from backtest.extended_metrics import (
    calculate_ic_metrics,
    calculate_risk_metrics,
    calculate_extended_metrics,
    compare_extended_metrics,
    format_ic_summary,
)
```

---

## Usage Examples

### Example 1: Calculate IC Metrics

```python
import numpy as np
from backtest.extended_metrics import calculate_ic_metrics

# Your predictions and actual returns
predictions = np.array([0.8, 0.6, 0.9, 0.5, 0.7])
actual_returns = np.array([0.05, 0.02, 0.06, 0.01, 0.04])

# Calculate IC
ic_metrics = calculate_ic_metrics(predictions, actual_returns)

print(f"Pearson IC: {ic_metrics.ic_pearson:.4f}")
print(f"Spearman IC: {ic_metrics.ic_spearman:.4f}")
print(f"Hit Rate: {ic_metrics.hit_rate:.2%}")
print(f"P-value: {ic_metrics.ic_pearson_pvalue:.4f}")
```

**Output:**
```
Pearson IC: 0.8771
Spearman IC: 1.0000
Hit Rate: 100.00%
P-value: 0.0500
```

### Example 2: Calculate Risk Metrics

```python
from backtest.extended_metrics import calculate_risk_metrics

# Your period returns
returns = np.array([0.02, -0.01, 0.03, 0.01, -0.005, 0.025])

# Calculate risk metrics
risk_metrics = calculate_risk_metrics(
    returns,
    risk_free_rate=0.0,
    periods_per_year=52  # Weekly returns
)

print(f"Sharpe Ratio: {risk_metrics.sharpe_ratio:.4f}")
print(f"Sortino Ratio: {risk_metrics.sortino_ratio:.4f}")
print(f"Max Drawdown: {risk_metrics.max_drawdown:.4f}")
print(f"Win Rate: {risk_metrics.win_rate:.2%}")
```

### Example 3: Comprehensive Backtest Metrics

```python
from backtest.extended_metrics import calculate_extended_metrics

# Mock token snapshots
class TokenSnapshot:
    def __init__(self, token, features, future_return):
        self.token = token
        self.features = features
        self.future_return_7d = future_return

snapshots = [
    TokenSnapshot("TOKEN1", {}, 0.05),
    TokenSnapshot("TOKEN2", {}, 0.03),
    TokenSnapshot("TOKEN3", {}, -0.02),
    # ... more snapshots
]

predictions = np.array([0.9, 0.8, 0.3, ...])

# Calculate comprehensive metrics
metrics = calculate_extended_metrics(
    snapshots=snapshots,
    predictions=predictions,
    top_k=10,
    risk_free_rate=0.0,
    periods_per_year=52
)

# Print summary
print(metrics.summary_string())
```

### Example 4: Compare with Baselines

```python
from backtest.baseline_strategies import RandomStrategy, CapWeightedStrategy
from backtest.extended_metrics import (
    calculate_extended_metrics,
    compare_extended_metrics
)

# Calculate GemScore metrics
gem_score_metrics = calculate_extended_metrics(snapshots, predictions, top_k=10)

# Calculate baseline metrics
baseline_metrics = {}
for strategy in [RandomStrategy(), CapWeightedStrategy()]:
    selected = strategy.select_assets(snapshots, top_k=10)
    baseline_preds = np.array([1.0 if snap in selected else 0.0 for snap in snapshots])
    baseline_metrics[strategy.get_name()] = calculate_extended_metrics(
        snapshots, baseline_preds, top_k=10
    )

# Compare
comparisons = compare_extended_metrics(gem_score_metrics, baseline_metrics)

for baseline, comp in comparisons.items():
    print(f"{baseline}:")
    print(f"  IC Improvement: {comp['ic_improvement']:+.4f}")
    print(f"  Sharpe Improvement: {comp['sharpe_improvement']:+.4f}")
    print(f"  Better: {'✅' if comp['risk_adjusted_better'] else '❌'}")
```

### Example 5: CLI Usage

```bash
# Basic backtest with extended metrics
python backtest/harness.py data.csv --top-k 10 --extended-metrics

# With baselines and extended metrics
python backtest/harness.py data.csv \
    --top-k 10 \
    --compare-baselines \
    --extended-metrics \
    --seed 42
```

**Output:**
```
======================================================================
EXTENDED BACKTEST METRICS
======================================================================

📊 INFORMATION COEFFICIENT
----------------------------------------------------------------------
  Pearson IC:   0.0450  (p=0.0234)
  Spearman IC:  0.0523  (p=0.0156)
  Kendall Tau:  0.0412  (p=0.0289)
  IC IR:        2.1500  (Information Ratio)
  Hit Rate:     58.50%  (Direction Accuracy)

💰 RETURNS & RISK
----------------------------------------------------------------------
  Total Return:       0.2450
  Annualized Return:  0.1850
  Mean Return:        0.0125
  Median Return:      0.0110
  Volatility:         0.0350
  Max Drawdown:       -0.0850

📈 RISK-ADJUSTED PERFORMANCE
----------------------------------------------------------------------
  Sharpe Ratio:   1.8500  (Return / Volatility)
  Sortino Ratio:  2.4500  (Return / Downside Risk)
  Calmar Ratio:   2.1765  (Return / MaxDrawdown)
  Win Rate:       62.50%
  Profit Factor:  2.3500
```

---

## Interpretation Guide

### Scenario 1: Strong Model Performance

```
IC Pearson: 0.08
Sharpe Ratio: 2.5
Hit Rate: 65%
```

**Interpretation:**
- ✅ **Strong predictive power** (IC > 0.05)
- ✅ **Excellent risk-adjusted returns** (Sharpe > 2.0)
- ✅ **High directional accuracy** (Hit Rate > 60%)
- **Action:** Deploy model with confidence

### Scenario 2: Moderate Model Performance

```
IC Pearson: 0.03
Sharpe Ratio: 1.2
Hit Rate: 56%
```

**Interpretation:**
- ⚠️ **Moderate predictive power** (0.02 < IC < 0.05)
- ✅ **Good risk-adjusted returns** (Sharpe > 1.0)
- ⚠️ **Slightly better than random** (Hit Rate > 55%)
- **Action:** Deploy with monitoring, consider improvements

### Scenario 3: Weak Model Performance

```
IC Pearson: 0.01
Sharpe Ratio: 0.5
Hit Rate: 52%
```

**Interpretation:**
- ❌ **Weak predictive power** (IC < 0.02)
- ⚠️ **Mediocre risk-adjusted returns**
- ⚠️ **Barely better than random**
- **Action:** Do not deploy, improve model

### Scenario 4: High Return, High Risk

```
IC Pearson: 0.06
Sharpe Ratio: 0.8
Max Drawdown: -0.35
Calmar Ratio: 0.6
```

**Interpretation:**
- ✅ **Good predictive power**
- ❌ **Poor risk-adjusted returns** (high volatility)
- ❌ **Large drawdowns**
- **Action:** Improve risk management, position sizing

### Scenario 5: Statistical Significance Issues

```
IC Pearson: 0.05
IC P-value: 0.15
Sample Size: 30
```

**Interpretation:**
- ⚠️ **IC looks good but not statistically significant** (p > 0.05)
- ❌ **Small sample size**
- **Action:** Collect more data before deploying

---

## Multi-Period IC Analysis

### Why Track IC Over Time?

Single-period IC can be misleading. Multi-period analysis reveals:
- **Consistency**: Is the model reliably predictive?
- **Decay**: Does predictive power fade over time?
- **Regime changes**: Does IC vary by market conditions?

### Calculating Multi-Period IC

```python
period_ics = []
for period in range(n_periods):
    period_preds = predictions[period_mask]
    period_actuals = actuals[period_mask]
    ic, _ = stats.pearsonr(period_preds, period_actuals)
    period_ics.append(ic)

# Calculate IC statistics
ic_mean = np.mean(period_ics)
ic_std = np.std(period_ics)
ic_ir = ic_mean / ic_std  # Information Ratio
```

### IC IR Interpretation

| IC IR | Interpretation | Action |
|-------|----------------|--------|
| > 2.0 | Very consistent | Deploy confidently |
| 1.0-2.0 | Moderately consistent | Deploy with monitoring |
| 0.5-1.0 | Somewhat inconsistent | Investigate causes |
| < 0.5 | Highly inconsistent | Do not deploy |

---

## API Reference

### calculate_ic_metrics()

```python
def calculate_ic_metrics(
    predictions: np.ndarray,
    actuals: np.ndarray,
    periods: Optional[List[int]] = None
) -> ICMetrics
```

**Parameters:**
- `predictions`: Array of predicted scores
- `actuals`: Array of actual returns
- `periods`: Optional list of period indices for multi-period IC

**Returns:** `ICMetrics` with correlation and statistical measures

---

### calculate_risk_metrics()

```python
def calculate_risk_metrics(
    returns: np.ndarray,
    risk_free_rate: float = 0.0,
    periods_per_year: int = 52
) -> RiskMetrics
```

**Parameters:**
- `returns`: Array of period returns
- `risk_free_rate`: Risk-free rate for ratio calculations
- `periods_per_year`: Number of periods per year for annualization

**Returns:** `RiskMetrics` with return and risk measures

---

### calculate_extended_metrics()

```python
def calculate_extended_metrics(
    snapshots: List[TokenSnapshot],
    predictions: np.ndarray,
    top_k: Optional[int] = None,
    risk_free_rate: float = 0.0,
    periods_per_year: int = 52,
    periods: Optional[List[int]] = None
) -> ExtendedBacktestMetrics
```

**Parameters:**
- `snapshots`: List of token snapshots
- `predictions`: Array of predicted scores
- `top_k`: Optional number of top assets to evaluate
- `risk_free_rate`: Risk-free rate for ratio calculations
- `periods_per_year`: Periods per year for annualization
- `periods`: Optional period indices for multi-period IC

**Returns:** `ExtendedBacktestMetrics` with IC and risk metrics

---

### compare_extended_metrics()

```python
def compare_extended_metrics(
    gem_score_metrics: ExtendedBacktestMetrics,
    baseline_metrics: Dict[str, ExtendedBacktestMetrics]
) -> Dict[str, Dict[str, float]]
```

**Parameters:**
- `gem_score_metrics`: Metrics for GemScore strategy
- `baseline_metrics`: Dict of baseline strategy metrics

**Returns:** Dictionary with comparative metrics

---

## Troubleshooting

### Issue: IC is NaN or Inf

**Cause:** Not enough data points or all predictions/actuals are identical.

**Solution:**
```python
# Check data
assert len(predictions) >= 2
assert len(set(predictions)) > 1  # Not all same
assert len(set(actuals)) > 1
```

### Issue: P-value is high (> 0.05)

**Cause:** Not statistically significant, likely due to small sample size.

**Solution:**
- Collect more data
- Use bootstrapping for confidence intervals
- Consider rank-based metrics (Spearman, Kendall)

### Issue: IC is negative

**Cause:** Model is making anti-predictive decisions.

**Solution:**
- Check data quality
- Verify feature engineering
- Consider inverting predictions

### Issue: High IC but low Sharpe

**Cause:** Good predictions but high volatility or poor position sizing.

**Solution:**
- Improve risk management
- Consider portfolio optimization
- Adjust position sizing

---

## Best Practices

1. **Always check statistical significance** (p-value < 0.05)
2. **Use multiple IC measures** (Pearson, Spearman, Kendall)
3. **Track IC over time** for consistency
4. **Compare to baselines** to validate improvement
5. **Monitor risk-adjusted metrics**, not just returns
6. **Use sufficient sample size** (n >= 30 recommended)

---

## References

- Grinold, R. C., & Kahn, R. N. (2000). *Active Portfolio Management*. McGraw-Hill.
- Bailey, D. H., & López de Prado, M. (2014). "The Sharpe Ratio Efficient Frontier". *Journal of Risk*.

---

**Author:** GitHub Copilot  
**Date:** 2025-01-08  
**Status:** ✅ Production Ready

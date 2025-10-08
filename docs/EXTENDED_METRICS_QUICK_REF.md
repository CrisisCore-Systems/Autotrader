# Extended Backtest Metrics - Quick Reference

**Information Coefficient (IC) & Risk-Adjusted Performance**

---

## Quick Start

```python
from backtest.extended_metrics import calculate_extended_metrics

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

---

## CLI Usage

```bash
# Basic extended metrics
python backtest/harness.py data.csv --extended-metrics

# With baselines and extended metrics
python backtest/harness.py data.csv --compare-baselines --extended-metrics --seed 42
```

---

## Key Metrics Cheat Sheet

### Information Coefficient (IC)

| Metric | Formula | Interpretation |
|--------|---------|----------------|
| **Pearson IC** | `corr(predictions, returns)` | IC > 0.05: Strong, IC > 0.02: Moderate |
| **Spearman IC** | `rank_corr(predictions, returns)` | Robust to outliers |
| **Kendall Tau** | `tau(predictions, returns)` | Conservative rank correlation |
| **Hit Rate** | `% correct direction` | > 60%: Strong, > 55%: Good |
| **IC IR** | `mean(IC) / std(IC)` | > 1.0: Consistent, > 0.5: Moderate |

### Risk-Adjusted Metrics

| Metric | Formula | Good Value |
|--------|---------|------------|
| **Sharpe Ratio** | `(Return - RFR) / Volatility` | > 2.0: Excellent, > 1.0: Good |
| **Sortino Ratio** | `(Return - RFR) / Downside Dev` | > 2.0: Excellent, > 1.0: Good |
| **Calmar Ratio** | `Return / |Max Drawdown|` | > 3.0: Excellent, > 1.0: Good |
| **Max Drawdown** | `min(peak - trough)` | Lower is better |
| **Win Rate** | `% positive returns` | > 60%: High, 40-60%: Typical |
| **Profit Factor** | `Σ(wins) / |Σ(losses)|` | > 2.0: Excellent, > 1.0: Profitable |

---

## Interpretation Quick Guide

### Strong Performance ✅
```
IC Pearson: 0.08
Sharpe: 2.5
Hit Rate: 65%
P-value: < 0.05
```
→ Deploy with confidence

### Moderate Performance ⚠️
```
IC Pearson: 0.03
Sharpe: 1.2
Hit Rate: 56%
P-value: < 0.05
```
→ Deploy with monitoring

### Weak Performance ❌
```
IC Pearson: 0.01
Sharpe: 0.5
Hit Rate: 52%
P-value: > 0.05
```
→ Do not deploy

---

## Code Examples

### Calculate IC Only

```python
from backtest.extended_metrics import calculate_ic_metrics

ic = calculate_ic_metrics(predictions, actual_returns)
print(f"IC: {ic.ic_pearson:.4f} (p={ic.ic_pearson_pvalue:.4f})")
print(f"Hit Rate: {ic.hit_rate:.2%}")
```

### Calculate Risk Metrics Only

```python
from backtest.extended_metrics import calculate_risk_metrics

risk = calculate_risk_metrics(returns, risk_free_rate=0.0)
print(f"Sharpe: {risk.sharpe_ratio:.4f}")
print(f"Max DD: {risk.max_drawdown:.4f}")
```

### Compare with Baselines

```python
from backtest.extended_metrics import compare_extended_metrics

comparisons = compare_extended_metrics(gem_score_metrics, baseline_metrics)
for baseline, comp in comparisons.items():
    print(f"{baseline}: IC improvement {comp['ic_improvement']:+.4f}")
```

### Multi-Period IC

```python
periods = [1, 1, 1, 2, 2, 2, 3, 3, 3]  # Period labels
ic = calculate_ic_metrics(predictions, actuals, periods=periods)
print(f"Mean IC: {ic.ic_mean:.4f}")
print(f"IC IR: {ic.ic_ir:.4f}")
```

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| IC is NaN | Check: len(predictions) >= 2, not all same values |
| P-value > 0.05 | Need more data or use rank-based metrics |
| Negative IC | Check data quality, consider inverting predictions |
| High IC, low Sharpe | Improve risk management, position sizing |

---

## Statistical Significance

| P-value | Interpretation | Action |
|---------|----------------|--------|
| < 0.01 | Highly significant | ✅ Deploy |
| < 0.05 | Significant | ✅ Deploy |
| < 0.10 | Marginally significant | ⚠️ Monitor |
| >= 0.10 | Not significant | ❌ Do not deploy |

---

## IC Benchmarks (Quantitative Finance)

| Asset Class | Typical IC | Notes |
|-------------|-----------|-------|
| Equities | 0.02 - 0.05 | Long-only strategies |
| Crypto | 0.03 - 0.08 | Higher volatility, more opportunities |
| Fixed Income | 0.01 - 0.03 | Lower volatility |
| Factor Models | 0.04 - 0.10 | Well-researched factors |

---

## Jupyter Notebook Example

See `notebooks/hidden_gem_scanner.ipynb` Section 9 for:
- IC calculation and visualization
- Risk metrics analysis
- Baseline comparisons
- Multi-period IC analysis
- Interpretation examples

---

## Files Created

- **Module:** `backtest/extended_metrics.py` (520 lines)
- **Tests:** `tests/test_extended_metrics.py` (590 lines, 29 tests, 100% pass)
- **Docs:** `docs/EXTENDED_BACKTEST_METRICS.md` (comprehensive guide)
- **Updated:** `backtest/harness.py` (extended metrics integration)
- **Notebook:** Section 9 in `notebooks/hidden_gem_scanner.ipynb`

---

## Performance Tips

1. **Sample Size:** Use n >= 30 for reliable statistics
2. **Outliers:** Use Spearman IC when returns have outliers
3. **Multiple Periods:** Calculate IC IR to assess consistency
4. **Baselines:** Always compare to random/simple strategies
5. **Statistical Tests:** Check p-values for significance

---

## Further Reading

- Full documentation: `docs/EXTENDED_BACKTEST_METRICS.md`
- Baseline strategies: `docs/BASELINE_STRATEGIES.md`
- Test examples: `tests/test_extended_metrics.py`

---

**Status:** ✅ Production Ready  
**Test Coverage:** 29 tests, 100% pass rate  
**Date:** 2025-01-08

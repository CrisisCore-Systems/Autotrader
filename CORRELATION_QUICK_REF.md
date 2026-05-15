# Correlation Analysis in Market Regime Classification — Quick Reference

## What's New?

The regime classifier now supports **rolling correlation analysis** to identify synchronized movement patterns across crypto assets. This enables:

- ✅ Multi-symbol correlation tracking
- ✅ Correlation-based regime refinement
- ✅ Pair/decorrelation trading signals
- ✅ Portfolio correlation monitoring

## Quick Start

### 1. Single Symbol (No Correlation)
```bash
python scripts/classify_market_regime.py
```

### 2. Multiple Symbols with Correlation
```bash
python scripts/classify_market_regime.py \
    --symbols BTC/USD,ETH/USD,SOL/USD \
    --compute-correlations
```

### 3. Programmatic API
```python
from scripts.classify_market_regime import (
    classify_regimes,
    classify_correlation_regimes,
    compute_rolling_correlations,
)

# Step 1: Load returns for multiple symbols
returns = {
    "BTC/USD": df_btc["ret_1"],
    "ETH/USD": df_eth["ret_1"],
}

# Step 2: Compute rolling correlations
rolling_corr = compute_rolling_correlations(returns, window=96)

# Step 3: Classify and refine regimes
df_classified = classify_regimes(df_btc, window=96)
df_with_corr = classify_correlation_regimes(
    df_classified,
    rolling_corr,
    "BTC/USD",
)
```

## Output Schema

### New Columns (when correlation enabled)

| Column | Type | Range | Meaning |
|--------|------|-------|---------|
| `mean_correlation` | float | [-1, 1] | Average rolling corr with other symbols |
| `corr_regime` | str | 3 values | Correlation classification |

### Correlation Regimes

| Regime | Correlation | Interpretation |
|--------|------------|-----------------|
| `high_correlation_sync` | > 0.7 (default) | Moving together; avoid mean-reversion |
| `neutral_correlation` | 0.3 to 0.7 | Standard regime rules apply |
| `decorrelation_risk` | < 0.3 (default) | Moving independently; pair trade opportunity |

## CLI Reference

```
--compute-correlations          Enable multi-symbol correlation analysis
--symbols SYM1,SYM2,...         Symbols to process (required for correlations)
--window N                      Volatility/autocorr window (bars, default 96)
--corr-window N                 Correlation window (default = --window)
--corr-threshold-high FLOAT     High-correlation threshold (default 0.7)
--corr-threshold-low FLOAT      Low-correlation threshold (default 0.3)
```

## Common Use Cases

### Detect Synchronized Movement
```bash
python scripts/classify_market_regime.py \
    --symbols BTC/USD,ETH/USD,SOL/USD \
    --compute-correlations \
    --summary
```
→ Look for bars with `corr_regime = high_correlation_sync`

### Find Decorrelation Opportunities
```bash
# When historically correlated assets diverge
python scripts/classify_market_regime.py \
    --symbols BTC/USD,ETH/USD \
    --compute-correlations \
    --corr-threshold-high 0.75 \
    --corr-threshold-low 0.25
```

### Adjust Position Sizing by Correlation
```python
if mean_correlation > 0.7:
    position_size *= 0.7  # Reduce for redundant exposure
elif mean_correlation < 0.3:
    position_size *= 1.2  # Increase for isolated movement
```

## Performance Tips

| Scenario | Optimization |
|----------|--------------|
| 2–3 symbols | No optimization needed |
| 5–10 symbols | Use reasonable window (96+) |
| 10+ symbols | Filter to most relevant or use async |
| Real-time | Pre-cache correlations; update incrementally |

## Data Requirements

- At least **2 symbols** for correlation analysis
- Each symbol needs return series (`ret_1` column)
- Minimum **window** bars of data per symbol
- Overlapping time periods (auto-aligned)

## Troubleshooting

**"0 correlation pairs computed"**
- Need ≥2 symbols: `--symbols SYM1,SYM2`
- Data length < window: increase bar count

**NaN in `mean_correlation`**
- Symbol has no correlated pairs
- Check data alignment across symbols

**Slow execution**
- O(N²) complexity for N symbols
- 10 symbols = 45 pairs; consider filtering

## References

- **Correlation:** Pearson correlation coefficient
- **Regimes:** Parkinson volatility + sign-autocorrelation
- **Window:** Default 96 bars (24h at 15-min)

---

**See:** [CORRELATION_ANALYSIS_GUIDE.md](CORRELATION_ANALYSIS_GUIDE.md) for full documentation  
**Example:** `examples/regime_correlation_example.py`

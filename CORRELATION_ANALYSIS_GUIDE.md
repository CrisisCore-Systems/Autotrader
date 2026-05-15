# Correlation Analysis Integration for Market Regime Classification

## Overview

The enhanced `classify_market_regime.py` script now includes **multi-symbol rolling correlation analysis**, enabling traders to identify synchronized movement patterns across crypto assets and refine regime classification based on correlation structure.

## New Features

### 1. Rolling Correlation Computation

**Function:** `compute_rolling_correlations(returns_dict, window)`

Computes pairwise rolling correlations between all symbol return series over a specified lookback window.

**Parameters:**
- `returns_dict`: Dict mapping symbol names to return series
- `window`: Rolling window in bars (default 96 = 24h at 15-min timeframe)

**Output:**
- Dict of `(symbol_a, symbol_b) → rolling_correlation_series`

**Example:**
```python
from scripts.classify_market_regime import compute_rolling_correlations
import pandas as pd

returns_data = {
    "BTC/USD": df_btc["ret_1"],
    "ETH/USD": df_eth["ret_1"],
    "SOL/USD": df_sol["ret_1"],
}

corr_dict = compute_rolling_correlations(returns_data, window=96)

# Access BTC-ETH correlation
btc_eth_corr = corr_dict[("BTC/USD", "ETH/USD")]
```

### 2. Correlation-Based Regime Classification

**Function:** `classify_correlation_regimes(df, rolling_correlations, symbol, corr_threshold_high, corr_threshold_low)`

Adds correlation-based regime classification to an existing regime-classified dataframe.

**Parameters:**
- `df`: Regime-classified dataframe (output of `classify_regimes()`)
- `rolling_correlations`: Dict from `compute_rolling_correlations()`
- `symbol`: Symbol name to classify
- `corr_threshold_high`: Correlation threshold for "sync" (default 0.7)
- `corr_threshold_low`: Correlation threshold for "decorrelation" (default 0.3)

**New Columns Added:**
- `mean_correlation`: Average rolling correlation with other symbols
- `corr_regime`: Classification into one of three states:
  - `high_correlation_sync`: Strong positive correlation (>0.7)
  - `neutral_correlation`: Mid-range correlation (0.3–0.7)
  - `decorrelation_risk`: Weak/negative correlation (<0.3)

**Example:**
```python
from scripts.classify_market_regime import (
    classify_regimes,
    classify_correlation_regimes,
    compute_rolling_correlations,
)

# Step 1: Classify base regimes
classified = classify_regimes(df_btc, window=96)

# Step 2: Compute correlations (requires multiple symbols)
rolling_corr = compute_rolling_correlations(
    {"BTC/USD": returns_btc, "ETH/USD": returns_eth},
    window=96
)

# Step 3: Apply correlation-based refinement
classified_with_corr = classify_correlation_regimes(
    classified,
    rolling_corr,
    "BTC/USD",
    corr_threshold_high=0.7,
    corr_threshold_low=0.3,
)

# Now columns include:
# - regime (original: mean_reversion / momentum_trend / liquidity_void)
# - mean_correlation (float: -1.0 to 1.0)
# - corr_regime (new: high_correlation_sync / neutral_correlation / decorrelation_risk)
```

### 3. CLI Usage

#### Basic single-symbol regime classification (no correlation)
```bash
python scripts/classify_market_regime.py \
    --input-dir data/crypto/features \
    --output-dir data/crypto/regime
```

#### Multi-symbol classification with correlation analysis
```bash
python scripts/classify_market_regime.py \
    --input-dir data/crypto/features \
    --output-dir data/crypto/regime \
    --symbols BTC/USD,ETH/USD,SOL/USD \
    --compute-correlations
```

#### Custom correlation thresholds
```bash
python scripts/classify_market_regime.py \
    --symbols BTC/USD,ETH/USD \
    --compute-correlations \
    --corr-threshold-high 0.75 \
    --corr-threshold-low 0.25 \
    --corr-window 96
```

#### Full parameter breakdown
```bash
python scripts/classify_market_regime.py \
    --input-dir data/crypto/features              # Source feature files
    --output-dir data/crypto/regime              # Output destination
    --symbols BTC/USD,ETH/USD                    # Limit to these symbols
    --window 96                                   # Base volatility window (bars)
    --compute-correlations                        # Enable correlation analysis
    --corr-window 96                              # Correlation window (default = --window)
    --corr-threshold-high 0.7                    # High-sync threshold
    --corr-threshold-low 0.3                     # Low-decorr threshold
    --park-void-pct 95.0                         # Liquidity void threshold
    --park-trend-pct 70.0                        # Momentum trend threshold
    --min-volume-intensity 0.15                  # Volume filter
    --summary                                     # Print table (default)
    --write-parquet                              # Write output files (default)
```

## Output Format

### Parquet Columns (per symbol)

When correlation analysis is enabled, the output parquet includes:

**Price Action Regime Columns:**
- `park_var` – Parkinson variance (per-bar)
- `rs_var` – Rogers-Satchell variance (per-bar)
- `park_vol_roll` – Rolling Parkinson volatility
- `rs_vol_roll` – Rolling Rogers-Satchell volatility
- `park_vol_ann` – Annualized Parkinson volatility
- `rs_vol_ann` – Annualized Rogers-Satchell volatility
- `sign_autocorr` – Return sign-autocorrelation
- `regime` – Primary classification (mean_reversion / momentum_trend / liquidity_void)

**Correlation Columns:**
- `mean_correlation` – Average rolling correlation with other symbols
- `corr_regime` – Correlation-based classification (high_correlation_sync / neutral_correlation / decorrelation_risk)

### Summary JSON

`regime_summary_*.json` includes:

```json
{
  "stage": "regime-classify",
  "timestamp_utc": "2024-10-28T15:30:00+00:00",
  "window": 96,
  "park_void_pct": 95.0,
  "park_trend_pct": 70.0,
  "compute_correlations": true,
  "num_correlation_pairs": 3,
  "symbols": [
    {
      "symbol": "BTC/USD",
      "total_bars": 10000,
      "current_regime": "momentum_trend",
      "last_park_vol_ann": 0.6234,
      "last_rs_vol_ann": 0.5891,
      "last_sign_autocorr": 0.1234,
      "last_mean_correlation": 0.6543,
      "current_corr_regime": "high_correlation_sync",
      "distribution": { ... },
      "corr_distribution": {
        "high_correlation_sync": {"count": 6234, "pct": 62.3},
        "neutral_correlation": {"count": 3100, "pct": 31.0},
        "decorrelation_risk": {"count": 666, "pct": 6.7}
      }
    }
  ]
}
```

## Trading Applications

### 1. Regime-Aware Position Sizing

Adjust position size based on both price action and correlation regime:

```python
# pseudo-code
if regime == "momentum_trend" and corr_regime == "high_correlation_sync":
    position_size = base_size * 0.75  # Reduce for correlated momentum
elif regime == "mean_reversion" and corr_regime == "decorrelation_risk":
    position_size = base_size * 1.25  # Increase for uncorrelated reversal
elif corr_regime == "high_correlation_sync":
    position_size = base_size * 0.8   # Reduce redundant correlation exposure
```

### 2. Pair/Correlation Trading

Identify divergences in correlated pairs:

```python
# When BTC and ETH typically correlate >0.7 but drop to <0.3:
if historical_corr > 0.7 and current_corr < 0.3:
    # Pair trade: long the laggard, short the leader
    trade_signal = "decorrelation_opportunity"
```

### 3. Portfolio Hedging

Monitor correlation regime shifts to adjust hedges:

```python
# If correlation_regime transitions from "high_correlation_sync" to "decorrelation_risk":
# Individual assets are moving independently → reduce portfolio hedge ratio
```

### 4. Volatility Surface Tracking

Use correlation changes as volatility regime indicators:

```python
if sign_autocorr > 0.1 and mean_correlation < 0.2:
    # Low correlation + trending returns = potential localized volatility event
    adjust_vega_exposure()
```

## Performance Notes

### Computation Cost

- **Single-symbol regime classification:** ~0.1–0.5 ms per bar
- **Correlation computation (N symbols):** O(N²) pairs, ~5–20 ms per bar for 5–10 symbols
- **Full pipeline (10 symbols, 10k bars):** ~1–2 seconds total

### Memory Usage

Correlation analysis loads all symbols' return series into memory. For ~10k bars × 10 symbols:
- Base regime: ~10 MB per symbol
- Correlations: ~30–50 MB additional (sparse dict of correlation pairs)

## Integration with Execution Pipeline

To wire correlation analysis into the main crypto strategy pipeline:

```python
# In crypto_strategy.py or execution layer:

from scripts.classify_market_regime import (
    classify_regimes,
    classify_correlation_regimes,
    compute_rolling_correlations,
    load_regime_config,
)

def get_active_policy(bar_data, all_symbols_returns):
    """Merge regime + correlation for final execution policy."""
    
    # Classify base regime
    regime_classified = classify_regimes(bar_data)
    
    # Add correlation if multi-symbol
    if len(all_symbols_returns) > 1:
        rolling_corr = compute_rolling_correlations(
            all_symbols_returns,
            window=96
        )
        regime_classified = classify_correlation_regimes(
            regime_classified,
            rolling_corr,
            symbol=bar_data["symbol"].iloc[-1],
        )
    
    # Load regime config and resolve policy
    regime_config = load_regime_config(Path("configs/crypto_strategy.yaml"))
    current_regime = regime_classified["regime"].iloc[-1]
    current_corr_regime = regime_classified.get("corr_regime", "neutral_correlation").iloc[-1]
    
    # Merge policies: base regime + correlation overlay
    base_policy = resolve_regime_policy(current_regime, regime_config, ...)
    
    # Apply correlation-based tweaks
    if current_corr_regime == "high_correlation_sync":
        base_policy["position_size_mult"] = 0.8
    elif current_corr_regime == "decorrelation_risk":
        base_policy["position_size_mult"] = 1.2
    
    return base_policy
```

## Troubleshooting

### "Computed correlations for 0 symbol pairs"
- **Cause:** Only one symbol provided or data length < correlation window
- **Fix:** Use `--compute-correlations` with ≥2 symbols, or increase data length

### NaN values in `mean_correlation`
- **Cause:** Symbol has insufficient overlapping data with other symbols
- **Fix:** Check data alignment and ensure all symbols span same time period

### Slow execution with many symbols
- **Cause:** O(N²) correlation pairs; with 10 symbols = 45 pairs
- **Fix:** Filter to most relevant symbols or increase window size (trades precision for speed)

## API Reference

### `compute_rolling_correlations(returns_dict: dict[str, pd.Series], window: int) → dict[tuple[str, str], pd.Series]`

Compute rolling Pearson correlations between all symbol pairs.

**Parameters:**
- `returns_dict`: Symbol → return series mapping
- `window`: Lookback window in bars

**Returns:**
- Dict of (symbol_a, symbol_b) → rolling correlation series (symbols sorted lexicographically)

---

### `classify_correlation_regimes(df: pd.DataFrame, rolling_correlations: dict, symbol: str, corr_threshold_high: float = 0.7, corr_threshold_low: float = 0.3) → pd.DataFrame`

Classify correlation regimes and add columns to dataframe.

**Parameters:**
- `df`: Regime-classified dataframe
- `rolling_correlations`: Output from `compute_rolling_correlations()`
- `symbol`: Symbol to classify
- `corr_threshold_high`: High-correlation threshold
- `corr_threshold_low`: Low-correlation threshold

**Returns:**
- Input df with added columns: `mean_correlation`, `corr_regime`

---

### `regime_summary(df: pd.DataFrame, symbol: str = "") → dict[str, Any]`

Generate summary statistics including correlation metrics.

**Parameters:**
- `df`: Classified dataframe
- `symbol`: Symbol name (for reporting)

**Returns:**
- Dict with keys: `symbol`, `current_regime`, `current_corr_regime`, `last_mean_correlation`, `distribution`, `corr_distribution`

---

## References

- Volatility estimators: Parkinson (1980), Rogers & Satchell (1991)
- Sign-autocorrelation momentum indicator: momentum/mean-reversion proxy
- Pearson correlation: Standard financial correlation metric
- Regime-switching models: Hamilton (1989), Guidolin & Timmermann (2007)

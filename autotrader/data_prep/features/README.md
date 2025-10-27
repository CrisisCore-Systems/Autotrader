# Feature Engineering — Quick Start Guide

**Phase 3 Week 5**: Modular feature extraction for HFT/intraday trading strategies

---

## 📋 Table of Contents

1. [Feature Extractors](#feature-extractors)
2. [Quick Start](#quick-start)
3. [Configuration Presets](#configuration-presets)
4. [Advanced Usage](#advanced-usage)
5. [Integration with Labeling](#integration-with-labeling)
6. [Testing](#testing)
7. [Troubleshooting](#troubleshooting)

---

## Feature Extractors

| Extractor | Features | Description |
|-----------|----------|-------------|
| **TechnicalFeatureExtractor** | 7 | Classic technical indicators (RSI, MACD, Bollinger Bands, ATR) |
| **RollingFeatureExtractor** | 6 × N windows | Rolling statistics (returns, volatility, percentiles, z-scores) |
| **TemporalFeatureExtractor** | 11 | Time-based features (hour, day-of-week, sessions, cyclical encoding) |
| **OrderBookFeatureExtractor** | 15 | Microstructure features (spread, depth, flow toxicity) — requires orderbook data |
| **FeatureFactory** | Configurable | Unified pipeline composing all extractors |

---

## Quick Start

### 1. Basic Feature Extraction

```python
from autotrader.data_prep.features import FeatureFactory, FeatureConfig
import pandas as pd

# Load your bar data (OHLCV + timestamp)
bars = pd.read_csv("bars.csv")

# Extract features with balanced preset
factory = FeatureFactory(config=FeatureConfig.balanced())
features = factory.extract_all(bars)

print(f"Extracted {len(features.columns)} features")
print(features.head())
```

**Output:**
```
Extracted 36 features
         rsi  macd_line  macd_signal  macd_histogram  bb_upper_pct  ...
0      50.2       0.12         0.08            0.04          0.62  ...
1      52.1       0.15         0.10            0.05          0.58  ...
...
```

### 2. Individual Extractors

```python
from autotrader.data_prep.features import TechnicalFeatureExtractor

# Just technical indicators
extractor = TechnicalFeatureExtractor()
tech_features = extractor.extract_all(bars)

# Get feature names
print(extractor.get_feature_names())
# ['rsi', 'macd_line', 'macd_signal', 'macd_histogram', 'bb_upper_pct', 'bb_lower_pct', 'atr']
```

### 3. Custom Configuration

```python
config = FeatureConfig(
    enable_technical=True,
    enable_rolling=True,
    enable_temporal=False,  # Disable temporal features
    rolling_windows=[10, 30, 100],  # Custom windows
    rsi_period=10,  # Aggressive RSI
    fill_method="zero",  # Fill NaN with zero
    min_valid_features=0.6
)

factory = FeatureFactory(config=config)
features = factory.extract_all(bars)
```

---

## Configuration Presets

### Conservative
**Use case:** Stable markets, longer-term strategies

```python
config = FeatureConfig.conservative()
# - Rolling windows: [50, 200]
# - RSI period: 20
# - BB period: 30
# - ATR period: 20
# - Total: 30 features
```

### Balanced (Default)
**Use case:** General-purpose

```python
config = FeatureConfig.balanced()
# - Rolling windows: [20, 50, 200]
# - RSI period: 14
# - BB period: 20
# - ATR period: 14
# - Total: 36 features
```

### Aggressive
**Use case:** Volatile markets, short-term strategies

```python
config = FeatureConfig.aggressive()
# - Rolling windows: [10, 20, 50]
# - RSI period: 10
# - BB period: 15
# - ATR period: 10
# - Total: 36 features
```

---

## Advanced Usage

### NaN Handling

```python
# Option 1: Forward fill (carry last valid value)
config = FeatureConfig(fill_method="forward")

# Option 2: Zero fill
config = FeatureConfig(fill_method="zero")

# Option 3: Drop rows with NaN
config = FeatureConfig(fill_method="drop")
```

### Selective Features

```python
# Only technical + rolling (no temporal)
config = FeatureConfig(
    enable_technical=True,
    enable_rolling=True,
    enable_temporal=False
)

# Only rolling with custom windows
config = FeatureConfig(
    enable_technical=False,
    enable_rolling=True,
    enable_temporal=False,
    rolling_windows=[5, 10, 20]
)
```

### Orderbook Features (Optional)

```python
# Requires orderbook + trade data
config = FeatureConfig(enable_orderbook=True)
factory = FeatureFactory(config=config)

features = factory.extract_all(
    bars_df=bars,
    order_book_df=orderbook,  # Required!
    trade_df=trades
)
```

---

## Integration with Labeling

Combine features with Week 4 labeling for ML-ready datasets:

```python
from autotrader.data_prep.features import FeatureFactory, FeatureConfig
from autotrader.data_prep.labeling import LabelFactory, CostModel

# 1. Extract features
feature_factory = FeatureFactory(config=FeatureConfig.balanced())
features = feature_factory.extract_all(bars)

# 2. Generate labels
cost_model = CostModel.from_ibkr(rebate_bps=0.5)
label_factory = LabelFactory(
    mode="classification",
    horizon_seconds=30,
    cost_model=cost_model
)
labels = label_factory.generate_labels(bars, cost_model=cost_model)

# 3. Combine for ML
ml_data = pd.concat([features, labels["label"]], axis=1).dropna()

print(f"ML dataset: {len(ml_data)} samples × {len(ml_data.columns)} columns")
```

---

## Testing

### Standalone Validation

```powershell
# Check imports work
python run_feature_tests.py --check

# Run 5 standalone validation tests
python run_feature_tests.py --validate

# Run full pytest suite
python run_feature_tests.py --pytest
```

### Expected Output

```
======================================================================
               FEATURE EXTRACTION VALIDATION
======================================================================

Test 1: Basic Feature Extraction ✓
Test 2: Feature Range Validation ✓
Test 3: NaN Handling ✓
Test 4: Performance Budget ✓
Test 5: Configuration Presets ✓

======================================================================
✅ ALL VALIDATION TESTS PASSED (5/5)
======================================================================
```

---

## Troubleshooting

### Error: "bars_df must have at least N rows"

**Cause:** Not enough data for longest rolling window

**Solution:** Either reduce window size or provide more data

```python
# Option 1: Shorter windows
config = FeatureConfig(rolling_windows=[10, 20, 50])

# Option 2: Use more bars (need 200+ for default config)
bars = load_more_data()
```

### Error: "Only X% of features are valid (minimum required: Y%)"

**Cause:** Too many NaN values after extraction

**Solution:** Relax `min_valid_features` threshold or use more data

```python
config = FeatureConfig(min_valid_features=0.6)  # Default: 0.7
```

### Warning: "DataFrame.fillna with 'method' is deprecated"

**Fixed in latest version.** We now use `.ffill()` instead.

### Slow Performance

**Expected:** ~1,700 rows/sec (0.6s for 1,000 bars)

If slower:
1. Check rolling window sizes (larger windows = slower)
2. Disable unnecessary extractors
3. Use fewer rolling windows

```python
# Faster configuration
config = FeatureConfig(
    rolling_windows=[20, 50],  # Fewer windows
    enable_temporal=False  # Disable if not needed
)
```

---

## Column Name Reference

### Technical Indicators (7)

```python
[
    'rsi',                  # Relative Strength Index [0, 100]
    'macd_line',            # MACD line (ℝ)
    'macd_signal',          # MACD signal line (ℝ)
    'macd_histogram',       # MACD histogram (ℝ)
    'bb_upper_pct',         # Upper Bollinger Band distance [0, 1]
    'bb_lower_pct',         # Lower Bollinger Band distance [0, 1]
    'atr'                   # Average True Range (ℝ⁺)
]
```

### Rolling Statistics (6 per window)

```python
[
    'roll_20_log_return',      # Log return
    'roll_20_simple_return',   # Simple return
    'roll_20_volatility',      # Realized volatility
    'roll_20_parkinson_vol',   # Parkinson volatility
    'roll_20_percentile',      # Percentile rank [0, 1]
    'roll_20_zscore',          # Z-score (ℝ)
    # (same for roll_50_* and roll_200_*)
]
```

### Temporal Features (11)

```python
[
    'hour_sin', 'hour_cos',              # Hour cycle [-1, 1]
    'minute_sin', 'minute_cos',          # Minute cycle [-1, 1]
    'day_of_week_sin', 'day_of_week_cos',  # Day cycle [-1, 1]
    'is_market_open',                    # Regular session {0, 1}
    'is_morning',                        # Morning session {0, 1}
    'is_afternoon',                      # Afternoon session {0, 1}
    'is_close',                          # Last 30 min {0, 1}
    'is_weekend'                         # Weekend {0, 1}
]
```

---

## Example: Complete Pipeline

```python
from autotrader.data_prep.features import FeatureFactory, FeatureConfig
import pandas as pd

# 1. Load data
bars = pd.read_csv("1min_bars.csv")
print(f"Loaded {len(bars)} bars")

# 2. Configure feature extraction
config = FeatureConfig.balanced()

# 3. Extract features
factory = FeatureFactory(config=config)
features = factory.extract_all(bars)

# 4. Check output
print(f"\nFeatures extracted: {len(features.columns)}")
print(f"NaN percentage: {features.isna().mean().mean():.1%}")
print(f"\nFirst 5 features:")
print(features.iloc[:, :5].head())

# 5. Save for later use
features.to_csv("features.csv", index=False)
print("\n✓ Features saved to features.csv")
```

---

## Performance Benchmarks

| Data Size | Time | Throughput |
|-----------|------|------------|
| 100 bars | ~0.1s | ~1,000 rows/s |
| 1,000 bars | ~0.6s | ~1,700 rows/s |
| 10,000 bars | ~6.0s | ~1,700 rows/s |

**Hardware:** Standard laptop (Intel i7, 16GB RAM)

---

## See Also

- **PHASE_3_WEEK_5_COMPLETE.md**: Executive summary with full documentation
- **PHASE_3_WEEK_4_COMPLETE.md**: Labeling infrastructure (combines with features)
- **test_feature_contracts.py**: Feature name reference and API contracts

---

**Questions?** Check `PHASE_3_WEEK_5_COMPLETE.md` for comprehensive documentation.

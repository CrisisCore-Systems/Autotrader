# Feature Store & Leakage Prevention Guide

## Overview

**Lookahead bias** (using future data) is the #1 fatal flaw in quantitative backtests. A single leaky feature can make a strategy appear profitable when it will lose money in live trading.

This guide explains how to use `FeatureStore` to prevent lookahead bias and ensure production-ready features.

---

## The Problem: Lookahead Bias

### Example of Leakage:

```python
# ❌ BAD: Using current bar's close for feature
df['sma_20'] = df['close'].rolling(20).mean()

# At time t, this uses close[t] to predict return[t]
# But in live trading, you don't know close[t] until bar closes!
```

### Correct Approach:

```python
# ✅ GOOD: Shift by 1 to use only past data
df['sma_20'] = df['close'].rolling(20).mean().shift(1)

# At time t, this uses close[t-1] to predict return[t]
# This matches live trading reality
```

---

## FeatureStore: Automatic Leakage Prevention

`FeatureStore` handles shifting automatically:

```python
from autotrader.data_prep.features import FeatureStore

store = FeatureStore()

# Register feature (NO manual shift needed)
store.add_feature(
    name='sma_20',
    compute_fn=lambda df: df['close'].rolling(20).mean(),
    warm_up_periods=20
)

# Extract features (automatically shifted by 1)
features = store.compute_features(
    df=bars,
    validate_leakage=True  # Check for lookahead bias
)

# features['sma_20'] at time t uses data up to t-1
```

---

## Key Concepts

### 1. Strict Causality

**Rule**: Features at time t must use only data up to time t-1.

| Time | close | sma_20 (BAD) | sma_20 (GOOD) |
|------|-------|--------------|---------------|
| t-2  | 100   | NaN          | NaN           |
| t-1  | 102   | 101          | NaN           |
| t    | 104   | 102          | 101           |
| t+1  | 103   | 103          | 102           |

- **BAD**: sma_20[t] = mean(close[t-19:t]) ← includes close[t]
- **GOOD**: sma_20[t] = mean(close[t-20:t-1]) ← excludes close[t]

### 2. Warm-Up Periods

**Definition**: Minimum rows required before feature is valid.

```python
store.add_feature(
    name='sma_20',
    compute_fn=lambda df: df['close'].rolling(20).mean(),
    warm_up_periods=20  # Need 20 bars of history
)

# If df has only 15 rows, this will raise ValueError
features = store.compute_features(df)
```

**Why it matters**: Features like SMA need history. Don't use features with NaN!

### 3. Leakage Detection

`validate_no_leakage()` checks for backward correlation:

```python
# Check if features[t] correlate with target[t-1]
# If yes, features are using future data
suspicious = store.validate_no_leakage(
    df=bars,
    features=features,
    target=returns,
    max_allowed_correlation=0.1
)

if suspicious:
    print("⚠️ WARNING: Potential lookahead bias!")
    for feat, corr in suspicious.items():
        print(f"  {feat}: backward_corr={corr:.4f}")
```

**Interpretation**:
- **Low backward correlation** (|r| < 0.1): Probably safe
- **High backward correlation** (|r| > 0.1): Suspicious, investigate

---

## Common Leakage Patterns

### Pattern 1: Using Current Bar

```python
# ❌ BAD: Using current close
df['return_today'] = df['close'].pct_change()

# ✅ GOOD: Using previous close
df['return_yesterday'] = df['close'].pct_change().shift(1)
```

### Pattern 2: Rolling Windows Without Shift

```python
# ❌ BAD: Includes current bar
df['vol_20'] = df['close'].pct_change().rolling(20).std()

# ✅ GOOD: Excludes current bar
df['vol_20'] = df['close'].pct_change().rolling(20).std().shift(1)
```

### Pattern 3: Forward-Looking Functions

```python
# ❌ BAD: Using future highs
df['future_high'] = df['high'].rolling(5).max().shift(-5)

# ✅ GOOD: Using past highs
df['past_high'] = df['high'].rolling(5).max().shift(1)
```

### Pattern 4: Global Statistics

```python
# ❌ BAD: Using entire dataset statistics
df['z_score'] = (df['close'] - df['close'].mean()) / df['close'].std()

# ✅ GOOD: Using expanding window
df['z_score'] = (
    (df['close'] - df['close'].expanding().mean()) /
    df['close'].expanding().std()
).shift(1)
```

---

## Using FeatureStore

### Basic Workflow

```python
from autotrader.data_prep.features import FeatureStore

# 1. Create store
store = FeatureStore(cache_dir='./cache')

# 2. Register features
store.add_feature(
    name='sma_20',
    compute_fn=lambda df: df['close'].rolling(20).mean(),
    warm_up_periods=20
)

store.add_feature(
    name='vol_20',
    compute_fn=lambda df: df['close'].pct_change().rolling(20).std(),
    warm_up_periods=20
)

# 3. Compute features
features = store.compute_features(
    df=bars,
    use_cache=True,
    validate_leakage=True
)

# 4. Check warm-up requirement
min_warmup = store.get_warm_up_requirement()
print(f"Minimum warm-up: {min_warmup} bars")
```

### Incremental Updates (Live Trading)

```python
# Initial features
features = store.compute_features(historical_bars)

# New bar arrives
new_bar = pd.DataFrame([new_data])

# Update features incrementally
updated_features = store.update_features(
    new_df=new_bar,
    previous_features=features
)

# Only computes features for new_bar (not entire history)
```

### Feature Versioning

```python
# Version 1
store.add_feature('sma_20', lambda df: df['close'].rolling(20).mean(), 20)
features_v1 = store.compute_features(bars, use_cache=True)

# Change feature definition
store.increment_version()  # Invalidates cache
store.add_feature('sma_20', lambda df: df['close'].rolling(50).mean(), 50)
features_v2 = store.compute_features(bars, use_cache=True)

# features_v1 and features_v2 use different SMA windows
```

---

## Testing for Leakage

### Method 1: Backward Correlation

```python
analyzer = FeatureAnalyzer()

report = analyzer.analyze(
    features=features,
    target=returns,
    task='regression'
)

# Check for leakage
if report['leakage']:
    print("⚠️ Leakage detected:")
    for feat, corr in report['leakage'].items():
        print(f"  {feat}: {corr:.4f}")
else:
    print("✓ No leakage detected")
```

### Method 2: Manual Inspection

```python
# Correlate features[t] with target[t-1]
target_backward = returns.shift(-1)

for col in features.columns:
    corr = features[col].corr(target_backward)
    if abs(corr) > 0.1:
        print(f"⚠️ {col}: backward_corr={corr:.4f}")
```

### Method 3: Walk-Forward Test

```python
# Split data into train/test
train = bars[:1000]
test = bars[1000:]

# Extract features on train (fit)
features_train = store.compute_features(train)

# Extract features on test (transform only)
# Should NOT use test data statistics
features_test = store.compute_features(test, use_cache=False)

# Check if features_test depends on test data
# (manually verify statistics match train distribution)
```

---

## Advanced Topics

### Online Statistics (Welford Algorithm)

For incremental computation without storing history:

```python
from autotrader.data_prep.features import OnlineStatistics

stats = OnlineStatistics()

for value in data:
    stats.update(value)
    print(f"Mean: {stats.mean}, Std: {stats.std}")
```

**Benefits**:
- No history storage (O(1) memory)
- O(1) update time
- Numerically stable

### Dependency Tracking

```python
# Feature B depends on Feature A
store.add_feature(
    name='feature_a',
    compute_fn=lambda df: df['close'].rolling(20).mean(),
    warm_up_periods=20
)

store.add_feature(
    name='feature_b',
    compute_fn=lambda df: features['feature_a'] * 2,
    warm_up_periods=20,
    dependencies=['feature_a']  # Track dependency
)

# Compute in correct order
features = store.compute_features(df)
```

### Cache Management

```python
# Set cache expiration
store = FeatureStore(
    cache_dir='./cache',
    max_cache_age_days=7  # Expire after 7 days
)

# Clear cache manually
store.clear_cache()

# Cache is invalidated when:
# 1. Feature version changes
# 2. Input data changes
# 3. max_cache_age_days exceeded
```

---

## Microstructure Features and Leakage

### Safe Microstructure Features:

```python
from autotrader.data_prep.features import MicropriceFeatureExtractor

# Microprice at time t uses orderbook at time t-1
extractor = MicropriceFeatureExtractor()
features = extractor.extract_all(orderbook_df)

# Features are automatically aligned to bars_df index
# and shifted to avoid leakage
```

### Trade Data Alignment:

```python
# Trades at time t should be used for features at time t+1
# (because you observe trade, then predict next move)

from autotrader.data_prep.features import OrderBookImbalanceExtractor

extractor = OrderBookImbalanceExtractor()
features = extractor.extract_all(
    orderbook_df=orderbook,
    trade_df=trades,  # Trades used for OFI
    target_index=bars.index  # Align to bars
)

# Features are shifted internally
```

---

## Checklist: Ensuring No Leakage

### Before Backtesting:

- [ ] All features shifted by 1 (or using FeatureStore)
- [ ] No forward-looking functions (e.g., shift(-1))
- [ ] Global statistics replaced with expanding windows
- [ ] Warm-up periods tracked and respected
- [ ] Leakage detection run (`validate_no_leakage()`)
- [ ] Backward correlation < 0.1 for all features
- [ ] Walk-forward test passed

### Before Live Trading:

- [ ] Incremental updates tested (FeatureStore.update_features())
- [ ] Feature versioning tracked
- [ ] Cache invalidation tested
- [ ] Real-time computation time < bar period
- [ ] Warm-up period pre-loaded
- [ ] No data snooping (parameters not optimized on test set)

---

## Examples

### Example 1: Safe SMA Feature

```python
store = FeatureStore()

# Register SMA (FeatureStore handles shift)
store.add_feature(
    name='sma_20',
    compute_fn=lambda df: df['close'].rolling(20).mean(),
    warm_up_periods=20
)

# Compute features
features = store.compute_features(df=bars)

# Verify no leakage
suspicious = store.validate_no_leakage(
    df=bars,
    features=features,
    target=bars['close'].pct_change().shift(-1),  # Future return
    max_allowed_correlation=0.1
)

assert len(suspicious) == 0, "Leakage detected!"
```

### Example 2: Safe Volatility Regime

```python
from autotrader.data_prep.features import SessionFeatureExtractor

# Session extractor handles shifting internally
extractor = SessionFeatureExtractor()

features = extractor.extract_all(price_df=bars)

# volatility_regime at time t uses data up to t-1
# No manual shift needed
```

### Example 3: Safe Microstructure Pipeline

```python
from autotrader.data_prep.features import (
    FeatureFactory,
    FeatureConfig,
    FeatureAnalyzer
)

# Configure microstructure features
config = FeatureConfig.microstructure()
factory = FeatureFactory(config)

# Extract features (all shifted internally)
features = factory.extract_all(
    bars_df=bars,
    order_book_df=orderbook,
    trade_df=trades
)

# Analyze for leakage
analyzer = FeatureAnalyzer()
report = analyzer.analyze(
    features=features,
    target=returns,
    task='regression'
)

# Verify no leakage
if report['leakage']:
    raise ValueError("Leakage detected! Do not use these features.")

print("✓ All features are leakage-safe")
```

---

## References

1. **Lopez de Prado (2018)**: "Advances in Financial Machine Learning", Chapter 7
   - Definitive guide to lookahead bias
   - Walk-forward analysis
   - Combinatorial purged cross-validation

2. **Welford (1962)**: "Note on a Method for Calculating Corrected Sums of Squares and Products"
   - Online statistics algorithm

3. **Bailey et al. (2014)**: "The Probability of Backtest Overfitting"
   - Data snooping and multiple testing

---

## Common Questions

### Q: Why shift by 1? Why not use current bar?

**A**: In live trading, you make decisions **before** the bar closes. You don't know the close price yet! Shifting by 1 simulates this reality.

### Q: What if I'm trading at bar close?

**A**: Still shift by 1. You need features to make a decision at close, so features must be available before close (using previous bars).

### Q: Can I use intraday bars without shift?

**A**: No. Even with 1-second bars, features at time t should use data up to t-1. Otherwise, you're assuming instant execution at exactly t.

### Q: How do I handle warm-up in live trading?

**A**: Pre-load features with historical data before going live:

```python
# Pre-load with 200 bars of history
historical_features = store.compute_features(historical_bars[-200:])

# Then update incrementally
for new_bar in live_stream:
    new_features = store.update_features(new_bar, historical_features)
    # Use new_features for trading decision
```

### Q: What's the performance impact of shifting?

**A**: Negligible. Shift is O(1) in memory and O(n) in time (one copy). Far less than feature computation cost.

---

## Conclusion

**Golden Rules**:

1. **Always shift features by 1** (or use FeatureStore)
2. **Track warm-up periods** (don't use NaN features)
3. **Validate leakage** before backtesting
4. **Test incrementally** before live trading

**Remember**: A single leaky feature can invalidate months of research. Invest time in leakage prevention!

---

**Next Steps**:
- Read MICROSTRUCTURE_FEATURES.md for feature details
- Run `run_feature_tests.py` to validate features
- Test your pipeline with `validate_no_leakage()`

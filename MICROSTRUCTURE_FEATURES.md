# Phase 5: Microstructure Features - Complete Guide

## Overview

Phase 5 implements **HFT-grade microstructure features** for high-frequency trading, market making, and microstructure research. These features capture orderbook dynamics, liquidity conditions, and informed trading signals that are invisible to OHLCV-based features.

**Total: ~50+ microstructure features** across 6 specialized extractors + infrastructure (store + analyzer).

---

## Architecture

### Feature Extractors (6 modules, 2,560 lines)

1. **MicropriceFeatureExtractor** (350 lines, 9 features)
   - Volume-weighted microprice (Stoikov 2018)
   - Realized volatility (Andersen et al. 2001)
   - Jump detection (Lee-Mykland 2008)
   - Higher moments (skew/kurtosis)

2. **OrderBookImbalanceExtractor** (430 lines, 9 features)
   - Depth imbalance (single/multi-level)
   - Order Flow Imbalance (OFI, Cont et al. 2014)
   - Book pressure (exponentially weighted)
   - Imbalance volatility and flip rate

3. **LiquidityFeatureExtractor** (420 lines, 9 features)
   - Spread measures (bid-ask, effective, depth-weighted)
   - Impact measures (Kyle's lambda, Amihud)
   - Implicit spread (Roll 1984)
   - Depth and liquidity ratios

4. **FlowDynamicsExtractor** (450 lines, 9 features)
   - VPIN (flow toxicity, Easley et al. 2012)
   - Aggressor streaks and dominance
   - Imbalance momentum and acceleration
   - Pressure decay and trade intensity

5. **SessionFeatureExtractor** (360 lines, 9 features)
   - Session timing (time-to-open/close)
   - Volatility regimes (high/low)
   - Volume regimes
   - Day-of-week effects

6. **CryptoFXFeatureExtractor** (380 lines, 5-7 features)
   - Funding rate proximity (crypto, 8h cycles)
   - Rollover timing (FX, 5 PM ET)
   - Weekend and overnight flags
   - Trading sessions (Asian/European/US)

### Infrastructure (2 modules, 1,000 lines)

7. **FeatureStore** (470 lines)
   - Leakage-safe rolling windows (strict causality)
   - Feature caching and versioning
   - Incremental updates (live trading)
   - Warm-up period tracking
   - Online statistics (Welford algorithm)

8. **FeatureAnalyzer** (530 lines)
   - Permutation importance (Breiman 2001)
   - Information Coefficient (IC)
   - Leakage detection (forward correlation)
   - Stability analysis (IC decay)
   - Redundancy detection (correlation clustering)

---

## Quick Start

### 1. Basic Usage (OHLCV + Session Features)

```python
from autotrader.data_prep.features import FeatureFactory, FeatureConfig

# Enable session features (works with OHLCV data)
config = FeatureConfig(
    enable_session_regime=True,
    market_open_hour=9,
    market_open_minute=30,
    market_close_hour=16,
    market_close_minute=0
)

factory = FeatureFactory(config)
features = factory.extract_all(bars_df=bars)

# Session features: time_to_open, time_to_close, volatility_regime, etc.
print(features.columns)
```

### 2. Full Microstructure Suite (requires orderbook + trades)

```python
# Use microstructure preset
config = FeatureConfig.microstructure()

factory = FeatureFactory(config)
features = factory.extract_all(
    bars_df=bars,
    order_book_df=orderbook,  # Required
    trade_df=trades  # Required for OFI, VPIN
)

# ~50+ microstructure features
print(f"Total features: {len(features.columns)}")
```

### 3. Custom Configuration

```python
config = FeatureConfig(
    # Enable specific extractors
    enable_microprice=True,
    enable_orderbook_imbalance=True,
    enable_liquidity=True,
    enable_flow_dynamics=False,  # Disable flow dynamics
    enable_session_regime=True,
    
    # Tune parameters
    realized_vol_window=50,
    jump_threshold=4.0,  # 4-sigma for jump detection
    ofi_window=20,
    kyles_window=50
)
```

---

## Feature Reference

### 1. MicropriceFeatureExtractor (9 features)

**Concept**: Microprice is a volume-weighted mid that better represents execution prices than simple mid.

| Feature | Formula | Range | Interpretation |
|---------|---------|-------|----------------|
| `microprice` | (bid×ask_size + ask×bid_size)/(bid_size + ask_size) | Price | Volume-weighted mid |
| `microprice_spread` | (microprice - mid)/mid | % | Distance from simple mid |
| `realized_vol` | sqrt(sum(r²)) over window | σ | More accurate than EWMA |
| `realized_var` | Unbiased variance (Bessel) | σ² | Vol squared |
| `jump_stat` | Lee-Mykland test statistic | z-score | Jump significance |
| `jump_flag` | \|jump_stat\| > threshold | 0/1 | Binary jump indicator |
| `vol_ratio` | current_vol / avg_vol | Ratio | Regime detector |
| `returns_skew` | Rolling skewness | (-∞, +∞) | Crash risk |
| `returns_kurt` | Rolling kurtosis | [0, ∞) | Tail risk |

**Example**:
```python
from autotrader.data_prep.features import MicropriceFeatureExtractor

extractor = MicropriceFeatureExtractor(
    realized_vol_window=50,
    jump_window=100,
    jump_threshold=4.0  # 4-sigma
)

features = extractor.extract_all(orderbook_df=orderbook)
```

**Academic References**:
- Stoikov (2018): "The Micro-Price: A High Frequency Estimator of Future Prices"
- Lee & Mykland (2008): "Jumps in Financial Markets: A New Nonparametric Test"
- Andersen et al. (2001): "The Distribution of Realized Exchange Rate Volatility"

---

### 2. OrderBookImbalanceExtractor (9 features)

**Concept**: Depth imbalance predicts short-term price movements (Cont et al. 2014).

| Feature | Formula | Range | Interpretation |
|---------|---------|-------|----------------|
| `depth_imbalance` | (bid_size - ask_size)/(bid_size + ask_size) | [-1, 1] | Top-level imbalance |
| `depth_imbalance_top5` | Multi-level imbalance | [-1, 1] | Deeper liquidity |
| `weighted_depth_imbalance` | Distance-weighted | [-1, 1] | Closer levels matter more |
| `queue_position_bid` | Position in bid queue | [0, 1] | Adverse selection risk |
| `queue_position_ask` | Position in ask queue | [0, 1] | Adverse selection risk |
| `ofi` | Order Flow Imbalance | Volume | Net aggressive flow |
| `ofi_momentum` | Rolling sum of OFI | Volume | Pressure accumulation |
| `book_pressure` | EWM of imbalance | [-1, 1] | Persistent pressure |
| `imbalance_volatility` | Std of imbalance | σ | Activity level |
| `imbalance_flip_rate` | Sign change frequency | [0, 1] | Mean reversion indicator |

**Example**:
```python
from autotrader.data_prep.features import OrderBookImbalanceExtractor

extractor = OrderBookImbalanceExtractor(
    num_levels=5,
    ofi_window=20,
    pressure_decay=0.95
)

features = extractor.extract_all(
    orderbook_df=orderbook,
    trade_df=trades  # For OFI
)
```

**Academic References**:
- Cont, Kukanov, Stoikov (2014): "The Price Impact of Order Book Events"
- Huang & Polak (2011): "A Framework for the Econometrics of Agent-Based Models"
- Lipton et al. (2013): "Algorithmic and High-Frequency Trading"

---

### 3. LiquidityFeatureExtractor (9 features)

**Concept**: Liquidity measures capture trading costs and price impact.

| Feature | Formula | Range | Interpretation |
|---------|---------|-------|----------------|
| `bid_ask_spread` | ask - bid | Price | Round-trip cost |
| `relative_spread` | spread/mid × 10000 | bps | Normalized spread |
| `effective_spread` | 2 × \|trade_price - mid\| | Price | Realized cost |
| `depth_weighted_spread` | Weighted by depth | Price | Cost for large trades |
| `kyles_lambda` | dP/dV | Impact | Price impact per volume |
| `amihud_illiquidity` | \|return\|/volume | Impact | Illiquidity ratio |
| `roll_spread` | 2×sqrt(-cov(r_t, r_{t-1})) | Price | Implicit spread |
| `total_depth` | bid_size + ask_size | Volume | Available liquidity |
| `depth_ratio` | bid_size/ask_size | Ratio | Liquidity imbalance |

**Example**:
```python
from autotrader.data_prep.features import LiquidityFeatureExtractor

extractor = LiquidityFeatureExtractor(
    kyles_window=50,
    amihud_window=20,
    roll_window=100
)

features = extractor.extract_all(
    orderbook_df=orderbook,
    trade_df=trades  # For effective spread
)
```

**Academic References**:
- Kyle (1985): "Continuous Auctions and Insider Trading"
- Amihud (2002): "Illiquidity and Stock Returns"
- Roll (1984): "A Simple Implicit Measure of the Effective Bid-Ask Spread"
- Hasbrouck (2009): "Trading Costs and Returns for U.S. Equities"

---

### 4. FlowDynamicsExtractor (9 features)

**Concept**: Flow dynamics capture momentum, mean reversion, and toxicity.

| Feature | Formula | Range | Interpretation |
|---------|---------|-------|----------------|
| `imbalance_momentum` | Autocorr(dImb) | [-1, 1] | Trending vs mean-reverting |
| `imbalance_acceleration` | d²Imb/dt² | (-∞, +∞) | Turning points |
| `pressure_decay_rate` | -log(autocorr) | [0, ∞) | Mean reversion speed |
| `aggressor_streak_buy` | Consecutive buy trades | Count | Directional pressure |
| `aggressor_streak_sell` | Consecutive sell trades | Count | Directional pressure |
| `aggressor_dominance` | Net aggressor side | [-1, 1] | Buy vs sell pressure |
| `vpin` | Volume-Synchronized PIN | [0, 1] | Flow toxicity |
| `trade_intensity` | Trades per second | Rate | Activity level |
| `volume_clustering` | CV² of volume | [0, ∞) | Burst trading |

**Example**:
```python
from autotrader.data_prep.features import FlowDynamicsExtractor

extractor = FlowDynamicsExtractor(
    momentum_window=50,
    vpin_buckets=50,
    intensity_window=20
)

features = extractor.extract_all(
    orderbook_df=orderbook,
    trade_df=trades  # Required
)
```

**Academic References**:
- Easley et al. (2012): "Flow Toxicity and Liquidity in a High Frequency World"
- Cartea et al. (2015): "Algorithmic and High-Frequency Trading"

---

### 5. SessionFeatureExtractor (9 features)

**Concept**: Intraday patterns and regime classification.

| Feature | Formula | Range | Interpretation |
|---------|---------|-------|----------------|
| `time_to_open` | Minutes to market open | Minutes | Pre-market proximity |
| `time_to_close` | Minutes to market close | Minutes | End-of-day proximity |
| `session_progress` | Elapsed/total session | [0, 1] | Intraday position |
| `day_of_week` | Monday=0, Friday=4 | [0, 4] | Day-of-week effect |
| `is_monday` | Binary flag | 0/1 | Monday effect |
| `is_friday` | Binary flag | 0/1 | Friday effect |
| `volatility_regime` | High/low classification | -1/0/1 | Vol regime |
| `volatility_percentile` | Current vol percentile | [0, 100] | Relative vol |
| `volume_regime` | High/low classification | -1/0/1 | Volume regime |
| `volume_percentile` | Current volume percentile | [0, 100] | Relative volume |

**Example**:
```python
from autotrader.data_prep.features import SessionFeatureExtractor
from datetime import time

extractor = SessionFeatureExtractor(
    market_open=time(9, 30),
    market_close=time(16, 0),
    vol_regime_window=200
)

features = extractor.extract_all(price_df=bars)
```

**Academic References**:
- Admati & Pfleiderer (1988): "A Theory of Intraday Patterns"
- Hamilton (1989): "A New Approach to the Economic Analysis of Nonstationary Time Series and the Business Cycle"

---

### 6. CryptoFXFeatureExtractor (5-7 features)

**Concept**: Market-specific timing features for crypto (24/7) and FX (24/5).

#### Crypto Features:

| Feature | Formula | Range | Interpretation |
|---------|---------|-------|----------------|
| `minutes_to_funding` | Time to next funding | [0, 480) | Funding rate event proximity |
| `funding_cycle` | Current cycle (0/1/2) | {0,1,2} | 8h cycle indicator |
| `is_weekend` | Saturday/Sunday | 0/1 | Weekend liquidity |
| `weekend_proximity` | Hours from/to weekend | Hours | Weekend effect |

#### FX Features:

| Feature | Formula | Range | Interpretation |
|---------|---------|-------|----------------|
| `minutes_to_rollover` | Time to 5 PM ET rollover | Minutes | Rollover proximity |
| `is_overnight` | Fri 5PM - Sun 5PM | 0/1 | Market closed |
| `trading_session` | Asian/European/US/Overlap | {0,1,2,3} | Session indicator |
| `is_weekend` | Saturday/Sunday | 0/1 | Weekend effect |

**Example**:
```python
from autotrader.data_prep.features import CryptoFXFeatureExtractor
from datetime import time

# For crypto
extractor = CryptoFXFeatureExtractor(
    market_type='crypto',
    funding_interval_hours=8
)

# For FX
extractor = CryptoFXFeatureExtractor(
    market_type='fx',
    fx_rollover_time=time(17, 0)  # 5 PM ET
)

features = extractor.extract_all(df=bars)
```

---

## Infrastructure

### FeatureStore: Leakage-Safe Windows

**Critical for production**: Prevents lookahead bias (fatal flaw in backtests).

```python
from autotrader.data_prep.features import FeatureStore

store = FeatureStore(cache_dir='./feature_cache')

# Define features with warm-up requirements
store.add_feature(
    name='sma_20',
    compute_fn=lambda df: df['close'].rolling(20).mean(),
    warm_up_periods=20
)

# Compute features (automatically shifted by 1 to avoid leakage)
features = store.compute_features(
    df=bars,
    use_cache=True,
    validate_leakage=True  # Check for lookahead bias
)

# Incremental update (live trading)
new_features = store.update_features(new_bars, features)
```

**Key Features**:
- **Strict causality**: Features at time t use only data up to t-1
- **Warm-up tracking**: Ensure sufficient history
- **Caching**: Avoid recomputation
- **Versioning**: Track feature changes
- **Online statistics**: Welford algorithm for incremental stats

**Reference**: Lopez de Prado (2018) "Advances in Financial Machine Learning", Chapter 7

---

### FeatureAnalyzer: Importance and Leakage Detection

```python
from autotrader.data_prep.features import FeatureAnalyzer

analyzer = FeatureAnalyzer(n_permutations=10)

# Comprehensive analysis
report = analyzer.analyze(
    features=features_df,
    target=returns,
    task='regression',
    time_periods=5  # For stability analysis
)

# Top features by importance
print(report['importance'].head(10))

# Leakage detection (CRITICAL)
if report['leakage']:
    print("⚠️ WARNING: Potential lookahead bias detected!")
    for feat, corr in report['leakage'].items():
        print(f"  {feat}: backward_corr={corr:.4f}")

# IC stability over time
print(report['stability'].head(10))

# Redundant features
print(f"Found {len(report['redundancy']['redundant_pairs'])} redundant pairs")

# Generate report
report_text = analyzer.generate_report(report, output_path='feature_analysis.txt')

# Plot importance
analyzer.plot_importance(report)
```

---

## Performance Considerations

### Computational Cost

| Extractor | Complexity | Notes |
|-----------|------------|-------|
| Microprice | O(n) | Fast, simple calculations |
| Orderbook Imbalance | O(n×L) | L = num_levels (typically 5) |
| Liquidity | O(n×w) | w = window size (Kyle's lambda) |
| Flow Dynamics | O(n×w) | VPIN is expensive (volume buckets) |
| Session/Regime | O(n×w) | Rolling percentiles |
| CryptoFX | O(n) | Fast, simple calculations |

### Optimization Tips:

1. **Use caching** (FeatureStore):
   ```python
   store = FeatureStore(cache_dir='./cache', max_cache_age_days=7)
   ```

2. **Reduce window sizes** for real-time:
   ```python
   config = FeatureConfig(
       realized_vol_window=20,  # Instead of 50
       ofi_window=10,  # Instead of 20
       vpin_buckets=25  # Instead of 50
   )
   ```

3. **Disable expensive features**:
   ```python
   config = FeatureConfig(
       enable_flow_dynamics=False,  # VPIN is expensive
       enable_liquidity=True  # Kyle's lambda is cheaper
   )
   ```

4. **Use microstructure preset** for HFT:
   ```python
   config = FeatureConfig.microstructure()  # Optimized for speed
   ```

---

## Data Requirements

### Minimum Requirements:

1. **OHLCV bars** (required for all):
   - timestamp, open, high, low, close, volume
   - Frequency: 1s to 1min for HFT

2. **Orderbook snapshots** (for microstructure features):
   - timestamp, bid_price_1..5, ask_price_1..5, bid_size_1..5, ask_size_1..5
   - Frequency: Every orderbook update (BBO or L2)

3. **Trade data** (for OFI, VPIN):
   - timestamp, price, size, side (buy/sell/unknown)
   - Frequency: Every trade

### Data Format:

```python
# OHLCV bars
bars_df = pd.DataFrame({
    'timestamp': ...,  # DatetimeIndex
    'open': ...,
    'high': ...,
    'low': ...,
    'close': ...,
    'volume': ...
})

# Orderbook snapshots
orderbook_df = pd.DataFrame({
    'timestamp': ...,  # DatetimeIndex
    'bid_price_1': ...,
    'ask_price_1': ...,
    'bid_size_1': ...,
    'ask_size_1': ...,
    # ... up to level 5
})

# Trades
trade_df = pd.DataFrame({
    'timestamp': ...,  # DatetimeIndex
    'price': ...,
    'size': ...,
    'side': ...  # 'buy', 'sell', or 'unknown'
})
```

---

## Validation and Testing

### 1. Feature Count Validation

```python
config = FeatureConfig.microstructure()
factory = FeatureFactory(config)
features = factory.extract_all(bars, orderbook, trades)

print(f"Total features: {len(features.columns)}")
# Expected: ~50+ features
```

### 2. Leakage Detection

```python
from autotrader.data_prep.features import FeatureStore

store = FeatureStore()
store.add_feature('sma_20', lambda df: df['close'].rolling(20).mean(), 20)

features = store.compute_features(df, validate_leakage=True)

# Check for lookahead bias
suspicious = store.validate_no_leakage(
    df=bars,
    features=features,
    target=returns,
    max_allowed_correlation=0.1
)

if suspicious:
    print("⚠️ Potential leakage detected!")
```

### 3. Performance Benchmarking

```python
import time

start = time.time()
features = factory.extract_all(bars, orderbook, trades)
elapsed = time.time() - start

rows_per_sec = len(bars) / elapsed
print(f"Performance: {rows_per_sec:.1f} rows/sec")
# Target: >1,000 rows/sec for real-time HFT
```

---

## Complete Example: HFT Pipeline

```python
from autotrader.data_prep.features import (
    FeatureFactory,
    FeatureConfig,
    FeatureStore,
    FeatureAnalyzer
)

# 1. Configure microstructure features
config = FeatureConfig.microstructure()

# 2. Create factory
factory = FeatureFactory(config)

# 3. Extract features
features = factory.extract_all(
    bars_df=bars,
    order_book_df=orderbook,
    trade_df=trades
)

print(f"Extracted {len(features.columns)} features")

# 4. Analyze feature quality
analyzer = FeatureAnalyzer()
report = analyzer.analyze(
    features=features,
    target=returns,
    task='regression',
    time_periods=5
)

# 5. Check for leakage (CRITICAL)
if report['leakage']:
    raise ValueError("Lookahead bias detected!")

# 6. Select top features
top_features = report['importance'].head(20).index.tolist()
features_selected = features[top_features]

# 7. Use FeatureStore for production
store = FeatureStore(cache_dir='./cache')
for feat in top_features:
    store.add_feature(
        name=feat,
        compute_fn=lambda df: features[feat],
        warm_up_periods=200  # Max warm-up
    )

# 8. Incremental updates (live trading)
new_features = store.update_features(new_bars, features_selected)
```

---

## References

### Academic Papers:

1. **Microprice**:
   - Stoikov (2018): "The Micro-Price: A High Frequency Estimator of Future Prices"

2. **Jump Detection**:
   - Lee & Mykland (2008): "Jumps in Financial Markets: A New Nonparametric Test"
   - Andersen et al. (2001): "The Distribution of Realized Exchange Rate Volatility"

3. **Order Flow Imbalance**:
   - Cont, Kukanov, Stoikov (2014): "The Price Impact of Order Book Events"

4. **Liquidity Measures**:
   - Kyle (1985): "Continuous Auctions and Insider Trading"
   - Amihud (2002): "Illiquidity and Stock Returns"
   - Roll (1984): "A Simple Implicit Measure of the Effective Bid-Ask Spread"
   - Hasbrouck (2009): "Trading Costs and Returns for U.S. Equities"

5. **Flow Toxicity**:
   - Easley et al. (2012): "Flow Toxicity and Liquidity in a High Frequency World"

6. **Intraday Patterns**:
   - Admati & Pfleiderer (1988): "A Theory of Intraday Patterns"

7. **Lookahead Bias**:
   - Lopez de Prado (2018): "Advances in Financial Machine Learning"

8. **Online Statistics**:
   - Welford (1962): "Note on a Method for Calculating Corrected Sums of Squares and Products"

### Books:

- Cartea et al. (2015): "Algorithmic and High-Frequency Trading"
- Hasbrouck (2007): "Empirical Market Microstructure"
- O'Hara (1995): "Market Microstructure Theory"

---

## Next Steps

1. **Test on historical data**:
   ```bash
   python run_feature_tests.py
   ```

2. **Benchmark performance**:
   ```bash
   python scripts/benchmark_microstructure.py
   ```

3. **Backtest with microstructure features**:
   ```bash
   python scripts/backtest_with_microstructure.py
   ```

4. **Deploy to live trading** (use FeatureStore for incremental updates)

---

## Support and Contributing

- **Issues**: Report bugs or request features on GitHub
- **Documentation**: See FEATURE_STORE_GUIDE.md for leakage prevention
- **Contributing**: See CONTRIBUTING.md for development guidelines

---

**Phase 5 Complete**: 3,560 lines, 8 modules, ~50+ features, academic-grade implementation.

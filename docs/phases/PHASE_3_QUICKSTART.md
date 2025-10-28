# Phase 3 Quick Start Guide

**Data Cleaning & Bar Construction**

---

## Overview

This guide provides a fast-track introduction to Phase 3 data preparation. For complete specifications, see [`PHASE_3_DATA_PREP_SPECIFICATION.md`](./PHASE_3_DATA_PREP_SPECIFICATION.md).

---

## What Phase 3 Does

Phase 3 transforms **raw tick data** (from Phase 2) into **clean feature datasets** ready for ML training (Phase 4):

```
Raw Ticks → Clean Data → Bars → Features → Labels
(Phase 2)    (Phase 3)   (Phase 3) (Phase 3) (Phase 3)
```

**Key Operations**:
1. **Data Cleaning**: Normalize timezones, filter by trading sessions, remove outliers
2. **Bar Construction**: Build 6 bar types (time, tick, volume, dollar, imbalance, run)
3. **Feature Engineering**: Extract order book features (spread, depth, flow toxicity)
4. **Label Integrity**: Prevent lookahead bias, ensure temporal alignment

---

## Installation (Prerequisites)

Ensure Phase 2 is complete and dependencies installed:

```bash
# From Autotrader directory
pip install -e .

# Additional dependencies for Phase 3
pip install pandas numpy scipy statsmodels
pip install pyarrow  # For Parquet I/O
pip install pandas-market-calendars  # For trading calendars
```

---

## Quick Examples

### 1. Clean Tick Data

```python
from autotrader.data_prep.cleaning import TimezoneNormalizer, SessionFilter, DataQualityChecker
import pandas as pd

# Load raw tick data from ClickHouse or Parquet
df = pd.read_parquet("data/historical/dukascopy/EURUSD_20241018_10.parquet")

# Step 1: Normalize to UTC
normalizer = TimezoneNormalizer(venue_timezones={"DUKASCOPY": "UTC"})
df = normalizer.normalize(df)

# Step 2: Filter by trading session
session_filter = SessionFilter(asset_class="FOREX", venue="DUKASCOPY")
df = session_filter.filter_regular_hours(df)

# Step 3: Quality checks
quality_checker = DataQualityChecker()
df = quality_checker.remove_duplicates(df)

# Detect outliers (Z-score > 5)
outliers = quality_checker.detect_outliers(df, price_col="price", method="zscore", threshold=5.0)
df = df[~outliers]

print(f"✅ Cleaned {len(df)} ticks")
```

---

### 2. Build Time Bars

```python
from autotrader.data_prep.bars import TimeBarConstructor

# Construct 1-minute OHLCV bars
constructor = TimeBarConstructor(interval="1min")
bars = constructor.construct(df)

print(bars.head())
#    timestamp_utc     open     high      low    close   volume   vwap  trades
# 0  2024-10-18 10:00  1.08587  1.08590  1.08585  1.08588  1500.0  1.08587  100
# 1  2024-10-18 10:01  1.08588  1.08592  1.08586  1.08590  1450.0  1.08589   98
```

**Supported intervals**:
- `"1s"`, `"5s"`, `"10s"`, `"30s"`
- `"1min"`, `"5min"`, `"15min"`, `"30min"`
- `"1h"`, `"4h"`, `"1d"`

---

### 3. Build Tick Bars

```python
from autotrader.data_prep.bars import TickBarConstructor

# Construct bars of 1000 ticks each
constructor = TickBarConstructor(num_ticks=1000)
bars = constructor.construct(df)

print(f"✅ Created {len(bars)} tick bars")
# Each bar contains exactly 1000 ticks
```

---

### 4. Build Volume Bars

```python
from autotrader.data_prep.bars import VolumeBarConstructor

# Bar closes after 1M shares traded
constructor = VolumeBarConstructor(volume_threshold=1_000_000)
bars = constructor.construct(df)

print(f"✅ Created {len(bars)} volume bars")
```

---

### 5. Build Dollar Bars

```python
from autotrader.data_prep.bars import DollarBarConstructor

# Bar closes after $10M traded
constructor = DollarBarConstructor(dollar_threshold=10_000_000)
bars = constructor.construct(df)

print(f"✅ Created {len(bars)} dollar bars")
# Popular for HFT - adapts to volatility
```

---

### 6. Build Imbalance Bars

```python
from autotrader.data_prep.bars import ImbalanceBarConstructor

# Bar closes when |cumulative signed volume| > threshold
constructor = ImbalanceBarConstructor(imbalance_threshold=10000)
bars = constructor.construct(df)

print(f"✅ Created {len(bars)} imbalance bars")
# Captures order flow toxicity
```

---

### 7. Extract Order Book Features

```python
from autotrader.data_prep.features import SpreadFeatures, DepthFeatures

# Calculate quoted spread
bid = 1.08587
ask = 1.08590
spread_bps = SpreadFeatures.quoted_spread(bid, ask)
print(f"Quoted spread: {spread_bps:.2f} bps")
# Output: Quoted spread: 2.76 bps

# Calculate order imbalance
bids = [{"price": 1.08587, "size": 10000}, {"price": 1.08586, "size": 8000}]
asks = [{"price": 1.08590, "size": 5000}, {"price": 1.08591, "size": 3000}]

imbalance = DepthFeatures.order_imbalance(bids, asks, num_levels=2)
print(f"Order imbalance: {imbalance:.3f}")
# Output: Order imbalance: 0.385 (buy pressure)

# Calculate microprice
microprice = DepthFeatures.microprice(bid, ask, bid_size=10000, ask_size=5000)
print(f"Microprice: {microprice:.5f}")
# Output: Microprice: 1.08588 (closer to bid due to larger size)
```

---

### 8. Validate Label Integrity

```python
from autotrader.data_prep.validation import LabelIntegrityValidator

validator = LabelIntegrityValidator()

# Check for lookahead bias
features = pd.DataFrame({
    "timestamp": pd.date_range("2024-10-18 10:00", periods=100, freq="1min"),
    "price": np.random.randn(100),
    "volume": np.random.randint(1000, 10000, 100)
})

labels = pd.DataFrame({
    "timestamp": pd.date_range("2024-10-18 10:01", periods=100, freq="1min"),
    "forward_return_5m": np.random.randn(100)
})

result = validator.check_lookahead(features, labels)
print(result)
# {"is_valid": True, "errors": [], "warnings": []}

# Split data temporally (no shuffling!)
train, val, test = validator.split_train_val_test(
    bars,
    train_frac=0.7,
    val_frac=0.15,
    test_frac=0.15
)

print(f"Train: {len(train)}, Val: {len(val)}, Test: {len(test)}")
```

---

## Bar Type Selection Guide

| Bar Type | Use Case | Pros | Cons |
|----------|----------|------|------|
| **Time Bars** | General-purpose, benchmarking | Simple, consistent intervals | Ignores activity (many bars with no trades) |
| **Tick Bars** | High-frequency strategies | Activity-based, no empty bars | Fixed tick count may not adapt to volatility |
| **Volume Bars** | Equity strategies | Adapts to trading activity | Doesn't account for price (1 share @ $1 = 1 share @ $100) |
| **Dollar Bars** | Multi-asset HFT | Normalizes by dollar value | Requires price * volume data |
| **Imbalance Bars** | Order flow strategies | Captures buy/sell pressure | Complex to tune threshold |
| **Run Bars** | Momentum/reversal strategies | Captures trend persistence | Sensitive to noise |

**Recommendation**: Start with **time bars** (1min, 5min) for prototyping, then experiment with **dollar bars** and **imbalance bars** for production HFT models.

---

## Complete Pipeline Example

```python
from autotrader.data_prep import DataPrepPipeline

# End-to-end pipeline
pipeline = DataPrepPipeline(
    asset_class="EQUITY",
    venue="NASDAQ",
    bar_type="dollar",
    bar_params={"dollar_threshold": 5_000_000},
    features=[
        "spread_bps",
        "order_imbalance",
        "microprice",
        "vpin",
        "kyles_lambda"
    ]
)

# Process raw tick data
features_df = pipeline.run(
    input_path="data/raw/AAPL_ticks.parquet",
    output_path="data/features/AAPL_dollar_bars.parquet"
)

print(f"✅ Generated {len(features_df)} feature bars")
print(features_df.head())
```

---

## Project Structure

```
autotrader/
├── data_prep/
│   ├── __init__.py
│   ├── cleaning.py              # TimezoneNormalizer, SessionFilter, DataQualityChecker
│   ├── bars/
│   │   ├── __init__.py
│   │   ├── time_bars.py         # TimeBarConstructor
│   │   ├── tick_bars.py         # TickBarConstructor
│   │   ├── volume_bars.py       # VolumeBarConstructor
│   │   ├── dollar_bars.py       # DollarBarConstructor
│   │   ├── imbalance_bars.py    # ImbalanceBarConstructor
│   │   ├── run_bars.py          # RunBarConstructor
│   │   └── factory.py           # BarFactory (unified interface)
│   ├── features/
│   │   ├── __init__.py
│   │   ├── spread.py            # SpreadFeatures
│   │   ├── depth.py             # DepthFeatures
│   │   └── flow_toxicity.py     # FlowToxicityFeatures (Kyle's lambda, VPIN)
│   ├── validation.py            # LabelIntegrityValidator
│   └── pipeline.py              # DataPrepPipeline (end-to-end)
├── tests/
│   ├── test_cleaning.py
│   ├── test_bars.py
│   ├── test_features.py
│   └── test_validation.py
└── scripts/
    └── prepare_features.py      # CLI tool
```

---

## CLI Tool

```bash
# Prepare features from raw tick data
python scripts/prepare_features.py \
    --input data/raw/AAPL_20241018.parquet \
    --output data/features/AAPL_1min_bars.parquet \
    --bar-type time \
    --interval 1min \
    --features spread,imbalance,vpin

# Output:
# ✅ Loaded 150,234 ticks
# ✅ Cleaned to 149,876 ticks (358 outliers removed)
# ✅ Constructed 390 time bars (1min)
# ✅ Extracted 5 features per bar
# ✅ Validated: No lookahead bias detected
# ✅ Saved to data/features/AAPL_1min_bars.parquet
```

---

## Common Workflows

### Workflow 1: Equity Day Trading (1-minute bars)

```python
# 1. Load IBKR tick data for AAPL
df = load_from_clickhouse("SELECT * FROM market_data.ticks WHERE symbol = 'AAPL'")

# 2. Clean data
df = clean_ticks(df, asset_class="EQUITY", venue="NASDAQ")

# 3. Build 1-minute time bars
bars = TimeBarConstructor(interval="1min").construct(df)

# 4. Extract features
bars["spread_bps"] = calculate_spread(bars)
bars["rsi_14"] = calculate_rsi(bars, window=14)
bars["macd"] = calculate_macd(bars)

# 5. Create labels (5-minute forward return)
bars["target"] = bars["close"].shift(-5) / bars["close"] - 1

# 6. Validate integrity
validator.check_lookahead(bars[["timestamp", "spread_bps", "rsi_14"]], bars[["timestamp", "target"]])

# 7. Save to feature store
bars.to_parquet("data/features/AAPL_1min_features.parquet")
```

---

### Workflow 2: Forex HFT (Tick bars)

```python
# 1. Load Dukascopy tick data for EUR/USD
df = pd.read_parquet("data/historical/dukascopy/EURUSD_20241018.parquet")

# 2. Build tick bars (1000 ticks each)
bars = TickBarConstructor(num_ticks=1000).construct(df)

# 3. Extract microstructure features
bars["microprice"] = calculate_microprice(bars)
bars["order_imbalance"] = calculate_order_imbalance(bars)
bars["vpin"] = calculate_vpin(bars)

# 4. Create labels (next-bar return)
bars["target"] = bars["close"].shift(-1) / bars["close"] - 1

# 5. Validate
validator.check_lookahead(bars[["timestamp_start", "microprice", "vpin"]], bars[["timestamp_end", "target"]])

# 6. Save
bars.to_parquet("data/features/EURUSD_tick1000_features.parquet")
```

---

### Workflow 3: Crypto Market Making (Dollar bars)

```python
# 1. Load Binance tick data for BTC/USDT
df = load_from_clickhouse("SELECT * FROM market_data.ticks WHERE symbol = 'BTC/USDT'")

# 2. Build dollar bars ($1M threshold)
bars = DollarBarConstructor(dollar_threshold=1_000_000).construct(df)

# 3. Extract order flow features
bars["kyles_lambda"] = calculate_kyles_lambda(bars)
bars["flow_toxicity"] = calculate_flow_toxicity(bars)
bars["depth_imbalance"] = calculate_depth_imbalance(bars)

# 4. Create labels (spread capture)
bars["target"] = bars["effective_spread"] - bars["realized_spread"]

# 5. Validate
validator.check_lookahead(bars[["timestamp_start", "kyles_lambda"]], bars[["timestamp_end", "target"]])

# 6. Save
bars.to_parquet("data/features/BTCUSDT_dollar1M_features.parquet")
```

---

## Performance Tips

1. **Use chunking for large datasets**:
   ```python
   # Process 1 day at a time
   for date in pd.date_range("2024-01-01", "2024-12-31"):
       df = load_ticks_for_date(date)
       bars = constructor.construct(df)
       bars.to_parquet(f"data/features/{date.strftime('%Y%m%d')}.parquet")
   ```

2. **Parallelize across symbols**:
   ```python
   from joblib import Parallel, delayed
   
   def process_symbol(symbol):
       df = load_ticks(symbol)
       bars = constructor.construct(df)
       return bars
   
   results = Parallel(n_jobs=-1)(delayed(process_symbol)(sym) for sym in symbols)
   ```

3. **Use Dask for distributed processing**:
   ```python
   import dask.dataframe as dd
   
   ddf = dd.read_parquet("data/raw/*.parquet")
   bars = ddf.map_partitions(lambda df: constructor.construct(df))
   bars.to_parquet("data/features/bars.parquet")
   ```

---

## Troubleshooting

### Empty bars after filtering

**Problem**: `SessionFilter` returns empty DataFrame.

**Solution**: Check timezone conversion and trading hours:
```python
print(df["timestamp_utc"].min(), df["timestamp_utc"].max())
print(df["timestamp_utc"].dt.dayofweek.unique())  # 0=Mon, 6=Sun

# Verify hours in UTC
print(df["timestamp_utc"].dt.hour.unique())
```

---

### Lookahead bias detected

**Problem**: `LabelIntegrityValidator` reports lookahead errors.

**Solution**: Ensure feature timestamps < label timestamps:
```python
# Incorrect: Using same-bar close price as feature for next-bar prediction
bars["feature"] = bars["close"]
bars["label"] = bars["close"].shift(-1)

# Correct: Use lagged features
bars["feature"] = bars["close"].shift(1)
bars["label"] = bars["close"].shift(-1)
```

---

### Outliers not detected

**Problem**: `detect_outliers()` misses obvious bad ticks.

**Solution**: Use rolling Z-score for better local detection:
```python
outliers = quality_checker.detect_outliers(
    df,
    method="rolling_zscore",
    threshold=5.0
)
```

---

## Next Steps

After Phase 3 completion:

1. **Phase 4: ML Model Training**
   - Train models on bar features
   - Hyperparameter optimization
   - Cross-validation strategies

2. **Phase 5: Strategy Development**
   - Signal generation from models
   - Backtesting framework
   - Walk-forward optimization

3. **Phase 6: Live Trading**
   - Real-time feature computation
   - Order execution
   - Risk management

---

## Resources

- **Full Specification**: [`PHASE_3_DATA_PREP_SPECIFICATION.md`](./PHASE_3_DATA_PREP_SPECIFICATION.md)
- **Phase 2 Docs**: [`PHASE_2_MARKET_DATA_COMPLETE.md`](./PHASE_2_MARKET_DATA_COMPLETE.md)
- **API Reference**: Auto-generated docs at `docs/api/data_prep.html`
- **Notebooks**: See `notebooks/` for interactive examples

---

**Last Updated**: October 23, 2025  
**Status**: Ready for Implementation  
**Estimated Duration**: 6 weeks

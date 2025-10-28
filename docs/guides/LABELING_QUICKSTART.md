# Cost-Aware Labeling Quick Start

## TL;DR

Generate ML training labels with realistic transaction costs in 3 lines:

```python
from autotrader.data_prep.labeling import LabelFactory

# Classification: {-1, 0, +1} labels (only profitable trades)
labels = LabelFactory.create(bars, method="classification", horizon_seconds=60)

# Regression: Continuous returns (microprice, clipped, cost-adjusted)
labels = LabelFactory.create(bars, method="regression", horizon_seconds=60)
```

---

## Installation

No installation needed - already part of AutoTrader data_prep module.

**Location**: `autotrader/data_prep/labeling/`

---

## Basic Usage

### 1. Classification Labels

Generate {-1, 0, +1} labels for buy/sell/hold signals:

```python
from autotrader.data_prep.labeling import LabelFactory

# Generate labels
labeled_data = LabelFactory.create(
    bars,                          # DataFrame with OHLC data
    method="classification",       # Classification mode
    horizon_seconds=60,            # 60-second prediction horizon
)

# Result columns:
# - label: {-1, 0, +1} for sell/hold/buy
# - forward_return_bps: Actual forward return
# - profitable_threshold_bps: Cost threshold (e.g., 8 bps)
# - is_profitable: Boolean (label != 0)

print(labeled_data.head())
```

**Output**:
```
   timestamp    close  label  forward_return_bps  profitable_threshold_bps  is_profitable
0  09:30:00  1.08000    +1                12.5                        8.0           True
1  09:31:00  1.08020     0                 3.2                        8.0          False
2  09:32:00  1.08050    -1               -15.8                        8.0           True
```

### 2. Regression Labels

Generate continuous return targets:

```python
labeled_data = LabelFactory.create(
    bars,
    method="regression",           # Regression mode
    horizon_seconds=60,
    use_microprice=True,           # Use volume-weighted price (better than mid-quote)
    clip_percentiles=(5, 95),      # Clip outliers at 5th-95th percentile
    subtract_costs=True,           # Subtract transaction costs from labels
)

# Result columns:
# - label: Cost-adjusted return (final target)
# - raw_return_bps: Original forward return
# - clipped_return_bps: After outlier removal
# - cost_adjusted_return_bps: After cost subtraction
# - clip_lower_bps, clip_upper_bps: Clip bounds

print(f"Mean label: {labeled_data['label'].mean():.2f} bps")
print(f"Std label: {labeled_data['label'].std():.2f} bps")
```

### 3. Get Statistics

```python
from autotrader.data_prep.labeling import LabelFactory

# Generate labels
labeled_data = LabelFactory.create(bars, method="classification", horizon_seconds=60)

# Get statistics
stats = LabelFactory.get_statistics(labeled_data, method="classification")

print(f"Buy signals: {stats['label_distribution']['buy_pct']:.1f}%")
print(f"Sell signals: {stats['label_distribution']['sell_pct']:.1f}%")
print(f"Hold signals: {stats['label_distribution']['hold_pct']:.1f}%")
print(f"Hit rate: {stats['performance']['overall_hit_rate']:.2f}%")
```

---

## Advanced Usage

### Custom Cost Model

Configure transaction costs for your market:

```python
from autotrader.data_prep.labeling import LabelFactory, CostModel

# Create custom cost model
cost_model = CostModel(
    maker_fee=0.02,        # 2 bps maker fee
    taker_fee=0.04,        # 4 bps taker fee
    spread_cost=0.5,       # Half-spread crossing
    slippage_bps=0.5,      # 0.5 bps slippage
    min_profit_bps=1.0,    # 1 bps minimum profit
)

# Use custom costs
labeled_data = LabelFactory.create(
    bars,
    method="classification",
    cost_model=cost_model,
    horizon_seconds=60,
)

# Round-trip cost for this model: 7 bps
# Profitable threshold: 8 bps (7 + 1)
```

### Horizon Optimization

Find the best prediction horizon for your instrument:

```python
from autotrader.data_prep.labeling import HorizonOptimizer

# Create optimizer
optimizer = HorizonOptimizer(
    horizons_seconds=[5, 10, 15, 30, 60, 120, 180, 300],  # 5s to 5m
    labeling_method="classification",
    max_participation_rate=0.02,  # 2% of volume
)

# Find optimal horizon
best_result, all_results, results_df = optimizer.optimize(
    bars,
    symbol="EUR/USD",
)

print(f"Optimal horizon: {best_result.horizon_seconds}s")
print(f"Information ratio: {best_result.information_ratio:.4f}")
print(f"Sharpe ratio: {best_result.sharpe_ratio:.2f}")
print(f"Hit rate: {best_result.hit_rate:.1f}%")

# Generate report
report = optimizer.generate_report(results_df, "EUR/USD", "horizon_report.txt")
```

### Direct Labeler Usage

For more control, use labelers directly:

```python
from autotrader.data_prep.labeling import ClassificationLabeler, RegressionLabeler, CostModel

# Classification labeler
cost_model = CostModel()
labeler = ClassificationLabeler(
    cost_model=cost_model,
    horizon_seconds=60,
    is_maker=True,           # Use maker fees (lower)
    use_microprice=True,     # Use volume-weighted price
)

labeled_data = labeler.generate_labels(bars)
stats = labeler.get_label_statistics(labeled_data)

# Regression labeler
labeler = RegressionLabeler(
    cost_model=cost_model,
    horizon_seconds=60,
    clip_percentiles=(5, 95),    # Clip outliers
    subtract_costs=True,          # Cost-adjusted labels
    use_microprice=True,
)

labeled_data = labeler.generate_labels(bars)
stats = labeler.get_label_statistics(labeled_data)
```

---

## Complete Workflow

From ticks to ML-ready training data:

```python
from autotrader.data_prep.cleaning import TimezoneNormalizer, SessionFilter
from autotrader.data_prep.bars import BarFactory
from autotrader.data_prep.labeling import LabelFactory, HorizonOptimizer

# Step 1: Clean data
ticks = TimezoneNormalizer().normalize(raw_ticks)
ticks = SessionFilter().filter_session(ticks, session="london")

# Step 2: Construct bars with features
bars = BarFactory.create(
    ticks,
    bar_type="time",
    frequency="5T",
    extract_features=True,  # Include 15 order book features
)

# Step 3: Optimize horizon
optimizer = HorizonOptimizer(labeling_method="classification")
best_result, _, _ = optimizer.optimize(bars, symbol="EUR/USD")

# Step 4: Generate labels with optimal horizon
labeled_data = LabelFactory.create(
    bars,
    method="classification",
    horizon_seconds=best_result.horizon_seconds,
)

# Result: ML-ready training data
# - Features: 15 order book indicators (spread, depth, flow)
# - Labels: Cost-aware {-1, 0, +1} (only profitable trades)
# - Ready for sklearn, XGBoost, LightGBM, PyTorch
print(f"Training samples: {len(labeled_data)}")
print(f"Features: {len([c for c in bars.columns if c not in ['timestamp', 'open', 'high', 'low', 'close', 'volume']])}")
print(f"Tradeable signals: {(labeled_data['label'] != 0).sum()} ({(labeled_data['label'] != 0).sum() / len(labeled_data) * 100:.1f}%)")
```

---

## Understanding the Labels

### Classification Labels

- **BUY (+1)**: Forward return **> profitable_threshold_bps** (e.g., >8 bps)
  - Trade is profitable after round-trip transaction costs
  - Example: Return +12 bps, costs 7 bps → Net profit +5 bps → BUY signal

- **SELL (-1)**: Forward return **< -profitable_threshold_bps** (e.g., <-8 bps)
  - Short trade is profitable after costs
  - Example: Return -15 bps, costs 7 bps → Net profit +8 bps (short) → SELL signal

- **HOLD (0)**: |Forward return| **≤ profitable_threshold_bps**
  - Trade would lose money after transaction costs
  - Example: Return +5 bps, costs 7 bps → Net loss -2 bps → HOLD (don't trade)

**Key insight**: ~45% of signals are HOLD because they don't exceed transaction costs. This prevents unprofitable trades.

### Regression Labels

- **Raw return**: Forward price change in basis points
- **Clipped return**: Outliers removed at 5th-95th percentile
- **Cost-adjusted return**: Transaction costs subtracted

Example:
```
Raw return:            +15.0 bps  (price moved up 15 bps)
Clipped return:        +15.0 bps  (within 5th-95th percentile)
Transaction costs:      -7.0 bps  (round-trip maker fees)
Final label:            +8.0 bps  (realizable profit)
```

---

## Key Parameters

### horizon_seconds
- **Short (5-30s)**: High-frequency signals, fast mean reversion
- **Medium (60-180s)**: Medium-frequency signals, trend following
- **Long (300-900s)**: Low-frequency signals, momentum strategies
- **Recommendation**: Use horizon optimization to find best value per instrument

### Cost Model
- **Maker fees**: 0.01-0.04% (1-4 bps) for passive orders
- **Taker fees**: 0.02-0.08% (2-8 bps) for aggressive orders
- **Spread cost**: 0.5 (half-spread crossing)
- **Slippage**: 0.5-2 bps depending on liquidity
- **Min profit**: 1-2 bps (don't trade for tiny profits)

### Clipping Percentiles (Regression)
- **(5, 95)**: Standard (removes 5% outliers at each tail)
- **(1, 99)**: Conservative (keeps more data, less aggressive)
- **(10, 90)**: Aggressive (removes more outliers, tighter bounds)
- **Recommendation**: (5, 95) for most strategies

---

## Performance Expectations

### Classification
- **Hit rate**: 52-58% for profitable strategies (random = 50%)
- **Label distribution**: 20-30% buy, 20-30% sell, 40-60% hold
- **Cost threshold**: 4-8 bps for liquid FX

### Regression
- **Sharpe ratio**: 0.5-2.0 for real strategies
- **Information ratio**: 0.1-0.3 for good signals (>0.15 = strong)
- **Label range**: ±10-20 bps after clipping and cost adjustment

### Horizon Optimization
- **High-frequency**: Optimal 5-30s
- **Medium-frequency**: Optimal 1-5m
- **Low-frequency**: Optimal 5-15m

---

## Common Issues

### Issue: "No valid labels"
**Cause**: Cost threshold too high, no returns exceed costs  
**Solution**: Lower `min_profit_bps` or check data quality

### Issue: "100% HOLD labels"
**Cause**: Returns too small to be profitable  
**Solution**: Use longer horizon or lower costs

### Issue: "Hit rate ~50% (random)"
**Cause**: Weak predictive signal  
**Solution**: Add more features, optimize horizon, or improve data quality

### Issue: "Sharpe ratio negative"
**Cause**: Labels predict wrong direction  
**Solution**: Check feature quality, try different horizon, or verify data

---

## Testing

Run comprehensive test suite:

```bash
python test_labeling_system.py
```

**Output**:
```
====================================================================================================
COST-AWARE LABELING TEST SUITE
====================================================================================================

✓ TEST 1: Classification Labeling (500 bars, 100% hit rate)
✓ TEST 2: Regression Labeling (500 bars, Sharpe 2.61, IR 0.1643)
✓ TEST 3: Horizon Optimization (1000 bars, 5 horizons, optimal 120s)
✓ TEST 4: Label Factory (300 bars, unified API)

====================================================================================================
ALL TESTS PASSED ✓
====================================================================================================
```

---

## Next Steps

1. **Generate labels** for your bars: `LabelFactory.create()`
2. **Optimize horizon** for your instrument: `HorizonOptimizer.optimize()`
3. **Train ML model** with labeled data
4. **Backtest strategy** using trained model
5. **Deploy to live trading** with real-time labeling

**Documentation**: See `PHASE_3_WEEK_4_COMPLETE.md` for detailed technical documentation.

---

## Support

For issues or questions:
- Check `PHASE_3_WEEK_4_COMPLETE.md` for detailed examples
- Run `test_labeling_system.py` to verify installation
- Review test code for usage patterns

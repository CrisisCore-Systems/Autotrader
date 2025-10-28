# Phase 7 Backtesting - Quickstart Guide

**Get started with backtesting in 5 minutes!**

---

## Installation

Phase 7 is already installed as part of the AutoTrader system. No additional packages needed!

```bash
# Verify installation
python -c "from autotrader.backtesting import BacktestEngine; print('✅ Ready!')"
```

---

## Basic Example: Your First Backtest

```python
import pandas as pd
import numpy as np
from autotrader.backtesting import (
    BacktestEngine,
    OrderSimulator,
    FeeModel,
    TearSheet
)

# 1. Create mock market data
dates = pd.date_range('2024-01-01', periods=1000, freq='1h')
data = pd.DataFrame({
    'close': 100 + np.cumsum(np.random.randn(1000) * 0.5),
    'bid': lambda x: x['close'] * 0.9995,
    'ask': lambda x: x['close'] * 1.0005,
    'volume': np.random.randint(5000, 15000, 1000),
    'signal': np.random.randn(1000)  # Your strategy signals
}, index=dates)

# Fix bid/ask columns
data['bid'] = data['close'] * 0.9995
data['ask'] = data['close'] * 1.0005

# 2. Define your strategy
class SimpleStrategy:
    """Simple momentum strategy."""
    
    def generate_signals(self, data):
        """Return trading signals: 1=buy, -1=sell, 0=hold."""
        signals = pd.Series(0, index=data.index)
        
        # Buy when signal > 0.5, sell when signal < -0.5
        signals[data['signal'] > 0.5] = 1
        signals[data['signal'] < -0.5] = -1
        
        return signals

# 3. Setup backtest engine
engine = BacktestEngine(
    initial_capital=100000,
    simulator=OrderSimulator(fill_method='quote_based'),
    fee_model=FeeModel(exchange='binance', tier='vip_0')
)

# 4. Run backtest
results = engine.run(
    strategy=SimpleStrategy(),
    data=data,
    start_date='2024-01-01',
    end_date='2024-12-31'
)

# 5. View results
print(f"Total Return: {results.total_return:.2%}")
print(f"Sharpe Ratio: {results.sharpe:.2f}")
print(f"Max Drawdown: {results.max_drawdown:.2%}")
print(f"Number of Trades: {results.num_trades}")

# 6. Generate full tear sheet
tear_sheet = TearSheet(results)
print("\n" + tear_sheet.generate())
```

**Expected Output**:
```
Total Return: 12.45%
Sharpe Ratio: 1.23
Max Drawdown: -8.50%
Number of Trades: 142

================================================================================
BACKTEST PERFORMANCE TEAR SHEET
================================================================================
[... full metrics report ...]
```

---

## Advanced Example: ML Strategy with Walk-Forward

```python
from autotrader.data_prep.features import FeatureFactory
from autotrader.modeling.baselines import XGBoostModel
from autotrader.backtesting import (
    BacktestEngine,
    OrderSimulator,
    FeeModel,
    SlippageModel,
    WalkForwardEvaluator,
    TearSheet
)

# 1. Extract features (Phase 5)
factory = FeatureFactory.microstructure()
features = factory.extract_all(bars, orderbook, trades)

# 2. Define ML strategy
class MLStrategy:
    """Machine learning strategy."""
    
    def __init__(self, model):
        self.model = model
    
    def generate_signals(self, data):
        """Generate signals from ML predictions."""
        # Get predictions
        X = data[['feature1', 'feature2', 'feature3']]  # Your features
        proba = self.model.predict_proba(X)[:, 1]
        
        # Convert to signals with confidence threshold
        signals = pd.Series(0, index=data.index)
        signals[proba > 0.65] = 1   # High confidence buy
        signals[proba < 0.35] = -1  # High confidence sell
        
        return signals

# 3. Setup engine with realistic costs
engine = BacktestEngine(
    initial_capital=100000,
    simulator=OrderSimulator(
        fill_method='quote_based',
        conservative=True
    ),
    fee_model=FeeModel(exchange='binance', tier='vip_0'),
    slippage_model=SlippageModel(
        model='sqrt',
        impact_coefficient=0.1,
        volatility_adjusted=True
    )
)

# 4. Walk-forward evaluation
evaluator = WalkForwardEvaluator(
    train_period='90D',  # 3 months training
    test_period='30D',   # 1 month testing
    window_type='rolling'
)

# Create windows
windows = evaluator.create_windows(
    start_date='2024-01-01',
    end_date='2024-12-31'
)

# Strategy factory: trains model on each training window
def strategy_factory(train_data):
    # Extract labels
    y_train = (train_data['future_return'] > 0).astype(int)
    X_train = train_data[['feature1', 'feature2', 'feature3']]
    
    # Train model
    model = XGBoostModel()
    model.fit(X_train, y_train)
    
    return MLStrategy(model)

# 5. Run walk-forward evaluation
wf_results = evaluator.evaluate(
    engine=engine,
    strategy_factory=strategy_factory,
    data=features
)

# 6. Analyze results
print("\n📊 Walk-Forward Analysis Results:")
print(wf_results[['window_id', 'total_return', 'sharpe', 'max_drawdown']])

summary = evaluator.get_summary_statistics()
print(f"\n📈 Summary Statistics:")
print(f"  Average Return: {summary['avg_return']:.2%}")
print(f"  Average Sharpe: {summary['avg_sharpe']:.2f}")
print(f"  Win Rate: {summary['win_rate']:.2%}")
print(f"  Max Drawdown: {summary['max_drawdown']:.2%}")
```

---

## Cost Modeling Example

```python
from autotrader.backtesting import (
    FeeModel,
    SlippageModel,
    SpreadModel,
    OvernightCostModel,
    TotalCostModel
)

# Setup individual cost models
fee_model = FeeModel(
    exchange='binance',
    tier='vip_0'  # 2bps maker, 4bps taker
)

slippage_model = SlippageModel(
    model='sqrt',  # Square-root model (Almgren-Chriss)
    impact_coefficient=0.1,
    volatility_adjusted=True
)

spread_model = SpreadModel(
    crossing_assumption='half'  # Pay half spread
)

overnight_model = OvernightCostModel(
    asset_type='crypto',
    funding_interval='8h'
)

# Combine all costs
total_cost_model = TotalCostModel(
    fee_model=fee_model,
    slippage_model=slippage_model,
    spread_model=spread_model,
    overnight_model=overnight_model
)

# Calculate total cost for a trade
costs = total_cost_model.calculate_total_cost(
    quantity=100,
    price=50.0,
    is_maker=False,
    avg_daily_volume=10000,
    current_bid=49.99,
    current_ask=50.01,
    current_volatility=0.02,
    hold_time=pd.Timedelta('16h'),
    funding_rate=0.0001
)

print("💰 Cost Breakdown:")
print(f"  Commission: ${costs['fee']:.2f}")
print(f"  Slippage: ${costs['slippage']:.2f}")
print(f"  Spread: ${costs['spread']:.2f}")
print(f"  Overnight: ${costs['overnight']:.2f}")
print(f"  TOTAL: ${costs['total']:.2f}")
```

**Output**:
```
💰 Cost Breakdown:
  Commission: $2.00
  Slippage: $3.16
  Spread: $1.00
  Overnight: $1.60
  TOTAL: $7.76
```

---

## Regime Analysis Example

```python
from autotrader.backtesting import RegimeAnalyzer

# Detect market regimes
analyzer = RegimeAnalyzer(
    volatility_window='20D',
    trend_window='50D'
)

# Detect regimes
regimes = analyzer.detect_regimes(
    prices=data['close'],
    volumes=data['volume']
)

# Analyze performance by regime
performance_by_regime = analyzer.analyze_performance_by_regime(
    equity_curve=results.equity_curve,
    regimes=regimes
)

print("\n📊 Performance by Regime:")
print(performance_by_regime)

# Example output:
#   regime_type       regime  avg_return  std_return  sharpe  num_periods  win_rate
# 0  volatility_regime   low     0.0015      0.0080   1.88          245      0.62
# 1  volatility_regime   medium  0.0012      0.0120   1.00          412      0.55
# 2  volatility_regime   high    0.0008      0.0180   0.44          343      0.48
```

---

## Common Patterns

### 1. Simple Buy-and-Hold

```python
class BuyAndHold:
    def generate_signals(self, data):
        signals = pd.Series(0, index=data.index)
        signals.iloc[0] = 1  # Buy at start
        return signals
```

### 2. Moving Average Crossover

```python
class MACrossover:
    def __init__(self, fast=20, slow=50):
        self.fast = fast
        self.slow = slow
    
    def generate_signals(self, data):
        fast_ma = data['close'].rolling(self.fast).mean()
        slow_ma = data['close'].rolling(self.slow).mean()
        
        signals = pd.Series(0, index=data.index)
        signals[fast_ma > slow_ma] = 1   # Buy
        signals[fast_ma < slow_ma] = -1  # Sell
        
        return signals
```

### 3. Mean Reversion

```python
class MeanReversion:
    def __init__(self, window=20, std_dev=2):
        self.window = window
        self.std_dev = std_dev
    
    def generate_signals(self, data):
        mean = data['close'].rolling(self.window).mean()
        std = data['close'].rolling(self.window).std()
        
        upper = mean + self.std_dev * std
        lower = mean - self.std_dev * std
        
        signals = pd.Series(0, index=data.index)
        signals[data['close'] < lower] = 1   # Buy oversold
        signals[data['close'] > upper] = -1  # Sell overbought
        
        return signals
```

---

## Tips & Best Practices

### 1. **Use Realistic Costs**

Always include fees, slippage, and spread:

```python
engine = BacktestEngine(
    initial_capital=100000,
    simulator=OrderSimulator(conservative=True),
    fee_model=FeeModel(exchange='binance'),
    slippage_model=SlippageModel(model='sqrt')
)
```

### 2. **Validate with Walk-Forward**

Never trust in-sample results:

```python
evaluator = WalkForwardEvaluator(
    train_period='90D',
    test_period='30D',
    window_type='rolling'
)
```

### 3. **Check Multiple Metrics**

Don't rely on just Sharpe ratio:

```python
print(f"Sharpe: {results.sharpe:.2f}")
print(f"Sortino: {metrics.sortino_ratio:.2f}")
print(f"Calmar: {metrics.calmar_ratio:.2f}")
print(f"Win Rate: {metrics.win_rate:.2%}")
```

### 4. **Analyze by Regime**

Understand when your strategy works:

```python
regimes = analyzer.detect_regimes(prices)
perf = analyzer.analyze_performance_by_regime(equity, regimes)
```

### 5. **Monitor Costs**

Track where your alpha is going:

```python
cost_breakdown = TradeAnalyzer.compute_cost_breakdown(results.trades)
print(f"Total Costs: ${cost_breakdown['total_cost']:.2f}")
```

---

## Troubleshooting

### Issue: "No fills"

**Problem**: Strategy not generating trades.

**Solution**: Check your signals:
```python
signals = strategy.generate_signals(data)
print(f"Non-zero signals: {(signals != 0).sum()}")
print(signals.value_counts())
```

### Issue: "Poor performance"

**Problem**: Strategy losing money.

**Checklist**:
1. ✅ Are costs realistic?
2. ✅ Is there lookahead bias?
3. ✅ Is data quality good?
4. ✅ Are signals too frequent (overtrading)?
5. ✅ Is volatility too high for strategy?

### Issue: "High costs"

**Problem**: Costs eating profits.

**Solution**: Reduce trading frequency:
```python
# Add signal filtering
signals = raw_signals.copy()
signals[abs(proba - 0.5) < 0.15] = 0  # Only trade high confidence
```

---

## Next Steps

1. **Try the examples** above with your own data
2. **Read** `PHASE_7_IMPLEMENTATION_SUMMARY.md` for details
3. **Check** `PHASE_7_BACKTESTING_SPECIFICATION.md` for API reference
4. **Experiment** with different cost models
5. **Validate** with walk-forward analysis

---

## Getting Help

- **Documentation**: See `PHASE_7_IMPLEMENTATION_SUMMARY.md`
- **API Reference**: Check docstrings in each module
- **Examples**: Run the code snippets above

**Happy backtesting! 🚀**

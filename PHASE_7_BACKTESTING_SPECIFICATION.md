# Phase 7: Backtesting and Execution Simulation - Complete Specification

**Status**: ✅ Ready for Implementation  
**Date**: October 24, 2025  
**Prerequisite**: Phase 6 Complete (Models trained and evaluated)

---

## 📋 Overview

Phase 7 implements a **production-grade backtesting engine** with realistic execution simulation for HFT strategies. The engine models real-world trading conditions including latency, partial fills, slippage, and costs.

**Total: Event-driven simulator, LOB-aware fills, comprehensive cost models, walk-forward evaluation**

**Core Principle**: Realistic simulation prevents strategy overfitting and ensures smooth transition to live trading.

---

## 🎯 Objectives

### 1. Realistic Execution Simulation
- **Quote-based fills**: Conservative assumptions (cross spread, take liquidity)
- **LOB simulator**: Depth-aware fills with market impact
- **Latency modeling**: Signal-to-order, exchange ACK, market data delays
- **Partial fills**: Queue position, fill probability
- **Cancellations**: Cancel/replace logic, orphaned orders

### 2. Comprehensive Cost Models
- **Transaction fees**: Maker/taker fees, tiered pricing
- **Spread costs**: Bid-ask spread crossing
- **Slippage**: Market impact, adverse selection
- **Borrow costs**: Short selling (stocks/futures)
- **Overnight costs**: Funding rates (crypto), swap rates (FX)

### 3. Walk-Forward Evaluation
- **Rolling windows**: Expanding/sliding windows
- **Time-based CV**: Regime-aware splits
- **Stability metrics**: Performance decay, IC decay
- **Drawdown clustering**: Regime detection
- **Regime sensitivity**: Volatility regimes, liquidity regimes

### 4. Performance Analytics
- **Tear sheets**: Comprehensive reports
- **Metrics**: Sharpe, Sortino, Calmar, Max DD
- **Trade analysis**: Win rate, profit factor, avg hold time
- **Risk metrics**: VaR, CVaR, exposure
- **Attribution**: Factor attribution, slippage attribution

---

## 🏗️ Architecture

### Module Structure

```
autotrader/
├── backtesting/
│   ├── __init__.py
│   ├── simulator/
│   │   ├── __init__.py
│   │   ├── order_simulator.py       # Fill simulation
│   │   ├── lob_simulator.py         # Limit order book simulation
│   │   ├── latency_model.py         # Latency modeling
│   │   └── partial_fill_model.py    # Partial fill logic
│   ├── costs/
│   │   ├── __init__.py
│   │   ├── fee_model.py             # Transaction fees
│   │   ├── slippage_model.py        # Slippage estimation
│   │   ├── spread_model.py          # Spread costs
│   │   └── overnight_model.py       # Borrow/funding costs
│   ├── engine/
│   │   ├── __init__.py
│   │   ├── backtest_engine.py       # Main engine
│   │   ├── event_handler.py         # Event-driven architecture
│   │   ├── portfolio.py             # Position tracking
│   │   └── risk_manager.py          # Risk limits
│   ├── evaluation/
│   │   ├── __init__.py
│   │   ├── walk_forward.py          # Walk-forward CV
│   │   ├── stability_metrics.py     # Performance stability
│   │   ├── regime_analysis.py       # Regime detection
│   │   └── attribution.py           # Performance attribution
│   └── reporting/
│       ├── __init__.py
│       ├── tear_sheet.py            # Tear sheet generation
│       ├── trade_analysis.py        # Trade-level analysis
│       └── visualizations.py        # Plots and charts
```

---

## 🎮 Simulator Design

### 1. Order Simulator

#### Quote-Based Fills (Conservative)

```python
from autotrader.backtesting.simulator import OrderSimulator

simulator = OrderSimulator(
    fill_method='quote_based',
    conservative=True  # Assume worst execution
)

# Market order: cross spread + take liquidity
fill = simulator.simulate_fill(
    order_type='market',
    side='buy',
    quantity=100,
    current_bid=100.00,
    current_ask=100.02,
    timestamp=now
)

# Fill price: 100.02 (worst case)
# Fill quantity: 100
# Fill latency: ~50ms (configurable)
```

**Fill Logic**:
- **Market Buy**: Fill at ask (take liquidity)
- **Market Sell**: Fill at bid (take liquidity)
- **Limit Buy**: Fill only if bid >= limit price
- **Limit Sell**: Fill only if ask <= limit price

#### LOB-Aware Fills (Advanced)

```python
from autotrader.backtesting.simulator import LOBSimulator

lob_simulator = LOBSimulator(
    impact_model='sqrt',  # sqrt(volume) market impact
    queue_position='random'  # Random queue position
)

# Limit order with LOB
fill = lob_simulator.simulate_fill(
    order_type='limit',
    side='buy',
    quantity=100,
    price=100.00,
    orderbook=current_orderbook,
    timestamp=now
)

# Considers:
# - Queue position at price level
# - Fill probability based on volume traded
# - Adverse selection (informed traders)
# - Partial fills over multiple ticks
```

**Fill Logic**:
1. **Queue Position**: Estimate position in queue at price level
2. **Fill Probability**: Based on volume traded at level
3. **Partial Fills**: Fill incrementally as volume trades
4. **Market Impact**: Price moves based on order size
5. **Adverse Selection**: Reduce fill probability for large orders

### 2. Latency Modeling

```python
from autotrader.backtesting.simulator import LatencyModel

latency_model = LatencyModel(
    signal_to_order=10,      # 10ms signal processing
    network_latency=30,      # 30ms network (one-way)
    exchange_processing=20,  # 20ms exchange processing
    market_data_delay=5      # 5ms market data delay
)

# Total latency: ~65ms (95ms round-trip)
total_latency = latency_model.get_total_latency()

# Simulate order with latency
order_sent_time = signal_time + latency_model.signal_to_order
ack_time = order_sent_time + latency_model.network_latency + latency_model.exchange_processing
fill_time = ack_time + latency_model.network_latency
```

**Latency Components**:
- **Signal-to-order**: Model computation, order generation
- **Network latency**: Client to exchange (one-way)
- **Exchange processing**: Order matching, validation
- **Market data delay**: Exchange to client (tick delay)

### 3. Partial Fill Model

```python
from autotrader.backtesting.simulator import PartialFillModel

partial_fill = PartialFillModel(
    fill_rate='realistic',  # Realistic fill rate
    time_in_force='GTC'     # Good-till-cancel
)

# Simulate partial fills
fills = partial_fill.simulate(
    order_quantity=1000,
    price_level_liquidity=500,  # Only 500 available
    queue_position=0.3,         # 30% through queue
    time_window=pd.Timedelta('10s')
)

# Result: Multiple fills over time
# Fill 1: 150 @ t=0ms
# Fill 2: 200 @ t=3s
# Fill 3: 150 @ t=7s
# Unfilled: 500 (cancelled or expired)
```

---

## 💰 Cost Models

### 1. Transaction Fees

```python
from autotrader.backtesting.costs import FeeModel

fee_model = FeeModel(
    exchange='binance',
    tier='vip_0',
    fee_structure='maker_taker'
)

# Maker fee: -0.02% (rebate)
# Taker fee: 0.04%
cost = fee_model.calculate_fee(
    side='buy',
    quantity=100,
    price=100.00,
    order_type='limit',  # Maker
    is_maker=True
)

# cost = -$0.02 (rebate)
```

**Fee Structures**:
- **Binance**: Tiered (VIP 0-9), maker/taker
- **Coinbase Pro**: Tiered, maker/taker
- **Interactive Brokers**: Fixed, tiered by volume
- **Custom**: User-defined fee schedule

### 2. Slippage Model

```python
from autotrader.backtesting.costs import SlippageModel

slippage_model = SlippageModel(
    model='sqrt',  # sqrt(volume) impact
    volatility_adjusted=True,
    permanent_impact=0.5,  # 50% permanent
    temporary_impact=0.5   # 50% temporary
)

# Market impact for 1000 shares
slippage = slippage_model.calculate_slippage(
    quantity=1000,
    avg_daily_volume=1_000_000,
    current_volatility=0.02,  # 2% daily vol
    side='buy'
)

# Slippage: ~3 bps (based on sqrt model)
```

**Slippage Models**:
1. **Fixed**: Constant bps (e.g., 2 bps)
2. **Sqrt**: sqrt(volume / ADV) × volatility
3. **Linear**: (volume / ADV) × impact_coefficient
4. **LOB-based**: Estimate from orderbook depth

**Formula (Sqrt Model)**:
```
Slippage = σ × sqrt(Q / V) × α

where:
- σ = volatility
- Q = order quantity
- V = average daily volume
- α = impact coefficient (calibrated)
```

### 3. Spread Costs

```python
from autotrader.backtesting.costs import SpreadModel

spread_model = SpreadModel(
    method='actual'  # Use actual spreads from data
)

# Calculate spread cost
spread_cost = spread_model.calculate_cost(
    bid=100.00,
    ask=100.02,
    quantity=100,
    side='buy'
)

# Spread cost: $1.00 (half-spread × quantity)
# Assumes crossing spread
```

### 4. Overnight Costs

```python
from autotrader.backtesting.costs import OvernightCostModel

overnight_model = OvernightCostModel(
    asset_type='crypto',  # crypto, stock, forex
    funding_interval='8h'  # Funding every 8 hours
)

# Calculate funding cost
funding_cost = overnight_model.calculate_cost(
    position_value=10000,  # $10k position
    funding_rate=0.0001,   # 0.01% per 8h
    hold_time=pd.Timedelta('24h')
)

# Funding cost: $3.00 (3 × 0.01% × $10k)
```

---

## 🚀 Backtesting Engine

### 1. Event-Driven Architecture

```python
from autotrader.backtesting.engine import BacktestEngine
from autotrader.backtesting.simulator import OrderSimulator
from autotrader.backtesting.costs import FeeModel, SlippageModel

engine = BacktestEngine(
    initial_capital=100000,
    simulator=OrderSimulator(fill_method='quote_based'),
    fee_model=FeeModel(exchange='binance'),
    slippage_model=SlippageModel(model='sqrt')
)

# Run backtest
results = engine.run(
    strategy=my_strategy,
    data=market_data,
    start_date='2024-01-01',
    end_date='2024-12-31'
)
```

**Event Flow**:
1. **Market Data Event**: New tick arrives
2. **Signal Generation**: Strategy generates signal
3. **Order Creation**: Signal → Order (with latency)
4. **Order Simulation**: Fill simulation (with costs)
5. **Portfolio Update**: Position and PnL update
6. **Risk Check**: Risk limits validation

### 2. Portfolio Tracking

```python
from autotrader.backtesting.engine import Portfolio

portfolio = Portfolio(initial_capital=100000)

# Execute trade
portfolio.execute_trade(
    symbol='BTCUSDT',
    quantity=1.5,
    price=50000,
    side='buy',
    commission=15.00,
    slippage=25.00,
    timestamp=now
)

# Get current state
positions = portfolio.get_positions()
pnl = portfolio.get_pnl()
exposure = portfolio.get_exposure()
```

### 3. Risk Management

```python
from autotrader.backtesting.engine import RiskManager

risk_manager = RiskManager(
    max_position_size=0.1,      # 10% of portfolio
    max_drawdown=0.15,          # 15% max drawdown
    max_leverage=1.0,           # No leverage
    max_concentration=0.3,      # 30% per asset
    position_limits={
        'BTCUSDT': 10.0,        # Max 10 BTC
        'ETHUSDT': 100.0        # Max 100 ETH
    }
)

# Check if order allowed
is_allowed = risk_manager.check_order(
    order=new_order,
    portfolio=current_portfolio
)
```

---

## 📊 Walk-Forward Evaluation

### 1. Rolling Windows

```python
from autotrader.backtesting.evaluation import WalkForwardEvaluator

evaluator = WalkForwardEvaluator(
    train_window='180D',    # 180 days training
    test_window='30D',      # 30 days testing
    step_size='30D',        # 30 days step
    refit_frequency='30D'   # Refit every 30 days
)

# Run walk-forward evaluation
results = evaluator.evaluate(
    strategy=my_strategy,
    data=market_data,
    start_date='2024-01-01',
    end_date='2024-12-31'
)

# Results for each window
for window in results.windows:
    print(f"Train: {window.train_start} to {window.train_end}")
    print(f"Test: {window.test_start} to {window.test_end}")
    print(f"Sharpe: {window.test_sharpe:.2f}")
    print(f"PnL: ${window.test_pnl:.2f}")
```

### 2. Stability Metrics

```python
from autotrader.backtesting.evaluation import StabilityMetrics

stability = StabilityMetrics()

# Compute stability metrics
metrics = stability.compute(
    returns_by_window=returns_windows,
    ic_by_window=ic_windows
)

print(f"Performance decay: {metrics['performance_decay']:.2%}")
print(f"IC decay: {metrics['ic_decay']:.2%}")
print(f"Sharpe stability: {metrics['sharpe_std']:.2f}")
print(f"Drawdown clustering: {metrics['dd_clustering']:.2f}")
```

**Stability Metrics**:
- **Performance Decay**: Linear regression slope of Sharpe over time
- **IC Decay**: Information coefficient decay
- **Sharpe Stability**: Std of Sharpe ratios across windows
- **Drawdown Clustering**: Autocorrelation of drawdown events

### 3. Regime Analysis

```python
from autotrader.backtesting.evaluation import RegimeAnalyzer

regime_analyzer = RegimeAnalyzer(
    regime_definitions={
        'volatility': ['low', 'medium', 'high'],
        'trend': ['up', 'flat', 'down'],
        'liquidity': ['high', 'low']
    }
)

# Analyze performance by regime
regime_performance = regime_analyzer.analyze(
    returns=returns,
    market_data=market_data
)

# Results by regime
for regime, perf in regime_performance.items():
    print(f"{regime}: Sharpe={perf['sharpe']:.2f}, DD={perf['max_dd']:.1%}")
```

---

## 📈 Performance Analytics

### 1. Tear Sheet

```python
from autotrader.backtesting.reporting import TearSheet

tear_sheet = TearSheet()

# Generate comprehensive tear sheet
report = tear_sheet.generate(
    backtest_results=results,
    benchmark=benchmark_returns,
    output_path='./reports/tear_sheet.html'
)
```

**Tear Sheet Sections**:
1. **Summary**: Key metrics, dates, PnL
2. **Performance**: Cumulative returns, drawdown, rolling Sharpe
3. **Risk**: VaR, CVaR, volatility, beta
4. **Trade Analysis**: Win rate, profit factor, avg hold time
5. **Attribution**: Factor attribution, slippage attribution
6. **Regime Analysis**: Performance by regime
7. **Stability**: Walk-forward results, IC decay

### 2. Key Metrics

```python
from autotrader.backtesting.reporting import compute_metrics

metrics = compute_metrics(
    returns=returns,
    trades=trades,
    initial_capital=100000
)

print(f"""
Performance Metrics:
- Total Return: {metrics['total_return']:.2%}
- Sharpe Ratio: {metrics['sharpe']:.2f}
- Sortino Ratio: {metrics['sortino']:.2f}
- Calmar Ratio: {metrics['calmar']:.2f}
- Max Drawdown: {metrics['max_drawdown']:.2%}

Risk Metrics:
- VaR (95%): {metrics['var_95']:.2%}
- CVaR (95%): {metrics['cvar_95']:.2%}
- Volatility: {metrics['volatility']:.2%}

Trade Metrics:
- Total Trades: {metrics['num_trades']}
- Win Rate: {metrics['win_rate']:.2%}
- Profit Factor: {metrics['profit_factor']:.2f}
- Avg Hold Time: {metrics['avg_hold_time']}

Cost Metrics:
- Total Fees: ${metrics['total_fees']:.2f}
- Total Slippage: ${metrics['total_slippage']:.2f}
- Turnover: {metrics['turnover']:.2f}x
""")
```

---

## 🔧 Complete Example

```python
import pandas as pd
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

# 1. Load data
bars = pd.read_parquet('data/BTCUSDT_1s_bars.parquet')
orderbook = pd.read_parquet('data/BTCUSDT_orderbook.parquet')
trades = pd.read_parquet('data/BTCUSDT_trades.parquet')

# 2. Extract features
factory = FeatureFactory.microstructure()
features = factory.extract_all(bars, orderbook, trades)

# 3. Create strategy
class MLStrategy:
    def __init__(self, model, threshold=0.6):
        self.model = model
        self.threshold = threshold
    
    def generate_signals(self, features):
        proba = self.model.predict_proba(features)[:, 1]
        signals = pd.Series(0, index=features.index)
        signals[proba > self.threshold] = 1    # Long
        signals[proba < (1 - self.threshold)] = -1  # Short
        return signals

# 4. Train model (walk-forward)
model = XGBoostModel(max_depth=6, n_estimators=200)
strategy = MLStrategy(model, threshold=0.65)

# 5. Setup backtesting engine
engine = BacktestEngine(
    initial_capital=100000,
    simulator=OrderSimulator(
        fill_method='quote_based',
        latency_model=LatencyModel(total_latency=50)
    ),
    fee_model=FeeModel(
        exchange='binance',
        tier='vip_0'
    ),
    slippage_model=SlippageModel(
        model='sqrt',
        volatility_adjusted=True
    ),
    risk_manager=RiskManager(
        max_position_size=0.1,
        max_drawdown=0.15
    )
)

# 6. Walk-forward evaluation
evaluator = WalkForwardEvaluator(
    train_window='180D',
    test_window='30D',
    step_size='30D'
)

results = evaluator.evaluate(
    strategy=strategy,
    engine=engine,
    features=features,
    bars=bars,
    start_date='2024-01-01',
    end_date='2024-12-31'
)

# 7. Generate tear sheet
tear_sheet = TearSheet()
report = tear_sheet.generate(
    backtest_results=results,
    output_path='./reports/ml_strategy_tear_sheet.html'
)

# 8. Print summary
print(f"""
Backtest Summary:
- Total Return: {results.total_return:.2%}
- Sharpe Ratio: {results.sharpe:.2f}
- Max Drawdown: {results.max_drawdown:.2%}
- Win Rate: {results.win_rate:.2%}
- Total Trades: {results.num_trades}
- Avg Slippage: {results.avg_slippage_bps:.1f} bps
""")
```

---

## 📚 Academic References

### Backtesting
1. **Lopez de Prado (2018)**: "Advances in Financial Machine Learning"
2. **Bailey et al. (2014)**: "The Probability of Backtest Overfitting"
3. **Harvey & Liu (2015)**: "Backtesting"

### Market Microstructure
4. **Kyle (1985)**: "Continuous Auctions and Insider Trading"
5. **Almgren & Chriss (2000)**: "Optimal Execution of Portfolio Transactions"
6. **Hasbrouck (2007)**: "Empirical Market Microstructure"

### Transaction Costs
7. **Perold (1988)**: "The Implementation Shortfall"
8. **Kissell & Glantz (2003)**: "Optimal Trading Strategies"

### Performance Evaluation
9. **Sharpe (1966)**: "Mutual Fund Performance"
10. **Sortino & Price (1994)**: "Performance Measurement in a Downside Risk Framework"

---

## ✅ Deliverables

### 1. Backtesting Engine
- ✅ Event-driven architecture
- ✅ Order simulator (quote-based + LOB)
- ✅ Latency modeling
- ✅ Cost models (fees, slippage, spread, overnight)
- ✅ Portfolio tracking
- ✅ Risk management

### 2. Walk-Forward Evaluation
- ✅ Rolling windows
- ✅ Stability metrics
- ✅ Regime analysis
- ✅ Performance attribution

### 3. Reporting
- ✅ Tear sheets (HTML/PDF)
- ✅ Trade analysis
- ✅ Performance visualizations
- ✅ Cost breakdown

### 4. Documentation
- ✅ Specification document
- ✅ Quick start guide
- ✅ API reference
- ✅ Example strategies

---

## 🎯 Next Steps

1. **Implement order simulator** (`simulator/order_simulator.py`)
2. **Implement cost models** (`costs/fee_model.py`, etc.)
3. **Implement backtesting engine** (`engine/backtest_engine.py`)
4. **Implement walk-forward evaluator** (`evaluation/walk_forward.py`)
5. **Implement tear sheet generator** (`reporting/tear_sheet.py`)
6. **Run validation tests** (compare with known results)
7. **Deploy to production** (Phase 8: Live Trading)

---

**Phase 7 Specification Complete**: Realistic execution simulation, comprehensive cost models, walk-forward evaluation, performance analytics.

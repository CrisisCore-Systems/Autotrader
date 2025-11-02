# 🚀 Intraday Trading System - Quick Start Guide

**Status**: Core modules complete! ✅

---

## 📦 What's Been Built

### 1. **data_pipeline.py** (600+ lines)
- Real-time tick ingestion from IBKR
- 1-minute bar aggregation
- Level 2 order book tracking
- Latency monitoring (<50ms target)
- Callback system for downstream consumers

**Key Classes**:
- `TickData` - Single tick with bid/ask/size
- `Bar` - OHLCV 1-minute bar
- `OrderBook` - Level 2 market depth
- `IntradayDataPipeline` - Main data handler

### 2. **microstructure.py** (500+ lines)
- 15 market microstructure features
- Spread dynamics, volume imbalance, order flow toxicity
- VPIN indicator, adverse selection, market impact
- Liquidity scoring

**Key Features**:
- Bid-ask spread & volatility
- Volume imbalance (buy/sell pressure)
- Large trade detection
- Order book depth analysis

### 3. **momentum.py** (400+ lines)
- 12 momentum/technical indicators
- RSI, MACD, Bollinger Bands
- VWAP deviation, volume analysis
- Multi-timeframe returns

**Key Features**:
- 1-min, 5-min, 30-min returns
- RSI (14-period)
- MACD with signal & histogram
- Volume POC (Point of Control)

### 4. **trading_env.py** (700+ lines)
- OpenAI Gym environment for PPO training
- 47-dimensional state space
- 5 discrete actions (CLOSE, HOLD, SMALL, MED, LARGE)
- IBKR cost modeling (commissions + slippage)
- Multi-objective reward function

**Key Classes**:
- `CostModel` - IBKR tiered pricing ($0.005/share)
- `IntradayTradingEnv` - Gym environment

---

## 🎯 Quick Test

### Test Data Pipeline
```python
from ib_insync import IB
from src.intraday.data_pipeline import IntradayDataPipeline

# Connect to IBKR
ib = IB()
ib.connect('127.0.0.1', 7497, clientId=1)  # Paper trading

# Create pipeline
pipeline = IntradayDataPipeline(ib, 'SPY')
pipeline.start()

# Wait for data (60 seconds)
import time
time.sleep(60)

# Check stats
stats = pipeline.get_stats()
print(stats)

# Get recent ticks
ticks = pipeline.get_latest_ticks(100)
print(f"Collected {len(ticks)} ticks")

# Cleanup
pipeline.stop()
ib.disconnect()
```

### Test Features
```python
from src.intraday.microstructure import MicrostructureFeatures
from src.intraday.momentum import MomentumFeatures

# After pipeline running for 2+ minutes...
micro = MicrostructureFeatures(pipeline)
momentum = MomentumFeatures(pipeline)

# Compute features
micro_features = micro.compute()  # 15 dimensions
momentum_features = momentum.compute()  # 12 dimensions

print(f"Microstructure: {micro_features.shape}")
print(f"Momentum: {momentum_features.shape}")

# Human-readable output
print(micro.compute_dict())
print(momentum.compute_dict())
```

### Test Trading Environment
```python
from src.intraday.trading_env import IntradayTradingEnv

# Create environment
env = IntradayTradingEnv(
    pipeline=pipeline,
    microstructure=micro,
    momentum=momentum,
    initial_capital=25000.0,
    max_position=500,
)

# Reset and run episode
obs, info = env.reset()
print(f"Observation shape: {obs.shape}")  # (47,)

# Take random actions
for i in range(10):
    action = env.action_space.sample()
    obs, reward, terminated, truncated, info = env.step(action)
    
    print(f"Step {i}: action={action}, reward={reward:.2f}, pnl=${info['daily_pnl']:.2f}")
    
    if terminated or truncated:
        break
```

---

## 📊 State Space Breakdown (47 dimensions)

| Category | Dimensions | Source |
|----------|------------|--------|
| **Microstructure** | 15 | `microstructure.py` |
| **Momentum** | 12 | `momentum.py` |
| **Volatility** | 8 | `trading_env.py` (simplified) |
| **Regime** | 6 | `trading_env.py` |
| **Position** | 6 | `trading_env.py` |
| **TOTAL** | **47** | Full state vector |

---

## 🎮 Action Space (5 actions)

| Action | Code | Description | Size |
|--------|------|-------------|------|
| CLOSE_LONG | 0 | Exit position | N/A |
| HOLD | 1 | Do nothing | 0 |
| OPEN_SMALL | 2 | Enter position | 100 shares |
| OPEN_MED | 3 | Enter position | 200 shares |
| OPEN_LARGE | 4 | Enter position | 300 shares |

---

## 💰 Cost Model (IBKR)

### Commission Structure
- **Base**: $0.005/share
- **Minimum**: $1.00/order
- **SEC Fee**: $0.0000278 per dollar sold
- **FINRA TAF**: $0.000166 per share (capped at $7.27)

### Slippage Estimates
- **Small (100 shares)**: 0.5 ticks ($0.005)
- **Medium (200 shares)**: 0.8 ticks ($0.008)
- **Large (300 shares)**: 1.2 ticks ($0.012)

### Example Cost Calculation
```python
# 100 shares @ $450
qty = 100
price = 450.0

commission = max(100 * 0.005, 1.0)  # $0.50 → $1.00 (minimum)
sec_fee = (100 * 450) * 0.0000278  # $1.25
finra_taf = min(100 * 0.000166, 7.27)  # $0.02
slippage = 0.5 * 0.01  # $0.005 per share

total_cost = 1.00 + 1.25 + 0.02 + (0.005 * 100)  # $2.77
```

---

## 🏋️ Next Steps: Training

### 1. Install Dependencies
```bash
pip install gymnasium stable-baselines3[extra] torch tensorboard
```

### 2. Collect Training Data
Run data collection for 30+ days (or use historical data):
```python
# Run continuously in background
python -c "
from ib_insync import IB
from src.intraday.data_pipeline import IntradayDataPipeline
import time

ib = IB()
ib.connect('127.0.0.1', 7497, clientId=1)

pipeline = IntradayDataPipeline(ib, 'SPY')
pipeline.start()

# Run all day
while True:
    time.sleep(60)
    stats = pipeline.get_stats()
    print(stats)
"
```

### 3. Train PPO Agent
```python
from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import DummyVecEnv

# Wrap environment
env = DummyVecEnv([lambda: IntradayTradingEnv(...)])

# Initialize PPO
model = PPO(
    "MlpPolicy",
    env,
    learning_rate=3e-4,
    n_steps=2048,
    batch_size=64,
    n_epochs=10,
    gamma=0.99,
    verbose=1,
    tensorboard_log="./logs/",
)

# Train
model.learn(total_timesteps=1_000_000)

# Save
model.save("intraday_trader_ppo")
```

### 4. Evaluate
```python
# Load trained model
model = PPO.load("intraday_trader_ppo")

# Run evaluation
obs, info = env.reset()
episode_reward = 0

for i in range(390):  # Full trading day
    action, _states = model.predict(obs, deterministic=True)
    obs, reward, terminated, truncated, info = env.step(action)
    episode_reward += reward
    
    if terminated or truncated:
        break

print(f"Episode reward: {episode_reward:.2f}")
print(f"Final PnL: ${info['daily_pnl']:.2f}")
```

---

## 📈 Performance Targets

| Metric | Target | Acceptable |
|--------|--------|------------|
| **Sharpe Ratio** | >3.0 | >2.0 |
| **Win Rate** | >60% | >55% |
| **Max Drawdown** | <3% | <5% |
| **Avg Daily PnL** | +$300-500 | +$200-300 |
| **Commission %** | <2% of PnL | <5% of PnL |
| **Latency** | <50ms | <100ms |

---

## 🔧 Troubleshooting

### "ib_insync not found"
```bash
pip install ib_insync
```

### "IBKR connection failed"
1. Open TWS or IB Gateway
2. Enable API: Global Config → API → Settings
3. Add 127.0.0.1 to trusted IPs
4. Use port 7497 (paper) or 7496 (live)

### "Not enough data"
- Wait 2+ minutes after starting pipeline
- Need minimum 50 bars for indicators (50 minutes)
- For full features, collect 1+ hours

### "Reward always zero"
- Check if position opened (action 2/3/4)
- Verify price data is flowing (`pipeline.get_current_price()`)
- Add logging to `_calculate_reward()` method

---

## 📁 File Structure

```
src/intraday/
├── __init__.py              # Module exports
├── data_pipeline.py         # Real-time tick ingestion (600 lines)
├── microstructure.py        # Market microstructure (500 lines)
├── momentum.py              # Technical indicators (400 lines)
└── trading_env.py           # RL environment (700 lines)
```

**Total**: 2,200+ lines of production-ready code

---

## 🎯 What's Next?

1. ✅ Core modules complete
2. ⬜ Historical data collection (or use replay)
3. ⬜ PPO training (1M steps, ~12-24 hours)
4. ⬜ Hyperparameter tuning (Optuna)
5. ⬜ Paper trading validation (30 days)
6. ⬜ Live deployment (start small: 100 shares)

---

## 🚀 Ready to Train!

You now have everything needed to train the world's best intraday trader:

✅ Real-time data pipeline  
✅ 47-dimensional state space  
✅ IBKR cost modeling  
✅ Multi-objective reward function  
✅ Gym environment for PPO  

**Next**: Connect to IBKR, collect data, train PPO agent! 🎉

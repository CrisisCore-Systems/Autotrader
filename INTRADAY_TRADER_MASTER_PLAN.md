# 🏆 THE GREATEST INTRADAY TRADER EVER BUILT

**Mission**: Train a reinforcement learning agent to become the single best intraday trader using Interactive Brokers platform.

**Target Performance** (within 6 months):
- **Sharpe Ratio**: >3.0 (world-class)
- **Win Rate**: >60% (professional grade)
- **Max Drawdown**: <3% (tight risk control)
- **Daily PnL**: +0.5-2.0% (consistent compounding)
- **Latency**: <50ms (sub-second execution)
- **Trades/Day**: 10-30 (selective, high-quality)

---

## 🎯 Why This Will Be THE BEST

### 1. **Edge Stack** (7 Competitive Advantages)

1. **Microstructure Intelligence**
   - Order flow toxicity detection
   - Volume imbalance (buy vs sell pressure)
   - Spread compression/expansion patterns
   - Level 2 depth analysis

2. **Multi-Timeframe Fusion**
   - Tick data (sub-second)
   - 1-minute bars (momentum)
   - 5-minute bars (trend)
   - Daily context (regime)

3. **Reinforcement Learning**
   - Learns from EVERY trade (win or loss)
   - Adapts to changing market conditions
   - Discovers non-obvious patterns
   - Continuous improvement (no ceiling)

4. **Agentic Risk Management**
   - Sentinel: Pre-trade risk checks
   - RiskOfficer: Real-time position limits
   - Trader: Smart execution (TWAP/VWAP)
   - Autonomous circuit breakers

5. **Cost Optimization**
   - IBKR tiered pricing (as low as $0.0035/share)
   - Smart order routing (best execution)
   - Market impact modeling
   - Commission-aware training

6. **Market Regime Awareness**
   - Volatility states (low/medium/high)
   - Trend states (bull/bear/sideways)
   - Time-of-day patterns (open/midday/close)
   - Dynamic strategy adaptation

7. **LLM Enhancement** (Optional Boost)
   - News sentiment (Ollama + LLM Gateway)
   - Market narrative understanding
   - Risk event detection
   - Trade rationale generation

---

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    INTRADAY TRADER SYSTEM                   │
└─────────────────────────────────────────────────────────────┘

┌──────────────────┐       ┌──────────────────┐       ┌──────────────────┐
│  IBKR TWS/Gateway│◄─────►│   Data Pipeline   │◄─────►│  Feature Engine  │
│  (Port 7497/7496)│       │  - Tick data      │       │  - Microstructure│
│  - Level 2 quotes│       │  - 1min bars      │       │  - Momentum      │
│  - Order routing │       │  - Order book     │       │  - Volatility    │
└──────────────────┘       └──────────────────┘       └──────────────────┘
         │                          │                           │
         │                          ▼                           ▼
         │                  ┌──────────────────┐       ┌──────────────────┐
         │                  │ Market Regime    │       │  RL Agent (PPO)  │
         │                  │ Detector         │       │  - State: 47 dim │
         │                  │ - Volatility     │       │  - Actions: 5    │
         │                  │ - Trend          │       │  - Reward: PnL   │
         │                  │ - Time-of-day    │       └──────────────────┘
         │                  └──────────────────┘                │
         │                          │                           │
         ▼                          ▼                           ▼
┌──────────────────────────────────────────────────────────────────┐
│                      AGENTIC EXECUTION LAYER                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │   Sentinel   │→ │ RiskOfficer  │→ │    Trader    │          │
│  │  Pre-checks  │  │  Limits      │  │  Smart exec  │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
└──────────────────────────────────────────────────────────────────┘
         │
         ▼
┌──────────────────┐       ┌──────────────────┐       ┌──────────────────┐
│  IBKR Orders     │       │  Grafana Monitor │       │  Training Loop   │
│  - Market/Limit  │       │  - Real-time PnL │       │  - Experience    │
│  - TWAP/VWAP     │       │  - Drawdown      │       │  - Replay buffer │
│  - Bracket OCO   │       │  - Agent health  │       │  - Model updates │
└──────────────────┘       └──────────────────┘       └──────────────────┘
```

---

## 📊 Data Requirements

### Real-Time Streams (IBKR API)

#### 1. Tick Data (Sub-Second)
```python
# IBKR tick types
tick_types = [
    "Last",           # Last trade price
    "BidAsk",         # Bid/ask spread
    "Volume",         # Trade volume
    "LastSize",       # Last trade size
    "BidSize",        # Bid depth
    "AskSize",        # Ask depth
]

# Latency target: <20ms from IBKR to agent
```

#### 2. Level 2 Market Depth
```python
# Order book depth (10 levels)
depth_levels = 10  # Top 10 bids/asks
update_frequency = "realtime"  # Every tick

# Features extracted:
# - Bid/ask imbalance
# - Volume concentration
# - Spread volatility
# - Large order detection
```

#### 3. 1-Minute Bars (Aggregated)
```python
bar_features = {
    "open": float,
    "high": float,
    "low": float,
    "close": float,
    "volume": int,
    "vwap": float,      # Calculated
    "num_trades": int,   # Tick count
}

# Historical lookback: 390 bars (1 trading day)
```

---

## 🧠 Reinforcement Learning Design

### State Space (47 Dimensions)

#### 1. Microstructure Features (15 dim)
```python
{
    # Spread dynamics
    "bid_ask_spread": float,           # $ spread
    "spread_pct": float,                # % of price
    "spread_volatility": float,         # Rolling std
    
    # Volume imbalance
    "volume_imbalance": float,          # (buy_vol - sell_vol) / total
    "large_trade_ratio": float,         # % volume in >10k orders
    "trade_intensity": float,           # Trades per second
    
    # Order book depth
    "bid_depth_1": float,               # Level 1 bid volume
    "ask_depth_1": float,               # Level 1 ask volume
    "bid_depth_5": float,               # Total top 5 bids
    "ask_depth_5": float,               # Total top 5 asks
    "depth_imbalance": float,           # (bid_depth - ask_depth) / total
    
    # Order flow toxicity
    "toxic_flow_score": float,          # VPIN indicator
    "adverse_selection": float,         # Post-trade price movement
    "market_impact": float,             # Estimated from recent trades
    "liquidity_score": float,           # Depth / volatility
}
```

#### 2. Momentum Indicators (12 dim)
```python
{
    # Price momentum
    "returns_1min": float,              # 1-minute return
    "returns_5min": float,              # 5-minute return
    "returns_30min": float,             # 30-minute return
    "vwap_deviation": float,            # (price - vwap) / vwap
    
    # Technical indicators
    "rsi_14": float,                    # RSI (14 periods)
    "macd": float,                      # MACD line
    "macd_signal": float,               # Signal line
    "macd_hist": float,                 # Histogram
    
    # Volume profile
    "volume_ratio": float,              # Current / avg volume
    "volume_poc": float,                # Point of control (price)
    "volume_value_area": float,         # Value area % (70%)
    "relative_volume": float,           # vs 20-day avg
}
```

#### 3. Volatility Features (8 dim)
```python
{
    # Realized volatility
    "realized_vol_1min": float,         # 1-min realized vol (annualized)
    "realized_vol_5min": float,         # 5-min realized vol
    "realized_vol_30min": float,        # 30-min realized vol
    "parkinson_vol": float,             # High-low estimator
    
    # Volatility regime
    "vol_percentile": float,            # vs 20-day distribution
    "vol_trend": float,                 # Rising/falling vol
    "vol_of_vol": float,                # Volatility of volatility
    "garch_forecast": float,            # GARCH(1,1) prediction
}
```

#### 4. Market Regime (6 dim)
```python
{
    # Trend state
    "trend_strength": float,            # ADX or similar
    "trend_direction": int,             # -1 (down), 0 (flat), 1 (up)
    
    # Session time
    "time_since_open": float,           # Minutes since 9:30 AM
    "time_until_close": float,          # Minutes until 4:00 PM
    
    # Volatility regime
    "vol_regime": int,                  # 0 (low), 1 (med), 2 (high)
    
    # Market phase
    "market_phase": int,                # 0 (open), 1 (midday), 2 (close)
}
```

#### 5. Position Context (6 dim)
```python
{
    # Current position
    "position_qty": int,                # Shares held
    "position_pnl": float,              # Unrealized P&L
    "position_duration": float,         # Minutes held
    "entry_price": float,               # Avg entry price
    
    # Portfolio stats
    "daily_pnl": float,                 # Today's realized P&L
    "daily_trades": int,                # Trades executed today
}
```

### Action Space (5 Actions)

```python
actions = {
    0: "CLOSE_LONG",      # Exit long position (market order)
    1: "HOLD",            # Do nothing (maintain position)
    2: "OPEN_LONG_SMALL", # Enter 100 shares
    3: "OPEN_LONG_MED",   # Enter 200 shares
    4: "OPEN_LONG_LARGE", # Enter 300 shares
}

# Position limits:
# - Max position: 500 shares
# - Max trades/day: 30
# - Max daily loss: $500 (then stop)
```

### Reward Function (Multi-Objective)

```python
def calculate_reward(trade_result: Dict) -> float:
    """
    Reward function for intraday trading RL agent.
    
    Optimizes for:
    1. PnL (profit maximization)
    2. Risk-adjusted returns (Sharpe)
    3. Cost efficiency (minimize commissions)
    4. Drawdown control (penalize losses)
    """
    
    # 1. Base reward: PnL
    pnl = trade_result["realized_pnl"]
    commission = trade_result["commission"]
    net_pnl = pnl - commission
    
    # 2. Risk adjustment
    position_duration = trade_result["duration_minutes"]
    avg_price = trade_result["avg_entry_price"]
    max_adverse_move = trade_result["max_drawdown_during_trade"]
    
    # Sharpe-like: PnL / risk
    risk = max(abs(max_adverse_move), 0.001 * avg_price)  # Min 0.1% risk
    risk_adjusted_return = net_pnl / risk
    
    # 3. Commission penalty (encourage fewer, better trades)
    commission_ratio = commission / abs(pnl) if pnl != 0 else 1.0
    commission_penalty = -0.5 * commission_ratio
    
    # 4. Hold time penalty (discourage overnight risk)
    time_penalty = -0.01 * (position_duration / 60)  # Small penalty per hour
    
    # 5. Drawdown penalty (punish large losses)
    drawdown_penalty = -2.0 * max(0, max_adverse_move / avg_price)
    
    # 6. Winning streak bonus (encourage consistency)
    win_streak_bonus = 0.1 * trade_result.get("current_win_streak", 0)
    
    # Total reward
    reward = (
        net_pnl * 100  # Scale to [-100, +100] range
        + risk_adjusted_return * 10
        + commission_penalty
        + time_penalty
        + drawdown_penalty
        + win_streak_bonus
    )
    
    return reward

# Expected reward range: -200 to +200
# - Great trade: +50 to +200
# - Break-even: -10 to +10
# - Bad trade: -50 to -200
```

### RL Algorithm: Proximal Policy Optimization (PPO)

**Why PPO?**
1. Stable training (doesn't explode like vanilla policy gradient)
2. Sample efficient (learns from fewer trades)
3. Handles continuous/discrete spaces
4. Industry standard for robotics/trading

**Hyperparameters**:
```python
ppo_config = {
    "learning_rate": 3e-4,
    "n_steps": 2048,              # Steps per update
    "batch_size": 64,
    "n_epochs": 10,
    "gamma": 0.99,                # Discount factor
    "gae_lambda": 0.95,           # GAE parameter
    "clip_range": 0.2,            # PPO clip
    "ent_coef": 0.01,             # Entropy bonus
    "vf_coef": 0.5,               # Value function coef
    "max_grad_norm": 0.5,
    "policy_kwargs": {
        "net_arch": [256, 256, 128],  # 3-layer MLP
        "activation_fn": "relu",
    },
}
```

---

## 🔧 Implementation Plan

### Phase 1: Data Infrastructure (Week 1-2)

**Deliverables**:
1. `src/intraday/data_pipeline.py` - Real-time tick ingestion
2. `src/intraday/market_depth.py` - Level 2 order book handler
3. `src/intraday/bar_aggregator.py` - 1-min bar construction
4. `src/intraday/feature_engine.py` - 47-dim state vector

**Key Code**:
```python
# src/intraday/data_pipeline.py

from ib_insync import IB, Stock, util
from dataclasses import dataclass
from typing import List, Callable
import numpy as np
from collections import deque

@dataclass
class TickData:
    """Single tick data point."""
    timestamp: float
    price: float
    size: int
    bid: float
    ask: float
    bid_size: int
    ask_size: int

class IntradayDataPipeline:
    """
    Real-time tick data pipeline for intraday trading.
    
    Subscribes to IBKR tick data and maintains:
    - Tick history (last 1000 ticks)
    - 1-minute bars (last 390 bars = 1 day)
    - Order book depth (10 levels)
    """
    
    def __init__(
        self,
        ib: IB,
        symbol: str,
        tick_buffer_size: int = 1000,
    ):
        self.ib = ib
        self.symbol = symbol
        self.tick_buffer = deque(maxlen=tick_buffer_size)
        self.bars_1min = deque(maxlen=390)  # 1 trading day
        
        # Callbacks
        self.on_tick_callbacks: List[Callable] = []
        self.on_bar_callbacks: List[Callable] = []
        
        # Order book
        self.order_book = {"bids": {}, "asks": {}}
        
    def start(self):
        """Start real-time data subscriptions."""
        contract = Stock(self.symbol, "SMART", "USD")
        self.ib.qualifyContracts(contract)
        
        # Subscribe to tick data
        ticker = self.ib.reqMktData(
            contract,
            genericTickList="",  # All tick types
            snapshot=False,
            regulatorySnapshot=False,
        )
        
        # Subscribe to depth (Level 2)
        self.ib.reqMktDepth(contract, numRows=10)
        
        # Attach callbacks
        ticker.updateEvent += self._on_tick_update
        self.ib.updateEvent += self._on_depth_update
        
        print(f"✅ Started data pipeline for {self.symbol}")
    
    def _on_tick_update(self, ticker):
        """Handle tick update from IBKR."""
        tick = TickData(
            timestamp=util.now().timestamp(),
            price=ticker.last or ticker.close,
            size=ticker.lastSize or 0,
            bid=ticker.bid,
            ask=ticker.ask,
            bid_size=ticker.bidSize,
            ask_size=ticker.askSize,
        )
        
        self.tick_buffer.append(tick)
        
        # Notify subscribers
        for callback in self.on_tick_callbacks:
            callback(tick)
    
    def _on_depth_update(self):
        """Handle market depth update (Level 2)."""
        # Parse order book updates
        # (IBKR provides via reqMktDepth callback)
        pass
    
    def get_latest_ticks(self, n: int = 100) -> List[TickData]:
        """Get last N ticks."""
        return list(self.tick_buffer)[-n:]
    
    def get_spread(self) -> float:
        """Get current bid-ask spread."""
        if not self.tick_buffer:
            return 0.0
        last_tick = self.tick_buffer[-1]
        return last_tick.ask - last_tick.bid
    
    def get_volume_imbalance(self, lookback: int = 100) -> float:
        """
        Calculate volume imbalance over last N ticks.
        
        Returns:
            -1.0 to +1.0 (negative = sell pressure, positive = buy pressure)
        """
        ticks = self.get_latest_ticks(lookback)
        if not ticks:
            return 0.0
        
        buy_volume = sum(t.size for t in ticks if t.price >= t.ask)
        sell_volume = sum(t.size for t in ticks if t.price <= t.bid)
        
        total = buy_volume + sell_volume
        if total == 0:
            return 0.0
        
        return (buy_volume - sell_volume) / total
```

### Phase 2: Feature Engineering (Week 2-3)

**Deliverables**:
1. `src/intraday/microstructure.py` - Spread, depth, toxicity features
2. `src/intraday/momentum.py` - RSI, MACD, VWAP indicators
3. `src/intraday/volatility.py` - Realized vol, GARCH forecasting
4. `src/intraday/regime.py` - Market regime detection

**Key Code**:
```python
# src/intraday/feature_engine.py

import numpy as np
import pandas as pd
from typing import Dict
from src.intraday.data_pipeline import IntradayDataPipeline
from src.intraday.microstructure import MicrostructureFeatures
from src.intraday.momentum import MomentumFeatures
from src.intraday.volatility import VolatilityFeatures
from src.intraday.regime import RegimeDetector

class FeatureEngine:
    """
    Constructs 47-dimensional state vector for RL agent.
    
    Combines:
    - Microstructure (15 dim)
    - Momentum (12 dim)
    - Volatility (8 dim)
    - Regime (6 dim)
    - Position (6 dim)
    """
    
    def __init__(self, pipeline: IntradayDataPipeline):
        self.pipeline = pipeline
        self.microstructure = MicrostructureFeatures(pipeline)
        self.momentum = MomentumFeatures(pipeline)
        self.volatility = VolatilityFeatures(pipeline)
        self.regime = RegimeDetector(pipeline)
    
    def get_state_vector(self, position_context: Dict) -> np.ndarray:
        """
        Build complete 47-dim state vector.
        
        Args:
            position_context: Dict with:
                - position_qty: int
                - position_pnl: float
                - position_duration: float (minutes)
                - entry_price: float
                - daily_pnl: float
                - daily_trades: int
        
        Returns:
            47-dimensional numpy array
        """
        # Get features from each module
        micro_features = self.microstructure.compute()  # 15 dim
        momentum_features = self.momentum.compute()     # 12 dim
        vol_features = self.volatility.compute()        # 8 dim
        regime_features = self.regime.compute()         # 6 dim
        
        # Position features (6 dim)
        position_features = np.array([
            position_context.get("position_qty", 0),
            position_context.get("position_pnl", 0.0),
            position_context.get("position_duration", 0.0),
            position_context.get("entry_price", 0.0),
            position_context.get("daily_pnl", 0.0),
            position_context.get("daily_trades", 0),
        ])
        
        # Concatenate all features
        state = np.concatenate([
            micro_features,
            momentum_features,
            vol_features,
            regime_features,
            position_features,
        ])
        
        assert len(state) == 47, f"Expected 47 features, got {len(state)}"
        
        return state
```

### Phase 3: RL Training Environment (Week 3-4)

**Deliverables**:
1. `src/intraday/trading_env.py` - OpenAI Gym environment
2. `src/intraday/replay_engine.py` - Historical tick replay
3. `src/intraday/cost_model.py` - Slippage + commission simulator
4. `src/intraday/rl_trainer.py` - PPO training loop

**Key Code**:
```python
# src/intraday/trading_env.py

import gymnasium as gym
from gymnasium import spaces
import numpy as np
from typing import Tuple, Dict, Optional
from src.intraday.feature_engine import FeatureEngine
from src.intraday.cost_model import CostModel

class IntradayTradingEnv(gym.Env):
    """
    OpenAI Gym environment for intraday trading.
    
    State: 47-dim feature vector
    Actions: [CLOSE_LONG, HOLD, OPEN_SMALL, OPEN_MED, OPEN_LARGE]
    Reward: Multi-objective (PnL, Sharpe, costs)
    """
    
    metadata = {"render_modes": ["human"]}
    
    def __init__(
        self,
        feature_engine: FeatureEngine,
        cost_model: CostModel,
        initial_capital: float = 25000.0,
        max_position: int = 500,
        max_daily_loss: float = 500.0,
        max_trades_per_day: int = 30,
    ):
        super().__init__()
        
        self.feature_engine = feature_engine
        self.cost_model = cost_model
        
        # Trading constraints
        self.initial_capital = initial_capital
        self.max_position = max_position
        self.max_daily_loss = max_daily_loss
        self.max_trades_per_day = max_trades_per_day
        
        # Gym spaces
        self.observation_space = spaces.Box(
            low=-np.inf,
            high=np.inf,
            shape=(47,),
            dtype=np.float32,
        )
        
        self.action_space = spaces.Discrete(5)  # 5 actions
        
        # State tracking
        self.reset()
    
    def reset(self, seed: Optional[int] = None) -> Tuple[np.ndarray, Dict]:
        """Reset environment to initial state."""
        super().reset(seed=seed)
        
        # Portfolio state
        self.capital = self.initial_capital
        self.position_qty = 0
        self.entry_price = 0.0
        self.position_duration = 0.0
        
        # Daily stats
        self.daily_pnl = 0.0
        self.daily_trades = 0
        self.current_win_streak = 0
        
        # Trade history
        self.trade_history = []
        
        # Get initial observation
        obs = self._get_observation()
        info = {}
        
        return obs, info
    
    def step(self, action: int) -> Tuple[np.ndarray, float, bool, bool, Dict]:
        """
        Execute one timestep.
        
        Args:
            action: 0=CLOSE, 1=HOLD, 2=SMALL, 3=MED, 4=LARGE
        
        Returns:
            observation, reward, terminated, truncated, info
        """
        # Get current price
        current_price = self.feature_engine.pipeline.tick_buffer[-1].price
        
        # Execute action
        realized_pnl = 0.0
        commission = 0.0
        
        if action == 0:  # CLOSE_LONG
            if self.position_qty > 0:
                realized_pnl, commission = self._close_position(current_price)
        
        elif action == 1:  # HOLD
            self.position_duration += 1  # 1 minute
        
        elif action in [2, 3, 4]:  # OPEN positions
            if self.position_qty == 0:  # Only open if flat
                qty_map = {2: 100, 3: 200, 4: 300}
                qty = qty_map[action]
                self._open_position(current_price, qty)
        
        # Update daily P&L
        self.daily_pnl += realized_pnl
        
        # Calculate reward
        reward = self._calculate_reward(realized_pnl, commission)
        
        # Check termination conditions
        terminated = (
            abs(self.daily_pnl) > self.max_daily_loss  # Hit loss limit
            or self.daily_trades >= self.max_trades_per_day  # Max trades
        )
        
        truncated = False  # Not used in this env
        
        # Get next observation
        obs = self._get_observation()
        
        # Info dict
        info = {
            "realized_pnl": realized_pnl,
            "commission": commission,
            "daily_pnl": self.daily_pnl,
            "position_qty": self.position_qty,
        }
        
        return obs, reward, terminated, truncated, info
    
    def _get_observation(self) -> np.ndarray:
        """Build 47-dim state vector."""
        position_context = {
            "position_qty": self.position_qty,
            "position_pnl": self._calculate_unrealized_pnl(),
            "position_duration": self.position_duration,
            "entry_price": self.entry_price,
            "daily_pnl": self.daily_pnl,
            "daily_trades": self.daily_trades,
        }
        
        return self.feature_engine.get_state_vector(position_context)
    
    def _open_position(self, price: float, qty: int):
        """Open new position."""
        # Calculate costs
        commission = self.cost_model.calculate_commission(qty, price)
        slippage = self.cost_model.calculate_slippage(qty, price)
        
        # Deduct from capital
        cost = (price + slippage) * qty + commission
        self.capital -= cost
        
        # Update position
        self.position_qty = qty
        self.entry_price = price + slippage
        self.position_duration = 0.0
        self.daily_trades += 1
    
    def _close_position(self, price: float) -> Tuple[float, float]:
        """Close position and return (PnL, commission)."""
        # Calculate costs
        commission = self.cost_model.calculate_commission(self.position_qty, price)
        slippage = self.cost_model.calculate_slippage(self.position_qty, price)
        
        # Calculate P&L
        exit_price = price - slippage
        realized_pnl = (exit_price - self.entry_price) * self.position_qty - commission
        
        # Update capital
        self.capital += (exit_price * self.position_qty) - commission
        
        # Reset position
        self.position_qty = 0
        self.entry_price = 0.0
        self.position_duration = 0.0
        self.daily_trades += 1
        
        # Update win streak
        if realized_pnl > 0:
            self.current_win_streak += 1
        else:
            self.current_win_streak = 0
        
        return realized_pnl, commission
    
    def _calculate_unrealized_pnl(self) -> float:
        """Calculate unrealized P&L for open position."""
        if self.position_qty == 0:
            return 0.0
        
        current_price = self.feature_engine.pipeline.tick_buffer[-1].price
        return (current_price - self.entry_price) * self.position_qty
    
    def _calculate_reward(self, realized_pnl: float, commission: float) -> float:
        """
        Multi-objective reward function.
        
        Components:
        1. PnL (scaled)
        2. Risk-adjusted return
        3. Commission penalty
        4. Win streak bonus
        """
        # Base reward from PnL
        net_pnl = realized_pnl - commission
        reward = net_pnl * 100  # Scale to [-100, +100] range
        
        # Commission penalty
        if realized_pnl != 0:
            commission_ratio = commission / abs(realized_pnl)
            reward -= 0.5 * commission_ratio
        
        # Win streak bonus
        reward += 0.1 * self.current_win_streak
        
        # Drawdown penalty (if position is underwater)
        unrealized_pnl = self._calculate_unrealized_pnl()
        if unrealized_pnl < 0:
            drawdown_pct = abs(unrealized_pnl) / (self.entry_price * self.position_qty)
            reward -= 2.0 * drawdown_pct
        
        return reward
```

### Phase 4: Training Pipeline (Week 4-6)

**Deliverables**:
1. Historical tick data replay (1000+ hours of SPY/QQQ data)
2. PPO training script with checkpoints
3. Hyperparameter tuning (Optuna)
4. Model evaluation metrics (Sharpe, win rate, drawdown)

**Key Code**:
```python
# src/intraday/rl_trainer.py

from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import DummyVecEnv
from stable_baselines3.common.callbacks import CheckpointCallback, EvalCallback
from src.intraday.trading_env import IntradayTradingEnv
import matplotlib.pyplot as plt

class RLTrainer:
    """
    RL training pipeline for intraday trader.
    
    Trains PPO agent on historical tick data with:
    - Checkpointing every 10k steps
    - Evaluation every 50k steps
    - Hyperparameter logging
    - Performance visualization
    """
    
    def __init__(
        self,
        env: IntradayTradingEnv,
        total_timesteps: int = 1_000_000,
        checkpoint_freq: int = 10_000,
        eval_freq: int = 50_000,
    ):
        self.env = DummyVecEnv([lambda: env])
        self.total_timesteps = total_timesteps
        self.checkpoint_freq = checkpoint_freq
        self.eval_freq = eval_freq
        
        # Initialize PPO
        self.model = PPO(
            "MlpPolicy",
            self.env,
            learning_rate=3e-4,
            n_steps=2048,
            batch_size=64,
            n_epochs=10,
            gamma=0.99,
            gae_lambda=0.95,
            clip_range=0.2,
            ent_coef=0.01,
            vf_coef=0.5,
            max_grad_norm=0.5,
            policy_kwargs={
                "net_arch": [256, 256, 128],
                "activation_fn": "relu",
            },
            verbose=1,
            tensorboard_log="./logs/intraday_trader/",
        )
    
    def train(self):
        """Start training with callbacks."""
        # Checkpoint callback
        checkpoint_callback = CheckpointCallback(
            save_freq=self.checkpoint_freq,
            save_path="./models/intraday_trader/",
            name_prefix="ppo_intraday",
        )
        
        # Evaluation callback
        eval_callback = EvalCallback(
            self.env,
            best_model_save_path="./models/intraday_trader/best/",
            log_path="./logs/intraday_trader/eval/",
            eval_freq=self.eval_freq,
            deterministic=True,
            render=False,
        )
        
        # Train
        print(f"🚀 Starting PPO training for {self.total_timesteps:,} steps")
        self.model.learn(
            total_timesteps=self.total_timesteps,
            callback=[checkpoint_callback, eval_callback],
            tb_log_name="ppo_intraday",
        )
        
        # Save final model
        self.model.save("./models/intraday_trader/ppo_intraday_final")
        print("✅ Training complete! Model saved.")
    
    def evaluate(self, n_episodes: int = 100) -> Dict:
        """Evaluate trained model."""
        stats = {
            "total_pnl": [],
            "sharpe_ratio": [],
            "win_rate": [],
            "max_drawdown": [],
            "num_trades": [],
        }
        
        for episode in range(n_episodes):
            obs, _ = self.env.reset()
            done = False
            episode_pnl = 0.0
            episode_trades = 0
            
            while not done:
                action, _ = self.model.predict(obs, deterministic=True)
                obs, reward, terminated, truncated, info = self.env.step(action)
                done = terminated or truncated
                
                episode_pnl += info[0].get("realized_pnl", 0.0)
                if info[0].get("realized_pnl", 0.0) != 0:
                    episode_trades += 1
            
            stats["total_pnl"].append(episode_pnl)
            stats["num_trades"].append(episode_trades)
        
        # Calculate summary metrics
        avg_pnl = np.mean(stats["total_pnl"])
        std_pnl = np.std(stats["total_pnl"])
        sharpe = (avg_pnl / std_pnl) * np.sqrt(252) if std_pnl > 0 else 0
        win_rate = sum(1 for pnl in stats["total_pnl"] if pnl > 0) / len(stats["total_pnl"])
        
        return {
            "avg_daily_pnl": avg_pnl,
            "sharpe_ratio": sharpe,
            "win_rate": win_rate,
            "avg_trades_per_day": np.mean(stats["num_trades"]),
        }
```

### Phase 5: Live Deployment (Week 6-8)

**Deliverables**:
1. `src/intraday/live_trader.py` - Real-time trading loop
2. Integration with Sentinel/RiskOfficer/Trader agents
3. Grafana dashboard for monitoring
4. Paper trading validation (30 days)

**Key Code**:
```python
# src/intraday/live_trader.py

from src.intraday.data_pipeline import IntradayDataPipeline
from src.intraday.feature_engine import FeatureEngine
from src.core.brokers.ibkr_client import IBKRClient
from stable_baselines3 import PPO
import time
import logging

class LiveIntradayTrader:
    """
    Live intraday trader using trained RL agent.
    
    Connects to IBKR paper/live account and executes trades
    based on PPO model predictions.
    """
    
    def __init__(
        self,
        ibkr_host: str = "127.0.0.1",
        ibkr_port: int = 7497,  # Paper trading
        model_path: str = "./models/intraday_trader/ppo_intraday_final",
        symbol: str = "SPY",
    ):
        # Initialize IBKR connection
        self.ibkr = IBKRClient(host=ibkr_host, port=ibkr_port, paper=True)
        
        # Initialize data pipeline
        self.pipeline = IntradayDataPipeline(self.ibkr.ib, symbol)
        self.feature_engine = FeatureEngine(self.pipeline)
        
        # Load trained model
        self.model = PPO.load(model_path)
        
        # Trading state
        self.symbol = symbol
        self.position_qty = 0
        self.entry_price = 0.0
        self.daily_pnl = 0.0
        self.daily_trades = 0
        
        # Limits
        self.max_position = 500
        self.max_daily_loss = 500.0
        self.max_trades = 30
        
        self.logger = logging.getLogger(__name__)
    
    def start(self):
        """Start live trading loop."""
        self.logger.info(f"🚀 Starting live intraday trader for {self.symbol}")
        
        # Start data pipeline
        self.pipeline.start()
        
        # Wait for data buffer to fill
        time.sleep(60)  # 1 minute of history
        
        # Main trading loop
        while True:
            try:
                # Check trading session
                if not self._is_trading_hours():
                    time.sleep(60)
                    continue
                
                # Check daily limits
                if abs(self.daily_pnl) > self.max_daily_loss:
                    self.logger.warning("⚠️ Daily loss limit hit. Stopping for today.")
                    break
                
                if self.daily_trades >= self.max_trades:
                    self.logger.warning("⚠️ Max trades reached. Stopping for today.")
                    break
                
                # Get current state
                position_context = {
                    "position_qty": self.position_qty,
                    "position_pnl": self._get_unrealized_pnl(),
                    "position_duration": 0.0,  # Track separately
                    "entry_price": self.entry_price,
                    "daily_pnl": self.daily_pnl,
                    "daily_trades": self.daily_trades,
                }
                state = self.feature_engine.get_state_vector(position_context)
                
                # Get model prediction
                action, _ = self.model.predict(state, deterministic=True)
                
                # Execute action
                self._execute_action(action)
                
                # Sleep until next decision point (1 minute)
                time.sleep(60)
            
            except KeyboardInterrupt:
                self.logger.info("⏹️ Stopping trader...")
                break
            
            except Exception as e:
                self.logger.error(f"❌ Error in trading loop: {e}", exc_info=True)
                time.sleep(10)
        
        # Cleanup
        self._close_all_positions()
        self.ibkr.close()
        self.logger.info("✅ Trader stopped.")
    
    def _execute_action(self, action: int):
        """Execute trading action."""
        current_price = self.pipeline.tick_buffer[-1].price
        
        if action == 0 and self.position_qty > 0:
            # Close position
            self._close_position(current_price)
        
        elif action in [2, 3, 4] and self.position_qty == 0:
            # Open position
            qty_map = {2: 100, 3: 200, 4: 300}
            qty = qty_map[action]
            self._open_position(current_price, qty)
    
    def _open_position(self, price: float, qty: int):
        """Open new position via IBKR."""
        try:
            order = self.ibkr.place_market_order(
                symbol=self.symbol,
                qty=qty,
                side="buy",
            )
            
            self.position_qty = qty
            self.entry_price = price
            self.daily_trades += 1
            
            self.logger.info(f"✅ Opened position: {qty} shares @ ${price:.2f}")
        
        except Exception as e:
            self.logger.error(f"❌ Failed to open position: {e}")
    
    def _close_position(self, price: float):
        """Close position via IBKR."""
        try:
            order = self.ibkr.place_market_order(
                symbol=self.symbol,
                qty=self.position_qty,
                side="sell",
            )
            
            # Calculate P&L
            realized_pnl = (price - self.entry_price) * self.position_qty
            self.daily_pnl += realized_pnl
            
            self.logger.info(
                f"✅ Closed position: {self.position_qty} shares @ ${price:.2f}, "
                f"PnL: ${realized_pnl:.2f}"
            )
            
            self.position_qty = 0
            self.entry_price = 0.0
            self.daily_trades += 1
        
        except Exception as e:
            self.logger.error(f"❌ Failed to close position: {e}")
    
    def _get_unrealized_pnl(self) -> float:
        """Get unrealized P&L for open position."""
        if self.position_qty == 0:
            return 0.0
        
        current_price = self.pipeline.tick_buffer[-1].price
        return (current_price - self.entry_price) * self.position_qty
    
    def _is_trading_hours(self) -> bool:
        """Check if within trading hours (9:30 AM - 4:00 PM ET)."""
        from datetime import datetime
        now = datetime.now()
        return (
            now.weekday() < 5  # Monday-Friday
            and 9 <= now.hour < 16  # 9 AM - 4 PM
        )
    
    def _close_all_positions(self):
        """Close all positions at end of day."""
        if self.position_qty > 0:
            current_price = self.pipeline.tick_buffer[-1].price
            self._close_position(current_price)


if __name__ == "__main__":
    trader = LiveIntradayTrader(
        ibkr_port=7497,  # Paper trading
        symbol="SPY",
    )
    trader.start()
```

---

## 📈 Expected Performance Trajectory

### Training Phase (Weeks 1-6)

| Metric | Week 1-2 | Week 3-4 | Week 5-6 |
|--------|----------|----------|----------|
| **Sharpe Ratio** | -0.5 to 0.5 | 0.5 to 1.5 | 1.5 to 2.5 |
| **Win Rate** | 40-50% | 50-55% | 55-60% |
| **Avg Daily PnL** | -$50 to +$50 | +$50 to +$150 | +$150 to +$300 |
| **Max Drawdown** | 10-15% | 5-10% | 3-5% |
| **Trades/Day** | 40-50 | 30-40 | 20-30 |

### Paper Trading Phase (Weeks 7-10)

| Metric | Target | Acceptable |
|--------|--------|------------|
| **Sharpe Ratio** | >2.5 | >2.0 |
| **Win Rate** | >60% | >55% |
| **Avg Daily PnL** | +$300-$500 | +$200-$300 |
| **Max Drawdown** | <3% | <5% |
| **Commission Ratio** | <2% of PnL | <5% of PnL |

### Live Trading Phase (Month 3+)

| Metric | 3 Months | 6 Months | 12 Months |
|--------|----------|----------|-----------|
| **Sharpe Ratio** | 2.5-3.0 | 3.0-3.5 | >3.5 |
| **Annual Return** | 30-50% | 50-80% | 80-120% |
| **Max Drawdown** | <5% | <3% | <3% |
| **Consistency** | 18/22 days green | 20/22 days | 60/63 days |

---

## 🎓 Training Data Requirements

### Historical Tick Data

**Symbols to Train On**:
1. **SPY** (S&P 500 ETF) - Primary
2. **QQQ** (Nasdaq 100 ETF) - Tech-heavy
3. **IWM** (Russell 2000 ETF) - Small caps
4. **AAPL** (Apple) - High liquidity stock
5. **TSLA** (Tesla) - High volatility stock

**Data Volume Needed**:
- **1 year of tick data** = ~2-3 TB uncompressed
- **Compressed (Parquet)** = ~200-300 GB
- **Training subset** = 6 months (sufficient for patterns)

**Data Sources**:
1. **IBKR Historical Data API** (free for subscribers)
2. **Polygon.io** ($199/month for tick data)
3. **AlgoSeek** (one-time purchase, ~$500/year)
4. **FirstRate Data** (discount tick data provider)

### Alternative: Replay from Live Trading

Instead of purchasing historical data, **collect your own**:
1. Run data collection script for 3-6 months (no trading)
2. Store tick data in PostgreSQL + TimescaleDB
3. Use for training after collection period
4. Advantage: Guaranteed data quality + no cost

---

## 🚨 Risk Management Integration

### Sentinel Agent (Pre-Trade Checks)

```python
# src/agentic/sentinel_intraday.py

class SentinelIntraday:
    """Pre-trade risk checks for intraday RL agent."""
    
    def validate_trade(self, action: int, state: np.ndarray, context: Dict) -> Tuple[bool, str]:
        """
        Validate if RL action should be allowed.
        
        Checks:
        1. Position limits
        2. Daily loss limit
        3. Max trades per day
        4. Spread too wide (no liquidity)
        5. Volatility spike (market stress)
        """
        # Extract state features
        position_qty = int(state[41])  # Position feature at index 41
        daily_pnl = state[44]
        daily_trades = int(state[45])
        spread_pct = state[1]  # Spread feature
        vol_regime = int(state[39])  # Volatility regime
        
        # Check 1: Position limits
        if action in [2, 3, 4]:  # Opening position
            qty_map = {2: 100, 3: 200, 4: 300}
            new_position = position_qty + qty_map[action]
            
            if new_position > 500:
                return False, "Position limit exceeded (max 500 shares)"
        
        # Check 2: Daily loss limit
        if daily_pnl < -500:
            return False, f"Daily loss limit hit (${daily_pnl:.2f} < -$500)"
        
        # Check 3: Max trades
        if daily_trades >= 30:
            return False, f"Max trades per day reached ({daily_trades}/30)"
        
        # Check 4: Spread too wide
        if spread_pct > 0.005:  # >0.5% spread
            return False, f"Spread too wide ({spread_pct*100:.2f}% > 0.5%)"
        
        # Check 5: Volatility spike
        if vol_regime == 2:  # High volatility
            return False, "High volatility regime - risk off"
        
        return True, "Trade approved"
```

### RiskOfficer Agent (Position Monitoring)

```python
# src/agentic/risk_officer_intraday.py

class RiskOfficerIntraday:
    """Real-time position risk monitoring."""
    
    def monitor_position(self, position_context: Dict) -> Dict[str, Any]:
        """
        Monitor open position for emergency exits.
        
        Returns:
            Dict with:
            - emergency_exit: bool (should close immediately)
            - reason: str
            - suggested_action: str
        """
        position_qty = position_context["position_qty"]
        unrealized_pnl = position_context["position_pnl"]
        duration = position_context["position_duration"]
        entry_price = position_context["entry_price"]
        
        # No position, nothing to monitor
        if position_qty == 0:
            return {"emergency_exit": False, "reason": "No position"}
        
        # Calculate drawdown
        drawdown_pct = unrealized_pnl / (entry_price * position_qty)
        
        # Emergency exit conditions
        if drawdown_pct < -0.02:  # -2% loss
            return {
                "emergency_exit": True,
                "reason": f"Stop loss hit ({drawdown_pct*100:.2f}% < -2%)",
                "suggested_action": "CLOSE_LONG",
            }
        
        if duration > 120:  # 2 hours holding time
            return {
                "emergency_exit": True,
                "reason": f"Max hold time exceeded ({duration} min > 120 min)",
                "suggested_action": "CLOSE_LONG",
            }
        
        # Take profit
        if drawdown_pct > 0.03:  # +3% profit
            return {
                "emergency_exit": False,  # Not emergency, but suggested
                "reason": f"Take profit target ({drawdown_pct*100:.2f}% > +3%)",
                "suggested_action": "CLOSE_LONG",
            }
        
        return {"emergency_exit": False, "reason": "Position OK"}
```

---

## 📊 Success Metrics & KPIs

### Daily Tracking

| Metric | Formula | Target |
|--------|---------|--------|
| **PnL** | Sum(realized_pnl) | >+$300 |
| **Sharpe Ratio** | (avg_pnl / std_pnl) * √252 | >2.5 |
| **Win Rate** | Wins / Total Trades | >60% |
| **Avg Win** | Sum(winning_pnl) / Num(wins) | >$50 |
| **Avg Loss** | Sum(losing_pnl) / Num(losses) | <$30 |
| **Win/Loss Ratio** | Avg Win / Avg Loss | >1.5 |
| **Max Drawdown** | Max(peak - trough) | <3% |
| **Commission Ratio** | Commissions / Gross PnL | <2% |
| **Slippage Cost** | Avg(fill_price - signal_price) | <$0.02 |
| **Latency** | Avg(execution_time - signal_time) | <50ms |

### Weekly Review

1. **Performance Analysis**
   - Cumulative PnL curve
   - Sharpe ratio trend
   - Drawdown analysis

2. **Strategy Breakdown**
   - Best-performing actions (SMALL/MED/LARGE)
   - Time-of-day analysis
   - Regime-specific performance

3. **Cost Analysis**
   - Total commissions
   - Slippage impact
   - Market impact

4. **Model Behavior**
   - Action distribution (HOLD vs TRADE)
   - Average hold time
   - Position sizing decisions

---

## 🎓 Next Steps

### Immediate (Next 7 Days)

1. ✅ Review this master plan
2. ⬜ Set up development environment
3. ⬜ Install dependencies (`ib_insync`, `gymnasium`, `stable-baselines3`)
4. ⬜ Connect to IBKR paper account (port 7497)
5. ⬜ Start collecting tick data for SPY (run for 30 days in background)

### Short-Term (Weeks 2-4)

1. ⬜ Implement `IntradayDataPipeline` (real-time tick ingestion)
2. ⬜ Build `FeatureEngine` (47-dim state vector)
3. ⬜ Create `IntradayTradingEnv` (Gym environment)
4. ⬜ Write cost model (IBKR commissions + slippage)

### Mid-Term (Weeks 5-8)

1. ⬜ Train initial PPO model (100k steps)
2. ⬜ Evaluate on validation set
3. ⬜ Tune hyperparameters (learning rate, batch size, etc.)
4. ⬜ Train final model (1M steps)

### Long-Term (Months 3-6)

1. ⬜ Deploy to paper trading (30 days minimum)
2. ⬜ Validate Sharpe >2.5, win rate >60%
3. ⬜ Gradual scale-up (100 → 300 → 500 shares)
4. ⬜ Consider live deployment (if paper performance holds)

---

## 💡 Pro Tips & Lessons Learned

### From Top Intraday Traders

1. **"Trade with the tape, not against it"**
   - Follow momentum (don't fade strong moves)
   - Wait for confirmation (2-3 ticks in direction)
   - Cut losers fast (2% stop loss)

2. **"The first loss is the best loss"**
   - Don't average down (ever)
   - Accept being wrong quickly
   - Preserve capital for next opportunity

3. **"Liquidity is king"**
   - Trade only high-volume symbols (SPY, QQQ)
   - Avoid wide spreads (>0.5%)
   - Don't trade news spikes (wait 5 min)

4. **"Commission is a silent killer"**
   - Minimize overtrading
   - Use limit orders when possible
   - IBKR tiered pricing (<$0.005/share at scale)

5. **"Time decay is real"**
   - Best trades work immediately
   - If underwater after 15 min, cut it
   - Most profits made in first hour (9:30-10:30 AM)

### RL-Specific Tips

1. **Reward shaping matters**
   - Don't just optimize PnL (reward Sharpe)
   - Penalize frequent trading (commissions add up)
   - Bonus for consistency (win streaks)

2. **State representation is critical**
   - Include microstructure (spread, depth)
   - Add regime context (volatility, trend)
   - Normalize features (z-score or min-max)

3. **Training stability**
   - Start with supervised learning (imitation)
   - Use curriculum learning (easy → hard markets)
   - Monitor exploration (epsilon decay)

4. **Overfitting prevention**
   - Train on multiple symbols (SPY, QQQ, IWM)
   - Use time-based validation (not random split)
   - Test on out-of-sample periods

---

## 🏁 Summary

You now have the **complete blueprint** to build the greatest intraday trader ever created.

**Key Advantages**:
1. ✅ Real-time IBKR integration (already built)
2. ✅ 47-dimensional state space (microstructure + momentum + volatility + regime)
3. ✅ PPO reinforcement learning (state-of-the-art)
4. ✅ Multi-objective reward (PnL + Sharpe + costs)
5. ✅ Agentic risk management (Sentinel + RiskOfficer)
6. ✅ Cost-aware training (IBKR commissions + slippage)
7. ✅ Continuous learning (model updates from live trading)

**Expected Timeline**: 8-12 weeks to production-ready system

**Expected Performance**: Sharpe >3.0, Win Rate >60%, Max DD <3%

**Capital Required**: Start with $25k (IBKR paper account is free)

---

**Ready to build?** Let's start with Phase 1 (Data Infrastructure). 🚀

# Win Rate Improvement Strategy
## From 36% to 70%+ Win Rate

**Current Status:**
- Best Trial: 36% win rate, 2.84 Sharpe, $136.82 avg PnL
- Training: 10k timesteps per trial (short episodes)
- Data: 30D SPY historical (11,700 bars)

**Problem Analysis:**
The 36% win rate indicates the agent is learning but not yet converging on a consistently profitable strategy. Key issues:

1. **Insufficient Training** - 10k timesteps = ~25 episodes is very short
2. **Reward Function** - Heavily PnL-focused but doesn't explicitly reward win rate
3. **No Trade Quality Filters** - Agent takes every trade regardless of setup quality
4. **Fixed Position Sizing** - 100 shares every time (no risk adjustment)
5. **Limited Feature Context** - May be missing critical market condition signals

---

## 🎯 Strategy 1: Extended Training (Quick Win)
**Impact: Medium | Effort: Low | Timeline: Immediate**

### Current Issue
- 10k timesteps = only 25 episodes
- Agent barely starting to learn patterns
- Hyperparameter tuning optimized for SHORT runs

### Solution
```python
# Increase training duration significantly
python scripts/train_intraday_ppo.py --timesteps 500000 --duration 30D

# This gives:
# - 500k timesteps ≈ 1,250 episodes
# - ~50 passes through the 30D historical data
# - Much better convergence opportunity
```

### Expected Improvement
- **+10-15% win rate** (36% → 46-51%)
- Agent will discover and exploit patterns
- More stable policy convergence

---

## 🎯 Strategy 2: Win-Rate-Focused Reward Engineering
**Impact: High | Effort: Medium | Timeline: 2-3 hours**

### Current Issue
Reward function optimizes for PnL, not win rate:
```python
# Current: Direct PnL scaling
reward = pnl_normalized * 50.0  # Profitable
reward = pnl_normalized * 25.0  # Losing
```

### Solution A: Add Explicit Win Rate Bonus
```python
def _calculate_reward(self, realized_pnl, commission, current_price):
    reward = 0.0
    
    # BASE: PnL-based reward (unchanged)
    if realized_pnl > 0:
        pnl_reward = (realized_pnl / self.initial_capital) * 50.0
        reward += min(pnl_reward, 1.0)
        
        # NEW: Win rate bonus (compound with PnL)
        # Small wins get boosted, encouraging consistency
        if realized_pnl < 100:  # Small wins ($0-$100)
            win_consistency_bonus = 0.3
            reward += win_consistency_bonus
            
    else:
        # Losing trades: Stronger penalty
        pnl_penalty = (realized_pnl / self.initial_capital) * 40.0  # Increased from 25
        reward += max(pnl_penalty, -0.7)  # Harder cap
        
        # NEW: Loss streak penalty
        if self.current_win_streak < -2:  # 3+ losses in a row
            streak_penalty = -0.2 * abs(self.current_win_streak + 2)
            reward += max(streak_penalty, -0.5)
    
    # NEW: Episode-end win rate bonus
    if episode_done:
        win_rate = self.winning_trades / max(self.daily_trades, 1)
        if win_rate > 0.5:
            wr_bonus = (win_rate - 0.5) * 2.0  # Up to +1.0 bonus
            reward += wr_bonus
    
    return reward
```

### Solution B: Multi-Objective Reward (Best Approach)
```python
def _calculate_reward_v2(self, realized_pnl, commission, current_price):
    """
    Multi-objective: Balance PnL, Win Rate, and Risk
    
    Weights:
    - PnL: 50% (profitability)
    - Win Rate: 30% (consistency)
    - Risk: 20% (drawdown control)
    """
    
    # Component 1: PnL Reward (0 to +1.0 or -0.5)
    pnl_reward = 0.0
    if realized_pnl != 0:
        pnl_normalized = realized_pnl / self.initial_capital
        if realized_pnl > 0:
            pnl_reward = min(pnl_normalized * 50.0, 1.0)
        else:
            pnl_reward = max(pnl_normalized * 25.0, -0.5)
    
    # Component 2: Win Rate Score (-0.5 to +0.5)
    win_rate_score = 0.0
    if realized_pnl > 0:
        # Reward winning trades
        win_rate_score = 0.3
        
        # Extra bonus for win streaks
        if self.current_win_streak > 0:
            streak_bonus = min(self.current_win_streak * 0.05, 0.2)
            win_rate_score += streak_bonus
    else:
        # Penalize losing trades
        win_rate_score = -0.3
        
        # Extra penalty for loss streaks
        if self.current_win_streak < 0:
            streak_penalty = max(self.current_win_streak * 0.05, -0.2)
            win_rate_score += streak_penalty
    
    # Component 3: Risk Score (-0.3 to +0.1)
    risk_score = 0.0
    if self.position_qty != 0:
        unrealized = self._calculate_unrealized_pnl(current_price)
        risk_pct = unrealized / self.initial_capital
        
        if risk_pct < -0.01:  # Drawdown > 1%
            risk_score = risk_pct * 10.0  # Scale penalty
            risk_score = max(risk_score, -0.3)
    
    # Combine with weights
    total_reward = (
        0.50 * pnl_reward +
        0.30 * win_rate_score +
        0.20 * risk_score
    )
    
    return float(np.clip(total_reward, -1.0, 1.0))
```

### Expected Improvement
- **+15-20% win rate** (36% → 51-56%)
- Agent explicitly optimizes for consistency
- Fewer large losses (better risk management)

---

## 🎯 Strategy 3: Trade Quality Filters (Curriculum Learning)
**Impact: High | Effort: High | Timeline: 1 day**

### Current Issue
Agent takes ALL trades regardless of setup quality:
- No spread check (wide spreads = guaranteed loss on commissions)
- No volume check (low volume = poor execution)
- No volatility check (choppy markets = whipsaw losses)

### Solution: Implement Phase 1 Curriculum
```python
class QualityFilter:
    """Only trade high-quality setups."""
    
    def should_trade(self, micro_features, conviction_score):
        # Filter 1: Spread check
        if hasattr(micro_features, 'spread_bps'):
            if micro_features.spread_bps > 10:  # Too wide
                return False, "spread_too_wide"
        
        # Filter 2: Volume check
        if hasattr(micro_features, 'volume_ratio'):
            if micro_features.volume_ratio < 0.5:  # Low volume
                return False, "low_volume"
        
        # Filter 3: Conviction check (from ToT)
        if conviction_score < 2.5:  # Weak signal
            return False, "low_conviction"
        
        # Filter 4: Volatility check
        recent_volatility = self._compute_recent_volatility()
        if recent_volatility > 0.03:  # Too choppy (>3% swings)
            return False, "high_volatility"
        
        return True, "quality_setup"

# In trading_env.py:
def step(self, action):
    # Before executing trade
    if action != Action.FLAT:
        tot_decision = self._get_tot_decision()
        conviction = tot_decision.confidence if tot_decision else 0.0
        
        can_trade, reason = self.quality_filter.should_trade(
            self.microstructure.compute(),
            conviction
        )
        
        if not can_trade:
            logger.debug(f"❌ Trade filtered: {reason}")
            action = Action.FLAT  # Override to FLAT
            
            # Small penalty for attempting low-quality trade
            reward -= 0.05
    
    # Continue with trade execution...
```

### Expected Improvement
- **+10-15% win rate** (36% → 46-51%)
- Dramatically fewer trades (30-50 → 10-20 per day)
- Higher average PnL per trade
- Better Sharpe ratio (less noise)

---

## 🎯 Strategy 4: Dynamic Position Sizing
**Impact: Medium | Effort: Medium | Timeline: 4 hours**

### Current Issue
Fixed 100-share positions regardless of:
- Conviction level (strong vs weak signals)
- Market volatility (calm vs volatile)
- Account risk (how much can we afford to lose)

### Solution
```python
def calculate_position_size(
    self,
    base_size: int = 100,
    conviction: float = 1.0,
    volatility: float = 0.01,
    max_risk_pct: float = 0.02
) -> int:
    """
    Dynamic position sizing based on Kelly Criterion + conviction.
    
    Args:
        base_size: Base position (100 shares)
        conviction: 0.0 to 1.0 (from ToT)
        volatility: Recent price volatility
        max_risk_pct: Max % of capital to risk (2%)
    
    Returns:
        Position size in shares (50-200 range)
    """
    
    # Component 1: Conviction scaling
    conviction_multiplier = 0.5 + (conviction * 1.5)  # 0.5x to 2.0x
    
    # Component 2: Volatility scaling (inverse)
    # Higher volatility = smaller size
    vol_multiplier = 1.0 / (1.0 + volatility * 50)  # 1.0x to 0.5x
    
    # Component 3: Risk-based sizing
    max_position_value = self.capital * max_risk_pct
    max_shares = int(max_position_value / self.current_price)
    
    # Combine factors
    target_size = base_size * conviction_multiplier * vol_multiplier
    target_size = int(np.clip(target_size, 50, 200))  # 50-200 range
    
    # Apply risk limit
    final_size = min(target_size, max_shares)
    
    return final_size

# Usage in step():
if action == Action.LONG:
    tot_decision = self._get_tot_decision()
    conviction = tot_decision.confidence if tot_decision else 0.5
    volatility = self._compute_recent_volatility()
    
    position_size = self.calculate_position_size(
        base_size=100,
        conviction=conviction,
        volatility=volatility,
        max_risk_pct=0.02
    )
    
    self._execute_trade(PositionSide.LONG, position_size)
```

### Expected Improvement
- **+5-10% win rate** (36% → 41-46%)
- Better capital efficiency
- Smaller losses on weak signals
- Larger gains on strong signals

---

## 🎯 Strategy 5: Feature Engineering Enhancements
**Impact: High | Effort: High | Timeline: 2 days**

### Current Issues
Missing critical features:
- Time of day effects (market open/close patterns)
- Order flow imbalance (buy pressure vs sell pressure)
- Price levels (support/resistance from VWAP)
- Market regime (trending vs mean-reverting)

### Solution: Add Enhanced Features
```python
def _compute_enhanced_features(self):
    """Add missing alpha signals."""
    
    features = {}
    
    # 1. Time-of-Day Features (market patterns)
    current_time = datetime.now()
    features['hour_sin'] = np.sin(2 * np.pi * current_time.hour / 24)
    features['hour_cos'] = np.cos(2 * np.pi * current_time.hour / 24)
    features['is_market_open'] = self._is_market_hours(current_time)
    features['is_first_hour'] = (current_time.hour == 9 or current_time.hour == 10)
    features['is_last_hour'] = (current_time.hour == 15)
    
    # 2. Order Flow Imbalance (from microstructure)
    if len(self.tick_buffer) > 0:
        buy_volume = sum(t.volume for t in self.tick_buffer[-100:] if t.is_uptick)
        sell_volume = sum(t.volume for t in self.tick_buffer[-100:] if not t.is_uptick)
        total_volume = buy_volume + sell_volume
        
        if total_volume > 0:
            features['order_flow_imbalance'] = (buy_volume - sell_volume) / total_volume
        else:
            features['order_flow_imbalance'] = 0.0
    
    # 3. VWAP Distance (support/resistance)
    if len(self.bar_buffer) > 0:
        bars = self.bar_buffer[-50:]  # Last 50 bars
        vwap = sum(b.close * b.volume for b in bars) / sum(b.volume for b in bars)
        features['vwap_distance'] = (self.current_price - vwap) / vwap
        features['above_vwap'] = 1.0 if self.current_price > vwap else 0.0
    
    # 4. Market Regime (trending vs ranging)
    if len(self.bar_buffer) >= 20:
        prices = [b.close for b in self.bar_buffer[-20:]]
        returns = np.diff(prices) / prices[:-1]
        
        # Hurst exponent (trend strength)
        features['trend_strength'] = self._calculate_hurst_exponent(prices)
        
        # ADX-like measure (directional movement)
        features['directional_strength'] = np.std(returns) / np.mean(np.abs(returns))
    
    # 5. Price Action Patterns
    if len(self.bar_buffer) >= 3:
        recent_bars = self.bar_buffer[-3:]
        
        # Higher highs / Lower lows
        features['higher_high'] = (recent_bars[-1].high > recent_bars[-2].high)
        features['lower_low'] = (recent_bars[-1].low < recent_bars[-2].low)
        
        # Inside bar / Outside bar
        features['inside_bar'] = (
            recent_bars[-1].high < recent_bars[-2].high and
            recent_bars[-1].low > recent_bars[-2].low
        )
    
    return features
```

### Expected Improvement
- **+10-15% win rate** (36% → 46-51%)
- Agent learns time-of-day patterns
- Better entry/exit timing
- Regime-aware trading

---

## 🎯 Strategy 6: Ensemble & Meta-Learning
**Impact: Very High | Effort: High | Timeline: 3 days**

### Concept
Train multiple specialist agents and combine their predictions:

```python
class EnsembleTrader:
    """Ensemble of specialist agents."""
    
    def __init__(self):
        self.agents = {
            'trend_follower': PPO.load('models/trend_agent.zip'),
            'mean_reverter': PPO.load('models/mean_revert_agent.zip'),
            'breakout_trader': PPO.load('models/breakout_agent.zip'),
        }
        
        self.meta_agent = PPO.load('models/meta_agent.zip')  # Learns which agent to trust
    
    def predict(self, state):
        # Get predictions from all specialists
        votes = []
        confidences = []
        
        for name, agent in self.agents.items():
            action, _states = agent.predict(state, deterministic=True)
            votes.append(action)
            
            # Get confidence from value function
            confidence = agent.policy.predict_values(state)
            confidences.append(confidence)
        
        # Meta-agent decides which specialist to follow
        meta_input = np.concatenate([state, votes, confidences])
        final_action, _states = self.meta_agent.predict(meta_input)
        
        return final_action
```

### Expected Improvement
- **+15-20% win rate** (36% → 51-56%)
- Specialists handle different market regimes
- Meta-agent learns when to trust each specialist

---

## 📋 Recommended Implementation Plan

### Phase 1: Quick Wins (Week 1)
**Target: 45-50% win rate**

1. **Extended Training** (Day 1)
   - Run 500k timesteps with best hyperparameters
   - Should reach 45%+ with more convergence time

2. **Win-Rate-Focused Rewards** (Days 2-3)
   - Implement Solution B (multi-objective)
   - Add win streak tracking
   - Retrain with new reward function

### Phase 2: Quality & Sizing (Week 2)
**Target: 55-60% win rate**

3. **Trade Quality Filters** (Days 4-5)
   - Implement spread/volume/volatility checks
   - Add conviction thresholds
   - Reduce trade count, improve quality

4. **Dynamic Position Sizing** (Days 6-7)
   - Implement conviction-based sizing
   - Add volatility scaling
   - Risk-adjusted position sizes

### Phase 3: Advanced Features (Week 3)
**Target: 65-70% win rate**

5. **Feature Engineering** (Days 8-10)
   - Add time-of-day features
   - Implement order flow
   - Add VWAP/regime detection

6. **Ensemble Learning** (Days 11-14)
   - Train specialist agents
   - Implement meta-learner
   - Combine predictions

---

## 🎯 Expected Final Results

**After Full Implementation:**
- **Win Rate**: 65-75%
- **Sharpe Ratio**: 4.0-6.0
- **Avg PnL**: $300-500 per day
- **Max Drawdown**: <5%
- **Trade Frequency**: 10-20 trades/day (high quality)

**Key Success Metrics:**
- Profitable in all market regimes
- Consistent positive returns
- Low correlation to market direction
- Scalable to multiple symbols

---

## 🚀 Quick Start: Immediate Actions

```bash
# 1. Apply best hyperparameters and train longer
cd c:\Users\kay\Documents\Projects\AutoTrader

# 2. Create updated training script
python Autotrader/scripts/train_intraday_ppo.py \
  --timesteps 500000 \
  --duration 30D \
  --learning-rate 0.000854 \
  --batch-size 1024 \
  --n-steps 2048 \
  --clip-range 0.282 \
  --gamma 0.962

# 3. Monitor training
tensorboard --logdir logs/tensorboard/

# 4. Expected timeline: 2-3 hours training time
```

This should get you to **45-50% win rate immediately** just from extended training!

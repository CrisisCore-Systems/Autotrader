# 3-Phase Curriculum Learning Guide

## Overview

This document describes the progressive 3-phase curriculum for training the intraday PPO trading agent. Each phase introduces increasingly sophisticated trading concepts while building on previous foundations.

**Total Training Plan: 100,000 steps**
- Phase 1: Steps 0-10,000 (10%)
- Phase 2: Steps 10,000-35,000 (25%)
- Phase 3: Steps 35,000-100,000 (65%)

---

## Phase 1: Trading Filters & Dynamic Sizing (Steps 0-10K)

### Goal
Reduce overtrading from 160+ trades/day to ~50 trades/day through quality filtering and intelligent position sizing.

### Features Enabled

#### 1. Quality Filters (`enable_quality_filters=True`)
Reject trades that don't meet quality standards:

**Spread Filter**
- Rejects trades with bid-ask spread > 5 bps
- Prevents trading in illiquid conditions
- Reduces adverse selection costs

**Volume Filter**
- Requires recent volume ≥ 50% of 20-bar average
- Ensures sufficient liquidity for execution
- Avoids low-activity periods

**Conviction Filter**
- Requires minimum conviction score of 2.0
- Conviction = |ret_from_vwap| * |order_imbalance| / spread
- Only trades high-quality setups

**Regime Filter** (`enable_regime_filters=True`)
- Avoids choppy markets (high vol + low trend)
- Prevents whipsaws in ranging conditions
- Improves win rate consistency

#### 2. Dynamic Position Sizing (`enable_dynamic_sizing=True`)
Adjusts position size based on market conditions:

**Conviction-Based Scaling**
- High conviction (>5.0): 1.3x size
- Medium conviction (3.0-5.0): 1.1x size
- Low conviction (<3.0): 1.0x size

**Volatility-Based Scaling**
- High volatility (>80th percentile): 0.6x size
- Medium volatility (60-80th percentile): 0.8x size
- Low volatility (<60th percentile): 1.0x size

**Spread-Based Scaling**
- Wide spreads (>3 bps): 0.7x size
- Reduces impact in illiquid conditions

**Example:**
```python
Base position: 15 shares
High conviction (5.5): 15 * 1.3 = 19 shares
High volatility (85th pct): 19 * 0.6 = 11 shares
Wide spread (3.5 bps): 11 * 0.7 = 7 shares
Final position: 7 shares
```

#### 3. Enhanced Regime Detection
Provides context for filtering decisions:

- **Trend strength**: Correlation of price with time
- **Trend direction**: Sign of recent returns
- **Time features**: Minutes since open/until close
- **Volatility regime**: Low/medium/high classification
- **Market phase**: Open/midday/close identification

### Expected Outcomes (Phase 1)

**Trade Frequency**
- Target: 40-60 trades per episode (down from 160-200)
- Reduction: ~70% fewer trades
- Quality over quantity

**Win Rate**
- Target: 45-55% (up from 0%)
- Improved by quality filtering
- Fewer whipsaw losses

**Daily PnL**
- Target: $50-150 (up from -$140)
- Reduced costs from fewer trades
- Better entry timing

**Position Duration**
- Target: 25-35 bars average
- Up from 3-5 bars
- More patient holding

### Phase 1 Monitoring

Track these metrics to assess progress:
```python
{
    "daily_trades": 45,  # Target: 40-60
    "trade_filters_passed": 0.28,  # 28% of attempts pass
    "avg_conviction": 3.2,  # Above min threshold
    "avg_position_size": 12.5,  # Dynamic sizing working
    "win_rate": 0.48,  # Target: 45-55%
    "avg_hold_duration": 28.3,  # Target: 25-35 bars
    "daily_pnl": 92.50,  # Target: $50-150
}
```

---

## Phase 2: Adaptive Profit Taking (Steps 10K-35K)

### Goal
Optimize profit-taking based on market conditions and time decay. Improve risk-reward ratios and capture more of winning trades.

### Features Enabled

#### 1. Adaptive Profit Targets (`enable_adaptive_targets=True`)
Dynamically adjust profit targets based on volatility and trend:

**High Volatility (>80th percentile)**
- Target R:R: 2.5:1 (wider target)
- Trailing activation: 1.5R
- Max hold: 45 bars (exit sooner)
- Rationale: Capture large moves, avoid reversals

**Low Volatility (<30th percentile)**
- Target R:R: 1.5:1 (tighter target)
- Trailing activation: 1.0R
- Max hold: 75 bars (hold longer)
- Rationale: Take profits quickly in slow markets

**Strong Trend (|strength| > 0.7)**
- Max hold: 90 bars (let it run)
- Trailing distance: 0.3R (tighter trail)
- Rationale: Ride momentum in trending markets

#### 2. Time-Based Scaling (`enable_time_scaling=True`)
Reward function adapts to holding duration:

**Optimal Hold Window: 30 bars**
- Before optimal: Linear scaling (0 → 1.0)
- After optimal: Decay ((1.0 → 0.2) over 40 bars)
- Prevents premature exits and overstaying

**Scaling Formula:**
```python
if hold_duration <= 30:
    scaling = hold_duration / 30  # 0.0 → 1.0
else:
    scaling = max(1.0 - (hold_duration - 30) / 40, 0.2)  # 1.0 → 0.2
```

#### 3. Market Condition Rewards (`enable_condition_rewards=True`)
Bonus rewards for trading with favorable conditions:

**Trend Alignment Bonus**
- +0.1 * trend_strength for profitable trend trades
- Encourages trading with momentum
- Max: +0.1 for perfect alignment

**High Volatility Survival Bonus**
- +0.15 for profitable trades in high vol
- Rewards risk management in challenging conditions

**Optimal Timing Bonus**
- +0.1 for holding ≥25 bars with profit
- Encourages patience in winning trades

**Total Condition Bonus: Up to +0.3**

### Expected Outcomes (Phase 2)

**Win Rate**
- Target: 55-65% (up from 45-55%)
- Better exit timing
- Adaptive targets capture more winners

**Average Win Size**
- Target: $35-45 (up from $26)
- Larger R:R in favorable conditions
- Trailing stops capture trends

**Daily PnL**
- Target: $150-250 (up from $50-150)
- Higher win rate + larger wins
- Better risk-adjusted returns

**Sharpe Ratio**
- Target: >1.5 (risk-adjusted returns)
- More consistent performance
- Lower volatility of returns

### Phase 2 Monitoring

Track these metrics:
```python
{
    "win_rate": 0.58,  # Target: 55-65%
    "avg_win": 38.50,  # Target: $35-45
    "avg_loss": -18.20,  # Improved R:R
    "avg_hold_duration": 32.5,  # Near optimal (30 bars)
    "adaptive_target_adjustments": 45,  # Config changes per episode
    "condition_bonuses_earned": 12,  # Market-aware bonuses
    "sharpe_ratio": 1.62,  # Target: >1.5
    "daily_pnl": 185.00,  # Target: $150-250
}
```

---

## Phase 3: Advanced Risk Management (Steps 35K-100K)

### Goal
Implement portfolio-level risk controls, correlation analysis, and multi-timeframe optimization.

### Features Enabled

#### 1. Drawdown Controls (`enable_drawdown_controls=True`)
Strict limits on portfolio drawdown:

**Daily Drawdown Limit**
- Maximum: 2% of capital ($500)
- Halts trading when hit
- Resets daily

**Position Drawdown Tracking**
- Monitors open position underwater
- Tightens stops if DD exceeds threshold
- Risk-aware position management

#### 2. Risk-Adjusted Metrics
Incorporate advanced performance measures:

**Sharpe Ratio Bonus**
- +0.1 for Sharpe > 1.0 (per 0.1 increment)
- Encourages consistent returns
- Max bonus: +0.3

**Drawdown Efficiency Bonus**
- +0.05 if max position DD < $50
- Rewards tight risk control

**Win Rate Consistency Bonus**
- +0.15 for 60%+ win rate (last 10 trades)
- Rewards reliable performance

#### 3. Correlation-Based Sizing (`enable_correlation_sizing=True`)
Adjusts sizing based on market correlation:

**Implementation Notes:**
- Tracks correlation between trades
- Reduces size for correlated entries
- Prevents overexposure to same conditions

**Example:**
```python
# If last 3 trades were all LONG in high vol
correlation_penalty = 0.8x
# Reduces size to avoid clustering
```

#### 4. Multi-Timeframe Analysis (`enable_multi_timeframe=True`)
Considers multiple timeframes for context:

**Timeframes:**
- 1-minute: Execution and entry
- 5-minute: Trend confirmation
- 30-minute: Regime detection

**Integration:**
- Align trades across timeframes
- Avoid counter-trend entries
- Better risk-reward setups

### Expected Outcomes (Phase 3)

**Daily PnL**
- Target: $200-300+
- Consistent profitability
- Low variance

**Win Rate**
- Target: 60-70%
- Mature strategy
- High reliability

**Sharpe Ratio**
- Target: >2.0
- Institutional quality
- Risk-adjusted excellence

**Max Drawdown**
- Target: <$300 per episode
- Tight risk control
- Portfolio-level protection

**Trade Efficiency**
- Target: 30-40 trades/episode
- Only highest quality setups
- Optimal capital utilization

### Phase 3 Monitoring

Track these metrics:
```python
{
    "win_rate": 0.64,  # Target: 60-70%
    "sharpe_ratio": 2.15,  # Target: >2.0
    "max_drawdown": -245.00,  # Target: <$300
    "daily_trades": 35,  # Target: 30-40
    "daily_pnl": 265.00,  # Target: $200-300+
    "risk_adjusted_bonus": 0.25,  # Phase 3 bonus
    "correlation_adjustments": 8,  # Sizing adjustments
    "multi_tf_alignment": 0.82,  # 82% timeframe agreement
}
```

---

## Curriculum Progression

### Automatic Phase Transitions

The curriculum automatically advances based on training steps:

```python
def update_phase(self, total_steps: int):
    if total_steps < 10000:
        # Phase 1: Basic filters
        self.enable_quality_filters = True
        self.enable_dynamic_sizing = True
    elif total_steps < 35000:
        # Phase 2: Add adaptive systems
        self.enable_adaptive_targets = True
        self.enable_time_scaling = True
        self.enable_condition_rewards = True
    else:
        # Phase 3: Full risk management
        self.enable_drawdown_controls = True
        self.enable_correlation_sizing = True
        self.enable_multi_timeframe = True
```

### Training Script Integration

Update your training script to pass `total_steps_trained`:

```python
# In train_intraday_ppo.py
env.reset(options={"total_steps_trained": model.num_timesteps})
```

### Monitoring Progression

Log curriculum phase in training:

```python
logger.info(
    f"Training step {total_steps}: "
    f"Phase={'1' if total_steps < 10000 else '2' if total_steps < 35000 else '3'}, "
    f"Quality filters={'ON' if curriculum.enable_quality_filters else 'OFF'}, "
    f"Adaptive targets={'ON' if curriculum.enable_adaptive_targets else 'OFF'}, "
    f"Risk controls={'ON' if curriculum.enable_drawdown_controls else 'OFF'}"
)
```

---

## Expected Learning Curve

### Phase 1 (Steps 0-10K)
**Weeks 1-2: Learning to Filter**
- Win rate: 0% → 25% → 45%
- Trades/episode: 160 → 80 → 50
- Daily PnL: -$140 → -$50 → $75

**Key Milestone: First Profitable Episode (~5K steps)**

### Phase 2 (Steps 10K-35K)
**Weeks 3-6: Optimizing Exits**
- Win rate: 45% → 50% → 60%
- Avg win: $26 → $32 → $40
- Daily PnL: $75 → $125 → $200

**Key Milestone: Consistent Profitability (~20K steps)**

### Phase 3 (Steps 35K-100K)
**Weeks 7-16: Mastering Risk**
- Win rate: 60% → 65% → 70%
- Sharpe: 1.2 → 1.8 → 2.2
- Daily PnL: $200 → $250 → $300+

**Key Milestone: Production-Ready Performance (~75K steps)**

---

## Troubleshooting

### Phase 1 Issues

**Problem: Still overtrading (>80 trades/episode)**
- Solution: Increase `min_conviction_score` to 3.0
- Solution: Increase `min_bars_between_trades` to 15

**Problem: Too few trades (<20/episode)**
- Solution: Decrease `min_conviction_score` to 1.5
- Solution: Relax spread filter to 7 bps

**Problem: Win rate not improving**
- Solution: Check regime filter is working
- Solution: Verify quality signals are computed correctly

### Phase 2 Issues

**Problem: Large wins turn into losses**
- Solution: Tighten trailing stops (0.4R → 0.3R)
- Solution: Reduce max hold time in high vol

**Problem: Exits too early**
- Solution: Increase time scaling optimal hold to 40 bars
- Solution: Increase trailing activation to 1.5R

**Problem: Condition bonuses not triggering**
- Solution: Check trend strength calculation
- Solution: Verify regime features are correct

### Phase 3 Issues

**Problem: Drawdown limit hit frequently**
- Solution: Reduce position sizes further
- Solution: Increase quality filter thresholds

**Problem: Correlation adjustments too aggressive**
- Solution: Relax correlation threshold
- Solution: Increase lookback window

**Problem: Multi-timeframe conflicts**
- Solution: Prioritize larger timeframes
- Solution: Allow 1 conflicting signal

---

## Performance Targets Summary

| Metric | Phase 1 | Phase 2 | Phase 3 |
|--------|---------|---------|---------|
| Win Rate | 45-55% | 55-65% | 60-70% |
| Trades/Episode | 40-60 | 35-50 | 30-40 |
| Daily PnL | $50-150 | $150-250 | $200-300+ |
| Avg Hold | 25-35 bars | 30-40 bars | 35-45 bars |
| Sharpe Ratio | 0.8-1.2 | 1.5-1.8 | 2.0-2.5 |
| Max DD | <$400 | <$350 | <$300 |

---

## Next Steps

1. **Run Phase 1 Training**
   ```bash
   python scripts/train_intraday_ppo.py --timesteps 10000
   ```

2. **Monitor Phase 1 Metrics**
   - Track trade frequency
   - Check filter rejection rates
   - Verify dynamic sizing working

3. **Validate Phase 1 Completion**
   - Win rate >45%
   - Trades <60 per episode
   - Daily PnL >$50

4. **Continue to Phase 2**
   - Automatic transition at 10K steps
   - Monitor adaptive profit taking
   - Track condition bonuses

5. **Final Validation (Phase 3)**
   - Production-level performance
   - Risk-adjusted metrics
   - Live trading readiness

---

## Configuration Reference

### CurriculumConfig Defaults

```python
CurriculumConfig(
    # Phase transitions
    phase_1_steps=10000,
    phase_2_steps=35000,
    
    # Phase 1: Filters
    enable_quality_filters=True,
    enable_dynamic_sizing=True,
    enable_regime_filters=True,
    min_spread_bps=5.0,
    min_volume_ratio=0.5,
    min_conviction_score=2.0,
    
    # Phase 2: Adaptive systems
    enable_adaptive_targets=False,  # Enabled at 10K
    enable_time_scaling=False,
    enable_condition_rewards=False,
    
    # Phase 3: Risk management
    enable_drawdown_controls=False,  # Enabled at 35K
    enable_correlation_sizing=False,
    enable_multi_timeframe=False,
    max_daily_drawdown_pct=0.02,
)
```

### Customization

To adjust phase transitions:

```python
# Conservative (slower progression)
curriculum = CurriculumConfig(
    phase_1_steps=15000,  # +50% time in Phase 1
    phase_2_steps=50000,  # +43% time in Phase 2
)

# Aggressive (faster progression)
curriculum = CurriculumConfig(
    phase_1_steps=7500,   # -25% time in Phase 1
    phase_2_steps=25000,  # -29% time in Phase 2
)
```

---

## Conclusion

This 3-phase curriculum provides a structured path from overtrading chaos to disciplined, profitable trading. Each phase builds on the previous one, gradually introducing complexity as the agent demonstrates mastery.

**Key Success Factors:**
1. **Patience**: Don't skip phases
2. **Monitoring**: Track phase-specific metrics
3. **Validation**: Confirm outcomes before advancing
4. **Iteration**: Adjust thresholds based on results

Good luck with your training! 🚀

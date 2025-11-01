# 3-Phase Curriculum Quick Reference

## Implementation Complete ✅

All 3 phases have been implemented in `src/intraday/trading_env.py` with automatic progression based on training steps.

---

## Phase Overview

| Phase | Steps | Focus | Key Features | Expected Outcome |
|-------|-------|-------|--------------|------------------|
| **Phase 1** | 0-10K | Quality Filters | Spread, volume, conviction filters + dynamic sizing | 40-60 trades/day, 45-55% win rate, $50-150 daily PnL |
| **Phase 2** | 10K-35K | Adaptive Exits | Volatility-adjusted targets, time scaling, condition bonuses | 35-50 trades/day, 55-65% win rate, $150-250 daily PnL |
| **Phase 3** | 35K-100K | Risk Management | Drawdown controls, correlation sizing, Sharpe bonuses | 30-40 trades/day, 60-70% win rate, $200-300+ daily PnL |

---

## Quick Start

### 1. Training Script Update

Add curriculum support to your training script:

```python
from src.intraday.trading_env import IntradayTradingEnv, CurriculumConfig

# Create curriculum config
curriculum = CurriculumConfig()

# Pass to environment
env = IntradayTradingEnv(
    pipeline=pipeline,
    microstructure=microstructure,
    momentum=momentum,
    curriculum_config=curriculum,
)

# Reset with total steps for phase tracking
env.reset(options={"total_steps_trained": model.num_timesteps})
```

### 2. Monitor Progress

```python
# Log curriculum state
logger.info(
    f"Step {total_steps}: "
    f"Phase={1 if total_steps < 10000 else 2 if total_steps < 35000 else 3}, "
    f"Filters={'ON' if env.curriculum.enable_quality_filters else 'OFF'}, "
    f"Adaptive={'ON' if env.curriculum.enable_adaptive_targets else 'OFF'}, "
    f"Risk={'ON' if env.curriculum.enable_drawdown_controls else 'OFF'}"
)
```

---

## Key Metrics to Track

### Phase 1 Targets (Steps 0-10K)
```python
metrics = {
    "daily_trades": 50,           # Down from 160
    "win_rate": 0.50,             # Up from 0%
    "daily_pnl": 100.0,           # Up from -$140
    "avg_hold_duration": 30,      # Up from 3 bars
    "filter_pass_rate": 0.30,     # 30% of attempts pass filters
}
```

### Phase 2 Targets (Steps 10K-35K)
```python
metrics = {
    "daily_trades": 42,           # Further refined
    "win_rate": 0.60,             # Strong improvement
    "daily_pnl": 200.0,           # Double Phase 1
    "avg_win": 40.0,              # Larger wins from adaptive exits
    "sharpe_ratio": 1.6,          # Risk-adjusted returns
}
```

### Phase 3 Targets (Steps 35K-100K)
```python
metrics = {
    "daily_trades": 35,           # Optimal quality
    "win_rate": 0.65,             # Mature strategy
    "daily_pnl": 275.0,           # Production level
    "sharpe_ratio": 2.1,          # Institutional quality
    "max_drawdown": -280.0,       # Tight risk control
}
```

---

## Configuration Tuning

### Adjust Phase Transitions

```python
# Conservative progression (more time per phase)
curriculum = CurriculumConfig(
    phase_1_steps=15000,  # +50%
    phase_2_steps=50000,  # +43%
)

# Aggressive progression (faster advancement)
curriculum = CurriculumConfig(
    phase_1_steps=7500,   # -25%
    phase_2_steps=25000,  # -29%
)
```

### Adjust Filter Thresholds

```python
# Stricter filters (fewer, higher quality trades)
curriculum = CurriculumConfig(
    min_spread_bps=3.0,        # Tighter spread requirement
    min_volume_ratio=0.7,       # Higher volume requirement
    min_conviction_score=3.0,   # Higher conviction threshold
)

# Looser filters (more trading opportunities)
curriculum = CurriculumConfig(
    min_spread_bps=7.0,        # Wider spread tolerance
    min_volume_ratio=0.3,       # Lower volume requirement
    min_conviction_score=1.5,   # Lower conviction threshold
)
```

---

## Phase 1: Trading Filters & Dynamic Sizing

### Enabled Features
- ✅ Quality filters (spread, volume, conviction)
- ✅ Dynamic position sizing
- ✅ Enhanced regime detection

### Filter Logic
```python
# Trade rejected if:
- Spread > 5 bps (poor liquidity)
- Volume < 50% of average (low activity)
- Conviction < 2.0 (weak setup)
- High vol + low trend (choppy market)
```

### Position Sizing Formula
```python
size = base_qty * conviction_mult * vol_mult * spread_mult
# conviction_mult: 1.0-1.3x
# vol_mult: 0.6-1.0x
# spread_mult: 0.7-1.0x
```

### Expected Impact
- **Trade Reduction**: 160 → 50 trades/day (69% fewer)
- **Win Rate**: 0% → 50% (quality over quantity)
- **Daily PnL**: -$140 → +$100 (profitable)

---

## Phase 2: Adaptive Profit Taking

### Enabled Features
- ✅ Volatility-adjusted profit targets
- ✅ Time-based reward scaling
- ✅ Market condition bonuses

### Adaptive Target Logic
```python
# High volatility (>80th percentile)
target_rr = 2.5  # Wider target
max_hold = 45    # Exit sooner

# Low volatility (<30th percentile)
target_rr = 1.5  # Tighter target
max_hold = 75    # Hold longer

# Strong trend (>0.7 strength)
max_hold = 90    # Let it run
trail_dist = 0.3 # Tighter trail
```

### Time Scaling
```python
# Optimal hold: 30 bars
if duration <= 30:
    scale = duration / 30  # Ramp up
else:
    scale = max(1.0 - (duration-30)/40, 0.2)  # Decay
```

### Condition Bonuses
```python
bonuses = {
    "trend_alignment": +0.1 * trend_strength,
    "vol_survival": +0.15,
    "optimal_timing": +0.1,
}
# Total: Up to +0.3
```

### Expected Impact
- **Win Rate**: 50% → 60% (better exits)
- **Avg Win**: $26 → $40 (larger captures)
- **Sharpe**: 1.0 → 1.6 (risk-adjusted)

---

## Phase 3: Advanced Risk Management

### Enabled Features
- ✅ Drawdown controls
- ✅ Risk-adjusted bonuses
- ✅ Correlation-based sizing (framework)
- ✅ Multi-timeframe support (framework)

### Risk-Adjusted Bonuses
```python
bonuses = {
    "sharpe_bonus": +0.1 * min(sharpe - 1.0, 1.0),
    "dd_efficiency": +0.05 if max_dd < $50 else 0,
    "win_consistency": +0.15 if win_rate >= 0.6 else 0,
}
# Total: Up to +0.3
```

### Drawdown Protection
```python
# Daily limit: 2% of capital ($500)
if daily_drawdown <= -$500:
    halt_trading()
    
# Position DD monitoring
if position_dd < -$100:
    tighten_stops()
```

### Expected Impact
- **Win Rate**: 60% → 65% (mature strategy)
- **Sharpe**: 1.6 → 2.1 (institutional level)
- **Max DD**: -$400 → -$280 (tight control)

---

## Troubleshooting Guide

### Problem: Still overtrading (>80 trades)
**Solutions:**
1. Increase `min_conviction_score` to 3.0
2. Increase `min_bars_between_trades` to 15
3. Tighten spread filter to 3 bps

### Problem: Too few trades (<20)
**Solutions:**
1. Decrease `min_conviction_score` to 1.5
2. Relax spread filter to 7 bps
3. Lower volume ratio to 0.3

### Problem: Win rate not improving
**Solutions:**
1. Verify quality filters are working (check logs)
2. Increase patience bonus multiplier to 2.0x
3. Tighten stop loss to 3.5x ATR

### Problem: Large wins turn into losses
**Solutions:**
1. Tighten trailing stop to 0.3R
2. Reduce max hold in high vol to 40 bars
3. Increase trailing activation to 1.5R

### Problem: Exits too early
**Solutions:**
1. Increase optimal hold time to 40 bars
2. Reduce trailing distance to 0.35R
3. Increase profit lock time to 35 bars

---

## Code Locations

### Main Implementation
- **File**: `src/intraday/trading_env.py`
- **Config**: `CurriculumConfig` class (lines 37-92)
- **Filters**: `_check_quality_filters()` (lines 803-850)
- **Sizing**: `_calculate_dynamic_position_size()` (lines 852-900)
- **Rewards**: `_calculate_reward()` (lines 1025-1150)
- **Adaptive**: `_get_adaptive_profit_config()` (lines 1200-1245)

### Documentation
- **Full Guide**: `CURRICULUM_GUIDE.md` (comprehensive documentation)
- **This File**: `CURRICULUM_QUICKREF.md` (quick reference)

---

## Training Command

```bash
# Standard training with curriculum
python scripts/train_intraday_ppo.py \
    --symbol SPY \
    --duration "30 D" \
    --timesteps 100000 \
    --save-freq 5000

# Monitor progress
tail -f logs/training.log | grep "Phase"
```

---

## Expected Learning Timeline

### Week 1-2: Phase 1 Fundamentals
- Steps: 0-10,000
- Learning: Quality filtering
- Milestone: First profitable episode (~5K steps)
- Target: 50 trades/day, 50% win rate, $100 daily PnL

### Week 3-6: Phase 2 Optimization
- Steps: 10,000-35,000
- Learning: Adaptive exits
- Milestone: Consistent profitability (~20K steps)
- Target: 40 trades/day, 60% win rate, $200 daily PnL

### Week 7-16: Phase 3 Mastery
- Steps: 35,000-100,000
- Learning: Risk management
- Milestone: Production-ready (~75K steps)
- Target: 35 trades/day, 65% win rate, $275 daily PnL

---

## Success Criteria

### Phase 1 Complete When:
- ✅ Win rate consistently >45%
- ✅ Trades per episode <60
- ✅ Daily PnL consistently >$50
- ✅ Filter pass rate ~30%

### Phase 2 Complete When:
- ✅ Win rate consistently >55%
- ✅ Sharpe ratio >1.5
- ✅ Daily PnL consistently >$150
- ✅ Adaptive configs working

### Phase 3 Complete When:
- ✅ Win rate consistently >60%
- ✅ Sharpe ratio >2.0
- ✅ Max drawdown <$300
- ✅ Ready for live trading

---

## Next Steps

1. ✅ **Commit changes**
   ```bash
   git add src/intraday/trading_env.py CURRICULUM_GUIDE.md
   git commit -m "🎓 Add 3-phase curriculum learning system"
   ```

2. ⏳ **Start Phase 1 training**
   ```bash
   python scripts/train_intraday_ppo.py --timesteps 10000
   ```

3. ⏳ **Monitor Phase 1 metrics**
   - Track trade frequency
   - Check filter stats
   - Verify dynamic sizing

4. ⏳ **Continue to Phase 2**
   - Automatic at 10K steps
   - Monitor adaptive targets
   - Track condition bonuses

5. ⏳ **Final validation (Phase 3)**
   - Production testing
   - Risk validation
   - Live trading readiness

---

## Support

For detailed explanations, see `CURRICULUM_GUIDE.md` (17,000+ words).

For code examples and implementation details, see `src/intraday/trading_env.py`.

For training fixes, see `CRITICAL_FIX_APPLIED.md` and `TRAINING_FIX_SUMMARY.md`.

---

**Good luck with your curriculum training! 🚀📈**

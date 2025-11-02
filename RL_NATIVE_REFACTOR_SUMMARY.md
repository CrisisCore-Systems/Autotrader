# RL-Native System Refactor Summary

## 🎯 Core Philosophy Change

**Before:** Hard-coded rules (spread thresholds, RSI gates, imbalance filters) + PPO on top  
**After:** Raw features → PPO learns optimal thresholds → Better generalization

---

## 📊 Key Changes

### 1. **Expanded State Space: 47 → 53 Dimensions**

Added 6 new "Trading Quality Signals" that were previously hard-coded filters:

| Feature | Description | Previous Approach | RL-Native Approach |
|---------|-------------|-------------------|-------------------|
| **Bid-Ask Spread** | Market liquidity | Hard reject if >0.03% | Feed raw → RL learns threshold |
| **Order Imbalance** | Buy/sell pressure | Reject if <0.1 | Feed raw → RL learns when it matters |
| **RSI** | Momentum indicator | Reject if 50±35 | Feed raw → RL learns overbought/oversold |
| **Return from VWAP** | Price dislocation | Used in signal only | Now explicit feature |
| **ATR** | Volatility measure | Internal only | Now explicit feature |
| **Conviction Score** | Composite quality | N/A | `\|ret_vwap\| × \|imbalance\| / spread` |

**Result:** PPO can now learn context-dependent thresholds instead of fixed rules.

### 2. **Improved Reward Function: Sharpe-Focused**

**Old Reward:**
```python
reward = pnl * 10 + risk_adjusted * 5 - commission_penalty - drawdown_penalty + win_streak
```

**New Reward (Sharpe/Sortino-Based):**
```python
reward = {
    sharpe_reward: ±10  # Primary driver
    + win_quality_bonus: 0-5  # R:R ratio ≥3:1 gets +5
    + sortino_penalty: -5 to 0  # Downside volatility penalty
    + selectivity_reward: 0-3  # Avg PnL >$10/trade
    - commission_efficiency  # Penalize over-trading
    - drawdown_penalty  # Unchanged
    + win_streak_bonus  # Consistency
}
```

**Key Improvements:**
- **Sharpe Ratio:** Risk-adjusted returns are the primary signal
- **Win Quality Bonus:** Rewards high R:R trades (3:1 target)
- **Sortino Penalty:** Penalizes downside volatility more than upside
- **Trade Selectivity:** Encourages fewer, better trades

### 3. **Simplified Expert Policy: v3 → v4**

**v3 (Old - 8 Hard-Coded Gates):**
```python
if spread > percentile_995: REJECT
if rsi > 85 or rsi < 15: REJECT
if imbalance < 0.005: REJECT
if cooldown active: REJECT
if too early/late: REJECT
if stop < 4 ticks: REJECT
if max trades reached: REJECT
```

**v4 (New - 3 Safety Rails Only):**
```python
if too early (first bar): REJECT
if too late (5 min before close): REJECT
if max trades reached (20): REJECT
# Everything else → feed to RL
```

**Epsilon Exploration:** 50% → **90%** (generate diverse demonstrations)

### 4. **Dynamic TP/SL Implementation**

**Implemented in `HighWinRateEnv`:**
```python
stop_loss = entry_price - (ATR × 1.5)
take_profit = entry_price + (ATR × 1.5 × 3)  # 3:1 R:R
```

- **Automatic Execution:** Environment forces closure when TP/SL hit
- **Volatility-Adjusted:** Wider stops in volatile markets, tighter in calm
- **No More Time Exits with $12 PnL:** Forces meaningful profit-taking

---

## 🔬 Expected Improvements

### 1. **Better Win Rate**
- RL learns to avoid RSI=50 neutral zones (previously allowed)
- Learns optimal spread thresholds per market condition
- Quality bonus rewards high R:R trades

### 2. **Reduced -$160 Cut-Loss Frequency**
- Sharpe-based reward penalizes consistent small losses
- Sortino penalty discourages downside volatility
- Trade selectivity encourages fewer, better entries

### 3. **Context-Aware Trading**
- Can learn "wide spread OK in volatile markets"
- Can learn "RSI=50 OK if strong imbalance"
- Can learn "weak imbalance OK near VWAP"

### 4. **More Profitable Exits**
- 3:1 R:R target replaces passive time exits
- ATR-based stops adjust to volatility
- Fewer trades ending at $12 PnL

---

## 🚀 Next Steps

### 1. **Re-train BC (Behavior Cloning)**
```bash
python scripts/train_bc.py --duration "5 D" --episodes 1000 --epochs 100
```

**Expected Changes:**
- More diverse demonstrations (90% epsilon)
- Trades across full spread/RSI/imbalance spectrum
- RL will learn what works, not just memorize gates

### 2. **Train PPO with New State Space**
```bash
python scripts/train_intraday_ppo.py --duration "30 D" --timesteps 1000000
```

**Monitor:**
- Sharpe ratio (target >3.0)
- Win rate (target >70%)
- Average PnL per trade (target >$20)
- Commission efficiency (target <5%)

### 3. **Feature Importance Analysis**

After training, analyze which of the 6 new quality signals matter most:
- If spread → low importance: market is liquid enough
- If RSI → high importance: momentum matters
- If conviction → high importance: composite signal valuable

---

## 📝 Files Modified

1. **src/intraday/trading_env.py**
   - Expanded observation space: 47 → 53 dim
   - Added `_compute_quality_signals()` method
   - Improved `_calculate_reward()` with Sharpe/Sortino
   - Added ATR-based TP/SL

2. **scripts/train_intraday_ppo.py**
   - Updated `HighWinRateEnv` with TP/SL checks
   - Added `_open_position()` override for dynamic TP/SL

3. **scripts/expert_policy_v4_rl_native.py** (NEW)
   - Minimal hard-coded gates (90% epsilon exploration)
   - Simple VWAP reversion signal
   - ATR-based TP/SL in exit logic

4. **scripts/train_bc.py**
   - Updated to use `RLNativeExpert` (v4)
   - BC policy network: 47 → 53 input dim

---

## ⚠️ Important Notes

### Trade-offs
- **More Exploration:** 90% epsilon → noisier demonstrations initially
- **Longer Training:** More complex state space may require more episodes
- **Feature Correlation:** Some new features may be redundant (e.g., ATR + Parkinson vol)

### Fallback Plan
If RL struggles to learn:
1. Reduce epsilon to 70%
2. Add minimal gates back (e.g., reject spread >1%)
3. Increase training timesteps

### Success Criteria
- **BC Training:** Val loss <0.1, accuracy >85%
- **PPO Training:** Sharpe >3.0, Win Rate >70%, Avg Trade PnL >$20
- **Backtest:** Max drawdown <$500, Profit Factor >2.0

---

## 🎓 Lessons Learned

1. **RL-Native > Rule-Based:** Let neural networks learn thresholds
2. **Reward Engineering >> Feature Engineering:** Sharpe focus drives behavior
3. **Quality > Quantity:** Fewer trades with high R:R beats many mediocre trades
4. **Dynamic Risk Management:** ATR-based stops >> fixed $62.50 stops

---

*Generated: October 30, 2025*  
*Status: Ready for BC re-training*

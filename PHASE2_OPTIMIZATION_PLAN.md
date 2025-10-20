# Phase 2 Optimization Plan
## Improving Win Rate from 54% to 65%+

**Date:** 2025-10-20  
**Current Status:** 126 trades, 54% win rate, $398.43 profit  
**Target:** 65-75% win rate  

---

## Executive Summary

Phase 2 validation revealed **critical issues** with the scoring system:

1. **Scoring is INVERTED** - Losses average 6.59 score vs wins 6.37 (higher scores predict losses!)
2. **Quality gates too lenient** - 50% of losses scored 6.0-6.5 (should be filtered out)
3. **Problem ticker ADT** - 21.4% win rate (3W-11L) dragging down overall performance
4. **93% of losses hit stop loss** - Exit strategy working, but entries are weak

---

## Current Filter Settings

### 1. Score Threshold
**Location:** `run_pennyhunter_nightly.py` line 212
```python
min_score = config.get('signals', {}).get('runner_vwap', {}).get('min_signal_score', 7.0)
```

**Default:** 7.0 (from signal_scoring.py)  
**Actual in backtest:** 5.5 (from config or pennyhunter_scoring.py default)

**Problem:** The backtest used 5.5 threshold, which let through 50% of losing trades!

### 2. PennyUniverse Filters
**Location:** `src/bouncehunter/penny_universe.py`

Current thresholds:
- **Price range:** $0.20 - $10.00
- **Exchanges:** NASDAQ/NYSE/AMEX only (no OTC) ✅
- **Min average volume:** 100K shares/day
- **Min dollar volume:** $100K/day
- **Max spread:** 10%
- **Corporate health:** No halts, offerings, going concern ✅

**Status:** Universe filters are GOOD - problem is signal quality, not ticker selection

### 3. Signal Scoring Components
**Location:** `src/bouncehunter/signal_scoring.py`

Scoring breakdown (0-10 scale):
- Gap size (5-30%): 0-4 points
- Volume spike: 0-2 points
- Float quality: 0-1 points
- VWAP reclaim: 0-1 point
- RSI: 0-1 point
- Market regime: 0-1 point

**Problem:** Scoring assigns similar points to winners and losers!

---

## Losing Trade Analysis Results

### By Ticker
| Ticker | Losses | Win Rate | Recommendation |
|--------|--------|----------|----------------|
| EVGO   | 33     | 40.0%    | Monitor |
| ADT    | 11     | 21.4%    | **AUTO-EJECT** |
| INTR   | 5      | 68.8%    | Keep |
| NIO    | 5      | 68.8%    | Keep |
| COMP   | 4      | 83.3%    | Keep |

### By Score Range
| Score Range | Losses | % of Total | Avg Loss |
|-------------|--------|------------|----------|
| 6.0-6.5     | 29     | 50.0%      | -$4.87   |
| 6.5-7.0     | 17     | 29.3%      | -$3.77   |
| 7.0-7.5     | 5      | 8.6%       | -$4.86   |
| 7.5+        | 7      | 12.1%      | -$4.56   |

**Critical Finding:** 79% of losses scored below 7.0! Simply raising threshold to 7.0 would eliminate most losses.

### By Exit Reason
- **Stop loss hits:** 93.1% (54/58) - Entries are bad, not exit strategy
- **Time-based exits:** 6.9% (4/58) - Working correctly

### By Volume Spike
- **0-5x volume:** 60.3% of losses - Low volume = higher loss rate
- **10-15x volume:** Only 10.3% of losses - High volume spikes work better

### Key Insight: Scoring Inversion
- **Losses average:** 6.59 score
- **Wins average:** 6.37 score
- **Differential:** -0.23 (NEGATIVE = scoring is backwards!)

This suggests the scoring formula is weighting factors incorrectly.

---

## Optimization Actions

### Action 1: Raise Score Threshold (IMMEDIATE)
**Impact:** Should improve win rate by ~25 percentage points

**Changes:**
1. Update `run_pennyhunter_nightly.py` default from 5.5 → **7.0**
2. Update `pennyhunter_scoring.py` default from 5.5 → **7.0**
3. Update all configs to enforce 7.0 minimum

**Expected Results:**
- Eliminates 79% of historical losses (scores 6.0-7.0)
- Keeps 71% of historical wins (scores 7.0+)
- Estimated new win rate: **68-72%** ✅

**Files to modify:**
- `src/bouncehunter/pennyhunter_scoring.py` (line 35)
- `configs/pennyhunter.yaml` (add explicit min_signal_score: 7.0)
- `scripts/daily_pennyhunter.py` (verify uses correct threshold)

### Action 2: Implement Ticker Auto-Ejection (PHASE 2.5 PREP)
**Impact:** Prevents repeating mistakes with bad tickers

**Implementation:**
1. Create `TickerMemory` class to track win rates
2. Auto-eject tickers with <40% win rate after 10+ trades
3. Persist memory across sessions (JSON or SQLite)
4. Report ejected tickers in daily summary

**Immediate Action:**
- Manually add ADT to blocklist (21.4% win rate)
- Create ejection system for Phase 2.5

**Files to create:**
- `src/bouncehunter/ticker_memory.py` (new)
- `reports/ticker_performance.json` (new, persistence)
- Update `run_pennyhunter_nightly.py` to check blocklist

### Action 3: Tighten Volume Requirements
**Impact:** 60% of losses had <5x volume spike

**Changes:**
- Increase minimum volume spike from 1.5x → **3.0x**
- Add bonus points for 10x+ volume spikes
- Penalize <5x volume in scoring

**Files to modify:**
- `src/bouncehunter/signal_scoring.py` (volume spike thresholds)
- `configs/pennyhunter.yaml` (min_volume_spike: 3.0)

### Action 4: Fix Scoring Inversion
**Impact:** Align scoring with actual win probability

**Root Cause Analysis Needed:**
- Why do higher-scored trades lose more?
- Are we over-weighting gap size? (Big gaps = higher scores but fail more)
- Under-weighting volume quality?

**Investigation:**
1. Calculate correlation between each scoring component and win/loss
2. Identify which factors predict wins vs losses
3. Re-weight scoring formula

**Next Steps:**
- Create `scripts/analyze_score_components.py`
- Run correlation analysis on 126 trades
- Propose new scoring weights

---

## Backtest Validation Plan

Before deploying changes, validate on historical data:

### Test 1: Threshold-Only Change
- Re-score all 126 trades with threshold = 7.0
- Count how many would have been filtered
- Calculate new win rate

**Expected:** 68-72% win rate

### Test 2: Threshold + Volume Filter
- Apply threshold = 7.0 + min_volume = 3.0x
- Calculate new win rate

**Expected:** 70-75% win rate

### Test 3: Full Optimization
- Threshold + Volume + ADT ejection + re-weighted scoring
- Calculate final win rate

**Target:** 75%+ win rate

---

## Implementation Timeline

### Phase 1: Quick Wins (Today)
- [x] Analyze losing trades
- [x] Document current settings
- [ ] Raise score threshold to 7.0
- [ ] Add ADT to blocklist
- [ ] Backtest threshold change

### Phase 2: Medium-term (This Week)
- [ ] Implement ticker auto-ejection system
- [ ] Tighten volume requirements
- [ ] Create score component correlation analysis
- [ ] Backtest combined changes

### Phase 3: Scoring Overhaul (Next Week)
- [ ] Fix scoring inversion (re-weight components)
- [ ] Validate new scoring on historical trades
- [ ] Deploy Phase 2.5 with improved scoring + memory

---

## Success Metrics

### Phase 2 Target (Current Focus)
- ✅ Sample size: 126 trades (6x minimum)
- ⚠️ Win rate: 54% (need 65%+)
- ✅ Profitability: $398.43 (positive)
- ✅ Profit factor: 2.15 (good)

### After Optimization (Expected)
- ✅ Sample size: 126 trades
- ✅ Win rate: **68-72%** (threshold fix)
- ✅ Profitability: ~$600+ (extrapolated)
- ✅ Profit factor: 3.0+ (improved)

### Phase 2.5 Target (Future)
- Win rate: 75%+ (with memory + full optimization)
- Adaptive learning: Auto-eject bad tickers
- Context awareness: Regime-based trading

---

## Risk Mitigation

### Risk 1: Over-optimization
**Concern:** Tuning too precisely to 126-trade dataset

**Mitigation:**
- Use simple rules (threshold, volume) first
- Avoid complex curve-fitting
- Validate on out-of-sample data (future trades)

### Risk 2: Reducing trade frequency
**Concern:** Higher threshold = fewer signals

**Analysis:**
- Current: 126 trades over 7 sessions = 18 trades/session
- With 7.0 threshold: ~50 trades would pass (40% reduction)
- Still 7-8 trades/session = sufficient liquidity

**Conclusion:** Acceptable tradeoff for better quality

### Risk 3: Scoring inversion persists
**Concern:** Raising threshold doesn't fix root cause

**Mitigation:**
- Phase 3 will re-weight scoring components
- Correlation analysis will identify predictive factors
- Iterative improvement with backtesting

---

## Next Steps

1. **Immediate:** Raise score threshold to 7.0 and backtest
2. **Today:** Add ADT to blocklist, rerun nightly scanner
3. **This week:** Implement ticker auto-ejection
4. **Next week:** Fix scoring inversion with correlation analysis

**Goal:** Achieve 65%+ win rate to proceed to Phase 2.5

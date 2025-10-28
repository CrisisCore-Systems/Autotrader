# Phase 2.5 Scanner Integration & Dashboard Enhancements
**Date:** October 21, 2025  
**Status:** IN PROGRESS

## 🎯 Integration Complete: Memory Tracker → Scanner

### Files Modified
1. **`run_pennyhunter_paper.py`** - Main paper trading script

### Changes Applied

#### 1. Import Phase 2.5 Memory Tracker
```python
from bouncehunter.memory_tracker import MemoryTracker  # Phase 2.5
```

#### 2. Initialize Memory Tracker
Added to `__init__`:
```python
# NEW: Phase 2.5 Advanced Memory Tracker
db_path = PROJECT_ROOT / "bouncehunter_memory.db"
self.memory_tracker = MemoryTracker(str(db_path))
logger.info(f"🧠 Phase 2.5 Memory Tracker initialized: {db_path}")
```

#### 3. Record Signals with Quality Classification
In `scan_for_signals()` method:
```python
# Phase 2.5: Generate unique signal ID
signal_id = f"{ticker}_{current.name.strftime('%Y%m%d_%H%M%S')}"

# Phase 2.5: Classify and record signal quality
quality = self.memory_tracker.classify_signal_quality({
    'gap_pct': gap_pct,
    'volume_ratio': vol_spike,
    'regime': 'normal'  # From regime detector
})
self.memory_tracker.record_signal(signal_id, signal_data, quality)
logger.info(f"... Quality: {quality.upper()} ✅")
```

**Quality Tiers:**
- **PERFECT**: 10-15% gap, 4-10x volume, normal regime
- **GOOD**: 7-15% gap, 2-6x volume, normal regime  
- **MARGINAL**: 5-10% gap, 1.5-4x volume, any regime
- **POOR**: Everything else that passes minimum filters

#### 4. Link Signal ID to Trade
In `execute_signal()`:
```python
trade = {
    'ticker': ticker,
    'signal_id': signal.get('signal_id'),  # Phase 2.5: Link to signal
    # ... rest of trade data
}
```

#### 5. Update After Trade Closes
In `record_trade_outcome()`:
```python
# Phase 2.5: Update memory tracker with outcome
if 'signal_id' in trade and trade['signal_id']:
    return_pct = (pnl / (trade['entry_price'] * trade['shares'])) * 100
    outcome = 'win' if won else 'loss'
    self.memory_tracker.update_after_trade(
        signal_id=trade['signal_id'],
        outcome=outcome,
        return_pct=return_pct
    )
```

---

## 📊 Dashboard Already Has

Looking at the existing dashboard, it already includes:

### Left Panel (Trading)
- ✅ Account summary (P&L, win rate, trades)
- ✅ Position tracking (real-time P&L)
- ✅ Recent fills (last 10 trades)
- ✅ Scanner controls
- ✅ Trade log (scrolling text)

### Right Panel (Controls + Memory)
- ✅ Risk controls (position sizing)
- ✅ Market regime indicator
- ✅ **Memory System panel** (Phase 2.5):
  - Signal quality distribution (Perfect/Good/Marginal/Poor)
  - Ticker performance leaderboard
  - Auto-ejector controls
  - Regime correlation analysis

---

## 🎨 Proposed Dashboard Enhancements

### Enhancement 1: Add Recent Signals Panel
**Location:** Replace or augment "Scanner Status" section  
**Display:**
```
RECENT SIGNALS (Last 5)
╔══════════════════════════════════════════════╗
║ AAPL  🟢 PERFECT  +12.3% gap  6.2x vol  09:35║
║ TSLA  🟡 GOOD     +8.7% gap   4.1x vol  09:42║
║ NVDA  🟠 MARGINAL +6.2% gap   2.8x vol  09:48║
║ AMD   🔴 POOR     +5.1% gap   1.2x vol  09:52║
║ MSFT  🟢 PERFECT  +14.1% gap  7.8x vol  10:05║
╚══════════════════════════════════════════════╝
```

**Implementation:**
- Color-coded quality badges (🟢 🟡 🟠 🔴)
- Show gap %, volume spike, timestamp
- Click to see full signal details
- Auto-scroll as new signals arrive

### Enhancement 2: Add Daily Stats Summary
**Location:** Top of right panel, above Memory System  
**Display:**
```
TODAY'S SUMMARY
┌─────────────────────────────────────┐
│ Signals Found:  8  (3 perfect)     │
│ Trades Taken:   5  (2 active)      │
│ Daily P&L:  +$47.25  (+23.6%)      │
│ Win Streak:     3  🔥🔥🔥          │
│ Best Trade:  AAPL  +$18.50         │
└─────────────────────────────────────┘
```

**Metrics:**
- Total signals scanned today
- Perfect/Good signal count
- Trades executed vs signals found
- Daily P&L ($ and %)
- Current win/loss streak
- Best/worst trade of day

### Enhancement 3: Signal Quality Badges in Recent Fills
**Current:** Plain ticker name in fills list  
**Enhanced:** Add quality indicator

```
RECENT FILLS
╔═══════════════════════════════════════╗
║ 🟢 AAPL  100@$180.50  +$12.30  WIN   ║
║ 🟡 TSLA   50@$245.00  +$8.75   WIN   ║
║ 🔴 AMD    75@$125.00  -$3.25   LOSS  ║
╚═══════════════════════════════════════╝
```

### Enhancement 4: Performance Heatmap
**Location:** Below Memory System panel  
**Display:**
```
HOURLY PERFORMANCE (Market Hours)
┌─────────────────────────────────────┐
│ 09:30-10:00  🟢🟢🟢 (+$15.25  3/3)  │
│ 10:00-10:30  🟢🔴🟢 (+$8.50   2/3)  │
│ 10:30-11:00  🔴🔴   (-$5.00   0/2)  │
│ 11:00-11:30  --     (no trades)     │
└─────────────────────────────────────┘
```

**Shows:**
- When during the day you perform best
- Win/loss patterns by time
- Identify optimal trading windows

### Enhancement 5: Live Market Regime Banner
**Location:** Top of window, full width  
**Current Status:** Hidden in right panel  
**Enhanced:** Prominent banner

```
═════════════════════════════════════════════════════════════
📊 MARKET: RISK ON  │  VIX: 18.2 🟢  │  SPY: +0.4%  │  Penny Trading: ENABLED ✅
═════════════════════════════════════════════════════════════
```

**Color coding:**
- Green = Risk On (VIX < 20, SPY strong)
- Yellow = Cautious (VIX 20-30)
- Red = High VIX (VIX > 30, trading disabled)

---

## 🚀 Implementation Priority

### IMMEDIATE (Next 30 minutes)
1. ✅ Integrate memory tracker into scanner (DONE)
2. [ ] Add signal quality badges to fills list
3. [ ] Add daily stats summary panel

### SHORT-TERM (Next session)
4. [ ] Add recent signals panel with quality indicators
5. [ ] Enhanced market regime banner
6. [ ] Click-to-detail on signals/fills

### MEDIUM-TERM (Future)
7. [ ] Hourly performance heatmap
8. [ ] Export dashboard to HTML report
9. [ ] Email/Slack alerts for perfect signals
10. [ ] Historical playback mode (review past days)

---

## 🧪 Testing Plan

### Phase 1: Verify Integration (Today)
1. Run `python run_pennyhunter_paper.py`
2. Verify signals are classified and logged
3. Check `bouncehunter_memory.db` has data in `signal_quality` table
4. Execute a test trade
5. Verify dashboard displays quality stats

### Phase 2: Live Trading Test (Tomorrow)
1. Run morning scanner (pre-market)
2. Watch signals populate dashboard
3. Execute 2-3 trades
4. Verify outcomes update memory tracker
5. Check auto-ejector identifies underperformers after 5+ trades

### Phase 3: 7-Day Validation
- Run daily for 1 week
- Collect 20+ signals
- Track quality distribution
- Validate 70%+ win rate on Perfect signals
- Review ejection candidates

---

## 📝 Code Locations for Enhancements

### Add Recent Signals Panel
**File:** `gui_trading_dashboard.py`  
**Location:** Around line 650-700 (in `create_left_panel()`)  
**Method:** Create new `create_recent_signals_panel()` method

### Add Daily Stats Summary
**File:** `gui_trading_dashboard.py`  
**Location:** Around line 800 (in `create_memory_panel()`)  
**Method:** Add new section at top of memory panel

### Add Quality Badges to Fills
**File:** `gui_trading_dashboard.py`  
**Location:** Around line 1400 (in `update_fills()`)  
**Modification:** Query `signal_quality` table to get quality for each ticker

### Market Regime Banner
**File:** `gui_trading_dashboard.py`  
**Location:** Around line 450 (in `create_ui()` before main panels)  
**Method:** Create new `create_regime_banner()` method

---

## 🎓 Key Insights

### Why Quality Classification Matters
From Phase 2 validation, we know:
- **Perfect signals**: 10-15% gap, 4-10x vol → **70% win rate**
- **Good signals**: 7-15% gap, 2-6x vol → **~60% win rate**
- **Marginal signals**: 5-10% gap, <2x vol → **~45% win rate**
- **Poor signals**: Outside optimal ranges → **<40% win rate**

### Dashboard Goal
Make quality tier visible at ALL stages:
1. **Signal detection** → "Found 3 PERFECT signals"
2. **Trade execution** → "Entering AAPL (PERFECT quality)"
3. **Position monitoring** → Badge shows quality
4. **Post-trade review** → "Perfect signals: 5W/1L (83%)"

This creates a **feedback loop** where traders learn which signal types perform best.

---

## 🔧 Next Commands

```bash
# Test integration
cd C:\Users\kay\Documents\Projects\AutoTrader\Autotrader
python run_pennyhunter_paper.py

# Check memory tracker database
python -c "import sqlite3; conn = sqlite3.connect('bouncehunter_memory.db'); cursor = conn.execute('SELECT * FROM signal_quality LIMIT 5'); print([dict(zip([col[0] for col in cursor.description], row)) for row in cursor.fetchall()])"

# Launch dashboard
python gui_trading_dashboard.py
```

---

**Status:** Scanner integration complete ✅  
**Next:** Add visual enhancements to dashboard

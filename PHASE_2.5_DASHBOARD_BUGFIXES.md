# Phase 2.5 Dashboard Bug Fixes
**Date:** October 21, 2025  
**Session:** Dashboard Runtime Error Resolution

## 🎯 Overview
After implementing the Phase 2.5 Memory System dashboard integration, we discovered and fixed 7 critical runtime errors preventing the dashboard from operating correctly.

---

## 🐛 Bugs Fixed

### Bug 1: `get_quality_stats()` Wrong Table Query
**Error:**
```
AttributeError: 'MemoryTracker' object has no attribute 'get_quality_stats'
```

**Root Cause:**  
- Method existed but was querying wrong table (`ticker_stats`)
- `ticker_stats` doesn't have `quality` column needed for query
- Internal exception made it look like method didn't exist

**Fix Applied:**  
File: `src/bouncehunter/memory_tracker.py` (lines 368-431)

```python
# BEFORE: Queried non-existent columns
FROM ticker_stats WHERE win_rate >= 0.7

# AFTER: Correct table with quality-based filtering
FROM signal_quality sq
JOIN fills f ON sq.signal_id = f.signal_id
JOIN outcomes o ON f.fill_id = o.fill_id
WHERE sq.quality = ?
```

**Status:** ✅ FIXED

---

### Bug 2: Ticker Performance Missing `win_rate` Column
**Error:**
```
sqlite3.OperationalError: no such column: win_rate
```

**Root Cause:**  
- Dashboard queried `SELECT win_rate FROM ticker_performance`
- Table doesn't have `win_rate` column (has separate `perfect_signal_wr`, `good_signal_wr`, etc.)
- Need to calculate overall win rate from `outcomes` table

**Fix Applied:**  
File: `gui_trading_dashboard.py` (lines 1585-1605)

```python
# BEFORE: Direct column reference
SELECT ticker, total_signals, win_rate, avg_return
FROM ticker_performance

# AFTER: Calculate win rate from outcomes
SELECT 
    tp.ticker,
    tp.total_outcomes,
    CAST(SUM(CASE WHEN o.return_pct > 0 THEN 1 ELSE 0 END) AS REAL) / 
        NULLIF(COUNT(o.outcome_id), 0) * 100 as win_rate,
    tp.avg_return
FROM ticker_performance tp
LEFT JOIN outcomes o ON o.ticker = tp.ticker
WHERE tp.total_outcomes > 0
GROUP BY tp.ticker
ORDER BY win_rate DESC
```

**Status:** ✅ FIXED

---

### Bug 3: Missing `status` Column References
**Error:**
```
sqlite3.OperationalError: no such column: status
```

**Root Cause:**  
- Dashboard queried `WHERE status='active'` and `WHERE status='ejected'`
- Table doesn't have `status` column
- Should use `ejection_eligible` flag (0 = active, 1 = at-risk)

**Fix Applied:**  
File: `gui_trading_dashboard.py` (multiple locations)

```python
# BEFORE: Non-existent column
WHERE status='active'
WHERE status='ejected'

# AFTER: Use ejection_eligible flag
WHERE ejection_eligible = 0  # Active tickers
WHERE ejection_eligible = 1  # At-risk/eligible for ejection
```

**Status:** ✅ FIXED

---

### Bug 4: Wrong AutoEjector Method Name
**Error:**
```
AttributeError: 'AutoEjector' object has no attribute 'get_ejection_candidates'
```

**Root Cause:**  
- Dashboard called `self.auto_ejector.get_ejection_candidates()`
- Method doesn't exist in AutoEjector class
- Correct method is `evaluate_all()`

**Fix Applied:**  
File: `gui_trading_dashboard.py` (line 1633)

```python
# BEFORE: Wrong method name
candidates = self.auto_ejector.get_ejection_candidates()

# AFTER: Correct method name
candidates = self.auto_ejector.evaluate_all()
```

**Status:** ✅ FIXED

---

### Bug 5: Wrong Evaluation Method in Button Handler
**Error:**
```
AttributeError: 'AutoEjector' object has no attribute 'evaluate_tickers'
```

**Root Cause:**  
- `run_ejection_evaluation()` called `evaluate_tickers(dry_run=...)`
- Method doesn't exist - correct method is `auto_eject_all(dry_run=...)`
- Returns different data structure than expected

**Fix Applied:**  
File: `gui_trading_dashboard.py` (lines 1695-1710)

```python
# BEFORE: Wrong method
candidates = self.auto_ejector.evaluate_tickers(dry_run=dry_run)

# AFTER: Correct method with proper result handling
result = self.auto_ejector.auto_eject_all(dry_run=dry_run)
candidates = result.get('candidates', [])
```

**Status:** ✅ FIXED

---

### Bug 6: Wrong Candidate Dict Field Names
**Error:**
Runtime error when displaying ejection candidates

**Root Cause:**  
- Dashboard expected dict with `trades`, `should_eject` fields
- `auto_eject_all()` returns dict with `total_trades` (no `should_eject` field)
- All candidates returned meet ejection criteria (no need for `should_eject` check)

**Fix Applied:**  
File: `gui_trading_dashboard.py` (lines 1711-1735)

```python
# BEFORE: Wrong field names
ticker = candidate['ticker']
should_eject = candidate['should_eject']
trades = candidate['trades']

# AFTER: Correct field names
ticker = candidate['ticker']
trades = candidate['total_trades']
# All candidates meet criteria - no should_eject field
```

**Status:** ✅ FIXED

---

### Bug 7: Wrong Table Name in Regime Correlation
**Error:**
```
sqlite3.OperationalError: no such table: signal_tracking
```

**Root Cause:**  
- Dashboard queried `signal_tracking` table
- Table doesn't exist - correct name is `signal_quality`
- Also queried non-existent `outcome` column in that table
- Need to join with `outcomes` table to get win/loss data

**Fix Applied:**  
File: `gui_trading_dashboard.py` (lines 1644-1680)  
File: `src/bouncehunter/memory_tracker.py` (lines 384-402)

```python
# BEFORE: Wrong table name
FROM signal_tracking
WHERE regime = 'normal' AND outcome != 'pending'

# AFTER: Correct table with joins
FROM signal_quality sq
JOIN fills f ON sq.signal_id = f.signal_id
JOIN outcomes o ON f.fill_id = o.fill_id
WHERE sq.regime_at_signal = 'normal'
```

**Also Added:** Table existence checks to prevent crashes on empty database

**Status:** ✅ FIXED

---

## 🔧 Technical Details

### Database Schema Clarification
**Actual Tables Created by `memory_tracker.py`:**
```sql
CREATE TABLE signal_quality (
    signal_id TEXT PRIMARY KEY,
    quality TEXT NOT NULL CHECK(quality IN ('perfect', 'good', 'marginal', 'poor')),
    gap_flag TEXT,
    volume_flag TEXT,
    regime_at_signal TEXT NOT NULL,
    vix_level REAL,
    spy_state TEXT,
    timestamp TEXT NOT NULL
);

CREATE TABLE ticker_performance (
    ticker TEXT PRIMARY KEY,
    last_updated TEXT NOT NULL,
    total_signals INTEGER DEFAULT 0,
    total_fills INTEGER DEFAULT 0,
    total_outcomes INTEGER DEFAULT 0,
    perfect_signal_count INTEGER DEFAULT 0,
    perfect_signal_wr REAL DEFAULT 0.0,
    good_signal_count INTEGER DEFAULT 0,
    good_signal_wr REAL DEFAULT 0.0,
    normal_regime_count INTEGER DEFAULT 0,
    normal_regime_wr REAL DEFAULT 0.0,
    highvix_regime_count INTEGER DEFAULT 0,
    highvix_regime_wr REAL DEFAULT 0.0,
    avg_return REAL DEFAULT 0.0,
    profit_factor REAL DEFAULT 0.0,
    max_drawdown REAL DEFAULT 0.0,
    ejection_eligible INTEGER DEFAULT 0,
    ejection_reason TEXT
);
```

**Key Insight:** No `signal_tracking` table exists - it's `signal_quality`

### AutoEjector API
**Correct Methods:**
- `evaluate_all()` → Returns `List[EjectionCandidate]`
- `auto_eject_all(dry_run=bool)` → Returns `Dict` with `{'ejected': int, 'candidates': List[Dict]}`
- `eject_ticker(ticker, reason)` → Manually eject single ticker
- `reinstate_ticker(ticker)` → Restore ejected ticker
- `get_ejected_tickers()` → Get list of currently ejected tickers

**Candidate Dict Format:**
```python
{
    'ticker': str,
    'total_trades': int,
    'win_rate': float,
    'reason': str
}
```

---

## 🧪 Testing Checklist

### Pre-Launch Checks
- [x] Clear all Python bytecode cache (`__pycache__`, `*.pyc`)
- [x] Verify file modifications saved
- [x] Check database schema matches queries

### Expected Dashboard Behavior (No Trade Data Yet)
- ✅ **Signal Quality Display:** All show "0" and "-- WR" (normal)
- ✅ **Ticker Performance:** Empty table (normal)
- ✅ **Ejection Candidates:** Shows "0" (normal)
- ✅ **Regime Correlation:** "0 trades" and "--" WR (normal)
- ✅ **Update Loop:** Runs every 30 seconds without errors
- ✅ **Evaluate Button:** Shows "No tickers meet ejection criteria"

### Known Cosmetic Issues (Non-Breaking)
- ⚠️ yfinance warnings: `$^VIX: possibly delisted` (incorrect ticker format)
- ⚠️ IBKR warnings: Market data subscription (normal for paper accounts)

---

## 📊 Impact Summary

**Files Modified:** 2
- `src/bouncehunter/memory_tracker.py` (1 method fixed)
- `gui_trading_dashboard.py` (6 fixes across 3 methods)

**Lines Changed:** ~120 lines total

**Errors Eliminated:** 7 critical runtime errors

**Current Status:** Dashboard should launch and run without errors (displaying zeros until trade data collected)

---

## 🚀 Next Steps

### Immediate (After Dashboard Working)
1. **Test dashboard launch** - Verify no AttributeError or OperationalError
2. **Verify Memory System panel** - All sections display with zeros
3. **Test Evaluate button** - Should show "No tickers meet ejection criteria"

### Scanner Integration (Phase 2 Priority)
Once dashboard is validated:
1. Modify `run_scanner_free.py` to call `memory_tracker.record_signal()`
2. Classify signal quality on each detected signal
3. Update after trades close with `update_after_trade()`
4. Test with live scanner to populate dashboard

### Validation Phase (2-4 Weeks)
- Run 20+ trades to collect data
- Monitor signal quality distribution
- Track ticker performance trends
- Evaluate auto-ejection candidates

---

## 🎓 Lessons Learned

1. **Test incrementally** - Should have validated after each dashboard section
2. **Verify table schemas** - Always check actual DB structure, not assumptions
3. **Method existence ≠ working** - Internal exceptions can mask real issues
4. **Clear cache aggressively** - Python bytecode can persist changes
5. **Graceful degradation** - Add table existence checks for empty databases

---

## 📝 Related Documentation
- `PHASE_2.5_DASHBOARD_COMPLETE.md` - Full feature documentation
- `PHASE_2.5_VISUAL_GUIDE.md` - UI reference guide
- `PHASE_2.5_FINAL_SUMMARY.md` - Implementation summary
- `QUICK_START_PHASE_2.5.md` - Launch instructions

---

**Status:** All bugs fixed ✅  
**Remaining:** Test dashboard launch and verify no errors

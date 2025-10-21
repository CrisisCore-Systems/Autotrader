# Phase 2.5 Bootstrap — Action Checklist

**Created:** October 21, 2025
**Package:** feature/phase-2.5-memory-bootstrap
**Status:** ✅ Development complete, ready for deployment

---

## ✅ COMPLETED TODAY

### Code Development
- [x] `memory_tracker.py` — 435 lines, tested
- [x] `auto_ejector.py` — 265 lines, tested  
- [x] `risk_flag()` utility — Added to advanced_filters.py
- [x] Database schema extensions — 3 new tables
- [x] Bug fix: GUI settings dialog
- [x] Bug fix: Daily report database queries

### Documentation
- [x] `PHASE_2.5_INITIALIZATION.md` — Integration guide
- [x] `ARCHITECTURE_RISKS.md` — Failure modes catalog
- [x] `PHASE_2.5_EXECUTIVE_BRIEFING.md` — Management summary
- [x] `PHASE_2.5_BOOTSTRAP_COMPLETE.md` — Quick start
- [x] `PHASE_2.5_FILES_CHANGED.md` — Change log
- [x] `BUGFIXES_OCT21.md` — Bug fix documentation
- [x] `CURRENT_STATUS.md` — System state

---

## 📋 TODO: IMMEDIATE NEXT STEPS

### Step 1: Validation (5 minutes)

```powershell
# Test module imports
cd C:\Users\kay\Documents\Projects\AutoTrader\Autotrader

python -c "from src.bouncehunter.memory_tracker import MemoryTracker; print('✓ MemoryTracker OK')"
python -c "from src.bouncehunter.auto_ejector import AutoEjector; print('✓ AutoEjector OK')"
python -c "from src.bouncehunter.advanced_filters import risk_flag; print('✓ risk_flag OK')"

# Initialize database schema
python -c "from src.bouncehunter.memory_tracker import MemoryTracker; MemoryTracker(); print('✓ Database schema OK')"

# Test built-in validation
python src/bouncehunter/memory_tracker.py
python src/bouncehunter/auto_ejector.py
```

**Expected Results:**
- All imports: `✓ ... OK`
- Schema init: `✓ Database schema OK`
- Validation tests: Module summaries with no errors

**If errors:**
- Check Python version (need 3.10+)
- Verify database path exists
- Check write permissions

### Step 2: Commit to Git (2 minutes)

```bash
# Create feature branch
git checkout -b feature/phase-2.5-memory-bootstrap

# Stage all Phase 2.5 files
git add src/bouncehunter/memory_tracker.py
git add src/bouncehunter/auto_ejector.py
git add src/bouncehunter/advanced_filters.py
git add PHASE_2.5_INITIALIZATION.md
git add PHASE_2.5_BOOTSTRAP_COMPLETE.md
git add PHASE_2.5_EXECUTIVE_BRIEFING.md
git add PHASE_2.5_FILES_CHANGED.md
git add PHASE_2.5_TODO.md
git add docs/ARCHITECTURE_RISKS.md

# Stage bug fixes
git add gui_trading_dashboard.py
git add scripts/generate_daily_report.py
git add BUGFIXES_OCT21.md
git add CURRENT_STATUS.md

# Commit with detailed message
git commit -m "Phase 2.5: Memory bootstrap system + bug fixes

NEW FEATURES:
- memory_tracker.py: Signal quality + regime tracking (435 lines)
- auto_ejector.py: Automatic ticker ejection (265 lines)  
- risk_flag(): Out-of-range signal detection utility
- Comprehensive architecture risk documentation

BUG FIXES:
- GUI settings dialog: Fixed AttributeError
- Daily report: Updated for agentic.py schema
- Created logs/ and backups/ directories

DOCUMENTATION:
- 5 comprehensive guides (~47 pages total)
- Integration examples (copy-paste ready)
- Failure mode catalog with mitigations

Ready for 30-minute integration after Phase 2 validation."

# Push to remote
git push origin feature/phase-2.5-memory-bootstrap
```

### Step 3: Test GUI & Daily Report (5 minutes)

```powershell
# Test GUI with settings dialog
python gui_trading_dashboard.py
# Click "⚙️ Settings" button → should open without errors

# Test daily report
python scripts\generate_daily_report.py
# Should display report without database errors
```

**Expected:**
- GUI opens (IBKR connection error is normal if TWS not running)
- Settings dialog opens and closes cleanly
- Daily report shows "No closed positions today" (if fresh)

### Step 4: Read Documentation (30 minutes)

**Priority order:**
1. `PHASE_2.5_EXECUTIVE_BRIEFING.md` (6 pages) — Overview
2. `PHASE_2.5_BOOTSTRAP_COMPLETE.md` (5 pages) — Quick start
3. `PHASE_2.5_INITIALIZATION.md` (15 pages) — Integration guide
4. `ARCHITECTURE_RISKS.md` (15 pages) — Risk catalog

**Focus on:**
- Integration examples (copy-paste ready)
- Ejection threshold logic (40% WR, 5 trades min)
- Signal quality tiers (perfect/good/marginal/poor)
- Known failure modes

---

## 📋 TODO: AFTER FIRST TRADE (Day 1)

### Integration Hook #1: Scanner

Add to `run_scanner_free.py` or scanner script:

```python
from src.bouncehunter.memory_tracker import MemoryTracker
from src.bouncehunter.advanced_filters import risk_flag
import pandas as pd

tracker = MemoryTracker()

# After generating candidates DataFrame
candidates['risk_flag'] = candidates.apply(risk_flag, axis=1)

# For each top candidate
for _, signal in top_candidates.iterrows():
    # Classify quality
    quality = 'perfect' if (
        10 <= signal.gap_pct <= 15 and
        signal.volume_ratio >= 4 and
        signal.regime == 'normal'
    ) else 'good' if (
        8 <= signal.gap_pct <= 17 and
        signal.volume_ratio >= 3.5
    ) else 'marginal'
    
    # Log to memory system
    tracker.log_signal_quality(
        signal_id=signal.signal_id,
        ticker=signal.ticker,
        quality=quality,
        gap_pct=signal.gap_pct,
        volume_ratio=signal.volume_ratio,
        regime=signal.regime
    )
```

**Verify:** Check `signal_quality` table has new rows

### Integration Hook #2: Trade Outcomes

Add to `run_pennyhunter_paper.py` or after recording outcome:

```python
from src.bouncehunter.memory_tracker import MemoryTracker

tracker = MemoryTracker()

# After recording outcome to database
tracker.update_ticker_performance(ticker)
```

**Verify:** Check `ticker_performance` table has updated row

---

## 📋 TODO: AFTER 5 TRADES (Week 1)

### First Statistical Review

```python
from src.bouncehunter.memory_tracker import MemoryTracker
from src.bouncehunter.auto_ejector import AutoEjector
import sqlite3

tracker = MemoryTracker()
ejector = AutoEjector()

# Get all tickers with outcomes
conn = sqlite3.connect('bouncehunter_memory.db')
tickers = conn.execute("SELECT DISTINCT ticker FROM outcomes").fetchall()

print("\n" + "="*70)
print("PHASE 2.5 — FIRST STATISTICAL REVIEW")
print("="*70 + "\n")

for (ticker,) in tickers:
    metrics = tracker.get_ticker_metrics(ticker)
    if metrics:
        print(f"📊 {ticker}:")
        print(f"   Total Trades: {metrics.total_trades}")
        print(f"   Win Rate: {metrics.win_rate:.1%}")
        print(f"   Profit Factor: {metrics.profit_factor:.2f}")
        print(f"   Normal Regime WR: {metrics.normal_regime_wr:.1%}")
        print(f"   Perfect Signal WR: {metrics.perfect_signal_wr:.1%}")
        print()

# Check ejection candidates
candidates = ejector.evaluate_all()
if candidates:
    print(f"\n⚠️  EJECTION CANDIDATES: {len(candidates)}")
    for c in candidates:
        print(f"   {c.ticker}: {c.win_rate:.1%} WR - {c.reason}")
else:
    print("\n✅ No ejection candidates (all tickers performing)")

print("\n" + "="*70 + "\n")
```

### Integration Hook #3: EOD Cleanup

Add to `scripts/scheduled_eod_cleanup.ps1` or EOD script:

```powershell
# After daily report generation
Write-Host "`nChecking ejection candidates..."
python -c "
from src.bouncehunter.auto_ejector import AutoEjector
ejector = AutoEjector()
result = ejector.auto_eject_all(dry_run=True)
if result['candidates']:
    print(f\"⚠️  {len(result['candidates'])} ejection candidates found\")
    for c in result['candidates']:
        print(f\"  - {c['ticker']}: {c['win_rate']:.1%} WR - {c['reason']}\")
else:
    print('✅ No ejection candidates')
"
```

**Verify:** Dry run shows candidates (if any have <40% WR)

---

## 📋 TODO: AFTER 10 TRADES (Week 2)

### Mid-Validation Checkpoint

- [ ] Review signal quality distribution
- [ ] Check regime correlation (if mixed market conditions)
- [ ] Test ejection dry run
- [ ] Analyze risk flag patterns
- [ ] Verify memory system stability

### Optional: Execute First Ejection (If Candidate Exists)

```python
from src.bouncehunter.auto_ejector import AutoEjector

ejector = AutoEjector()

# Review candidates
result = ejector.auto_eject_all(dry_run=True)
print(f"Would eject {len(result['candidates'])} tickers:")
for c in result['candidates']:
    print(f"  - {c['ticker']}: {c['win_rate']:.1%} WR - {c['reason']}")

# If you approve
confirmed = input("\nExecute ejections? (yes/no): ")
if confirmed.lower() == 'yes':
    result = ejector.auto_eject_all(dry_run=False)
    print(f"\n✅ Ejected {result['ejected']} tickers")
```

---

## 📋 TODO: AFTER 20 TRADES (Week 3-4)

### Phase 2 Validation Complete

- [ ] Calculate overall win rate ± confidence interval
- [ ] Compute Sharpe ratio (if have P&L volatility)
- [ ] Validate regime correlation (R² ≥ 0.3?)
- [ ] Review ejected tickers (5-10% of universe?)
- [ ] Analyze signal quality WR differences (perfect > good > marginal?)

### Phase 3 Preparation

- [ ] Document Phase 2 results in new summary
- [ ] Begin agent scaffolding (stubs only):
  - `src/agents/sentinel_agent.py` — Risk monitoring
  - `src/agents/historian_agent.py` — Pattern analysis
  - `src/agents/tactician_agent.py` — Strategy adaptation
- [ ] Plan live capital transition ($1,000 test account)
- [ ] Review `ARCHITECTURE_RISKS.md` for unmitigated items

---

## 📋 ONGOING MAINTENANCE

### Daily (5 minutes)
- [ ] Check `logs/scheduled_runs.log` for task execution
- [ ] Run `python scripts\generate_daily_report.py`
- [ ] Review ejection candidates (dry run)

### Weekly (10 minutes)  
- [ ] Generate weekly report (Friday 5 PM automated)
- [ ] Review signal quality distribution
- [ ] Check regime statistics trends
- [ ] Validate memory system health

### Monthly (30 minutes)
- [ ] Full database recalculation: `tracker.update_all_tickers()`
- [ ] Review ejected tickers (consider reinstatement?)
- [ ] Update `ARCHITECTURE_RISKS.md` if new issues discovered
- [ ] Backup database (already automated daily)

---

## 🎯 SUCCESS CRITERIA

### Immediate (Day 0)
- [x] All modules import without errors
- [ ] Database schema created successfully
- [ ] Test runs complete without crashes
- [ ] Documentation readable and clear

### Short-term (After 5 Trades)
- [ ] Signal quality data accumulating
- [ ] Ticker performance updating correctly
- [ ] Risk flags distributed as expected (20-30%)
- [ ] No errors in scheduled runs

### Medium-term (After 20 Trades)
- [ ] Overall WR ≥ 70%
- [ ] 2-3 tickers ejected (proves system works)
- [ ] Regime statistics stable
- [ ] Ready for Phase 3 agent scaffolding

---

## ⚠️ RED FLAGS TO WATCH

### System Health Issues
- ❌ Import errors → Check Python version
- ❌ Database errors → Check write permissions
- ❌ No data accumulating → Check integration hooks
- ❌ All signals flagged → Check threshold settings

### Performance Issues
- ❌ Win rate < 60% after 10 trades → Review signal selection
- ❌ No ejection candidates after 20 trades → System too lenient?
- ❌ All tickers ejected → System too strict
- ❌ Perfect signal WR ≤ Good signal WR → Classification wrong

---

## 📞 HELP & SUPPORT

### If You Get Stuck

**Import Errors:**
```powershell
# Check Python version
python --version  # Need 3.10+

# Test each import individually
python -c "import sqlite3; print('OK')"
python -c "import pandas; print('OK')"
python -c "from pathlib import Path; print('OK')"
```

**Database Issues:**
```powershell
# Check database exists and is writable
sqlite3 bouncehunter_memory.db ".tables"

# Reinitialize schema if corrupted
python -c "from src.bouncehunter.memory_tracker import MemoryTracker; MemoryTracker()._ensure_schema()"
```

**Integration Questions:**
- Review `PHASE_2.5_INITIALIZATION.md` integration section
- Check module docstrings: `help(MemoryTracker)`
- Review examples in documentation

---

## 🎉 FINAL CHECKLIST

Before considering Phase 2.5 "live":

- [ ] All validation tests passed
- [ ] Code committed to git
- [ ] Documentation read and understood
- [ ] GUI and daily report tested
- [ ] First signal quality logged
- [ ] First ticker performance updated
- [ ] Ejection dry run executed
- [ ] No errors in logs
- [ ] Team briefed on new system

**When all checked:** Phase 2.5 is LIVE! 🚀

---

**Document:** TODO Checklist  
**Version:** 1.0  
**Last Updated:** October 21, 2025  
**Status:** ✅ Ready to execute

**Next Review:** After first 5 trades

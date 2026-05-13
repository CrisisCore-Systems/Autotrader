# Phase 2.5 Initialization Package
## "Memory Bootstrap" — Continuous Learning Without Neural Overhead

**Created:** October 21, 2025
**Version:** 1.0
**Status:** 🟢 READY FOR INTEGRATION

---

## 🎯 Mission Statement

Phase 2.5 bridges the gap between **Phase 2 validation** (statistical proof of edge) and **Phase 3 agentic operations** (full autonomous trading). It introduces a lightweight continuous learning loop that:

- **Tracks** signal quality → outcome relationships
- **Ejects** persistently poor performers (< 40% WR)
- **Accumulates** regime-specific statistics
- **Prepares** infrastructure for Phase 3 agent recursion

**Key Principle:** Learn from every trade without adding complexity.

---

## 📦 Package Contents

### Core Modules (New)

| File | Lines | Purpose | Status |
|------|-------|---------|--------|
| `src/bouncehunter/memory_tracker.py` | ~435 | Signal quality + regime tracking | ✅ COMPLETE |
| `src/bouncehunter/auto_ejector.py` | ~265 | Automatic ticker ejection | ✅ COMPLETE |
| `src/bouncehunter/advanced_filters.py` | +40 | Risk flagging utility added | ✅ UPDATED |

### Documentation (New)

| File | Pages | Purpose | Status |
|------|-------|---------|--------|
| `docs/ARCHITECTURE_RISKS.md` | ~15 | Known failure modes & mitigations | ✅ COMPLETE |
| `PHASE_2.5_INITIALIZATION.md` | This doc | Integration guide | ✅ COMPLETE |

### Database Schema Extensions

**New Tables (auto-created by `memory_tracker.py`):**

```sql
-- Signal quality annotations
signal_quality (
    signal_id PRIMARY KEY,
    quality TEXT,  -- 'perfect', 'good', 'marginal', 'poor'
    gap_flag TEXT,
    volume_flag TEXT,
    regime_at_signal TEXT,
    vix_level REAL,
    spy_state TEXT,
    timestamp TEXT
)

-- Regime state snapshots
regime_snapshots (
    snapshot_id PRIMARY KEY,
    timestamp TEXT,
    spy_close REAL,
    spy_regime TEXT,
    vix_close REAL,
    vix_regime TEXT,
    market_state TEXT,
    notes TEXT
)

-- Enhanced ticker performance
ticker_performance (
    ticker PRIMARY KEY,
    last_updated TEXT,
    total_outcomes INTEGER,
    perfect_signal_wr REAL,
    good_signal_wr REAL,
    normal_regime_wr REAL,
    highvix_regime_wr REAL,
    avg_return REAL,
    profit_factor REAL,
    ejection_eligible INTEGER,
    ejection_reason TEXT
)
```

---

## 🚀 Integration Guide

### Step 1: Validate Installation

```powershell
# Test memory tracker
python -c "from src.bouncehunter.memory_tracker import MemoryTracker; print('✓ MemoryTracker OK')"

# Test auto-ejector
python -c "from src.bouncehunter.auto_ejector import AutoEjector; print('✓ AutoEjector OK')"

# Test risk_flag utility
python -c "from src.bouncehunter.advanced_filters import risk_flag; print('✓ risk_flag OK')"
```

**Expected:** All three print "✓ ... OK"

### Step 2: Initialize Database Schema

```python
from src.bouncehunter.memory_tracker import MemoryTracker

tracker = MemoryTracker()
# Schema auto-created on first init
print("✓ Database schema initialized")
```

### Step 3: Hook into Existing Workflow

**A. Scanner Integration (run_scanner_free.py)**

Add signal quality annotation:

```python
from src.bouncehunter.memory_tracker import MemoryTracker
from src.bouncehunter.advanced_filters import risk_flag

tracker = MemoryTracker()

# After generating signals
for signal in top_candidates:
    # Determine quality based on parameters
    quality = 'perfect' if (
        10 <= signal.gap_pct <= 15 and
        signal.volume_ratio >= 4 and
        signal.regime == 'normal'
    ) else 'good' if (
        8 <= signal.gap_pct <= 17 and
        signal.volume_ratio >= 3.5
    ) else 'marginal'
    
    # Log to memory tracker
    tracker.log_signal_quality(
        signal_id=signal.signal_id,
        ticker=signal.ticker,
        quality=quality,
        gap_pct=signal.gap_pct,
        volume_ratio=signal.volume_ratio,
        regime=signal.regime,
        vix_level=current_vix,
        spy_state=spy_regime
    )
```

**B. Trade Outcome Integration (run_pennyhunter_paper.py)**

Update ticker performance after each trade:

```python
from src.bouncehunter.memory_tracker import MemoryTracker

tracker = MemoryTracker()

# After recording outcome in database
tracker.update_ticker_performance(ticker)
```

**C. EOD Cleanup Integration (scripts/scheduled_eod_cleanup.ps1)**

Add auto-ejection check:

```python
from src.bouncehunter.auto_ejector import AutoEjector

ejector = AutoEjector(min_trades=5, wr_threshold=0.40)

# Dry run to see candidates
result = ejector.auto_eject_all(dry_run=True)

if result['candidates']:
    print(f"⚠️  {len(result['candidates'])} ejection candidates found")
    for c in result['candidates']:
        print(f"  - {c['ticker']}: {c['win_rate']:.1%} WR ({c['reason']})")
    
    # Uncomment after validating dry run results:
    # ejector.auto_eject_all(dry_run=False)
```

### Step 4: Validation (After 5 Completed Trades)

Run the first statistical review:

```python
from src.bouncehunter.memory_tracker import MemoryTracker
import sqlite3

tracker = MemoryTracker()

# Get all tickers with outcomes
conn = sqlite3.connect('bouncehunter_memory.db')
tickers = conn.execute("""
    SELECT DISTINCT ticker FROM outcomes
""").fetchall()

print(f"\n{'='*70}")
print("PHASE 2.5 VALIDATION — FIRST STATISTICAL REVIEW")
print(f"{'='*70}\n")

for (ticker,) in tickers:
    metrics = tracker.get_ticker_metrics(ticker)
    if metrics:
        print(f"📊 {ticker}:")
        print(f"   Total Trades: {metrics.total_trades}")
        print(f"   Win Rate: {metrics.win_rate:.1%}")
        print(f"   Avg Return: {metrics.avg_return:.2%}")
        print(f"   Profit Factor: {metrics.profit_factor:.2f}")
        print(f"   Normal Regime WR: {metrics.normal_regime_wr:.1%}")
        print(f"   HighVIX Regime WR: {metrics.highvix_regime_wr:.1%}")
        print(f"   Perfect Signal WR: {metrics.perfect_signal_wr:.1%}")
        print()

# Check ejection candidates
ejector = AutoEjector()
candidates = ejector.evaluate_all()

if candidates:
    print(f"\n⚠️  EJECTION CANDIDATES: {len(candidates)}")
    for c in candidates:
        print(f"   {c.ticker}: {c.win_rate:.1%} WR over {c.total_trades} trades")
        print(f"   Reason: {c.reason}")
else:
    print("\n✅ No ejection candidates (all tickers performing)")

print(f"\n{'='*70}\n")
```

---

## 📊 Usage Examples

### Example 1: Manual Signal Quality Logging

```python
from src.bouncehunter.memory_tracker import MemoryTracker

tracker = MemoryTracker()

# Log a perfect setup
tracker.log_signal_quality(
    signal_id="AAPL_2025-10-21_12345",
    ticker="AAPL",
    quality="perfect",
    gap_pct=12.5,
    volume_ratio=5.2,
    regime="normal",
    vix_level=15.3,
    spy_state="bullish"
)

print("✓ Signal quality logged")
```

### Example 2: Capture Market Regime

```python
from src.bouncehunter.memory_tracker import MemoryTracker

tracker = MemoryTracker()

# Capture regime at pre-market (7:30 AM)
snapshot_id = tracker.capture_regime_snapshot(
    spy_close=450.25,
    spy_regime="bullish",
    vix_close=15.8,
    vix_regime="low",
    market_state="pre_market",
    notes="Typical low-vol environment"
)

print(f"✓ Regime snapshot captured: {snapshot_id}")
```

### Example 3: Check Ticker Performance

```python
from src.bouncehunter.memory_tracker import MemoryTracker

tracker = MemoryTracker()

metrics = tracker.get_ticker_metrics("TSLA")

if metrics:
    print(f"TSLA Performance:")
    print(f"  Win Rate: {metrics.win_rate:.1%}")
    print(f"  Avg Return: {metrics.avg_return:.2%}")
    print(f"  Normal Regime WR: {metrics.normal_regime_wr:.1%}")
else:
    print("No data for TSLA yet")
```

### Example 4: Auto-Eject Poor Performers

```python
from src.bouncehunter.auto_ejector import AutoEjector

ejector = AutoEjector(min_trades=5, wr_threshold=0.40)

# Dry run first
result = ejector.auto_eject_all(dry_run=True)
print(f"Would eject {len(result['candidates'])} tickers")

# Execute if you approve
if len(result['candidates']) > 0:
    confirmed = input("Execute ejections? (yes/no): ")
    if confirmed.lower() == 'yes':
        result = ejector.auto_eject_all(dry_run=False)
        print(f"✓ Ejected {result['ejected']} tickers")
```

### Example 5: Reinstate Ejected Ticker

```python
from src.bouncehunter.auto_ejector import AutoEjector

ejector = AutoEjector()

# Reinstate if ticker improves or manual override
success = ejector.reinstate_ticker("AAPL")

if success:
    print("✓ AAPL reinstated to active trading")
else:
    print("❌ AAPL not found in ejection list")
```

---

## 🎓 Best Practices

### Signal Quality Classification

**Perfect Signal:** All criteria in optimal range
- Gap: 10-15%
- Volume ratio: ≥4x
- Regime: normal
- No risk flags

**Good Signal:** Most criteria good, minor deviation
- Gap: 8-17%
- Volume ratio: ≥3.5x
- Any regime
- Maximum 1 risk flag

**Marginal Signal:** Acceptable but suboptimal
- Gap: 6-20%
- Volume ratio: ≥3x
- Any regime
- Multiple risk flags OK

**Poor Signal:** Outside safe parameters
- Gap: <6% or >20%
- Volume ratio: <3x
- Do not trade these

### Ejection Decision Tree

```
Ticker has ≥5 completed trades?
├─ No → Keep monitoring
└─ Yes → Check win rate
    ├─ WR ≥ 40% → Keep active
    └─ WR < 40% → Check regimes
        ├─ Both regimes < 35% → EJECT (fundamental issue)
        ├─ One regime < 35% → Mark as regime-specific only
        └─ Profit factor < 0.5 → EJECT (bad risk/reward)
```

### Memory System Maintenance

**Daily:**
- Update ticker performance after each trade
- Check ejection candidates (dry run)

**Weekly:**
- Review ejected tickers list
- Consider reinstatement if market conditions changed
- Analyze regime correlation (normal vs highvix WR)

**Monthly:**
- Full database recalculation: `tracker.update_all_tickers()`
- Review risk flags distribution
- Validate signal quality classifications

---

## ⚠️ Important Warnings

### DO NOT:
1. **Eject after < 5 trades** — sample size too small, random variance
2. **Ignore risk flags** — they exist for a reason, heed warnings
3. **Reinstate frequently** — ejection should be deliberate, not yo-yo
4. **Skip daily updates** — stale statistics = poor decisions

### DO:
1. **Run dry runs first** — always preview ejections before executing
2. **Log perfect setups** — these are your alpha, study them
3. **Monitor regime transitions** — performance differs by environment
4. **Review weekly** — 5-10 minutes keeps system healthy

---

## 📈 Success Metrics (Phase 2.5)

### Primary Goals (Next 14 Days)

| Metric | Target | Status |
|--------|--------|--------|
| Total completed trades | ≥20 | ⏳ 0/20 |
| Overall win rate | ≥70% | ⏳ TBD |
| Perfect signal WR | ≥75% | ⏳ TBD |
| Ejected tickers | 5-10% of universe | ⏳ 0 |
| Memory system uptime | 100% | 🟢 Ready |

### Secondary Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Regime correlation | R² ≥ 0.3 | After 15 trades |
| Signal quality distribution | 40% perfect, 40% good, 20% marginal | Ongoing |
| Average return per trade | ≥2% | Rolling 10-trade window |
| Profit factor | ≥2.0 | After 20 trades |

---

## 🛠️ Troubleshooting

### Issue: "No such table: signal_quality"

**Cause:** Database schema not initialized
**Fix:**
```python
from src.bouncehunter.memory_tracker import MemoryTracker
tracker = MemoryTracker()  # Auto-creates tables
```

### Issue: "Ejector finds no candidates but I know ticker is failing"

**Cause:** Not enough trades yet (< 5 required)
**Check:**
```python
import sqlite3
conn = sqlite3.connect('bouncehunter_memory.db')
count = conn.execute("SELECT COUNT(*) FROM outcomes WHERE ticker = ?", ('AAPL',)).fetchone()[0]
print(f"AAPL has {count} outcomes (need ≥5)")
```

### Issue: "Memory tracker update is slow"

**Cause:** Large outcome table, no indexes
**Fix:** Already built in — schema includes indexes on key columns

### Issue: "Risk flags showing on all signals"

**Cause:** Gap or volume thresholds too strict for current market
**Options:**
1. Wait for more volatile market conditions
2. Expand ticker universe (more candidates)
3. Slightly relax thresholds (TEST FIRST in backtest)

---

## 🔄 Integration Workflow Diagram

```
┌─────────────────────────────────────────────────────────┐
│              PHASE 2.5 CONTINUOUS LEARNING              │
└─────────────────────────────────────────────────────────┘

7:30 AM - Pre-Market Scan
│
├─ Scanner generates gap candidates
│  └─> Memory Tracker: log_signal_quality()
│      ├─ Classify: perfect/good/marginal
│      ├─ Flag risks: gap range, volume
│      └─ Capture regime snapshot
│
9:35 AM - Market Entry
│
├─ Agentic system selects best signals
│  └─> Check ejected tickers (skip if ejected)
│      └─> Place orders
│
4:15 PM - EOD Cleanup
│
├─ Close positions / record outcomes
│  └─> Memory Tracker: update_ticker_performance()
│      ├─ Recalculate WR, profit factor
│      ├─ Update regime statistics
│      └─ Mark ejection candidates
│
├─ Auto Ejector: evaluate_all()
│  └─> Dry run: review candidates
│      └─> Execute: eject if approved
│
Weekly (Friday 5 PM)
│
└─ Generate comprehensive report
   ├─ Signal quality distribution
   ├─ Regime correlation analysis
   ├─ Ejection effectiveness
   └─ Phase 2 validation progress
```

---

## 📋 Pre-Phase 3 Checklist

Before moving to full agentic operations, verify:

- [ ] Memory tracker running daily without errors
- [ ] All outcomes have signal quality annotations
- [ ] Ejection system tested (dry run → execute → reinstate)
- [ ] At least 3 tickers tracked with ≥5 trades each
- [ ] Regime statistics show meaningful correlation (R² ≥ 0.3)
- [ ] Risk flags documented and understood
- [ ] Database backup strategy in place
- [ ] All failure modes from ARCHITECTURE_RISKS.md mitigated
- [ ] Ready for agent recursion (feedback loops)

---

## 🚀 Next Steps After Phase 2.5

Once you hit **20 completed trades** with **70%+ WR**:

### Phase 2.5 → Phase 3 Transition

1. **Statistical Validation**
   - Calculate confidence intervals
   - Compute Sharpe ratio (return/volatility)
   - Validate against null hypothesis (p < 0.05)

2. **Agent Scaffolding** (stub only, no logic)
   - `sentinel_agent.py` — monitors risk, halts if needed
   - `historian_agent.py` — analyzes past trades, spots patterns
   - `tactician_agent.py` — adapts strategy to regime

3. **Live Capital Preparation**
   - Switch from paper → small live account ($1,000)
   - Run parallel (paper + live) for 1 week
   - Validate fill quality, slippage, broker behavior

4. **Full Phase 3 Launch**
   - Enable agent recursion
   - Implement dynamic strategy adaptation
   - Scale capital gradually (10% increase per week if WR maintained)

---

## 📞 Support & Questions

**Integration Issues:**
- Check `docs/ARCHITECTURE_RISKS.md` for known issues
- Validate database schema: `sqlite3 bouncehunter_memory.db ".schema"`
- Review logs: `logs/scheduled_runs.log`

**Performance Questions:**
- Review metrics after 5 trades (first checkpoint)
- Compare to Phase 2 backtest (70% WR baseline)
- Analyze regime-specific performance

**Feature Requests:**
- Document in GitHub issues with `[Phase 2.5]` tag
- Test in isolated branch before merging
- Validate doesn't break existing workflows

---

**Package Version:** 1.0
**Last Updated:** October 21, 2025
**Status:** ✅ Initialization snapshot complete
**Integration Time:** ~30 minutes
**Maintenance:** 5 minutes/day

---

## 🎉 Conclusion

Phase 2.5 gives you **continuous learning without complexity**. Every trade teaches the system something new, poor performers get ejected automatically, and you build towards Phase 3 agent intelligence organically.

**Start small:** Log signal quality for 5 trades, see how it works.
**Scale gradually:** Add auto-ejection after you're comfortable.
**Build momentum:** By trade 20, you'll have a robust memory system ready for agent recursion.

Let's build! 🚀

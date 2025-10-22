# PennyHunter Phase 2 Validation Plan

**Status**: 🟢 IN PROGRESS  
**Goal**: Accumulate 20+ paper trades to validate 65-75% win rate improvement  
**Current Progress**: 2/20 trades (10%)

---

## Overview

This document outlines the phased approach to making PennyHunter agentic, starting with Phase 2 validation.

### Phased Roadmap

| Phase | Description | Win Rate Target | Effort | Status |
|-------|-------------|-----------------|--------|--------|
| **Phase 2** | Market Regime + Signal Scoring + Advanced Filters | 65-75% | ✅ Complete | 🟢 Validating |
| **Phase 2.5** | Lightweight agentic memory (auto-eject bad tickers) | 70-80% | 1-2 days | ⏳ Waiting for data |
| **Phase 3** | Full agentic system (adaptive thresholds, portfolio AI) | 75-85% | 3-5 days | ⏳ After 50+ trades |

---

## Phase 2: Current Validation (IN PROGRESS)

### Objective
Accumulate 20+ paper trades to establish statistical confidence that Phase 2 improvements (market regime detection + signal scoring + advanced risk filters) deliver 65-75% win rate.

### Implementation Status
✅ **Complete**:
- Market regime detector (blocks trading when SPY < 200MA or VIX > 30)
- Signal scoring system (0-10 points, min 5.5 threshold temporarily)
- Advanced risk filters (5 modules):
  - Dynamic liquidity delta (-30% threshold)
  - Effective slippage estimation (5% max)
  - Cash runway filter (6+ months)
  - Sector diversification (max 3 per sector)
  - Volume fade detection (<50% threshold)
- Paper trading integration with quality gates
- Trade accumulation system

### Daily Workflow

**Step 1: Run Daily Scanner**
```bash
cd C:/Users/kay/Documents/Projects/AutoTrader/Autotrader
python scripts/daily_pennyhunter.py --tickers INTR,ADT,SAN,COMP,CLOV,EVGO
```

This will:
- Load cumulative trade history
- Execute paper trading with quality gates
- Merge results into cumulative history
- Show progress toward 20-trade goal

**Step 2: Monitor Progress**
```bash
python scripts/analyze_pennyhunter_results.py
```

This will:
- Calculate current win rate
- Compare vs baseline (45-55%) and targets (65-75%)
- Identify best/worst performing tickers
- Show statistical significance status

### Timeline
- **Target**: 2-3 weeks of daily trading
- **Current**: Day 1 (2 trades)
- **Next Milestone**: 20 completed trades

### Success Criteria
- [ ] Accumulate 20+ completed trades (n=20 for statistical significance)
- [ ] Win rate ≥ 65% (lower bound of Phase 2 target)
- [ ] Profit factor ≥ 1.5
- [ ] Max drawdown < 15%
- [ ] Avg R-multiple ≥ 1.5R

### Risks & Mitigation
- **Risk**: Insufficient market opportunities (low gap activity)
  - *Mitigation*: Using under-$10 stocks (broader universe than pure pennies)
  - *Mitigation*: 90-day lookback to find historical gaps for testing

- **Risk**: Active positions take time to close
  - *Mitigation*: Track both completed and active trades separately
  - *Mitigation*: Analysis focuses on completed trades only

- **Risk**: Win rate below 65% target
  - *Mitigation*: Review quality gate settings
  - *Mitigation*: Analyze losing trades for patterns
  - *Mitigation*: Consider tightening advanced filter thresholds

---

## Phase 2.5: Lightweight Agentic Memory (PLANNED)

### Objective
Add ticker-level learning without full multi-agent complexity. Auto-eject underperforming tickers based on historical win rates.

### Implementation Plan (~200 lines)

**File**: `src/bouncehunter/pennyhunter_memory.py`

```python
class PennyHunterMemory:
    """Lightweight outcome tracking for PennyHunter"""
    
    def __init__(self, db_path="data/pennyhunter.db"):
        # SQLite schema: signals, fills, outcomes, ticker_stats
        self._init_schema()
    
    def record_outcome(self, ticker, entry, exit, reason):
        # Store trade outcome
        # Update ticker stats
        self.update_ticker_stats(ticker)
    
    def get_ticker_quality(self, ticker) -> float:
        # Return base rate (% of trades that hit target)
        stats = self.get_ticker_stats(ticker)
        return stats['base_rate'] if stats else 0.5
    
    def should_trade_ticker(self, ticker) -> bool:
        # Auto-eject if base rate < 40% after 10+ trades
        stats = self.get_ticker_stats(ticker)
        if stats and stats['total_outcomes'] >= 10:
            return stats['base_rate'] >= 0.40
        return True
```

**Integration** into `run_pennyhunter_paper.py`:
```python
# In __init__:
self.memory = PennyHunterMemory()

# Before executing signal:
if not self.memory.should_trade_ticker(ticker):
    logger.info(f"❌ {ticker} auto-ejected (historical win rate < 40%)")
    continue

# After trade closes:
self.memory.record_outcome(ticker, entry, exit, reason)
```

### Expected Benefits
- ✅ Automatic ticker quality learning
- ✅ Auto-eject bad performers (< 40% win rate)
- ✅ Minimal code changes (~200 lines)
- ✅ Foundation for full agentic system
- 🎯 **Expected Win Rate**: 70-80% (vs 65-75% Phase 2)

### Prerequisites
- ✅ 20+ Phase 2 trades for baseline
- ✅ Clean data structure from cumulative history
- ✅ Validated that Phase 2 filters work

### Timeline
- Start: After Phase 2 validation complete (20+ trades)
- Duration: 1-2 days implementation
- Validation: 10-20 more trades with memory enabled

---

## Phase 3: Full Agentic System (FUTURE)

### Objective
Implement complete multi-agent orchestration with adaptive learning, similar to BounceHunter's agentic architecture.

### Agent Architecture

**Agents** (7 total):
1. **Sentinel**: Monitors market regime, triggers scans
2. **Screener**: Generates candidate signals
3. **Forecaster**: Scores signals with adaptive thresholds
4. **RiskOfficer**: Enforces portfolio limits, sector caps
5. **NewsSentry**: Vetos trades on adverse headlines
6. **Trader**: Executes trades via broker
7. **Historian**: Persists outcomes to database
8. **Auditor**: Analyzes outcomes, updates thresholds

**Orchestrator**: Coordinates agent execution flow

### Key Features

**1. Adaptive Thresholds**
```python
# Auditor automatically adjusts based on outcomes
if ticker_base_rate < 40% after 20 trades:
    → Increase min_score from 7.0 to 8.0
    
if ticker_base_rate > 75% after 20 trades:
    → Lower min_score to 6.0
```

**2. Regime-Specific Learning**
```python
# Track performance by market regime
if highvix_regime_rate < 50%:
    → Increase BCS threshold from 0.62 to 0.70
    → Reduce position size from 2.5% to 1.2%
```

**3. Portfolio Intelligence**
```python
# RiskOfficer dynamic management
if open_positions >= 8:
    → Veto all new signals
    
if recent trades have 2 consecutive losses:
    → Reduce size from $5 to $3 risk per trade
```

**4. Automated Backtesting**
```python
# Historian records both taken AND vetoed signals
# Auditor compares outcomes to identify filter bias
# Auto-tune filters to minimize total error rate
```

### Implementation Effort
- **Complexity**: High (500+ lines)
- **Duration**: 3-5 days
- **Dependencies**: Phase 2.5 memory layer, solid trade data (50+ trades)

### Expected Benefits
- 🎯 **Win Rate**: 75-85%
- 🤖 Self-optimizing system
- 📊 Regime-specific adaptation
- 🎓 Continuous learning from outcomes
- 🚫 Automatic underperformer ejection
- 📈 Portfolio-level intelligence

### Prerequisites
- ✅ Phase 2 validated (20+ trades, 65%+ win rate)
- ✅ Phase 2.5 memory system working (10+ trades)
- ✅ 50+ total trades accumulated
- ✅ Validated that memory improves win rate by 5-10%

### Timeline
- Start: After Phase 2.5 validation (50+ total trades)
- Duration: 3-5 days implementation
- Validation: 20+ trades with full agentic system

---

## Comparison: Phase 2 vs 2.5 vs 3

| Feature | Phase 2 (Current) | Phase 2.5 (Planned) | Phase 3 (Future) |
|---------|-------------------|---------------------|------------------|
| **Architecture** | Sequential pipeline | Sequential + memory | Multi-agent orchestration |
| **Thresholds** | Static (5.5 or 7.0) | Static | **Adaptive** |
| **Ticker Memory** | None | ✅ Auto-eject <40% | ✅ + Base rate tracking |
| **Learning** | Manual analysis | Ticker-level only | **System-wide + regime-specific** |
| **Risk Management** | Pre-execution gates | Gates + auto-eject | **Dynamic portfolio intelligence** |
| **Effort** | ✅ Done | 1-2 days | 3-5 days |
| **Win Rate Target** | 65-75% | 70-80% | 75-85% |

---

## Current Action Items

### Immediate (This Week)
- [x] Set up daily automation scripts ✅
- [x] Create cumulative history tracking ✅
- [x] Create analysis dashboard ✅
- [ ] Run daily paper trading for 2-3 weeks
- [ ] Accumulate 20+ completed trades
- [ ] Validate 65-75% win rate

### Next Week (After 20+ Trades)
- [ ] Run comprehensive analysis
- [ ] Validate Phase 2 improvements
- [ ] Implement Phase 2.5 lightweight memory (~200 lines)
- [ ] Integrate memory into paper trader
- [ ] Test auto-ejection feature

### Future (After 50+ Trades)
- [ ] Design full agentic architecture
- [ ] Implement 8-agent system (~500+ lines)
- [ ] Add adaptive thresholds
- [ ] Add regime-specific learning
- [ ] Validate 75-85% win rate target

---

## Files & Commands Reference

### Daily Operations

**Run Paper Trading:**
```bash
cd C:/Users/kay/Documents/Projects/AutoTrader/Autotrader
python scripts/daily_pennyhunter.py
```

**Analyze Results:**
```bash
python scripts/analyze_pennyhunter_results.py
python scripts/analyze_pennyhunter_results.py --export-csv
```

### Key Files

**Automation:**
- `scripts/daily_pennyhunter.py` - Daily runner with accumulation
- `scripts/analyze_pennyhunter_results.py` - Analysis dashboard

**Core System:**
- `run_pennyhunter_paper.py` - Paper trading orchestrator (410 lines)
- `src/bouncehunter/advanced_filters.py` - Risk filters (460 lines)
- `src/bouncehunter/market_regime.py` - Market regime detector (270 lines)
- `src/bouncehunter/signal_scoring.py` - Signal scoring engine (310 lines)

**Data:**
- `reports/pennyhunter_paper_trades.json` - Daily results
- `reports/pennyhunter_cumulative_history.json` - All-time accumulated trades
- `reports/pennyhunter_trades_export.csv` - CSV export for external analysis

**Configuration:**
- `configs/pennyhunter.yaml` - Complete system configuration

---

## Success Metrics

### Phase 2 (Current)
- **Milestone**: 20 completed trades
- **Target**: 65-75% win rate
- **Confidence**: Statistical significance with n=20

### Phase 2.5 (Next Week)
- **Milestone**: Memory system operational
- **Target**: 70-80% win rate (5-10% improvement)
- **Validation**: 10-20 trades with auto-ejection enabled

### Phase 3 (Future)
- **Milestone**: Full agentic system live
- **Target**: 75-85% win rate (10-15% improvement over Phase 2)
- **Validation**: 20+ trades with adaptive thresholds

---

## Decision Points

### After 20 Trades

**IF** win rate ≥ 65%:
- ✅ Proceed to Phase 2.5 (lightweight memory)
- 🎯 Expected timeline: 1-2 days implementation

**IF** win rate 55-65%:
- ⚠️ Review quality gates (may be too lenient)
- 🔧 Tighten advanced filter thresholds
- 🔄 Collect 10 more trades before Phase 2.5

**IF** win rate < 55%:
- ❌ Phase 2 validation failed
- 🛠️ Debug losing trades
- 🔍 Identify systematic issues
- ⏸️ Pause Phase 2.5 until fixed

### After Phase 2.5 (30-40 Total Trades)

**IF** win rate improved 5-10%:
- ✅ Memory system validated
- 🎯 Proceed to Phase 3 design after 50+ trades

**IF** win rate unchanged:
- ⚠️ Review auto-ejection logic
- 🔧 Adjust 40% threshold
- 🔄 Collect more data

---

## Conclusion

**Current Status**: Phase 2 validation in progress (2/20 trades)

**Recommendation**: Continue daily paper trading for 2-3 weeks to accumulate data. Once 20+ trades completed and 65%+ win rate validated, proceed to Phase 2.5 lightweight memory implementation.

**Timeline Summary**:
- **Week 1-3**: Phase 2 validation (daily trading)
- **Week 4**: Phase 2.5 implementation (1-2 days)
- **Week 5-7**: Phase 2.5 validation (daily trading)
- **Week 8+**: Phase 3 design & implementation (after 50+ trades)

**Next Command**: `python scripts/daily_pennyhunter.py`

# PennyHunter Agentic Roadmap - Quick Reference

## 📊 Current Status: Phase 2 Validation (2/20 trades)

---

## 🚀 Daily Workflow

### **Step 1: Run Paper Trading**
```bash
cd C:/Users/kay/Documents/Projects/AutoTrader/Autotrader
python scripts/daily_pennyhunter.py
```

### **Step 2: Check Progress**
```bash
python scripts/analyze_pennyhunter_results.py
```

**Repeat daily for 2-3 weeks until 20+ trades accumulated**

---

## 🎯 Three-Phase Plan

| Phase | Status | Win Rate | Timeline | Effort |
|-------|--------|----------|----------|--------|
| **Phase 2** | 🟢 In Progress | 65-75% | 2-3 weeks | ✅ Done |
| **Phase 2.5** | ⏳ Next Week | 70-80% | After 20 trades | 1-2 days |
| **Phase 3** | ⏳ Future | 75-85% | After 50 trades | 3-5 days |

---

## 📁 Key Files Created

### Automation Scripts
- ✅ `scripts/daily_pennyhunter.py` - Daily runner (271 lines)
- ✅ `scripts/analyze_pennyhunter_results.py` - Analysis dashboard (442 lines)

### Documentation
- ✅ `PHASE2_VALIDATION_PLAN.md` - Complete roadmap
- ✅ `SYSTEM_READY.md` - Production checklist
- ✅ `ADVANCED_FILTERS_COMPLETE.md` - Filter implementation guide

### Data Files (Auto-generated)
- `reports/pennyhunter_cumulative_history.json` - All accumulated trades
- `reports/pennyhunter_paper_trades.json` - Latest session results
- `reports/pennyhunter_trades_export.csv` - CSV export for analysis

---

## 🎓 What Each Phase Does

### Phase 2 (Current)
**Components:**
- Market regime detection (blocks bad market conditions)
- Signal scoring (0-10 point quality system)
- 5 advanced risk filters (liquidity, slippage, cash runway, sector, volume fade)

**Goal:** Validate 65-75% win rate with 20+ trades

**Status:** Infrastructure complete, collecting data (2/20 trades)

---

### Phase 2.5 (Next Week)
**New Component:**
- Lightweight agentic memory with SQLite

**Key Feature:** Auto-eject bad tickers
```python
if ticker_win_rate < 40% after 10 trades:
    → Never trade this ticker again (automatic)
```

**Goal:** Improve win rate to 70-80% via ticker learning

**Timeline:** Implement after Phase 2 validated (20+ trades collected)

---

### Phase 3 (Future)
**New Components:**
- 8-agent orchestration system
- Adaptive thresholds (auto-adjust based on outcomes)
- Regime-specific learning (normal vs high VIX)
- Portfolio intelligence (dynamic risk management)

**Key Features:**
```python
# Adaptive scoring
if ticker_base_rate > 75%:
    → Lower min_score to capture more opportunities
    
# Regime adaptation  
if high_VIX_win_rate < 50%:
    → Increase threshold during volatile markets
    
# Portfolio management
if 2 consecutive losses:
    → Reduce position size automatically
```

**Goal:** 75-85% win rate with fully autonomous system

**Timeline:** Implement after 50+ total trades accumulated

---

## 📈 Expected Win Rate Progression

```
Baseline (No enhancements):           45-55%
Phase 1 (Regime + Scoring):          55-65%  ✅ Complete
Phase 2 (+ Advanced Filters):        65-75%  🟢 Validating (current)
Phase 2.5 (+ Ticker Memory):         70-80%  ⏳ Next week
Phase 3 (Full Agentic):              75-85%  ⏳ After 50+ trades
```

---

## ⚡ Quick Commands

**Run daily trading:**
```bash
python scripts/daily_pennyhunter.py
```

**Analyze results:**
```bash
python scripts/analyze_pennyhunter_results.py
```

**Export to CSV:**
```bash
python scripts/analyze_pennyhunter_results.py --export-csv
```

**Check specific tickers:**
```bash
python scripts/daily_pennyhunter.py --tickers INTR,ADT,SAN
```

---

## 🎯 Success Milestones

### Milestone 1: Phase 2 Validation ⏳
- [ ] 20 completed trades
- [ ] 65%+ win rate
- [ ] Statistical significance confirmed
- **ETA:** 2-3 weeks

### Milestone 2: Phase 2.5 Implementation ⏳
- [ ] Memory system built (200 lines)
- [ ] Auto-ejection working
- [ ] 10+ trades with memory
- [ ] 70%+ win rate validated
- **ETA:** Week 4-5

### Milestone 3: Phase 3 Full Agentic ⏳
- [ ] 8-agent system built (500+ lines)
- [ ] Adaptive thresholds operational
- [ ] 20+ trades with full system
- [ ] 75%+ win rate validated
- **ETA:** Week 8+

---

## 🔍 Decision Tree

```
[20 trades accumulated]
    |
    ├─ Win rate ≥ 65%? YES → ✅ Proceed to Phase 2.5
    |                   NO  → ⚠️ Review & debug
    |
[Phase 2.5 implemented]
    |
    ├─ Win rate improved 5-10%? YES → ✅ Continue to 50 trades
    |                           NO  → ⚠️ Adjust thresholds
    |
[50+ total trades]
    |
    └─ Phase 2.5 validated? YES → ✅ Build Phase 3
                            NO  → ⚠️ More validation needed
```

---

## 💡 Why This Approach?

### Phase 2.5 First (Not Phase 3)
- ✅ 80% of benefits with 20% of complexity
- ✅ Quick to implement (1-2 days vs 3-5 days)
- ✅ Provides clean data for Phase 3 design
- ✅ Lower risk (simpler to debug)

### Memory Before Multi-Agent
- ✅ Ticker learning is the highest-value feature
- ✅ Foundation for full agentic system
- ✅ Validates SQLite persistence layer
- ✅ Tests auto-ejection logic in isolation

### 50 Trades Before Full Agentic
- ✅ Need solid baseline for adaptive thresholds
- ✅ Regime-specific learning requires diverse conditions
- ✅ More data = better agent training
- ✅ Validates that simpler approach (Phase 2.5) isn't sufficient

---

## 📋 Current TODO Summary

### This Week
- [x] Build automation scripts ✅
- [x] Build analysis dashboard ✅
- [x] Create documentation ✅
- [ ] Run daily for 2-3 weeks (in progress: 2/20 trades)

### Next Week (After 20 trades)
- [ ] Validate Phase 2 (analyze results)
- [ ] Implement Phase 2.5 memory (~200 lines)
- [ ] Test auto-ejection feature
- [ ] Run 10-20 more trades

### Future (After 50 trades)
- [ ] Design Phase 3 architecture
- [ ] Implement 8-agent system (~500 lines)
- [ ] Validate 75-85% win rate

---

## 🎉 What's Been Accomplished

### Infrastructure Complete
- ✅ Advanced risk filters (5 modules, 460 lines)
- ✅ Paper trading system with quality gates (410 lines)
- ✅ Daily automation script (271 lines)
- ✅ Analysis dashboard (442 lines)
- ✅ Cumulative history tracking (JSON)
- ✅ Progress monitoring (visual bars, stats)

### System Validated
- ✅ Market regime detection working (NEUTRAL status)
- ✅ Signal scoring working (INTR 6.0/10.0)
- ✅ Quality gates working (CLOV rejected, INTR approved)
- ✅ Paper trading functional (trades executed)
- ✅ Accumulation working (2 trades logged)

### Ready For
- 🎯 Daily paper trading (2-3 weeks)
- 🎯 Data collection (18 more trades needed)
- 🎯 Phase 2 validation (65-75% win rate)

---

## 🆘 Troubleshooting

**Q: Daily script fails?**
```bash
# Check you're in the right directory
cd C:/Users/kay/Documents/Projects/AutoTrader/Autotrader

# Verify Python environment
python --version  # Should be 3.13

# Test with small ticker set
python scripts/daily_pennyhunter.py --tickers INTR,ADT
```

**Q: No signals found?**
- Market may have no gaps today (normal)
- Try expanding ticker list: `--tickers INTR,ADT,SAN,COMP,CLOV,EVGO`
- Check if tickers passed universe filters (see log output)

**Q: Analysis shows 0% win rate?**
- Normal if trades haven't closed yet (active positions)
- Analysis only counts completed trades
- Wait for target/stop hits to complete

**Q: When to move to Phase 2.5?**
- After 20+ **completed** trades (not active)
- After win rate ≥ 65% validated
- See analysis dashboard for readiness

---

## 📞 Next Steps

1. **Today**: Continue running `python scripts/daily_pennyhunter.py` 
2. **Daily**: Check progress with `python scripts/analyze_pennyhunter_results.py`
3. **After 20 trades**: Review analysis and proceed to Phase 2.5
4. **Next week**: Implement lightweight agentic memory
5. **Future**: Plan Phase 3 after 50+ total trades

**Current Command**: `python scripts/daily_pennyhunter.py`

---

*Last Updated: October 18, 2025*  
*Phase: 2 (Validation)*  
*Progress: 2/20 trades (10%)*  
*Next Milestone: 18 more trades needed*

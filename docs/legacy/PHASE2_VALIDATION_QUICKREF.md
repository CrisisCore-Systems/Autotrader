# Phase 2 Validation - Quick Reference

**Status:** 🟢 ACTIVE (1/20 trades)  
**Started:** 2025-10-20  
**Goal:** 70% win rate on 20 new trades

---

## Daily Workflow (30 seconds)

### Single Command:
```powershell
python scripts/daily_validation.py
```

This runs:
1. Daily paper trading
2. Validation status check

---

## Current Progress

- **Trades Completed:** 0/20
- **Trades Active:** 1 (INTR)
- **Win Rate:** TBD (need 5 completed)

### Active Positions
- **INTR:** 13 shares @ $7.46 (Gap 12.6%, Vol 4.2x ✅)

---

## Milestones

| Trades | Target WR | Status |
|--------|-----------|--------|
| 5 | 60%+ (3+ wins) | ⏳ 0/5 |
| 10 | 70%+ (7+ wins) | ⏳ 0/10 |
| 20 | 70%+ (14+ wins) | ⏳ 0/20 |

**Phase 2.5 Approved** when 20 trades @ 70%+ WR ✅

---

## Quick Commands

```powershell
# Full workflow (recommended)
python scripts/daily_validation.py

# Just check status (no trading)
python scripts/check_validation_status.py

# Manual trading only
python scripts/daily_pennyhunter.py
```

---

## What's Next

### After 5 Completed Trades:
- Check if 60%+ win rate
- ✅ Continue if passing
- ⚠️ Review if failing

### After 20 Completed Trades:
- Check if 70%+ win rate (14+ wins)
- ✅ Proceed to Phase 2.5 if passing
- 📊 Re-analyze if failing

---

## Files to Monitor

- **PHASE2_VALIDATION_TRACKER.md** - Manual trade log
- **reports/pennyhunter_paper_trades.json** - Today's trades
- **reports/pennyhunter_cumulative_history.json** - All historical

---

## Troubleshooting

### If win rate drops below 60% after 10+ trades:
1. Run: `python scripts/analyze_losing_trades.py`
2. Check market regime (VIX > 30?)
3. Review if gap/volume ranges still optimal

### If signal frequency too low (<2/day):
1. Check filter logs in paper trading output
2. Consider slight gap range expansion (9-16%?)
3. Add more liquid penny stocks to universe

---

**Last Updated:** 2025-10-20  
**Next Review:** After 5 completed trades (~1-2 weeks)

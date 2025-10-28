# 🎨 Phase 2.5 Dashboard - Visual Guide

## 🚀 Launch Command
```powershell
python gui_trading_dashboard.py
```

---

## 📊 New Memory System Panel (Right Column)

```
┌─────────────────────────────────────────────────────────┐
│ 🧠 Memory System (Phase 2.5)                            │
├─────────────────────────────────────────────────────────┤
│                                                          │
│ ┌──────── 📊 Signal Quality Distribution ───────────┐  │
│ │  ⭐ Perfect  │ ✓ Good   │ ⚠ Marginal │ ✗ Poor    │  │
│ │     12       │    24    │     8      │     3     │  │
│ │  75.0% WR    │ 65.2% WR │  55.0% WR  │ 33.3% WR  │  │
│ └─────────────────────────────────────────────────────┘  │
│                                                          │
│ ┌──────────── 🏆 Top/Bottom Performers ─────────────┐  │
│ │ Ticker │ Trades │ WR%   │ Avg Ret │ Status       │  │
│ │────────────────────────────────────────────────────│  │
│ │ AAPL   │   12   │ 83.3% │ +5.2%   │ ✅ Strong    │  │
│ │ TSLA   │   8    │ 75.0% │ +4.8%   │ ✅ Strong    │  │
│ │ NVDA   │   10   │ 60.0% │ +2.1%   │ 📊 Active    │  │
│ │ AMD    │   7    │ 42.9% │ -0.5%   │ ⚠️ At Risk   │  │
│ │ GME    │   5    │ 20.0% │ -3.5%   │ 🚫 Ejected   │  │
│ └─────────────────────────────────────────────────────┘  │
│                                                          │
│ ┌──────────────── ⚡ Auto-Ejector ──────────────────┐  │
│ │ Candidates: 2   Ejected: 1   [✓] Dry Run        │  │
│ │                                 [🔍 Evaluate]     │  │
│ │──────────────────────────────────────────────────│  │
│ │ ⚠️ Found 2 ejection candidate(s):                │  │
│ │                                                   │  │
│ │ 1. GME: ⚠️ WOULD EJECT                           │  │
│ │    Win Rate: 20.0% (5 trades)                    │  │
│ │    Reason: Win rate < 40% threshold              │  │
│ │                                                   │  │
│ │ 💡 Dry Run Mode: No changes made.                │  │
│ └─────────────────────────────────────────────────────┘  │
│                                                          │
│ ┌────────────── 🌡️ Regime Correlation ─────────────┐  │
│ │  🟢 RISK ON      │  🔴 HIGH VIX                   │  │
│ │     68.5%        │     45.2%                      │  │
│ │   37 trades      │   15 trades                    │  │
│ └─────────────────────────────────────────────────────┘  │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

---

## 🎯 Key Features at a Glance

### Signal Quality (Top Section)
**What it shows:** How many signals in each quality tier  
**Color coding:**
- 🟢 Green = Perfect (75%+ WR expected)
- 🔵 Blue = Good (65-70% WR expected)
- 🟡 Yellow = Marginal (55-60% WR expected)
- 🔴 Red = Poor (<50% WR expected)

**Use case:** "Are my 'Perfect' signals really winning more?"

---

### Ticker Performance (Middle Section)
**What it shows:** Top 10 tickers ranked by win rate  
**Status meanings:**
- ✅ **Strong** - WR ≥ 70% (keep using)
- 📊 **Active** - WR 40-70% (normal)
- ⚠️ **At Risk** - WR < 40%, ≥5 trades (watch closely)
- 🚫 **Ejected** - Removed from scanner (done)

**Use case:** "Which tickers are dragging down my performance?"

---

### Auto-Ejector (Control Section)
**What it does:** Evaluates tickers for ejection  
**Controls:**
- **[✓] Dry Run** - Safe preview (ON by default)
- **[🔍 Evaluate]** - Run analysis

**Workflow:**
1. Click Evaluate (dry run shows preview)
2. Review candidates
3. Uncheck dry run → Click again to actually eject

**Use case:** "Which tickers should I stop trading?"

---

### Regime Correlation (Bottom Section)
**What it shows:** Win rate by market regime  
**Displays:**
- 🟢 **RISK ON** - VIX < 20 (normal volatility)
- 🔴 **HIGH VIX** - VIX ≥ 20 (elevated volatility)

**Use case:** "Does my strategy work better in calm or chaotic markets?"

---

## 🔄 Update Frequency

**Real-time updates every 30 seconds:**
- Signal quality counts
- Ticker performance leaderboard
- Ejection candidate counts
- Regime statistics

**Manual updates (button click):**
- Auto-ejector evaluation
- Ejection execution (when dry run unchecked)

---

## 💡 Common Scenarios

### Scenario 1: First Launch (No Trades Yet)
**What you'll see:**
- All counts at `0`
- Win rates showing `--`
- Empty performance table
- "No ejection candidates"

**This is normal!** Wait for first scanner run.

---

### Scenario 2: After 10 Trades
**What you'll see:**
- Signal quality bars filling in
- Tickers appearing in performance table
- Win rates calculating
- Regime stats populating

**Action:** Monitor signal quality distribution

---

### Scenario 3: Found Underperforming Ticker
**What you'll see:**
- Ticker in performance table with ⚠️ At Risk status
- Ejection candidates count increases
- Click Evaluate → See detailed reason

**Action:**
1. Review why it's underperforming
2. Decide: Eject or give more time?
3. If ejecting: Uncheck dry run → Evaluate again

---

### Scenario 4: Validating Strategy
**What you'll see:**
- Signal quality: Perfect signals winning most
- Performance: Several tickers at ✅ Strong
- Regime: Both show similar WR (regime-agnostic)

**Interpretation:** Strategy is working as designed! 🎉

---

## ⚠️ Warning Signs

### 🚨 Signal Quality Inverted
```
Perfect: 12 (40.0% WR)  ← Should be HIGHEST
Good:    24 (65.2% WR)
```
**Problem:** Classification broken  
**Fix:** Check gap_pct/volume_ratio thresholds

---

### 🚨 Too Many Poor Signals
```
Poor: 45 (33.3% WR)  ← Should be <10% of total
```
**Problem:** Filters not strict enough  
**Fix:** Increase quality gate thresholds

---

### 🚨 Many Tickers At Risk
```
Ejection Candidates: 12  ← Should be <20% of tickers
```
**Problem:** Scanner selecting bad tickers  
**Fix:** Review scanner criteria, run bulk ejection

---

### 🚨 Regime Mismatch
```
RISK ON: 35.0% WR  ← Should be HIGHER
HIGH VIX: 75.0% WR
```
**Problem:** Strategy assumptions inverted  
**Fix:** Review mean reversion logic, VIX thresholds

---

## 🎓 Pro Tips

### Tip 1: Use Dry Run First
Always run ejection with dry run ON first to preview before executing.

### Tip 2: Monitor Signal Quality Weekly
Perfect + Good should be 70%+ of all signals.

### Tip 3: Eject Early
Don't wait for 10+ losing trades. Eject at 5 trades if WR < 40%.

### Tip 4: Check Regime Balance
Aim for at least 10 trades in each regime for valid comparison.

### Tip 5: Sort Performance Table
Click column headers to sort by different metrics.

---

## 📚 Full Documentation

- `PHASE_2.5_DASHBOARD_COMPLETE.md` - Complete technical guide
- `PHASE_2.5_INITIALIZATION.md` - Scanner integration steps
- `ARCHITECTURE_RISKS.md` - Known issues & solutions

---

## 🚀 Ready to Launch!

```powershell
cd Autotrader
python gui_trading_dashboard.py
```

**Expected:**
- Dashboard opens with enhanced Memory System panel
- All sections render correctly
- Initially empty (normal before trades)
- Will auto-populate as trades execute

**First Action:**
- Look for "[OK] Phase 2.5 Memory System initialized" in logs
- If missing: Run `python patch_v2.5_hotfix.py`

---

**🎉 Phase 2.5 Dashboard: Fully Operational!**

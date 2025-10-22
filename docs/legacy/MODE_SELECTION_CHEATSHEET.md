# 🎯 Mode Selection Cheat Sheet

## Which Script Should I Run?

```
┌─────────────────────────────────────────────────────────────────┐
│ WHAT DO YOU WANT TO DO?                                         │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ 1. Just scan for ideas (no trading)                            │
│                                                                  │
│    python run_pennyhunter_nightly.py                           │
│                                                                  │
│    ✅ Generates watchlist                                       │
│    ❌ No trades executed                                        │
│    ❌ No broker connection                                      │
│    ⏰ Run anytime (usually 4:30 PM after close)                │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ 2. Test my strategy (paper trading - CURRENT)                  │
│                                                                  │
│    python scripts\daily_pennyhunter.py                         │
│                                                                  │
│    ✅ Scans for setups                                          │
│    ✅ Executes SIMULATED trades                                 │
│    ✅ Tracks cumulative history                                 │
│    ❌ NO REAL MONEY                                             │
│    ⏰ Run daily during Phase 2 validation                      │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ 3. Trade with real money (FUTURE - after validation)           │
│                                                                  │
│    python src/bouncehunter/agentic_cli.py \                    │
│      --broker questrade --live-trading                         │
│                                                                  │
│    ✅ Scans for setups                                          │
│    ✅ Executes REAL trades                                      │
│    ✅ Connects to real broker API                               │
│    🔴 USES REAL MONEY                                           │
│    ⏰ Run after 20+ trades validated                           │
│    ⚠️  NOT READY YET (Phase 3)                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🔍 How to Tell Which Mode You're In

### When You Run the Script

```powershell
# SCAN ONLY MODE
PS> python run_pennyhunter_nightly.py
==================== PENNYHUNTER NIGHTLY SCAN ====================
📊 Mode: SCAN ONLY (no trades will be executed)
...

# PAPER TRADING MODE
PS> python scripts\daily_pennyhunter.py
==================== PENNYHUNTER DAILY AUTOMATION ====================
📊 Mode: PAPER TRADING (simulated trades)
🔧 Broker: PaperBroker (no real money)
...

# LIVE TRADING MODE (future)
PS> python src/bouncehunter/agentic_cli.py --broker questrade --live-trading
==================== AGENTIC TRADING SYSTEM ====================
🔴 Mode: LIVE TRADING
🔴 Broker: Questrade
🔴 Account: XXXXX123
⚠️  WARNING: THIS USES REAL MONEY
Type 'CONFIRM' to proceed: _
```

---

## 📋 Mode Comparison Table

| Feature | Scan Only | Paper Trading | Live Trading |
|---------|-----------|---------------|--------------|
| **Script** | `nightly.py` | `daily.py` | `agentic_cli.py` |
| **Scans market** | ✅ Yes | ✅ Yes | ✅ Yes |
| **Executes trades** | ❌ No | ✅ Yes (fake) | ✅ Yes (real) |
| **Broker connection** | ❌ None | 📊 Paper | 🔴 Real API |
| **Real money** | ❌ $0 | ❌ $0 | 🔴 **YES** |
| **Output** | Watchlist | Trade log | Order IDs |
| **When to use** | Evening prep | Validation | After validation |
| **Current phase** | Optional | ✅ **NOW** | ⏳ Future |

---

## 🚦 Safety Levels

```
LOW RISK ────────────────────────────────────────► HIGH RISK

┌──────────┐    ┌─────────────┐    ┌──────────────┐
│ SCAN     │───►│ PAPER       │───►│ LIVE         │
│ ONLY     │    │ TRADING     │    │ TRADING      │
│          │    │             │    │              │
│ No       │    │ Simulated   │    │ Real         │
│ trades   │    │ trades      │    │ trades       │
│          │    │             │    │              │
│ No       │    │ Fake        │    │ Real         │
│ broker   │    │ broker      │    │ broker       │
│          │    │             │    │              │
│ $0 risk  │    │ $0 risk     │    │ $ RISK       │
└──────────┘    └─────────────┘    └──────────────┘
    ↑                 ↑                   ↑
    │                 │                   │
Optional         CURRENT PHASE       FUTURE PHASE
                 (Phase 2)           (Phase 3)
```

---

## 🎯 Current Workflow (Phase 2 - October 2025)

### What You Should Run Daily

```powershell
# THIS IS YOUR MAIN COMMAND:
python scripts\daily_pennyhunter.py
```

**What it does**:
1. Scans market for gap setups
2. Executes SIMULATED trades (paper broker)
3. Tracks results toward 20-trade goal
4. Shows progress dashboard

**What it DOESN'T do**:
- ❌ Connect to real broker
- ❌ Use real money
- ❌ Place real orders

**Current progress**: 2/20 trades (10%)

---

### Optional: Nightly Watchlist

```powershell
# OPTIONAL (for planning):
python run_pennyhunter_nightly.py
```

**Use this if**:
- You want to know tomorrow's setups in advance
- You're trading manually and need a watchlist
- You want to review ideas before bed

**Skip this if**:
- You trust the daily automation
- You're busy and want minimal workflow

---

## 🚀 Future Workflow (Phase 3 - After 20 Trades)

### What You'll Run (After Validation)

```powershell
# FUTURE - LIVE TRADING:
python src/bouncehunter/agentic_cli.py \
  --broker questrade \
  --config configs/pennyhunter.yaml \
  --live-trading \
  --auto-execute
```

**What it will do**:
1. Scans market for gap setups
2. Executes REAL trades (via Questrade API)
3. Uses REAL money ($200 account)
4. Manages stops/targets automatically

**Prerequisites**:
- ✅ 20+ trades completed
- ✅ 65%+ win rate validated
- ✅ Phase 2.5 memory system tested
- ✅ Broker credentials configured
- ✅ You're comfortable with automation

---

## 🔧 How to Switch Modes

### From Scan to Paper Trading

```powershell
# Before (scan only):
python run_pennyhunter_nightly.py

# After (paper trading):
python scripts\daily_pennyhunter.py  # ← Just run different script
```

**No config changes needed** - different scripts = different modes.

---

### From Paper to Live Trading (Future)

**Step 1: Complete Phase 2 validation**
```powershell
# Keep running until 20 trades:
python scripts\daily_pennyhunter.py
```

**Step 2: Validate win rate**
```powershell
python scripts\analyze_pennyhunter_results.py

# Check: Win rate ≥ 65%?
# If YES → proceed
# If NO → debug and collect more data
```

**Step 3: Configure broker**
```yaml
# Edit configs/pennyhunter.yaml
scanner:
  live_trading: true        # ← Change from false
  broker: "questrade"       # ← Specify real broker
```

**Step 4: Test connection**
```powershell
python diagnose_questrade.py  # Verify API works
```

**Step 5: Run live (with confirmation)**
```powershell
python src/bouncehunter/agentic_cli.py \
  --broker questrade \
  --live-trading

# System will prompt:
# "⚠️  WARNING: LIVE TRADING - Type 'CONFIRM' to proceed: _"
```

---

## ❓ FAQ

### Q: Which script should I run right now (October 2025)?

**A**: `python scripts\daily_pennyhunter.py` (paper trading)

This is your **Phase 2 validation workflow**. Run it daily until you have 20 trades.

---

### Q: Can I accidentally trade real money?

**A**: **No.** 

The current script (`daily_pennyhunter.py`) is hardcoded to use the paper broker. You'd have to:
1. Edit the source code
2. Change `"paper"` to `"questrade"`
3. Save and run

This is intentionally difficult to prevent accidents.

---

### Q: When will I switch to live trading?

**A**: After Phase 2 validation complete:
1. ✅ 20+ trades accumulated
2. ✅ Win rate ≥ 65% confirmed
3. ✅ Phase 2.5 memory system tested
4. ✅ You feel confident in the strategy

**Estimated timeline**: 2-3 weeks (currently 2/20 trades)

---

### Q: Do I need to run the nightly scan?

**A**: **No** - it's optional.

`scripts\daily_pennyhunter.py` does its own scanning. The nightly scan is just for:
- Getting tomorrow's watchlist early
- Planning manual trades
- Reviewing ideas before bed

Most users skip it during paper trading.

---

### Q: How do I know which mode I'm in?

**A**: Look at the script name and output:

```powershell
# SCAN ONLY
python run_pennyhunter_nightly.py
# Output: "Mode: SCAN ONLY"

# PAPER TRADING
python scripts\daily_pennyhunter.py
# Output: "Mode: PAPER TRADING | Broker: PaperBroker"

# LIVE TRADING (future)
python src/bouncehunter/agentic_cli.py --live-trading
# Output: "🔴 LIVE TRADING | Broker: Questrade"
```

The script name and first line of output tell you everything.

---

## 🎯 Summary

### Right Now (Phase 2)

```powershell
# Run this daily:
python scripts\daily_pennyhunter.py

# Mode: Paper trading (no real money)
# Goal: Accumulate 20 trades
# Progress: 2/20 (10%)
```

### Future (Phase 3)

```powershell
# Run this daily:
python src/bouncehunter/agentic_cli.py --broker questrade --live-trading

# Mode: Live trading (real money)
# Goal: Automated gap trading
# Prerequisites: 20+ trades validated
```

### The System Knows Because

1. **You choose the script** (not automatic)
2. **Script determines mode** (hardcoded broker)
3. **No config changes needed** (different scripts = different modes)
4. **Output clearly shows mode** (SCAN/PAPER/LIVE)

**You're always in control!**

---

Last Updated: October 20, 2025  
Current Mode: 📊 Paper Trading (Phase 2)  
Next Mode: 🚀 Live Trading (Phase 3 - after validation)

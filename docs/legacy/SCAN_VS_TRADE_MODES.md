# 🔀 How the System Knows: Scanning vs Trading

## TL;DR

**The system uses DIFFERENT SCRIPTS for different modes:**

1. **`run_pennyhunter_nightly.py`** = 🔍 SCAN ONLY (no trades)
2. **`run_pennyhunter_paper.py`** = 📊 SCAN + PAPER TRADE (simulated)
3. **`scripts/daily_pennyhunter.py`** = 🤖 WRAPPER (calls #2, tracks history)
4. **`src/bouncehunter/agentic_cli.py`** = 🚀 LIVE TRADING (future, real broker)

**YOU control the mode by choosing which script to run.**

---

## 🎯 The Four Modes Explained

### Mode 1: 🔍 Scan Only (Nightly Watchlist)

**Script**: `run_pennyhunter_nightly.py`

**What it does**:
- ✅ Downloads EOD data from Yahoo Finance
- ✅ Scans 200+ penny stocks for gap setups
- ✅ Generates tomorrow's watchlist (2-3 tickers)
- ❌ **Does NOT execute any trades**
- ❌ **Does NOT connect to broker**

**When to use**:
- Evening routine (4:30 PM after market close)
- Planning tomorrow's trading day
- Generating ideas for manual trading

**Output**:
```
==================== PENNYHUNTER NIGHTLY SCAN ====================
RUNNER VWAP CANDIDATES:
  1. ADT  - Gap: +24.5% | Score: 8.5/10 ← WATCHLIST
  2. SAN  - Gap: +21.8% | Score: 7.8/10 ← WATCHLIST

FRD BOUNCE CANDIDATES:
  3. COMP - Flush: -11.2% | Score: 7.2/10 ← WATCHLIST

✅ NO TRADES EXECUTED (scan only)
==================================================================
```

**Command**:
```powershell
python run_pennyhunter_nightly.py
python run_pennyhunter_nightly.py --tickers AAPL,TSLA,ADT
python run_pennyhunter_nightly.py --output reports/scan.txt
```

---

### Mode 2: 📊 Paper Trading (Simulated Execution)

**Script**: `run_pennyhunter_paper.py`

**What it does**:
- ✅ Downloads current market data
- ✅ Scans for gap setups
- ✅ **Executes SIMULATED trades** (PaperBroker)
- ✅ Tracks entry/exit/P&L
- ❌ **Does NOT use real money**
- ❌ **Does NOT connect to real broker**

**When to use**:
- Phase 2 validation (current phase)
- Testing strategy before going live
- Accumulating 20+ trades for validation

**Output**:
```
==================== PAPER TRADING RESULTS ====================
📊 Scanned: 6 tickers
✅ Signals Found: 2 (ADT, SAN)
💼 Trades Executed: 1 (ADT)

TRADE DETAILS:
  Ticker: ADT
  Entry: $8.52 (VWAP reclaim)
  Exit: $9.20 (+8% target hit)
  Shares: 58
  P&L: +$39.44
  Status: CLOSED ✅

PAPER ACCOUNT:
  Starting: $200.00
  Current: $239.44
  Profit: +$39.44 (+19.7%)
===============================================================
```

**Command**:
```powershell
python run_pennyhunter_paper.py
python run_pennyhunter_paper.py --tickers ADT,SAN
python run_pennyhunter_paper.py --account-size 200 --max-risk 5
```

**How it knows it's paper trading**:
```python
# From run_pennyhunter_paper.py, line 55
self.broker = create_broker("paper", initial_cash=account_size)
#                            ^^^^^^^ ← "paper" mode = simulated
```

---

### Mode 3: 🤖 Daily Automation (Paper Trading Wrapper)

**Script**: `scripts/daily_pennyhunter.py`

**What it does**:
- ✅ Calls `run_pennyhunter_paper.py` internally
- ✅ Executes paper trades
- ✅ Appends results to cumulative history
- ✅ Tracks progress toward 20-trade goal
- ✅ Shows daily + all-time stats
- ❌ **Still paper trading** (no real money)

**When to use**:
- Daily Phase 2 validation routine
- Automatically tracking all trades
- Building historical database

**Output**:
```
==================== PENNYHUNTER DAILY AUTOMATION ====================
Date: 2025-10-20 16:00:00
Goal: Accumulate 20+ trades to validate 65-75% win rate

TODAY'S SESSION:
  Signals Found: 1
  Trades Executed: 1
  Active Positions: 0

CUMULATIVE STATISTICS (ALL TIME):
  Total Trades: 3
  Completed: 3 | Active: 0
  Wins: 3 | Losses: 0
  Win Rate: 100.0%
  Total P&L: $127.50

PHASE 2 VALIDATION PROGRESS:
  [======---------------------------------] 15%
  3/20 trades completed
  17 more trades needed for Phase 2 validation
=====================================================================
```

**Command**:
```powershell
python scripts\daily_pennyhunter.py
python scripts\daily_pennyhunter.py --tickers ADT,SAN,COMP
```

**How it wraps paper trading**:
```python
# From scripts/daily_pennyhunter.py, line 46
cmd = [
    sys.executable,
    str(PROJECT_ROOT / "run_pennyhunter_paper.py"),  # ← Calls paper trader
    "--tickers", tickers,
    "--account-size", "200",
    "--output", str(RESULTS_FILE)
]
result = subprocess.run(cmd, ...)  # ← Executes and captures output
```

---

### Mode 4: 🚀 Live Trading (Real Broker - Future)

**Script**: `src/bouncehunter/agentic_cli.py`

**What it does**:
- ✅ Downloads current market data
- ✅ Scans for gap setups
- ✅ **Executes REAL trades** (via broker API)
- ✅ **Uses REAL money** 💰
- ✅ Connects to Questrade/Alpaca/IBKR
- ✅ Full agentic system with 8 agents

**When to use**:
- After Phase 2 validation complete (20+ trades, 65%+ win rate)
- After Phase 2.5 memory system validated
- Phase 3 - Full agentic automation
- **NOT NOW** (still in Phase 2 validation)

**Output** (future):
```
==================== LIVE TRADING SESSION ====================
🔴 LIVE BROKER: Questrade (Account: XXXXX123)
⚠️  REAL MONEY TRADING ACTIVE

📊 Scanned: 6 tickers
✅ Signals Found: 2 (ADT, SAN)
💰 Trades Executed: 1 (ADT)

TRADE DETAILS:
  Ticker: ADT
  Entry: $8.52 (VWAP reclaim)
  Order ID: QT-123456789
  Shares: 58
  Cost: $494.16 (+ $1.00 commission)
  Stop Loss: $7.98 (set via broker API)
  Target: $9.20 (+8%)
  Status: ACTIVE (monitoring via API)

LIVE ACCOUNT:
  Cash Available: $4,505.84
  Active Positions: 1 (ADT)
  Daily P&L: TBD (position open)
==============================================================
```

**Command** (future):
```powershell
# Live trading with real broker
python src/bouncehunter/agentic_cli.py \
  --broker questrade \
  --config configs/pennyhunter.yaml \
  --mode scan  # or --mode trade

# With automation
python src/bouncehunter/agentic_cli.py \
  --broker questrade \
  --auto-execute \
  --live-trading  # ← REAL MONEY FLAG
```

**How it knows it's live trading**:
```python
# From agentic_cli.py, line 71
policy = Policy(
    config=config,
    live_trading=scanner_cfg.get("live_trading", False),  # ← From config
    # ... other params
)

# From configs/pennyhunter.yaml (future):
scanner:
  live_trading: true  # ← Set to true for REAL trading
  # OR
  live_trading: false  # ← Set to false for paper trading
```

---

## 🔧 How the System Determines Mode

### Method 1: Script Selection (Current)

**You choose the mode by running different scripts:**

```powershell
# SCAN ONLY (no trades)
python run_pennyhunter_nightly.py

# PAPER TRADING (simulated)
python run_pennyhunter_paper.py
python scripts\daily_pennyhunter.py  # ← Calls paper trader internally

# LIVE TRADING (future - real money)
python src/bouncehunter/agentic_cli.py --broker questrade --live-trading
```

**Key code**:
```python
# run_pennyhunter_paper.py creates PAPER broker
self.broker = create_broker("paper", initial_cash=200)
#                            ^^^^^^ ← Hardcoded to paper

# agentic_cli.py creates REAL broker (future)
if args.broker == "questrade":
    broker = create_broker("questrade")  # ← Real broker
    #                      ^^^^^^^^^^ ← From command line arg
```

---

### Method 2: Configuration Flag (Future)

**Set mode in config file:**

```yaml
# configs/pennyhunter.yaml
scanner:
  live_trading: false  # ← Paper trading
  # OR
  live_trading: true   # ← Live trading

  broker: "paper"      # ← Which broker to use
  # OR
  broker: "questrade"  # ← Real broker
```

**Code reads config**:
```python
# From agentic_cli.py
policy = Policy(
    live_trading=scanner_cfg.get("live_trading", False),  # ← From YAML
)

if policy.live_trading:
    print("🔴 LIVE TRADING MODE - REAL MONEY")
    broker = create_broker(scanner_cfg.get("broker", "questrade"))
else:
    print("📊 PAPER TRADING MODE - SIMULATED")
    broker = create_broker("paper")
```

---

### Method 3: Command Line Argument (Future)

**Override config via CLI:**

```powershell
# Force paper trading (even if config says live)
python src/bouncehunter/agentic_cli.py --broker paper

# Force live trading (even if config says paper)
python src/bouncehunter/agentic_cli.py --broker questrade --live-trading

# Scan only (no trades at all)
python src/bouncehunter/agentic_cli.py --mode scan
```

**Code checks args**:
```python
# From agentic_cli.py (future enhancement)
parser.add_argument("--broker", choices=["paper", "questrade", "alpaca", "ibkr"])
parser.add_argument("--live-trading", action="store_true")
parser.add_argument("--mode", choices=["scan", "trade"])

args = parser.parse_args()

if args.mode == "scan":
    # Scan only, no trades
    result = await run_scan(policy, db_path, broker=None)
elif args.live_trading:
    # Live trading with real broker
    broker = create_broker(args.broker)
    result = await run_scan(policy, db_path, broker=broker)
else:
    # Paper trading (default)
    broker = create_broker("paper")
    result = await run_scan(policy, db_path, broker=broker)
```

---

## 🔍 Visual Decision Tree

```
┌─────────────────────────────────────────────────────────────┐
│ USER RUNS A SCRIPT                                          │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
        ┌────────────────────────────────┐
        │ Which script did you run?      │
        └────────────────────────────────┘
                     │
        ┌────────────┼────────────┬───────────────┐
        │            │            │               │
        ▼            ▼            ▼               ▼
┌──────────────┐ ┌──────────┐ ┌─────────┐ ┌──────────────┐
│ nightly.py   │ │ paper.py │ │ daily.py│ │ agentic_cli  │
└──────────────┘ └──────────┘ └─────────┘ └──────────────┘
        │            │            │               │
        ▼            ▼            ▼               ▼
┌──────────────┐ ┌──────────┐ ┌─────────┐ ┌──────────────┐
│ SCAN ONLY    │ │ SCAN +   │ │ Calls   │ │ Check config │
│              │ │ PAPER    │ │ paper.py│ │ live_trading │
│ No broker    │ │ TRADE    │ │         │ │ flag         │
│ No trades    │ │          │ │ PAPER   │ │              │
│              │ │ Broker:  │ │ TRADE   │ │ true/false?  │
│ Output:      │ │ "paper"  │ │         │ │              │
│ Watchlist    │ │          │ │ Track   │ └──────┬───────┘
│              │ │ Output:  │ │ history │        │
│              │ │ Trades   │ │         │   ┌────┴────┐
│              │ │ Simulated│ │         │   │         │
│              │ │          │ │         │   ▼         ▼
│              │ │          │ │         │ false      true
│              │ │          │ │         │   │         │
│              │ │          │ │         │   ▼         ▼
│              │ │          │ │         │ PAPER     LIVE
│              │ │          │ │         │ Broker:   Broker:
│              │ │          │ │         │ "paper"   "questrade"
└──────────────┘ └──────────┘ └─────────┘           │
                                                     ▼
                                              🔴 REAL MONEY
```

---

## 📊 Current vs Future State

### Current State (Phase 2 - October 2025)

**What you're using**:
```powershell
# Evening scan (optional - just for watchlist ideas)
python run_pennyhunter_nightly.py

# Daily paper trading (MAIN WORKFLOW)
python scripts\daily_pennyhunter.py  # ← This is what you run daily
```

**Mode**: 📊 Paper Trading (100% simulated)  
**Broker**: PaperBroker (fake account)  
**Money**: $0 real money at risk  
**Purpose**: Accumulate 20 trades to validate 65%+ win rate

---

### Future State (Phase 3 - After Validation)

**What you'll use**:
```powershell
# Nightly scan (automated via cron)
# (runs automatically at 4:30 PM)

# Live trading bot (morning - 9:25 AM)
python src/bouncehunter/agentic_cli.py \
  --broker questrade \
  --config configs/pennyhunter.yaml \
  --live-trading \
  --auto-execute
```

**Mode**: 🚀 Live Trading (real money)  
**Broker**: Questrade (or Alpaca/IBKR)  
**Money**: $200 real capital  
**Purpose**: Automated gap trading with validated strategy

---

## 🛡️ Safety Mechanisms

### Paper Trading Safeguards

**Can't accidentally trade real money**:
```python
# run_pennyhunter_paper.py, line 55
self.broker = create_broker("paper", ...)  # ← Hardcoded to "paper"

# There's NO code path to real broker in current scripts
# You'd have to manually edit the source code (very obvious)
```

### Live Trading Safeguards (Future)

**Multiple confirmations required**:
```python
# configs/pennyhunter.yaml
scanner:
  live_trading: true  # ← Must set to true

# Command line
python agentic_cli.py --live-trading  # ← Must pass flag

# Startup confirmation
if policy.live_trading and broker != "paper":
    print("⚠️  WARNING: LIVE TRADING MODE - REAL MONEY")
    print(f"   Broker: {broker_name}")
    print(f"   Account: {account_id}")
    confirm = input("   Type 'CONFIRM' to proceed: ")
    if confirm != "CONFIRM":
        sys.exit("Aborted by user")
```

---

## 🎯 Quick Reference

| Script | Mode | Trades? | Broker | Real Money? | Use Case |
|--------|------|---------|--------|-------------|----------|
| `run_pennyhunter_nightly.py` | 🔍 Scan | ❌ No | None | ❌ No | Generate watchlist |
| `run_pennyhunter_paper.py` | 📊 Paper | ✅ Yes | Paper | ❌ No | Test strategy |
| `scripts/daily_pennyhunter.py` | 📊 Paper | ✅ Yes | Paper | ❌ No | **Daily workflow** |
| `agentic_cli.py` (future) | 🚀 Live | ✅ Yes | Real | ✅ **YES** | Automated trading |

---

## ❓ Common Questions

### Q: How do I switch from paper to live trading?

**A**: You'll use a **completely different script**:

```powershell
# Current (paper)
python scripts\daily_pennyhunter.py

# Future (live) - DIFFERENT SCRIPT
python src/bouncehunter/agentic_cli.py --broker questrade --live-trading
```

You **cannot accidentally** switch to live trading because the scripts are separate.

---

### Q: Can the paper trading script connect to a real broker?

**A**: No. The broker is hardcoded:

```python
# run_pennyhunter_paper.py, line 55
self.broker = create_broker("paper", initial_cash=account_size)
#                            ^^^^^^ ← Always "paper"
```

To use a real broker, you'd have to:
1. Edit the source code (very obvious)
2. Change `"paper"` to `"questrade"` (intentional)
3. Save the file and run it

**This is a FEATURE** - prevents accidental live trading during validation.

---

### Q: How does the system know market hours?

**A**: It doesn't care (for paper trading):

```python
# Paper trading runs anytime (uses historical data)
python scripts\daily_pennyhunter.py  # Works at 8 PM

# Live trading (future) would check market hours:
if not market_is_open():
    print("Market closed - cannot execute live trades")
    sys.exit(1)
```

---

### Q: What if I run the wrong script?

**A**: 
- ✅ Running `nightly.py` by mistake → Just generates watchlist (harmless)
- ✅ Running `paper.py` by mistake → Simulated trades only (harmless)
- ✅ Running `daily.py` by mistake → Calls `paper.py` internally (harmless)
- ⚠️ Running `agentic_cli.py` (future) → Would require `--live-trading` flag + config change + confirmation prompt

**You'd need to intentionally override 3+ safety checks to trade live.**

---

## 🚀 Summary

### How the System Knows

1. **YOU tell it** by choosing which script to run
2. **Script determines mode** via hardcoded broker type
3. **Config overrides** (future) via `live_trading` flag
4. **CLI flags** (future) via `--broker` and `--live-trading`

### Current Workflow (Phase 2)

```powershell
# You run this daily (paper trading only):
python scripts\daily_pennyhunter.py

# System knows it's paper because:
# 1. Script calls run_pennyhunter_paper.py
# 2. That script uses broker = create_broker("paper")
# 3. No real broker connection possible
```

### Future Workflow (Phase 3)

```powershell
# You'll run this daily (live trading):
python src/bouncehunter/agentic_cli.py \
  --broker questrade \
  --live-trading

# System knows it's live because:
# 1. --broker questrade (not "paper")
# 2. --live-trading flag passed
# 3. Config has live_trading: true
# 4. User confirms at prompt
```

**Bottom line**: The mode is determined by **which script you run**, not by time-of-day or automatic detection. This gives you **full control** and prevents accidental live trading.

---

**Last Updated**: October 20, 2025  
**Current Phase**: Phase 2 Validation (paper trading only)  
**Scripts in Use**: `scripts/daily_pennyhunter.py` (paper)  
**Future Scripts**: `src/bouncehunter/agentic_cli.py` (live - not yet used)

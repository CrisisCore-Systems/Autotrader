# 📅 Daily Trading Schedule - Visual Guide

## The Complete 24-Hour Cycle

```
                    PENNYHUNTER GAP TRADING WORKFLOW
                    
┌─────────────────────────────────────────────────────────────────┐
│ PREVIOUS DAY (Market Close)                                     │
│ Time: 4:00 PM - 8:00 PM ET                                      │
└─────────────────────────────────────────────────────────────────┘
                           │
                           ▼
        ┌──────────────────────────────────────┐
        │  EVENING ROUTINE (10 minutes)        │
        │                                       │
        │  4:30 PM - Run Nightly Scanner       │
        │  python run_pennyhunter_nightly.py   │
        │                                       │
        │  What happens:                       │
        │  • Download EOD data (Yahoo Finance) │
        │  • Scan ~200 penny stocks            │
        │  • Find gap setups                   │
        │  • Generate watchlist (2-3 tickers)  │
        │                                       │
        │  Output: "Watch ADT, SAN tomorrow"   │
        └──────────────────────────────────────┘
                           │
                           ▼
        ┌──────────────────────────────────────┐
        │  REVIEW & PLAN (5 minutes)           │
        │                                       │
        │  • Read scan report                  │
        │  • Set price alerts on phone         │
        │  • Note entry/stop levels            │
        │                                       │
        │  Example:                            │
        │  ADT - Entry: $8.50 | Stop: $7.98   │
        │  SAN - Entry: $9.80 | Stop: $9.20   │
        └──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│ OVERNIGHT (Sleep)                                                │
│ System Status: IDLE (no processes running)                       │
│ Data: Watchlist saved in reports/pennyhunter_scan.txt          │
└─────────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│ NEXT DAY (Pre-Market)                                            │
│ Time: 9:00 AM - 9:30 AM ET                                       │
└─────────────────────────────────────────────────────────────────┘
                           │
                           ▼
        ┌──────────────────────────────────────┐
        │  PRE-MARKET CHECK (5 minutes)        │
        │                                       │
        │  9:25 AM - Validate Setups           │
        │                                       │
        │  • Check if gaps still holding       │
        │  • Verify no offering/halt news      │
        │  • Confirm volume is strong          │
        │                                       │
        │  Decision: Go/No-Go for each ticker  │
        └──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│ MARKET OPEN (Trading Window)                                     │
│ Time: 9:30 AM - 10:30 AM ET (1 HOUR ONLY)                       │
└─────────────────────────────────────────────────────────────────┘
                           │
                           ▼
        ┌──────────────────────────────────────┐
        │  ACTIVE TRADING (15-30 minutes)      │
        │                                       │
        │  9:30 AM - Market Opens              │
        │    • ADT gaps to $8.75               │
        │                                       │
        │  9:35 AM - First Pullback            │
        │    • ADT pulls back to $8.45         │
        │                                       │
        │  9:38 AM - ENTRY TRIGGER             │
        │    • ADT reclaims VWAP at $8.52     │
        │    • Place order: 58 shares          │
        │    • Set stop: $7.98                 │
        │    • Set target: $9.20 (+8%)        │
        │                                       │
        │  9:55 AM - TARGET HIT               │
        │    • ADT reaches $9.22              │
        │    • Exit 50% position              │
        │    • Move stop to breakeven         │
        │                                       │
        │  10:12 AM - SECOND TARGET           │
        │    • ADT reaches $9.80 (+15%)       │
        │    • Exit remaining 50%             │
        │                                       │
        │  Trade Complete: +$62 profit        │
        └──────────────────────────────────────┘
                           │
                           ▼
        ┌──────────────────────────────────────┐
        │  TIME STOP (if needed)               │
        │                                       │
        │  10:30 AM - Close All Positions     │
        │                                       │
        │  • Exit any remaining trades        │
        │  • No overnight holds               │
        │  • Record results                   │
        └──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│ POST-TRADING (Rest of Day)                                       │
│ Time: 10:30 AM - 4:00 PM ET                                      │
│ System Status: IDLE (no active trades)                           │
└─────────────────────────────────────────────────────────────────┘
                           │
                           ▼
        ┌──────────────────────────────────────┐
        │  LUNCH REVIEW (5 minutes)            │
        │                                       │
        │  12:00 PM - Analyze Results          │
        │  python scripts\analyze_pennyhunter_results.py
        │                                       │
        │  • Review win/loss                   │
        │  • Update trade journal              │
        │  • Calculate cumulative stats        │
        │                                       │
        │  Progress: 3/20 trades (15%)        │
        └──────────────────────────────────────┘
                           │
                           ▼
        ┌──────────────────────────────────────┐
        │  GIT COMMIT (2 minutes)              │
        │                                       │
        │  git add reports/                    │
        │  git commit -m "chore: Add Phase 2 trade results"
        │  git push origin main                │
        └──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│ EVENING (Prepare for Tomorrow)                                   │
│ Time: 4:00 PM - 8:00 PM ET                                       │
│ REPEAT CYCLE ────────────────────────────────────────────────►  │
└─────────────────────────────────────────────────────────────────┘
```

---

## ⏱️ Time Breakdown

| Activity | Time | When | Required? |
|----------|------|------|-----------|
| **Nightly Scan** | 10 min | 4:30 PM (after close) | ✅ Required |
| **Review Watchlist** | 5 min | Evening | ✅ Required |
| **Pre-Market Check** | 5 min | 9:25 AM | ✅ Required |
| **Active Trading** | 15-30 min | 9:30-10:30 AM | ✅ Required |
| **Lunch Review** | 5 min | 12:00 PM | ⚠️ Optional |
| **Git Commit** | 2 min | Anytime | ⚠️ Optional |
| **TOTAL** | **30-45 min** | Spread across day | — |

---

## 🤖 Automation Comparison

### Level 1: Manual (Current - Phase 2)
```
Evening:  👤 Run scanner manually (10 min)
Morning:  👤 Watch tickers, enter manually (30 min)
Review:   👤 Analyze results manually (5 min)

Total Time: 45 min/day
```

### Level 2: Semi-Auto (Phase 2.5 - Future)
```
Evening:  🤖 Cron job runs scanner (0 min)
Morning:  🤖 Bot places orders, you monitor (10 min)
Review:   🤖 Auto-generated dashboard (2 min)

Total Time: 12 min/day
```

### Level 3: Full Auto (Phase 3 - Future)
```
Evening:  🤖 Cron job runs scanner (0 min)
Morning:  🤖 Bot trades completely autonomously (0 min)
Review:   🤖 Email summary sent automatically (2 min)

Total Time: 2 min/day (just read email)
```

---

## 📊 Data Update Frequency

### What Gets Updated & When

```
╔════════════════════════════════════════════════════════════════╗
║ DATA TYPE          │ FREQUENCY      │ SOURCE         │ COST   ║
╠════════════════════════════════════════════════════════════════╣
║ EOD Prices         │ Daily 4:30 PM  │ Yahoo Finance  │ FREE   ║
║ Gap Detection      │ Nightly        │ Yahoo Finance  │ FREE   ║
║ Market Regime      │ Daily          │ Yahoo Finance  │ FREE   ║
║ Intraday Candles   │ 9:30-10:30 AM  │ Yahoo Finance  │ FREE   ║
║ Order Execution    │ Real-time      │ Broker API     │ FREE*  ║
║ Position Tracking  │ Real-time      │ Broker API     │ FREE*  ║
╚════════════════════════════════════════════════════════════════╝

* FREE with brokerage account
```

### Data Staleness is OK

```
Scenario: ADT is trading at $8.50

Real-Time Feed:  $8.50 ───► Enter immediately
15-Min Delayed:  $8.52 ───► Enter 2 minutes late

Profit Target:   $9.20 (+8% = $0.68 gain)
Slippage Cost:   $0.02 (only 3% of profit)

Verdict: ✅ ACCEPTABLE (96% of profit retained)
```

---

## 🎯 Key Insights

### ✅ Why This Works Without Real-Time Data

1. **Gap setups are SLOW** - Develop over 5-30 minutes
2. **Profit targets are LARGE** - 8-15% (vs 0.1% for scalpers)
3. **Stops are WIDE** - 5-10% away (vs 0.1% for HFT)
4. **Holding time is LONG** - 30 min to 3 hours (vs seconds)
5. **Trade frequency is LOW** - 1-3 trades/day (vs 100+)

### ❌ Why Scalpers Need Real-Time

1. **Profit targets are TINY** - 0.1-0.5% (every penny matters)
2. **Holding time is SHORT** - Seconds to minutes
3. **Trade frequency is HIGH** - 50-100 trades/day
4. **Execution speed is CRITICAL** - Milliseconds matter
5. **Spreads eat profit** - Must have tight spreads

---

## 📱 Mobile Workflow (If You Have a Day Job)

### Using Your Phone

```
4:30 PM (At home)
  ├─ Run scanner on PC: python run_pennyhunter_nightly.py
  └─ Read watchlist email

9:20 AM (Bathroom break)
  ├─ Open broker app
  ├─ Place GTC limit orders for 2-3 watchlist tickers
  │  Example: "Buy ADT @ $8.52, Stop @ $7.98"
  └─ Set profit target alerts

10:00 AM (Coffee break)
  ├─ Check if any orders filled
  └─ Adjust stops if needed

11:00 AM (Quick check)
  ├─ See if profit targets hit
  └─ Close remaining positions

12:00 PM (Lunch)
  └─ Review results in trade journal

Total Time on Phone: 10-15 minutes
```

**Key**: Use **limit orders** so you don't need to watch live

---

## 🚀 Next Steps

### This Week (Phase 2 Validation)
```powershell
# Run nightly scan daily
python run_pennyhunter_nightly.py

# Review results (paper trading)
python scripts\daily_pennyhunter.py

# Track progress
python scripts\analyze_pennyhunter_results.py
```

**Goal**: Accumulate 18 more trades (currently 2/20)

### Next Month (Phase 2.5 - Semi-Automation)
```powershell
# Set up cron job (Windows Task Scheduler)
schtasks /create /tn "PennyHunter Scan" /tr "python run_pennyhunter_nightly.py" /sc daily /st 16:30

# Run semi-automated bot in morning
python src/bouncehunter/agentic_cli.py --broker questrade --auto-execute
```

**Goal**: Reduce time to 10 min/day

### Future (Phase 3 - Full Automation)
```powershell
# Everything runs automatically
# You just review weekly summaries
```

**Goal**: Reduce time to 10 min/week

---

**Bottom Line**: Your system is **optimized for part-time traders** who can dedicate **30 minutes/day** split between evening scanning and morning execution. No need for expensive real-time data or all-day monitoring!

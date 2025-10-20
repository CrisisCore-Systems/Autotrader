# PennyHunter Paper Trading - Quick Start Guide

**Status**: ✅ INFRASTRUCTURE COMPLETE  
**Date**: October 18, 2025  
**System**: Phase 3 Production with Agent Weighting v1.0

---

## 🎯 **What's Ready**

All infrastructure for 30-day paper trading deployment:

✅ **AlpacaBroker Integration** (`src/bouncehunter/alpaca_broker.py`)
- Paper trading execution
- Order management (entry, stop, target)
- Position tracking
- Risk checks (max position, concurrent limits)
- Portfolio management

✅ **Configuration** (`configs/paper_trading.yaml`)
- Trading parameters (position sizing, risk limits)
- Agent settings (consensus thresholds)
- Circuit breakers (consecutive losses, drawdown)
- Alert configuration (Slack, Discord, Email)

✅ **Daily Scanner** (`scripts/run_daily_scan.py`)
- Pre-market gap scanning
- Agent consensus execution
- Automated trade placement via Alpaca
- Performance logging

✅ **Nightly Auditor** (`scripts/run_nightly_audit.py`)
- Agent performance updates
- Portfolio monitoring
- Circuit breaker checks
- Daily reports

✅ **Trade Journal** (`reports/paper_trading_journal.xlsx`)
- Trade tracking with agent votes
- Auto-calculated performance metrics
- Agent accuracy monitoring

✅ **Dependencies**
- `alpaca-py` installed
- `openpyxl` installed

---

## 🚀 **Setup Steps (30 minutes)**

### **Step 1: Create Alpaca Account (10 min)**

1. Go to https://alpaca.markets
2. Click "Sign Up" → Create account
3. Navigate to **Paper Trading** section
4. Generate API keys:
   - API Key ID
   - Secret Key
5. **IMPORTANT**: Copy both keys securely

### **Step 2: Configure Environment (5 min)**

Set environment variables with your Alpaca keys:

**Windows PowerShell:**
```powershell
# Temporary (current session only)
$env:ALPACA_API_KEY = "your_api_key_here"
$env:ALPACA_API_SECRET = "your_secret_key_here"

# Permanent (all sessions)
[System.Environment]::SetEnvironmentVariable('ALPACA_API_KEY', 'your_api_key_here', 'User')
[System.Environment]::SetEnvironmentVariable('ALPACA_API_SECRET', 'your_secret_key_here', 'User')
```

**OR create `.env` file:**
```bash
# .env (in project root)
ALPACA_API_KEY=your_api_key_here
ALPACA_API_SECRET=your_secret_key_here
```

### **Step 3: Test Connection (5 min)**

Test your Alpaca connection:

```powershell
python -c "from bouncehunter.alpaca_broker import AlpacaBroker; broker = AlpacaBroker(); print(broker.get_account())"
```

Expected output:
```
✅ AlpacaBroker initialized (PAPER trading)
{'cash': 25000.0, 'portfolio_value': 25000.0, 'buying_power': 100000.0, ...}
```

### **Step 4: Run Test Scan (10 min)**

Run a test daily scan:

```powershell
python scripts/run_daily_scan.py
```

This will:
- Connect to Alpaca paper trading
- Check current market regime
- Scan for gap opportunities
- Run agent consensus
- Display results (no trades executed yet - it's a dry run)

---

## 📅 **Daily Operations**

### **Morning Routine (8:30 AM ET)**

```powershell
# Activate virtual environment
cd C:\Users\kay\Documents\Projects\AutoTrader\Autotrader
.\.venv-1\Scripts\Activate.ps1

# Run daily scan
python scripts/run_daily_scan.py
```

**What happens:**
1. System scans for gap-up stocks
2. Agents evaluate each signal
3. Approved trades execute via Alpaca
4. Results logged to console and file

### **Evening Routine (6:00 PM ET)**

```powershell
# Run nightly audit
python scripts/run_nightly_audit.py
```

**What happens:**
1. Check for stop/target hits
2. Update agent performance
3. Calculate daily P&L
4. Check circuit breakers
5. Generate report

### **Manual Trade Tracking**

Update your trade journal after each trade:

1. Open `reports/paper_trading_journal.xlsx`
2. Add row with trade details
3. Fill in agent votes (✅ or ❌)
4. Update outcome when trade closes
5. Summary tab auto-calculates metrics

---

## 🔄 **Windows Task Scheduler (Optional)**

Automate daily scans:

```powershell
# Create scheduled task for 8:30 AM daily
$action = New-ScheduledTaskAction `
    -Execute "C:\Users\kay\Documents\Projects\AutoTrader\.venv-1\Scripts\python.exe" `
    -Argument "scripts/run_daily_scan.py" `
    -WorkingDirectory "C:\Users\kay\Documents\Projects\AutoTrader\Autotrader"

$trigger = New-ScheduledTaskTrigger -Daily -At 8:30AM

$principal = New-ScheduledTaskPrincipal `
    -UserId "$env:USERNAME" `
    -LogonType Interactive

$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable

Register-ScheduledTask `
    -TaskName "PennyHunter-DailyScan" `
    -Action $action `
    -Trigger $trigger `
    -Principal $principal `
    -Settings $settings
```

---

## 📊 **Monitoring**

### **Check Account Status**

```powershell
python -c "from bouncehunter.alpaca_broker import AlpacaBroker; b=AlpacaBroker(); print(b.get_account())"
```

### **Check Open Positions**

```powershell
python -c "from bouncehunter.alpaca_broker import AlpacaBroker; b=AlpacaBroker(); [print(f'{p.ticker}: {p.unrealized_pnl_pct:+.1f}%') for p in b.get_positions()]"
```

### **View Logs**

```powershell
# Daily scan log
Get-Content logs/daily_scan.log -Tail 50

# Nightly audit log
Get-Content logs/nightly_audit.log -Tail 50

# Errors
Get-Content logs/errors.log -Tail 50
```

---

## ⚙️ **Configuration Tuning**

Edit `configs/paper_trading.yaml` to adjust:

### **Risk Parameters**
```yaml
trading:
  max_position_pct: 0.10      # 10% max position (adjust 0.05-0.15)
  risk_per_trade_pct: 0.01    # 1% risk per trade (adjust 0.005-0.02)
  max_concurrent: 5           # Max positions (adjust 3-7)
```

### **Confidence Thresholds**
```yaml
trading:
  regime_adjustments:
    NORMAL:
      confidence_threshold: 5.5  # Adjust 5.0-6.5
    HIGH_VIX:
      confidence_threshold: 6.5  # Adjust 6.0-7.5
    STRESS:
      confidence_threshold: 7.5  # Adjust 7.0-8.5
```

### **Agent Consensus**
```yaml
agents:
  min_trades_for_weighting: 20  # Binary mode until X trades
  min_consensus: 0.70           # 70% weighted approval needed
```

---

## 🚨 **Circuit Breakers**

System automatically pauses trading if:

1. **3 Consecutive Losses**
   - Manual review required
   - Check agent accuracy
   - Review losing trades

2. **Drawdown >15%**
   - Reduce position sizes to 0.5%
   - Increase confidence threshold
   - Consider taking break

3. **Daily Loss >3%**
   - Stop trading for the day
   - Review what went wrong
   - Reset next day

---

## 📈 **Success Metrics (30 Days)**

Track these in your journal:

| Metric | Target | Minimum |
|--------|--------|---------|
| **Win Rate** | 60-70% | 55% |
| **Total Trades** | 20-30 | 20 |
| **Profit Factor** | 2.5x+ | 2.0x |
| **Avg Return** | +5% | +3% |
| **Max Drawdown** | <15% | <20% |

---

## 🔧 **Troubleshooting**

### **Error: Alpaca credentials not found**
```
Solution: Set ALPACA_API_KEY and ALPACA_API_SECRET environment variables
```

### **Error: No signals found for 3+ days**
```
Solution: 
1. Check ticker universe is valid
2. Verify market regime (high-vix = fewer signals)
3. Consider lowering confidence threshold temporarily
```

### **Error: Module not found**
```
Solution: 
pip install alpaca-py openpyxl
```

### **Error: Order rejected**
```
Solution:
1. Check if max concurrent positions reached
2. Verify buying power sufficient
3. Check if already in position for ticker
```

---

## 📞 **Next Steps**

1. ✅ **Complete Setup** (Steps 1-4 above)
2. 🧪 **Run Test Scan** (verify everything works)
3. 📝 **Review Trade Journal** (familiarize yourself)
4. 🚀 **Begin Day 1** (tomorrow morning!)
5. 📊 **Daily: Scan → Trade → Audit → Journal**
6. 📈 **Weekly Review** (every Sunday)
7. 🎯 **30-Day Decision** (proceed to live or iterate)

---

## 📚 **Additional Resources**

- **Deployment Guide**: `docs/PAPER_TRADING_DEPLOYMENT.md`
- **Agent Weighting System**: `docs/AGENT_WEIGHTING_SYSTEM.md`
- **Phase 3 Documentation**: `docs/PHASE_3_PRODUCTION_COMPLETE.md`
- **Alpaca API Docs**: https://alpaca.markets/docs/

---

## 💡 **Pro Tips**

1. **Start Conservative**: Use default settings for first week
2. **Track Everything**: Note observations in trade journal
3. **Review Agent Votes**: Pay attention to which agents veto
4. **Monitor Consensus**: Watch for consensus score patterns
5. **Adjust Gradually**: Only change one parameter at a time
6. **Trust the System**: Let the agents do their job
7. **Learn from Losses**: Every loss teaches something
8. **Celebrate Wins**: Acknowledge good trades
9. **Stay Patient**: Need 20+ trades for weighted mode
10. **Have Fun**: This is exciting technology!

---

**Ready to start? Run your first test scan now! 🚀**

```powershell
python scripts/run_daily_scan.py
```

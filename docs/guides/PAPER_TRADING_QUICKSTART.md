# Paper Trading Quick Start Guide

**Date**: October 20, 2025 22:00 EDT  
**Status**: Test Suite Validated ✅

---

## ⚠️ Important: Script Locations

The paper trading scripts are in **different locations**:

- **Paper Trading Bot**: `run_pennyhunter_paper.py` (ROOT directory)
- **Test Suite**: `scripts/test_paper_trading_ibkr.py` (scripts directory)
- **Monitor**: `scripts/monitor_adjustments.py` (scripts directory)
- **Reports**: `scripts/generate_weekly_report.py` (scripts directory)

---

## 🚀 Running Paper Trading

### From ROOT directory (Autotrader/)

```powershell
# Navigate to root
cd C:\Users\kay\Documents\Projects\AutoTrader\Autotrader

# Start paper trading bot
python run_pennyhunter_paper.py
```

**What it does**:
- Runs PennyHunter scanner with Phase 1 enhancements
- Filters signals by market regime
- Executes trades via IBKR paper account
- Monitors positions and exits at targets/stops
- Logs all trades to database

**Options**:
```powershell
# With specific tickers
python run_pennyhunter_paper.py --tickers SENS,SPCE,CLOV

# Custom account size and risk
python run_pennyhunter_paper.py --account-size 200 --max-risk 5
```

---

## 📊 Monitoring (Real-time)

### From ANY directory

```powershell
# Monitor adjustments (24-hour view)
python scripts/monitor_adjustments.py

# Custom time window
python scripts/monitor_adjustments.py --hours 48
```

**Shows**:
- Win rate by adjustment range
- Recent exits with adjustment breakdowns
- VIX and regime distributions
- Adjustment effectiveness

**Note**: Will show "no trades recorded" until first trade exits

---

## 📈 Weekly Reports

### From ANY directory

```powershell
# Generate weekly report
python scripts/generate_weekly_report.py

# Custom date range
python scripts/generate_weekly_report.py --days 14
```

**Includes**:
- Trade performance summary
- Adjustment effectiveness analysis
- VIX regime distribution
- Win rate by market condition
- Symbol-specific insights

---

## 🧪 Testing & Validation

### From ANY directory

```powershell
# Run full test suite
python scripts/test_paper_trading_ibkr.py

# Quick IBKR connection test
python scripts/ibkr_smoke_test.py

# Test VIX provider
python scripts/test_yahoo_vix.py
```

---

## 📁 Directory Structure

```
Autotrader/
├── run_pennyhunter_paper.py          # ← Paper trading bot (ROOT)
├── run_pennyhunter_nightly.py        # ← Nightly scan runner (ROOT)
├── configs/
│   └── my_paper_config.yaml          # ← Your configuration
├── scripts/
│   ├── test_paper_trading_ibkr.py    # ← Test suite
│   ├── monitor_adjustments.py        # ← Real-time monitor
│   ├── generate_weekly_report.py     # ← Weekly reports
│   ├── ibkr_smoke_test.py            # ← Connection test
│   ├── ibkr_connector.py             # ← CLI harness
│   └── ...
├── logs/                              # ← All log files
├── reports/                           # ← Generated reports
└── bouncehunter_memory.db            # ← Trade history database
```

---

## 🔧 Common Issues & Solutions

### Issue 1: "No such file or directory: run_pennyhunter_paper.py"

**Problem**: Running from wrong directory  
**Solution**: The script is in ROOT, not `scripts/`

```powershell
# ❌ WRONG
python scripts/run_pennyhunter_paper.py

# ✅ CORRECT
python run_pennyhunter_paper.py
```

### Issue 2: "no such table: position_exits"

**Problem**: No trades recorded yet (table created on first exit)  
**Solution**: This is expected before first trade completes  
**Status**: Monitor script now handles this gracefully

```powershell
# Will show friendly message:
# "Table 'position_exits' does not exist yet (no trades recorded)"
```

### Issue 3: IBKR Market Data Subscription Error

**Problem**: Real-time quotes require subscription  
**Solution**: Use delayed quotes or subscribe  
**Impact**: None for paper trading (historical data works)

### Issue 4: TWS Not Connected

**Problem**: Paper trading bot can't connect to TWS  
**Solution**: Verify TWS is running:

```powershell
# Test connection first
python scripts/ibkr_smoke_test.py
```

**Checklist**:
- [ ] TWS running
- [ ] Logged into paper account
- [ ] API enabled (Global Configuration → API → Settings)
- [ ] Port 7497 set
- [ ] "Read-Only API" unchecked

---

## 🎯 Recommended Workflow

### Daily Pre-Market (Before 9:30 AM ET)

1. **Start TWS**
   - Login to paper account
   - Verify API settings

2. **Test Connection**
   ```powershell
   python scripts/ibkr_smoke_test.py
   ```

3. **Check VIX**
   ```powershell
   python scripts/test_yahoo_vix.py
   ```

### Market Hours (9:30 AM - 4:00 PM ET)

4. **Start Paper Trading Bot**
   ```powershell
   python run_pennyhunter_paper.py
   ```
   - Scanner runs and finds signals
   - Trades executed automatically
   - Positions monitored continuously

5. **Monitor in Real-time** (separate terminal)
   ```powershell
   python scripts/monitor_adjustments.py
   ```

### After Market Close (After 4:00 PM ET)

6. **Review Day's Activity**
   ```powershell
   # View recent exits
   python scripts/monitor_adjustments.py --hours 8
   ```

### Weekly (Friday After Close)

7. **Generate Weekly Report**
   ```powershell
   python scripts/generate_weekly_report.py
   ```
   - Review win rates
   - Analyze adjustment effectiveness
   - Identify learning opportunities

---

## 📊 Expected Output Examples

### Paper Trading Bot Starting
```
2025-10-20 09:25:00 - INFO - PennyHunter Paper Trading Started
2025-10-20 09:25:01 - INFO - Connected to IBKR (DUO071381)
2025-10-20 09:25:02 - INFO - VIX: 18.23 (NORMAL)
2025-10-20 09:25:02 - INFO - Market Regime: BULL
2025-10-20 09:25:05 - INFO - Scanner running...
2025-10-20 09:25:12 - INFO - Found 3 signals: SENS, CLOV, SPCE
2025-10-20 09:25:15 - INFO - Placing order: BUY 100 SENS @ $0.45
2025-10-20 09:25:16 - INFO - Order filled: SENS entry @ $0.45
```

### Monitor Output (No Trades Yet)
```
2025-10-20 22:00:15 - INFO - Monitor initialized: DB=bouncehunter_memory.db
2025-10-20 22:00:15 - INFO - Generating 24h monitoring report...
2025-10-20 22:00:15 - WARNING - Table 'position_exits' does not exist yet (no trades recorded)

================================================================================
ADJUSTMENT MONITORING REPORT
Period: Last 24 hours
Generated: 2025-10-20 22:00:15
================================================================================

No exits recorded yet. Run paper trading bot to collect data.

Suggestions:
- Start paper trading: python run_pennyhunter_paper.py
- Wait for first position to exit
- Re-run monitor after trades complete
```

### Monitor Output (With Trades)
```
================================================================================
ADJUSTMENT MONITORING REPORT
Period: Last 24 hours
Generated: 2025-10-20 22:00:15
================================================================================

WIN RATE BY ADJUSTMENT RANGE
----------------------------
High Increase (+0.5%+):     75.0% (3/4 wins)
Moderate Increase:          60.0% (3/5 wins)
Minimal Change:             50.0% (2/4 wins)
High Decrease (-0.5%+):     40.0% (2/5 wins)

RECENT EXITS (Last 10)
----------------------------
SENS  | +2.1% | Tier 1 | Adj: +1.2% | VIX: NORMAL | Regime: BULL | Won
CLOV  | -0.8% | Tier 1 | Adj: +0.5% | VIX: NORMAL | Regime: BULL | Loss
SPCE  | +3.5% | Tier 1 | Adj: +1.5% | VIX: NORMAL | Regime: BULL | Won
...

MARKET CONDITIONS DISTRIBUTION
----------------------------
VIX Levels:
- NORMAL: 85% (17/20)
- LOW: 10% (2/20)
- HIGH: 5% (1/20)

Market Regimes:
- BULL: 60% (12/20)
- SIDEWAYS: 30% (6/20)
- BEAR: 10% (2/20)
```

---

## 🔍 Troubleshooting Commands

```powershell
# Check Python environment
python --version  # Should be 3.13

# Verify dependencies
pip list | grep ib-insync  # Should show ib-insync
pip list | grep yfinance   # Should show yfinance

# Check database exists
dir bouncehunter_memory.db

# View logs
cat logs/paper_trading_YYYYMMDD.log

# Test IBKR connection
python scripts/ibkr_smoke_test.py

# Test VIX provider
python scripts/test_yahoo_vix.py

# Run full test suite
python scripts/test_paper_trading_ibkr.py
```

---

## 📝 Configuration

Your config is at: `configs/my_paper_config.yaml`

**Key Settings**:
```yaml
broker:
  name: ibkr
  host: 127.0.0.1
  port: 7497              # TWS paper port
  client_id: 42
  paper: true

vix_provider:
  provider_type: "yahoo"  # Free, no API key needed

intelligent_adjustments:
  enable_volatility_adjustments: true
  enable_time_adjustments: true
  enable_regime_adjustments: true
```

**To modify**:
```powershell
notepad configs/my_paper_config.yaml
```

---

## 📚 Documentation

- **Connection Testing**: `docs/IBKR_CONNECTION_QUICK_REF.md`
- **Setup Guide**: `IBKR_SETUP_README.md`
- **Test Results**: `TEST_SUITE_VALIDATED.md`
- **Script README**: `scripts/README.md`

---

## ✅ Pre-Flight Checklist

Before starting paper trading:

- [ ] TWS running and logged in
- [ ] API enabled in TWS settings
- [ ] Port 7497 configured
- [ ] Test suite passed (all 5 tests)
- [ ] VIX provider working (18.23 NORMAL)
- [ ] Config file validated
- [ ] Virtual environment activated

**Quick Validation**:
```powershell
python scripts/test_paper_trading_ibkr.py
```

Should show: `[OK] All tests passed successfully!`

---

## 🆘 Getting Help

If issues persist:

1. **Check logs**:
   ```powershell
   cat logs/paper_trading_YYYYMMDD.log
   ```

2. **Run diagnostics**:
   ```powershell
   python scripts/ibkr_smoke_test.py
   python scripts/test_paper_trading_ibkr.py
   ```

3. **Review configuration**:
   ```powershell
   cat configs/my_paper_config.yaml
   ```

4. **Verify database**:
   ```powershell
   sqlite3 bouncehunter_memory.db ".tables"
   ```

---

**Last Updated**: October 20, 2025 22:00 EDT  
**System Status**: VALIDATED ✅  
**Ready**: Yes - Start with `python run_pennyhunter_paper.py`

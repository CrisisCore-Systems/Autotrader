# Scripts Directory - IBKR Testing & Utilities

This directory contains scripts for testing and managing IBKR connections and paper trading.

---

## 🔥 Quick Start - Prove TWS Connection Works

### 1. Start TWS and Configure API

**TWS Setup (5 minutes):**
1. Start TWS, log in to **Paper Trading** account
2. **File → Global Configuration → API → Settings**
3. ✅ Enable ActiveX and Socket Clients
4. ❌ Read-only API = **OFF**
5. Port = **7497** (TWS paper)
6. Trusted IPs = **127.0.0.1**
7. **Restart TWS**

See `docs/IBKR_REFERENCE_CARD.md` for detailed checklist.

### 2. Run Smoke Test

```powershell
# From Autotrader directory
python scripts\ibkr_smoke_test.py
```

**Should print:**
```
✅ SMOKE TEST PASSED - YOU'RE WIRED INTO TWS!
```

**Should see in TWS:**
- Status bar: "Accepted incoming connection from 127.0.0.1"
- Mosaic: Test order appears briefly, then cancels
- Logs: API connection messages

---

## 📋 Available Scripts

### Connection Testing

| Script | Purpose | Usage |
|--------|---------|-------|
| `ibkr_smoke_test.py` | **Start here!** End-to-end connection test | `python scripts\ibkr_smoke_test.py` |
| `ibkr_connector.py` | Production CLI harness with utilities | `python scripts\ibkr_connector.py --help` |
| `test_yahoo_vix.py` | Test Yahoo VIX provider (no IBKR needed) | `python scripts\test_yahoo_vix.py` |

### Paper Trading Tests

| Script | Purpose | Usage |
|--------|---------|-------|
| `test_paper_trading_ibkr.py` | Full 5-test validation suite | `python scripts\test_paper_trading_ibkr.py` |

### Deployment

| Script | Purpose | Usage |
|--------|---------|-------|
| `run_pennyhunter_paper.py` | Launch paper trading bot | `python scripts\run_pennyhunter_paper.py` |
| `monitor_adjustments.py` | Monitor active positions | `python scripts\monitor_adjustments.py` |

---

## 🛠️ CLI Harness Commands

The `ibkr_connector.py` harness provides production utilities:

```powershell
# Test connection
python scripts\ibkr_connector.py --ping

# Show account summary (equity, cash, buying power)
python scripts\ibkr_connector.py --account

# Show current positions
python scripts\ibkr_connector.py --positions

# Show open orders
python scripts\ibkr_connector.py --orders

# Get quote for symbol
python scripts\ibkr_connector.py --quote AAPL
python scripts\ibkr_connector.py --quote SHOP.TO  # Canadian stock

# Place test order (auto-cancels)
python scripts\ibkr_connector.py --place-test

# Cancel all open orders
python scripts\ibkr_connector.py --cancel-all
```

All activity logged to: `logs/ibkr_connector_YYYYMMDD.log`

---

## 🔧 Environment Variables

Configure connection via environment variables:

```powershell
# Default values (TWS Paper)
$env:IBKR_HOST="127.0.0.1"
$env:IBKR_PORT="7497"      # 7497=TWS Paper, 7496=TWS Live
$env:IBKR_CLIENT_ID="42"   # Any unique integer

# Example: Use different client ID
$env:IBKR_CLIENT_ID="99"
python scripts\ibkr_smoke_test.py

# Example: Connect to Gateway Paper
$env:IBKR_PORT="4002"
python scripts\ibkr_connector.py --ping
```

---

## ✅ Testing Workflow

### New Setup (First Time)

1. **Yahoo VIX Test** (no IBKR required)
   ```powershell
   python scripts\test_yahoo_vix.py
   ```
   Proves system dependencies work.

2. **TWS Smoke Test** (requires TWS running)
   ```powershell
   python scripts\ibkr_smoke_test.py
   ```
   Proves TWS connection works.

3. **Full Test Suite**
   ```powershell
   python scripts\test_paper_trading_ibkr.py
   ```
   Validates entire paper trading system.

4. **Deploy Bot**
   ```powershell
   python scripts\run_pennyhunter_paper.py
   ```
   Start paper trading automation.

### Daily Validation

```powershell
# Quick connection test
python scripts\ibkr_connector.py --ping

# Check positions
python scripts\ibkr_connector.py --positions

# Monitor bot (if running)
python scripts\monitor_adjustments.py
```

---

## 🚨 Common Issues

### Connection Refused

**Symptoms:**
```
✗ Connection FAILED: Connection refused
```

**Fixes:**
1. Is TWS running and logged in?
2. Is port 7497 correct? (paper=7497, live=7496)
3. Did you restart TWS after enabling API?
4. Is 127.0.0.1 in Trusted IPs?

### Orders Not Appearing

**Symptoms:**
- Connection succeeds
- No orders appear in TWS

**Fixes:**
1. **Read-only API must be OFF**
   - File → Global Configuration → API → Settings
   - Uncheck "Read-only API"
2. Restart TWS

### Client ID Clash

**Symptoms:**
```
Error: Client ID already in use
```

**Fix:**
```powershell
$env:IBKR_CLIENT_ID="43"  # Use different ID
python scripts\ibkr_smoke_test.py
```

---

## 📚 Documentation

- **Quick Reference:** `docs/IBKR_REFERENCE_CARD.md` (print this!)
- **Connection Guide:** `docs/IBKR_CONNECTION_QUICK_REF.md`
- **Full Setup:** `docs/IBKR_SETUP_GUIDE.md`
- **10-Min Start:** `docs/QUICK_START_CANADA.md`
- **Migration Summary:** `docs/CANADIAN_MIGRATION_COMPLETE.md`

---

## 🇨🇦 Canadian Stocks

Scripts automatically detect and handle Canadian stocks:

| Exchange | Symbol Format | Example | Currency |
|----------|---------------|---------|----------|
| TSX      | SYMBOL.TO     | SHOP.TO | CAD      |
| TSXV     | SYMBOL.V      | NUMI.V  | CAD      |

No special configuration needed - just use `.TO` or `.V` suffix.

---

## 🔍 Logs

All scripts log to:
```
C:\Users\kay\Documents\Projects\AutoTrader\Autotrader\logs\
```

Files:
- `ibkr_connector_YYYYMMDD.log` - CLI harness activity
- `paper_trading_YYYYMMDD.log` - Bot trading activity

Check logs if issues occur.

---

## 🎯 Next Steps

1. **Prove Connection:** `python scripts\ibkr_smoke_test.py`
2. **Run Full Tests:** `python scripts\test_paper_trading_ibkr.py`
3. **Deploy Bot:** `python scripts\run_pennyhunter_paper.py`
4. **Monitor Daily:** `python scripts\ibkr_connector.py --positions`
5. **Automate:** Right-click `SETUP_SCHEDULER.bat` → Run as Administrator

---

## 🕐 Automated Scheduling (NEW!)

Run paper trading automatically at optimal times using Windows Task Scheduler.

### Quick Setup
```batch
REM Right-click → "Run as Administrator"
SETUP_SCHEDULER.bat
```

Configures 4 tasks:
- 🌅 Pre-Market Scan (7:30 AM ET Mon-Fri)
- 🚀 Market Open Entry (9:35 AM ET Mon-Fri)
- 🧹 EOD Cleanup (4:15 PM ET Mon-Fri)
- 📊 Weekly Report (5:00 PM ET Friday)

### Verify Tasks
```powershell
Get-ScheduledTask -TaskName "PennyHunter_*" | Get-ScheduledTaskInfo
```

### View Logs
```powershell
Get-Content ..\logs\scheduled_runs.log -Tail 20
```

**Documentation:** See `../SCHEDULING_GUIDE.md` for complete guide.

---

**🍁 CrisisCore AutoTrader - Canadian Markets Integration**  
**Last Updated:** 2025-10-21

For support, see troubleshooting guides in `docs/` directory.

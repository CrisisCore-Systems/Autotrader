# Interactive Brokers (IBKR) Setup Guide - Canadian Trading

## 🍁 Canadian-Friendly Trading Stack

This guide replaces the Alpaca-based setup with **Interactive Brokers (IBKR)** - the realistic choice for Canadian algorithmic trading.

**What Changed:**
- ❌ Alpaca (US-only, no Canadian stocks)
- ✅ **IBKR** (global reach, Canadian markets, real APIs)
- ✅ **Yahoo Finance** for VIX data (free, no API keys)
- ✅ Same intelligent adjustment system, new data sources

---

## ⚡ Quick Start

**Want to prove your TWS connection works RIGHT NOW?**

See **[IBKR_CONNECTION_QUICK_REF.md](IBKR_CONNECTION_QUICK_REF.md)** for:
- Tactical TWS configuration checklist
- Smoke test script (`ibkr_smoke_test.py`)
- Production CLI harness (`ibkr_connector.py`)
- Common blocker troubleshooting
- 10-minute validation workflow

**Or continue below for comprehensive setup...**

---

## 📋 Prerequisites

### 1. IBKR Account Setup

1. **Open IBKR Account**: https://www.interactivebrokers.com/
   - Choose **Individual** account type
   - Select **Paper Trading** account (for testing)
   - Complete account application

2. **Install TWS or IB Gateway**:
   - **TWS** (Trader Workstation): Full GUI trading platform
     - Download: https://www.interactivebrokers.com/en/trading/tws.php
     - Use for: Manual trading + API automation
     - Port: **7497** (paper), **7496** (live)
   
   - **IB Gateway**: Headless API gateway (recommended for bots)
     - Download: https://www.interactivebrokers.com/en/trading/ibgateway-stable.php
     - Use for: Pure API automation
     - Port: **4002** (paper), **4001** (live)

3. **Login to Paper Account**:
   - Username: Your IBKR username
   - Password: Your IBKR password
   - Trading mode: **Paper Trading**

### 2. Enable API Access

1. **In TWS/Gateway**, go to:
   ```
   File → Global Configuration → API → Settings
   ```

2. **Configure API Settings**:
   - ☑ **Enable ActiveX and Socket Clients**
   - **Socket port**: 
     - TWS Paper: `7497`
     - Gateway Paper: `4002`
   - **Master API client ID**: Leave blank (or set to specific ID)
   - **Read-Only API**: Uncheck (we need trade execution)
   - **Download open orders on connection**: Check
   - **Trusted IPs**: Add `127.0.0.1`

3. **Security Settings**:
   - **Allow connections from localhost only**: Check
   - **Create API message log file**: Check (for debugging)

### 3. Install Python Dependencies

```powershell
# Install IBKR and VIX data dependencies
pip install ib-insync yfinance

# Verify installation
python -c "import ib_insync; print(f'ib-insync version: {ib_insync.__version__}')"
python -c "import yfinance; print('yfinance installed OK')"
```

---

## ⚙️ Environment Configuration

### Windows PowerShell

```powershell
# IBKR Connection Settings
$env:IBKR_HOST = "127.0.0.1"
$env:IBKR_PORT = "7497"          # 7497=TWS paper, 4002=Gateway paper, 7496=TWS live, 4001=Gateway live
$env:IBKR_CLIENT_ID = "42"       # Any positive integer, keep stable per bot
$env:USE_PAPER = "1"             # 1=paper, 0=live (BE VERY CAREFUL)

# Broker Selection
$env:BROKER_NAME = "ibkr"        # ibkr | alpaca (legacy) | mock

# Verify settings
echo "IBKR Host: $env:IBKR_HOST"
echo "IBKR Port: $env:IBKR_PORT"
echo "Client ID: $env:IBKR_CLIENT_ID"
echo "Paper Mode: $env:USE_PAPER"
```

### Linux/macOS

```bash
# IBKR Connection Settings
export IBKR_HOST=127.0.0.1
export IBKR_PORT=7497            # 7497=TWS paper, 4002=Gateway paper
export IBKR_CLIENT_ID=42
export USE_PAPER=1

# Broker Selection
export BROKER_NAME=ibkr

# Add to ~/.bashrc or ~/.zshrc for persistence
echo 'export IBKR_HOST=127.0.0.1' >> ~/.bashrc
echo 'export IBKR_PORT=7497' >> ~/.bashrc
echo 'export IBKR_CLIENT_ID=42' >> ~/.bashrc
echo 'export USE_PAPER=1' >> ~/.bashrc
```

### Permanent Configuration (Recommended)

Create a `.env` file in your project root:

```bash
# .env file
IBKR_HOST=127.0.0.1
IBKR_PORT=7497
IBKR_CLIENT_ID=42
USE_PAPER=1
BROKER_NAME=ibkr
```

Then load with `python-dotenv`:

```powershell
pip install python-dotenv
```

```python
# In your scripts
from dotenv import load_dotenv
load_dotenv()
```

---

## 🧪 Testing the Setup

### 1. Verify TWS/Gateway is Running

Before running any scripts, ensure TWS or IB Gateway is:
- ✅ Logged in to **Paper Trading** account
- ✅ API settings enabled
- ✅ Listening on correct port (7497 or 4002)

### 2. Run Validation Test

```powershell
cd Autotrader
python scripts\test_paper_trading_ibkr.py
```

**Expected Output:**

```
================================================================================
PAPER TRADING VALIDATION - Intelligent Adjustments System (IBKR + Yahoo)
================================================================================

TEST 1: Configuration Loading
[OK] Configuration loaded successfully
[OK] Broker configured: IBKR
[OK] Intelligent adjustments ENABLED

TEST 2: Broker Connectivity (IBKR)
  IBKR Host: 127.0.0.1
  IBKR Port: 7497 (TWS paper)
  Client ID: 42
  Paper Mode: True
[OK] Connected to IBKR successfully
  Account equity: $1000000.00
  Buying power: $4000000.00
[OK] Market data working: AAPL = $175.43

TEST 3: VIX Data Provider (Yahoo Finance)
[OK] Using Yahoo Finance for VIX data (free)
[OK] Yahoo Finance API accessible
[OK] VIX data retrieved: 18.45
  VIX Regime: NORMAL

TEST 4: Market Regime Detector
[!] Using MockRegimeDetector (Yahoo SPY detector coming soon)
[OK] Market regime detected: BULL

TEST 5: Adjustment Calculation
[OK] Market conditions: VIX=18.45 (NORMAL), Regime=BULL
[OK] Adjustment calculation successful
  Base target: 5.0%
  Adjusted target: 4.70%
  Total adjustment: -0.30%
  
TEST SUMMARY
[OK] All tests passed successfully!

Paper trading system is READY for deployment!
```

### 3. Troubleshooting Connection Issues

**Problem: "Connection refused" or "Failed to connect"**

```
[X] IBKR connection failed: [Errno 10061] No connection could be made
```

**Solutions:**
1. Verify TWS/Gateway is running and logged in
2. Check port number matches (7497 for TWS paper, 4002 for Gateway paper)
3. Verify API is enabled in Global Configuration → API → Settings
4. Check firewall isn't blocking localhost connections
5. Try restarting TWS/Gateway

**Problem: "Error validating request" or "Authentication failed"**

```
[X] IBKR connection failed: error validating request
```

**Solutions:**
1. Ensure you're logged in to the correct account (Paper vs Live)
2. Check API settings allow socket connections
3. Verify client ID isn't already in use by another connection
4. Try a different client ID (change IBKR_CLIENT_ID)

**Problem: "Market data not available"**

```
[!] Market data working: AAPL = $0.00
```

**Solutions:**
1. Subscribe to market data in IBKR account settings
2. Paper accounts have free delayed data (15min)
3. Real-time data requires market data subscriptions
4. Canadian stocks (TSX) require separate data subscription

---

## 🚀 Deployment

### 1. Configuration Review

Verify your `configs/my_paper_config.yaml`:

```yaml
# Broker settings
broker:
  name: ibkr
  host: ${IBKR_HOST}
  port: ${IBKR_PORT}
  client_id: ${IBKR_CLIENT_ID}
  paper: ${USE_PAPER}

# VIX provider (Yahoo Finance - free)
vix_provider:
  provider_type: "yahoo"
  yahoo:
    low_threshold: 15.0
    normal_threshold: 25.0
    high_threshold: 35.0

# Regime detector (Mock for now)
regime_detector:
  detector_type: "mock"
  mock:
    default_regime: "BULL"

# Adjustments enabled
adjustments:
  enabled: true
  # ... rest of adjustment settings
```

### 2. Start Paper Trading Bot

```powershell
# Ensure TWS/Gateway is running first!
python scripts\run_pennyhunter_paper.py
```

**Bot will:**
- Connect to IBKR paper account
- Monitor open positions
- Apply intelligent adjustments based on:
  - VIX levels (Yahoo Finance)
  - Market regime (Mock detector)
  - Time decay
  - Symbol-specific learning
- Execute tier exits when conditions met

### 3. Monitor Performance

```powershell
# Daily monitoring (run once per day)
python scripts\monitor_adjustments.py

# Weekly analysis (run every Sunday)
python scripts\generate_weekly_report.py
```

**Reports saved to:**
- `reports/adjustment_monitoring.txt` (daily)
- `reports/weekly_adjustment_report_YYYYMMDD_HHMMSS.txt` (weekly)

---

## 📊 Trading Canadian Stocks

### Symbol Format

IBKR uses different symbol formats than Yahoo Finance:

| Exchange | Yahoo Format | IBKR Format | Currency |
|----------|--------------|-------------|----------|
| TSX      | `SHOP.TO`    | `SHOP`      | CAD      |
| TSXV     | `NUMI.V`     | `NUMI`      | CAD      |
| NYSE     | `AAPL`       | `AAPL`      | USD      |
| NASDAQ   | `TSLA`       | `TSLA`      | USD      |

**The IBKR adapter automatically handles this:**

```python
# Your code (keeps Yahoo format)
broker.get_quote("SHOP.TO")  # Canadian stock

# Adapter converts to:
# Symbol: SHOP
# Exchange: TSE (Toronto Stock Exchange)
# Currency: CAD
```

### Currency Handling

IBKR paper accounts default to USD, but support multi-currency:

```python
# USD stocks (default)
broker.place_market_order("AAPL", qty=10, side="buy")

# CAD stocks (auto-detected from .TO suffix)
broker.place_market_order("SHOP.TO", qty=5, side="buy")  # Uses CAD automatically
```

**Account currencies:**
- Paper account: USD base currency
- Real account: Can set CAD as base currency in account settings

---

## 🔧 Advanced Configuration

### Multiple Bots (Different Client IDs)

Run multiple bots simultaneously with different client IDs:

```powershell
# Bot 1 - Penny Hunter
$env:IBKR_CLIENT_ID = "42"
python scripts\run_pennyhunter_paper.py

# Bot 2 - Another Strategy (separate terminal)
$env:IBKR_CLIENT_ID = "43"
python scripts\run_other_strategy.py
```

**Important:** Each bot needs a unique client ID!

### Gateway vs TWS

**Use IB Gateway if:**
- Running headless (server, cloud, Docker)
- Don't need GUI for manual trading
- Want lower resource usage
- Production/automation focus

**Use TWS if:**
- Want to see positions/orders visually
- Mix manual + automated trading
- Need charts and analysis tools
- Development/testing phase

**Switching between them:**

```powershell
# TWS Paper
$env:IBKR_PORT = "7497"

# Gateway Paper
$env:IBKR_PORT = "4002"

# TWS Live (DANGER - REAL MONEY!)
$env:IBKR_PORT = "7496"
$env:USE_PAPER = "0"
```

### Docker Deployment

Create `Dockerfile.ibkr`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install ib-insync yfinance

# Copy application
COPY . .

# Set environment
ENV IBKR_HOST=host.docker.internal
ENV IBKR_PORT=7497
ENV IBKR_CLIENT_ID=42
ENV USE_PAPER=1

CMD ["python", "scripts/run_pennyhunter_paper.py"]
```

Build and run:

```powershell
docker build -f Dockerfile.ibkr -t pennyhunter-ibkr .
docker run --network=host pennyhunter-ibkr
```

---

## 🎯 Migration Checklist

### From Alpaca to IBKR

- [ ] Install TWS or IB Gateway
- [ ] Create paper trading account
- [ ] Enable API access (port 7497 or 4002)
- [ ] Install `ib-insync` and `yfinance`
- [ ] Set environment variables (IBKR_HOST, IBKR_PORT, etc.)
- [ ] Update `configs/my_paper_config.yaml` (broker: ibkr)
- [ ] Run `python scripts\test_paper_trading_ibkr.py`
- [ ] Verify all 5 tests pass
- [ ] Start paper trading bot
- [ ] Monitor for 24 hours
- [ ] Review adjustment logs
- [ ] Generate weekly report after 7 days

### Paper to Live Trading

**⚠️ CRITICAL: Only migrate after 2-4 weeks of successful paper trading!**

- [ ] Paper trading win rate >= 5% improvement
- [ ] No system errors for 7+ consecutive days
- [ ] VIX provider >= 95% uptime
- [ ] Regime detector >= 95% uptime
- [ ] Review all adjustment calculations
- [ ] Understand P&L attribution
- [ ] Set position size limits
- [ ] Configure stop losses
- [ ] Enable alerting (Telegram/email)
- [ ] **CHANGE PORT TO LIVE** (7496 TWS or 4001 Gateway)
- [ ] **SET USE_PAPER=0**
- [ ] **START WITH SMALL POSITIONS**
- [ ] Monitor continuously for first week

---

## 📚 Additional Resources

- **IBKR API Docs**: https://interactivebrokers.github.io/tws-api/
- **ib-insync Docs**: https://ib-insync.readthedocs.io/
- **Yahoo Finance API**: https://github.com/ranaroussi/yfinance
- **Canadian Markets**: https://www.tsx.com/
- **IBKR Paper Trading**: https://www.interactivebrokers.com/en/trading/demoaccount.php

---

## 🆘 Support

**IBKR Connection Issues:**
- Check TWS/Gateway logs: `C:\Users\<username>\Trader Workstation\logs\`
- IBKR Client Portal: https://www.interactivebrokers.com/portal/
- IBKR Support: https://www.interactivebrokers.com/en/support/contact.php

**Bot Issues:**
- Review logs: `logs/paper_test.log`, `logs/paper_adjustments.log`
- Enable DEBUG logging in config
- Test each component individually (VIX, regime, broker)
- Check environment variables are set correctly

**Performance Questions:**
- Generate weekly reports: `python scripts\generate_weekly_report.py`
- Compare vs baseline in reports
- Review adjustment effectiveness by component
- Check symbol-specific learning stats

---

## ✅ Success Criteria

**Your setup is ready when:**
1. ✅ IBKR connection test passes
2. ✅ Yahoo VIX data retrieves successfully
3. ✅ Regime detector returns market condition
4. ✅ Adjustment calculation produces valid targets
5. ✅ Bot runs for 1 hour without errors
6. ✅ Orders execute successfully in paper account
7. ✅ Monitoring scripts generate reports

**After 2-4 weeks of paper trading:**
- Win rate improves >= 5% vs baseline
- Profit factor > 1.5
- Average PnL improved vs base targets
- No critical errors or crashes
- VIX availability >= 95%
- Regime detection >= 95%

**Then you're ready for live trading! 🚀**

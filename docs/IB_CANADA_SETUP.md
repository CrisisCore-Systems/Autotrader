# 🍁 Interactive Brokers Setup Guide (Canada)

**Platform**: Interactive Brokers Canada  
**Compatibility**: ✅ Canadian Residents  
**Status**: READY FOR PAPER TRADING

---

## 🎯 **Why Interactive Brokers for Canada?**

**✅ Advantages:**
- ✅ Available to Canadian residents
- ✅ Free paper trading account
- ✅ Trade US and Canadian markets
- ✅ CAD and USD account support
- ✅ Low commissions ($1-5 per trade)
- ✅ Advanced trading platform (TWS)
- ✅ Excellent API (ib_insync)

**vs Alpaca:**
- ❌ Alpaca does NOT accept Canadian residents
- ❌ Alpaca is US-only

**vs Questrade:**
- ⚠️ Questrade API is more limited
- ⚠️ Higher commissions
- ✅ IB has better API and lower costs

---

## 📋 **Setup Steps (45 minutes)**

### **Step 1: Create IB Account (20 min)**

1. **Go to Interactive Brokers Canada**
   - Visit: https://www.interactivebrokers.ca/
   - Click "Open Account"

2. **Choose Account Type**
   - Select "Individual" account
   - Choose your country: Canada
   - Currency: CAD or USD (your choice)

3. **Complete Application**
   - Provide personal information
   - Answer investment experience questions
   - Submit application

4. **Wait for Approval**
   - Usually approved within 24-48 hours
   - You'll receive email confirmation

### **Step 2: Enable Paper Trading (5 min)**

1. **Log into Account Management**
   - Go to: https://www.interactivebrokers.com/
   - Click "Login" → "Account Management"

2. **Navigate to Paper Trading**
   - Click "Settings" → "Paper Trading Account"
   - Click "Request Paper Trading Account"

3. **Receive Paper Account**
   - You'll get a separate paper trading username
   - Paper account has $1,000,000 virtual capital
   - Reset anytime

### **Step 3: Download TWS/Gateway (10 min)**

**Choose ONE:**

**Option A: TWS (Trader Workstation)** - Full featured GUI
- Download: https://www.interactivebrokers.com/en/trading/tws.php
- Size: ~450 MB
- Features: Charts, news, full trading interface
- **Use for**: Monitoring + trading

**Option B: IB Gateway** - Lightweight (RECOMMENDED)
- Download: https://www.interactivebrokers.com/en/trading/ibgateway-stable.php
- Size: ~50 MB
- Features: API connection only, no GUI
- **Use for**: Automated trading only

**Recommendation for Paper Trading:**
- Start with **IB Gateway** (simpler, uses less resources)
- Add TWS later if you want to monitor manually

### **Step 4: Configure TWS/Gateway (10 min)**

1. **Install and Launch**
   - Run installer
   - Launch IB Gateway (or TWS)

2. **Login with Paper Trading**
   - Username: Your PAPER trading username (not live!)
   - Password: Same as live account
   - Trading Mode: **Paper Trading** (IMPORTANT!)

3. **Enable API**
   - Click "Configure" → "Settings"
   - Go to "API" → "Settings"
   - ✅ Enable ActiveX and Socket Clients
   - ✅ Read-Only API: **Unchecked** (need trading)
   - Socket Port: **7497** (paper) or 7496 (live)
   - Master API Client ID: 1
   - Click "OK"

4. **Trusted IP Addresses**
   - Add: 127.0.0.1 (localhost)
   - This allows your Python script to connect

5. **Auto-Restart**
   - Set auto-restart time (2:00 AM recommended)
   - IB Gateway requires daily restart

---

## ⚙️ **Configuration**

Your `configs/paper_trading.yaml` is already configured for IB:

```yaml
broker:
  name: interactive_brokers
  paper_trading: true
  host: 127.0.0.1
  port: 7497  # Paper trading port
  client_id: 1
```

**Ports:**
- **7497**: Paper trading (default)
- **7496**: Live trading (use with caution!)

---

## 🧪 **Test Connection**

### **1. Start IB Gateway**
- Launch IB Gateway
- Login with paper trading credentials
- Make sure "Paper Trading" mode is selected
- Keep it running in background

### **2. Test Python Connection**

```powershell
python -c "from bouncehunter.ib_broker import IBBroker; broker = IBBroker(); broker.connect(); print(broker.get_account()); broker.disconnect()"
```

**Expected Output:**
```
✅ IBBroker initialized (PAPER trading)
   Host: 127.0.0.1:7497
✅ Connected to Interactive Brokers
{'cash': 1000000.0, 'portfolio_value': 1000000.0, 'buying_power': 4000000.0, ...}
Disconnected from IB
```

**If connection fails:**
- ✅ IB Gateway is running
- ✅ Logged in with PAPER trading account
- ✅ API enabled in settings
- ✅ Port 7497 configured
- ✅ Localhost (127.0.0.1) trusted

---

## 📊 **Daily Workflow**

### **Morning Routine (8:30 AM ET)**

```powershell
# 1. Start IB Gateway (if not already running)
# 2. Login with paper trading credentials
# 3. Run daily scan
python scripts/run_daily_scan.py
```

### **Evening Routine (6:00 PM ET)**

```powershell
# Run nightly audit
python scripts/run_nightly_audit.py
```

### **Keep IB Gateway Running**
- IB Gateway must be running for scripts to work
- Set to auto-restart at 2:00 AM
- Check daily before market open

---

## 💰 **Account Settings**

### **Initial Capital**
- Paper account starts with $1M USD
- Configure system to use $25k for realism:

```yaml
trading:
  initial_capital: 25000  # Use only $25k of paper account
```

### **Currency**
- Paper trading supports USD and CAD
- System configured for USD (most liquid)
- You can trade TSX stocks (CAD) if needed

### **Market Data**
- Paper trading includes delayed market data (15 min)
- For real-time data, need market data subscription
- Not required for paper trading (delayed is fine)

---

## 🔄 **Key Differences from Alpaca**

| Feature | Alpaca | Interactive Brokers |
|---------|--------|---------------------|
| Canadian Access | ❌ No | ✅ Yes |
| API Keys | Required | Not required (TWS login) |
| Connection | REST API | Socket connection |
| Setup | Simple | More complex |
| Paper Trading | $25k-1M | $1M (configurable) |
| Commission | Free | $1-5 per trade |
| Markets | US only | Global (US, Canada, Europe, Asia) |
| Platform | API only | TWS GUI + API |

---

## 🚨 **Important Notes**

### **IB Gateway Must Be Running**
- Scripts won't work if IB Gateway is closed
- Need to keep it running in background
- Set to auto-restart daily at 2 AM

### **Paper Trading Mode**
- ALWAYS use paper trading for testing
- Double-check "Paper Trading" is selected in login
- Port 7497 is paper, 7496 is LIVE (careful!)

### **Market Hours**
- IB Gateway works 24/7 for paper trading
- Real market data only during market hours
- Pre-market: 4:00 AM - 9:30 AM ET
- Regular: 9:30 AM - 4:00 PM ET
- After-hours: 4:00 PM - 8:00 PM ET

### **Daily Restart**
- IB Gateway auto-restarts daily (configurable time)
- Scripts will disconnect during restart
- Re-run scan after restart if needed

---

## 🛠️ **Troubleshooting**

### **Error: Not connected to IB**
```
Solution:
1. Check IB Gateway is running
2. Verify logged in with paper trading account
3. Check port 7497 in config matches IB settings
4. Run test connection command
```

### **Error: Connection refused**
```
Solution:
1. Enable API in IB Gateway settings
2. Add 127.0.0.1 to trusted IP addresses
3. Make sure port 7497 is correct
4. Restart IB Gateway
```

### **Error: Already connected from another client**
```
Solution:
1. Close any other Python scripts using IB
2. Increase client_id in config (try 2, 3, 4)
3. Restart IB Gateway
```

### **Error: Market data not available**
```
Solution:
1. This is normal for paper trading (delayed data)
2. System uses last price or close price
3. Subscribe to real-time data if needed (costs money)
```

---

## 📚 **Resources**

**Interactive Brokers:**
- Main Site: https://www.interactivebrokers.ca/
- TWS/Gateway Download: https://www.interactivebrokers.com/en/trading/tws.php
- API Documentation: https://interactivebrokers.github.io/tws-api/
- Paper Trading: https://www.interactivebrokers.com/en/trading/free-trial.php

**ib_insync Library:**
- Documentation: https://ib-insync.readthedocs.io/
- GitHub: https://github.com/erdewit/ib_insync
- Examples: https://ib-insync.readthedocs.io/recipes.html

**Our Documentation:**
- Quick Start: `docs/QUICK_START_GUIDE.md`
- Deployment: `docs/PAPER_TRADING_DEPLOYMENT.md`
- Agent Weighting: `docs/AGENT_WEIGHTING_SYSTEM.md`

---

## 🚀 **Ready to Start!**

**Checklist:**
- [ ] IB account created and approved
- [ ] Paper trading account enabled
- [ ] IB Gateway downloaded and installed
- [ ] API enabled in settings
- [ ] Test connection successful
- [ ] `ib_insync` package installed (✅ done)

**Next:**
1. Keep IB Gateway running
2. Run first test scan: `python scripts/run_daily_scan.py`
3. Follow 30-day paper trading plan
4. Track results in trade journal

---

**🍁 You're ready for Canadian paper trading with Interactive Brokers! 🚀**

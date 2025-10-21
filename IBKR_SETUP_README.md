# IBKR Connection & Testing - Quick Access

**Tactical tools to prove your TWS connection works end-to-end.**

---

## 🔥 3-Step Validation (10 Minutes)

### Step 1: Configure TWS (5 min)

1. Start TWS, log in to **Paper Trading** account
2. **File → Global Configuration → API → Settings**
   - ✅ Enable ActiveX and Socket Clients
   - ❌ **Read-only API = OFF** (CRITICAL for orders)
   - Port = **7497**
   - Trusted IPs = **127.0.0.1**
3. **Restart TWS**

### Step 2: Run Smoke Test (2 min)

```powershell
cd Autotrader
python scripts\ibkr_smoke_test.py
```

**Should print:** `✅ SMOKE TEST PASSED`

### Step 3: Verify in TWS (1 min)

Check TWS for:
- ✓ Status bar: "Accepted incoming connection from 127.0.0.1"
- ✓ Mosaic: Test order appeared & canceled
- ✓ Logs (View → Logs → API): Connection messages

---

## � Quick Commands

```powershell
# End-to-end smoke test (start here!)
python scripts\ibkr_smoke_test.py

# Test connection only
python scripts\ibkr_connector.py --ping

# Show account summary
python scripts\ibkr_connector.py --account

# Show positions
python scripts\ibkr_connector.py --positions

# Get quote (US or Canadian)
python scripts\ibkr_connector.py --quote AAPL
python scripts\ibkr_connector.py --quote SHOP.TO

# Place test order (auto-cancels)
python scripts\ibkr_connector.py --place-test
```

---

## 📚 Documentation Hierarchy

**Pick your path:**

### 🏃 Fast Track (Want proof NOW)

1. **[docs/IBKR_REFERENCE_CARD.md](docs/IBKR_REFERENCE_CARD.md)** ← **Print this!**
   - One-page desk reference
   - Port numbers, settings, error codes
   - Quick troubleshooting

2. **[scripts/README.md](scripts/README.md)**
   - Script usage guide
   - Testing workflow
   - Common issues

### 📖 Comprehensive Setup

1. **[docs/IBKR_CONNECTION_QUICK_REF.md](docs/IBKR_CONNECTION_QUICK_REF.md)**
   - Tactical TWS configuration
   - Smoke test walkthrough
   - Common blocker troubleshooting
   - Error code reference

2. **[docs/IBKR_SETUP_GUIDE.md](docs/IBKR_SETUP_GUIDE.md)**
   - Full IBKR account setup
   - TWS/Gateway installation
   - Environment variables
   - Canadian trading details
   - Production deployment

### 🍁 Canadian Integration

1. **[docs/QUICK_START_CANADA.md](docs/QUICK_START_CANADA.md)**
   - 10-minute setup
   - Daily workflow
   - Weekly monitoring

2. **[docs/CANADIAN_MIGRATION_COMPLETE.md](docs/CANADIAN_MIGRATION_COMPLETE.md)**
   - What changed from Alpaca
   - All new components
   - Testing status
   - Next steps


---

## 🛠️ Available Tools

### Connection Testing Tools

| Tool | Purpose | Time |
|------|---------|------|
| `scripts/ibkr_smoke_test.py` | **Start here!** End-to-end validation | 30 sec |
| `scripts/ibkr_connector.py` | Production CLI harness with utilities | Varies |
| `scripts/test_yahoo_vix.py` | VIX provider test (no IBKR needed) | 10 sec |

### Paper Trading Suite

| Tool | Purpose | Time |
|------|---------|------|
| `scripts/test_paper_trading_ibkr.py` | Full 5-test validation suite | 2 min |
| `scripts/run_pennyhunter_paper.py` | Deploy paper trading bot | Continuous |
| `scripts/monitor_adjustments.py` | Monitor active positions | On-demand |

---

## 🚨 Quick Troubleshooting

| Error | Fix |
|-------|-----|
| Connection refused | TWS not running or wrong port (use **7497** for paper) |
| No connection message in TWS | Add **127.0.0.1** to Trusted IPs, restart TWS |
| Orders ignored | Turn **OFF** "Read-only API" setting |
| Client ID in use | Change `IBKR_CLIENT_ID` environment variable |
| Firewall blocks | Allow `javaw.exe` and `TWS.exe` through firewall |

---

## 📊 Port Reference

| Platform | Mode  | Port |
|----------|-------|------|
| TWS      | Paper | **7497** |
| TWS      | Live  | 7496 |
| Gateway  | Paper | 4002 |
| Gateway  | Live  | 4001 |

---

## � Environment Variables

```powershell
# Default (TWS Paper)
$env:IBKR_HOST="127.0.0.1"
$env:IBKR_PORT="7497"
$env:IBKR_CLIENT_ID="42"

# Custom client ID (if clash)
$env:IBKR_CLIENT_ID="99"

# Gateway Paper (instead of TWS)
$env:IBKR_PORT="4002"
```

---

## 🇨🇦 Canadian Stocks

**Auto-detected by symbol suffix:**

- **TSX:** `SHOP.TO` → CAD currency, TSE exchange
- **TSXV:** `NUMI.V` → CAD currency, VENTURE exchange

No special configuration needed!

---

## ✅ Success Checklist

When smoke test passes, you should see:

- [ ] Terminal: `✅ SMOKE TEST PASSED`
- [ ] TWS Status: "Accepted incoming connection from 127.0.0.1"
- [ ] TWS Mosaic: Test order appeared & canceled
- [ ] TWS Logs (View → Logs → API): Connection messages visible
- [ ] Account info retrieved
- [ ] Market data working (AAPL quote)
- [ ] Order placement working
- [ ] Order cancellation working

---

## 🎯 Recommended Testing Flow

### First Time Setup

1. ✅ **Test Yahoo VIX** (proves dependencies work, no TWS needed)
   ```powershell
   python scripts\test_yahoo_vix.py
   ```

2. ✅ **Configure TWS** (see Step 1 above)

3. ✅ **Run Smoke Test** (proves TWS connection works)
   ```powershell
   python scripts\ibkr_smoke_test.py
   ```

4. ✅ **Full Test Suite** (validates entire paper trading system)
   ```powershell
   python scripts\test_paper_trading_ibkr.py
   ```

5. ✅ **Deploy Bot** (start paper trading automation)
   ```powershell
   python scripts\run_pennyhunter_paper.py
   ```

### Daily Validation

```powershell
# Morning check
python scripts\ibkr_connector.py --ping
python scripts\ibkr_connector.py --positions

# Monitor bot (if running)
python scripts\monitor_adjustments.py
```

---

## �📁 File Locations

```
Autotrader/
├── scripts/
│   ├── ibkr_smoke_test.py          ← Start here!
│   ├── ibkr_connector.py           ← CLI utilities
│   ├── test_yahoo_vix.py           ← VIX test (no IBKR)
│   ├── test_paper_trading_ibkr.py  ← Full suite
│   └── README.md                   ← Script guide
├── docs/
│   ├── IBKR_REFERENCE_CARD.md      ← Print this!
│   ├── IBKR_CONNECTION_QUICK_REF.md
│   ├── IBKR_SETUP_GUIDE.md
│   ├── QUICK_START_CANADA.md
│   └── CANADIAN_MIGRATION_COMPLETE.md
└── logs/
    └── ibkr_connector_YYYYMMDD.log
```

---

## 🆘 Support Resources

**Stuck?** Check in this order:

1. **[docs/IBKR_REFERENCE_CARD.md](docs/IBKR_REFERENCE_CARD.md)** - Quick fixes
2. **[docs/IBKR_CONNECTION_QUICK_REF.md](docs/IBKR_CONNECTION_QUICK_REF.md)** - Detailed troubleshooting
3. **[scripts/README.md](scripts/README.md)** - Script-specific issues
4. **Logs:** `logs/ibkr_connector_*.log`
5. **TWS Logs:** View → Logs → API

---

## 🚀 Next Steps After Validation

1. **Run full tests:** `python scripts\test_paper_trading_ibkr.py`
2. **Deploy bot:** `python scripts\run_pennyhunter_paper.py`
3. **Monitor daily:** `python scripts\ibkr_connector.py --positions`
4. **Weekly reports:** `python scripts\generate_weekly_report.py`

---

## 📝 Legacy Configuration (Not Used by New Tools)

The following configuration files were used by older broker integration code. The new Canadian migration uses direct IBKR integration via `ib_insync`:

### `ibkr_config.json` (Legacy)
Standalone JSON configuration for older IBKR integration:
```json
{
  "ibkr": {
    "enabled": true,
    "host": "127.0.0.1",
    "port": 7497,
    "client_id": 1,
    "account_id": "DU0071381",
    "timeout": 60,
    "readonly": false
  }
}
```

**Note:** New Canadian migration tools use environment variables (see above) instead of config files for IBKR connection settings.

---

**🍁 CrisisCore AutoTrader - Canadian Markets Integration**  
**Last Updated:** 2025-10-20

**Ready to validate your connection?**  
Run: `python scripts\ibkr_smoke_test.py`
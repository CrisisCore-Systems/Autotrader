# IBKR TWS Connection Setup - Quick Reference

**Tactical checklist to prove you're wired into TWS via the API.**

---

## 1. TWS API Configuration

### Global Configuration → API → Settings

Open TWS, then: **File → Global Configuration → API → Settings**

Required settings:

- ✅ **Enable ActiveX and Socket Clients**
- ✅ **Download open orders on connection**
- ✅ **Include FX in portfolio/positions** (optional)
- ✅ **Show API messages in log** (useful for debugging)
- ❌ **Read-only API** → **MUST BE OFF** (to place/cancel orders)

**Socket Port:**
- **7497** = TWS Paper (DU... account)
- **7496** = TWS Live (U... account)
- **4002** = Gateway Paper
- **4001** = Gateway Live

**Trusted IPs:**
- Add: `127.0.0.1` (localhost)
- Add your LAN IP if connecting from another machine

**(Optional) Use SSL:**
- Turn ON for encrypted connection (match in client code)

### Global Configuration → API → Precautions

- Uncheck any prompts that would block orders
- You can leave protective prompts on while learning

### Restart TWS

**CRITICAL:** Restart TWS after changing API settings.

---

## 2. Verify TWS Connection

### From TWS Status Bar

Bottom status line / log will show when client connects:
```
Accepted incoming connection from 127.0.0.1 with clientId X
```

### From TWS Logs

**View → Logs → API** - Watch messages scroll as your client connects/disconnects.

---

## 3. Python Smoke Test

### Quick Installation

```powershell
# Should already be installed from Canadian migration
pip install ib-insync
```

### Run Smoke Test

```powershell
cd C:\Users\kay\Documents\Projects\AutoTrader\Autotrader
python scripts\ibkr_smoke_test.py
```

### What "Working" Looks Like

**Terminal output:**
```
✓ Connected: True
✓ Server Version: 178
✓ Account: DU123456
✓ AAPL last: $178.45
✓ Order placed: PreSubmitted
✓ Order canceled: Cancelled
```

**TWS Mosaic:**
- Test order appears briefly
- Order then disappears (canceled)

**TWS Log:**
- "Accepted incoming connection from 127.0.0.1"
- Order submission messages
- Order cancellation messages

---

## 4. Production CLI Harness

### Test Connection

```powershell
python scripts\ibkr_connector.py --ping
```

### Get Account Summary

```powershell
python scripts\ibkr_connector.py --account
```

### Show Current Positions

```powershell
python scripts\ibkr_connector.py --positions
```

### Show Open Orders

```powershell
python scripts\ibkr_connector.py --orders
```

### Get Quote

```powershell
python scripts\ibkr_connector.py --quote AAPL
python scripts\ibkr_connector.py --quote SHOP.TO  # Canadian stock
```

### Place Test Order

```powershell
python scripts\ibkr_connector.py --place-test
```

### Cancel All Orders

```powershell
python scripts\ibkr_connector.py --cancel-all
```

---

## 5. Common Blockers - Fast Triage

### No Connection / Timeouts

**Symptoms:**
- `Connection refused`
- `Timeout after 10 seconds`

**Causes:**
- ❌ Wrong port (paper=7497, live=7496)
- ❌ TWS not running or not logged in
- ❌ Firewall blocking `javaw.exe` or `TWS.exe`
- ❌ `127.0.0.1` not in Trusted IPs

**Fix:**
1. Verify TWS is running and logged in
2. Check port: 7497 for paper, 7496 for live
3. Add `127.0.0.1` to Trusted IPs
4. Allow TWS through Windows Firewall
5. Restart TWS after changes

### Code Connects But Orders Ignored

**Symptoms:**
- Connection succeeds
- Account data loads
- Orders don't appear in TWS

**Causes:**
- ❌ `Read-only API` is ON
- ❌ Precaution prompts blocking orders

**Fix:**
1. **File → Global Configuration → API → Settings**
2. **UNCHECK** "Read-only API"
3. **File → Global Configuration → API → Precautions**
4. Disable blocking prompts
5. Restart TWS

### Client ID Clash

**Symptoms:**
- Error: "Client ID already in use"

**Causes:**
- ❌ Multiple clients using same ID
- ❌ TWS own UI using the ID

**Fix:**
Use a different client ID in your code:
```powershell
$env:IBKR_CLIENT_ID="43"
python scripts\ibkr_smoke_test.py
```

### No Market Data

**Symptoms:**
- `ticker.last = NaN`
- `ticker.close = NaN`

**Causes:**
- ❌ Paper accounts often have delayed data
- ❌ Market closed
- ❌ No data subscription

**Fix:**
- Use `snapshot=True` for delayed data (OK for testing)
- Paper accounts simulate fills anyway
- For live trading, subscribe to market data

### Error Codes

Common IBKR error codes:

| Code | Meaning | Fix |
|------|---------|-----|
| 1100 | Connection to IB servers lost | Wait for reconnection |
| 1101 | Connection restored | No action needed |
| 1102 | Connectivity between IB and server restored | No action needed |
| 201 | Order rejected | Check order parameters |
| 202 | Order canceled | Requested cancellation |
| 354 | Market data farm connection OK but delayed | Use snapshot=True |

---

## 6. Environment Variables Reference

```powershell
# Default values (TWS Paper)
$env:IBKR_HOST="127.0.0.1"
$env:IBKR_PORT="7497"      # 7497=TWS Paper, 7496=TWS Live
$env:IBKR_CLIENT_ID="42"   # Any unique integer
$env:USE_PAPER="1"         # 1=paper, 0=live
$env:BROKER_NAME="ibkr"

# Example: Connect to Gateway Paper
$env:IBKR_PORT="4002"
python scripts\ibkr_smoke_test.py

# Example: Use different client ID
$env:IBKR_CLIENT_ID="99"
python scripts\ibkr_connector.py --ping
```

---

## 7. Quick Sanity Checklist

Print this and check off each item:

- [ ] TWS running & logged in to **Paper** account (DU...)
- [ ] **File → Global Configuration → API → Settings** opened
- [ ] `Enable ActiveX and Socket Clients` ✅ CHECKED
- [ ] Port **7497** set (for TWS paper)
- [ ] `127.0.0.1` in **Trusted IPs**
- [ ] `Read-only API` ❌ **UNCHECKED** (OFF)
- [ ] TWS **restarted** after settings changed
- [ ] Python environment activated (`.venv-1\Scripts\Activate.ps1`)
- [ ] `ib-insync` installed (`pip install ib-insync`)
- [ ] Smoke test runs: `python scripts\ibkr_smoke_test.py`
- [ ] Terminal shows `Connected: True`
- [ ] Test order appears in TWS Mosaic
- [ ] Test order gets canceled
- [ ] TWS log shows "Accepted incoming connection ... clientId X"

---

## 8. Next Steps After Connection Proven

Once smoke test passes:

### 1. Run Full IBKR Tests

```powershell
python scripts\test_paper_trading_ibkr.py
```

Tests:
- ✓ Configuration loading
- ✓ IBKR broker connectivity
- ✓ Yahoo VIX provider
- ✓ Market regime detector
- ✓ Adjustment calculations

### 2. Deploy Paper Trading Bot

```powershell
python scripts\run_pennyhunter_paper.py
```

### 3. Monitor Adjustments

```powershell
python scripts\monitor_adjustments.py
```

### 4. Generate Reports

```powershell
python scripts\generate_weekly_report.py
```

---

## 9. Logs Location

All IBKR connector activity logged to:

```
C:\Users\kay\Documents\Projects\AutoTrader\Autotrader\logs\ibkr_connector_YYYYMMDD.log
```

Review logs if issues occur.

---

## 10. Support Resources

### Official IBKR API Documentation
- https://interactivebrokers.github.io/tws-api/

### ib-insync Documentation
- https://ib-insync.readthedocs.io/

### CrisisCore Documentation
- `docs/IBKR_SETUP_GUIDE.md` - Comprehensive setup
- `docs/QUICK_START_CANADA.md` - 10-minute quick start
- `docs/CANADIAN_MIGRATION_COMPLETE.md` - Migration summary

### Troubleshooting
If stuck, check:
1. TWS logs (View → Logs → API)
2. Python logs (`logs/ibkr_connector_*.log`)
3. Windows Event Viewer (firewall issues)
4. IBKR support forums

---

## Summary

**3-Step Validation:**

1. **Configure TWS** (5 min)
   - Enable API, set port 7497, add 127.0.0.1, disable read-only
   - Restart TWS

2. **Run Smoke Test** (2 min)
   - `python scripts\ibkr_smoke_test.py`
   - Should print "SMOKE TEST PASSED"

3. **Verify in TWS** (1 min)
   - Check status bar: "Accepted incoming connection"
   - Check Mosaic: Test order appeared then canceled
   - Check logs: API connection messages

**Total time: ~10 minutes**

Once validated, proceed to full paper trading deployment.

---

**Last Updated:** 2025-10-20  
**For:** CrisisCore AutoTrader - Canadian Markets Integration

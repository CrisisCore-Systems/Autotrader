# IBKR TWS API - One Page Reference Card

**Print this and keep by your desk for quick troubleshooting.**

---

## Connection Ports

| Platform | Mode  | Port |
|----------|-------|------|
| TWS      | Paper | 7497 |
| TWS      | Live  | 7496 |
| Gateway  | Paper | 4002 |
| Gateway  | Live  | 4001 |

---

## TWS Configuration (Critical Settings)

**File → Global Configuration → API → Settings**

| Setting | Required Value |
|---------|----------------|
| Enable ActiveX and Socket Clients | ✅ CHECKED |
| Read-only API | ❌ UNCHECKED (OFF) |
| Download open orders on connection | ✅ CHECKED |
| Trusted IPs | 127.0.0.1 |
| Socket port | 7497 (paper) |

**⚠️ MUST RESTART TWS AFTER CHANGES**

---

## Quick Validation Commands

```powershell
# Smoke test (full end-to-end)
python scripts\ibkr_smoke_test.py

# Test connection only
python scripts\ibkr_connector.py --ping

# Show account
python scripts\ibkr_connector.py --account

# Show positions
python scripts\ibkr_connector.py --positions

# Test order placement
python scripts\ibkr_connector.py --place-test
```

---

## Environment Variables

```powershell
$env:IBKR_HOST="127.0.0.1"
$env:IBKR_PORT="7497"      # 7497=TWS Paper
$env:IBKR_CLIENT_ID="42"   # Any unique int
```

---

## Success Indicators

✓ Terminal: `Connected: True`  
✓ TWS Status: `Accepted incoming connection from 127.0.0.1`  
✓ TWS Mosaic: Test order appears then cancels  
✓ TWS Logs: API connection messages visible  

---

## Common Errors & Fixes

| Error | Cause | Fix |
|-------|-------|-----|
| Connection refused | TWS not running | Start TWS, log in |
| Connection refused | Wrong port | Use 7497 for TWS paper |
| Timeout | Firewall | Allow javaw.exe/TWS.exe |
| No incoming connection | Trusted IPs | Add 127.0.0.1 |
| Orders ignored | Read-only API ON | Turn OFF read-only |
| Client ID in use | ID clash | Change CLIENT_ID |

---

## Error Code Quick Reference

| Code | Meaning |
|------|---------|
| 1100 | IB server connection lost (wait for restore) |
| 1101 | Connection restored |
| 1102 | Server connectivity restored |
| 201  | Order rejected (check params/permissions) |
| 202  | Order canceled |
| 354  | Delayed market data (use snapshot=True) |

---

## 3-Step Validation (10 minutes)

1. **Configure TWS** (5 min)
   - Enable API ✅
   - Port 7497 ✅
   - Add 127.0.0.1 ✅
   - Read-only OFF ❌
   - Restart TWS ✅

2. **Run Smoke Test** (2 min)
   ```powershell
   python scripts\ibkr_smoke_test.py
   ```
   Should print: `✅ SMOKE TEST PASSED`

3. **Verify in TWS** (1 min)
   - Status bar: "Accepted incoming connection"
   - Mosaic: Test order appeared & canceled
   - Logs: API messages visible

---

## Canadian Stocks

| Exchange | Symbol Format | Example |
|----------|---------------|---------|
| TSX      | SYMBOL.TO     | SHOP.TO |
| TSXV     | SYMBOL.V      | NUMI.V  |

System auto-detects Canadian stocks and sets:
- Exchange: TSE or VENTURE
- Currency: CAD

---

## Logs Location

```
C:\Users\kay\Documents\Projects\AutoTrader\Autotrader\logs\
ibkr_connector_YYYYMMDD.log
```

---

## Support Docs

- `IBKR_CONNECTION_QUICK_REF.md` - Full troubleshooting
- `IBKR_SETUP_GUIDE.md` - Comprehensive setup
- `QUICK_START_CANADA.md` - 10-min deployment guide

---

## Firewall Rule (Windows)

If connection fails:

1. Windows Security → Firewall → Allow an app
2. Find: `javaw.exe` (Java platform for TWS)
3. Allow: Private ✅ Public ✅
4. Find: `TWS.exe` (TWS itself)
5. Allow: Private ✅ Public ✅

Or PowerShell (run as admin):
```powershell
netsh advfirewall firewall add rule name="IBKR TWS" dir=in action=allow program="C:\Jts\tws\tws.exe" enable=yes
```

---

## Quick Checklist

- [ ] TWS running & logged in (paper account)
- [ ] API enabled (File → Config → API → Settings)
- [ ] Port 7497 configured
- [ ] 127.0.0.1 in Trusted IPs
- [ ] Read-only API is OFF
- [ ] TWS restarted after changes
- [ ] Python env activated (`.venv-1`)
- [ ] Smoke test passes
- [ ] Test order appeared in TWS
- [ ] TWS log shows connection

---

**🍁 CrisisCore AutoTrader - Canadian Markets**  
**Last Updated:** 2025-10-20

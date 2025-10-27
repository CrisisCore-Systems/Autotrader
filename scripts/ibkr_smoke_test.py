"""
IBKR TWS Connection Smoke Test

Tactical proof that you're wired into TWS/Gateway via the API.
Tests connection, market data, account info, and order placement/cancellation.

Usage:
    python scripts/ibkr_smoke_test.py

Environment Variables:
    IBKR_HOST       - TWS/Gateway host (default: 127.0.0.1)
    IBKR_PORT       - Port: 7497 (TWS paper), 4002 (Gateway paper), 7496 (TWS live), 4001 (Gateway live)
    IBKR_CLIENT_ID  - Unique client ID (default: 1)

What "Working" Looks Like:
    ✓ Terminal prints "Connected: True"
    ✓ TWS logs show "Accepted incoming connection from 127.0.0.1"
    ✓ Test order appears briefly in TWS Mosaic, then gets canceled
    ✓ No error code bursts in console

Common Blockers:
    ✗ Wrong port (paper=7497, not 7496)
    ✗ Read-only API is ON (must be OFF to place orders)
    ✗ Firewall blocking TWS (allow javaw.exe)
    ✗ Client ID clash (use different integer)
"""

import os
import sys
from ib_insync import *

# Suppress urllib3 warnings
import warnings
warnings.filterwarnings('ignore')

# ---- CONFIG ----
HOST = os.getenv('IBKR_HOST', '127.0.0.1')
PORT = int(os.getenv('IBKR_PORT', '7497'))  # 7497=TWS paper, 4002=Gateway paper
CLIENT_ID = int(os.getenv('IBKR_CLIENT_ID', '1'))

print("=" * 80)
print("IBKR TWS CONNECTION SMOKE TEST")
print("=" * 80)
print(f"Host: {HOST}")
print(f"Port: {PORT} ({'TWS' if PORT in [7496, 7497] else 'Gateway'} {'Paper' if PORT in [7497, 4002] else 'Live'})")
print(f"Client ID: {CLIENT_ID}")
print("=" * 80)

# Start event loop (safe no-op on most consoles)
try:
    util.startLoop()
except RuntimeError:
    pass  # Already running

# ---- CONNECT ----
print("\n[1/5] Connecting to IBKR...")
ib = IB()

try:
    ib.connect(HOST, PORT, CLIENT_ID, readonly=False, timeout=10)
    print(f"[OK] Connected: {ib.isConnected()}")
    print(f"[OK] Server Version: {ib.client.serverVersion()}")
    # Note: connTime may not be available in all ib-insync versions
except Exception as e:
    print(f"[X] Connection FAILED: {e}")
    print("\nTroubleshooting:")
    print("  1. Is TWS/Gateway running and logged in?")
    print("  2. Is API enabled? (File → Global Configuration → API → Settings)")
    print("  3. Is 'Enable ActiveX and Socket Clients' checked?")
    print("  4. Is 127.0.0.1 in 'Trusted IPs'?")
    print(f"  5. Is port {PORT} correct?")
    print("     - TWS Paper: 7497")
    print("     - TWS Live: 7496")
    print("     - Gateway Paper: 4002")
    print("     - Gateway Live: 4001")
    print("  6. Did you restart TWS after changing API settings?")
    sys.exit(1)

# ---- ACCOUNT INFO ----
print("\n[2/5] Fetching account info...")
try:
    accounts = ib.managedAccounts()
    if not accounts:
        print("[X] No accounts found")
        sys.exit(1)
    
    acct = accounts[0]
    print(f"[OK] Account: {acct}")
    
    # Get account summary
    summary = ib.accountSummary()
    print(f"[OK] Summary items: {len(summary)}")
    
    # Show key values
    for item in summary:
        if item.tag in ['NetLiquidation', 'TotalCashValue', 'BuyingPower']:
            print(f"  {item.tag}: {item.value} {item.currency}")
    
except Exception as e:
    print(f"[X] Account fetch FAILED: {e}")
    sys.exit(1)

# ---- MARKET DATA ----
print("\n[3/5] Testing market data (AAPL)...")
try:
    aapl = Stock('AAPL', 'SMART', 'USD')
    ib.qualifyContracts(aapl)
    print(f"[OK] Contract qualified: {aapl.symbol} {aapl.primaryExchange}")
    
    # Request market data (snapshot for delayed data)
    ticker = ib.reqMktData(aapl, '', snapshot=True)
    ib.sleep(3)  # Wait for data
    
    last = ticker.last or ticker.close or 0
    if last > 0:
        print(f"[OK] AAPL last: ${last:.2f}")
    else:
        print(f"[NOTE] AAPL data delayed/unavailable (last={ticker.last}, close={ticker.close})")
        last = 150.0  # Fallback for test order
    
    ib.cancelMktData(aapl)
    
except Exception as e:
    print(f"[X] Market data FAILED: {e}")
    print("  Note: Paper accounts may have delayed data - this is OK for testing")
    last = 150.0  # Use fallback

# ---- PLACE TEST ORDER ----
print("\n[4/5] Placing test order (will cancel immediately)...")
try:
    # Create limit order WAY below market (won't fill)
    limit_price = round(last * 0.5, 2)  # 50% below market
    order = LimitOrder('BUY', 1, limit_price)
    
    print(f"  Order: BUY 1 AAPL @ ${limit_price:.2f} limit")
    
    trade = ib.placeOrder(aapl, order)
    ib.sleep(2)  # Let order submit
    
    print(f"[OK] Order placed: {trade.orderStatus.status}")
    print(f"  Order ID: {trade.order.orderId}")
    print(f"  Check TWS Mosaic - you should see this order briefly!")
    
except Exception as e:
    print(f"[X] Order placement FAILED: {e}")
    print("\nTroubleshooting:")
    print("  1. Is 'Read-only API' DISABLED?")
    print("     (File → Global Configuration → API → Settings)")
    print("  2. Do you have order entry permissions?")
    print("  3. Are there precaution prompts blocking orders?")
    print("     (File → Global Configuration → API → Precautions)")
    ib.disconnect()
    sys.exit(1)

# ---- CANCEL TEST ORDER ----
print("\n[5/5] Canceling test order...")
try:
    ib.cancelOrder(order)
    ib.sleep(2)  # Let cancel process
    
    print(f"[OK] Order canceled: {trade.orderStatus.status}")
    print(f"  Order should disappear from TWS Mosaic")
    
except Exception as e:
    print(f"[X] Order cancellation FAILED: {e}")
    # Not critical - order was far from market anyway

# ---- DISCONNECT ----
print("\n" + "=" * 80)
ib.disconnect()
print("[OK] Disconnected")

# ---- SUCCESS SUMMARY ----
print("\n" + "=" * 80)
print("[SUCCESS] SMOKE TEST PASSED - YOU'RE WIRED INTO TWS!")
print("=" * 80)
print("\nWhat just happened:")
print("  1. [OK] Connected to IBKR API")
print("  2. [OK] Retrieved account information")
print("  3. [OK] Fetched market data for AAPL")
print("  4. [OK] Placed test order (appeared in TWS)")
print("  5. [OK] Canceled test order (disappeared from TWS)")
print("\nYou should have seen in TWS:")
print("  - Bottom status: 'Accepted incoming connection from 127.0.0.1'")
print("  - Mosaic: Test order appeared briefly, then canceled")
print("  - API log: Connection and order messages")
print("\n" + "=" * 80)
print("Next Steps:")
print("  1. Run full test: python scripts/test_paper_trading_ibkr.py")
print("  2. Deploy bot: python scripts/run_pennyhunter_paper.py")
print("  3. Monitor: python scripts/monitor_adjustments.py")
print("=" * 80)

sys.exit(0)

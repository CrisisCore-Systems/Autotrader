#!/usr/bin/env python3
"""
IBKR FA Scrubbing Test - Following user's exact pattern
"""

from ib_insync import *

HOST, PORT, CLIENT = "127.0.0.1", 7497, 7
ib = IB()
ib.connect(HOST, PORT, clientId=CLIENT)

acct = "DU0071381"  # Explicit account ID
print("Account:", acct)

# Sanity: confirm TWS has no FA artifacts
print("FA groups:", ib.requestFA(1))        # 1=Groups
print("FA profiles:", ib.requestFA(2))      # 2=Profiles
print("FA aliases:", ib.requestFA(3))       # 3=Aliases

def scrub_fa(order: Order):
    # Wipe every advisor field
    for k in ("faGroup","faProfile","faMethod","faPercentage","account"):
        setattr(order, k, None)
    order.account = acct                     # explicit account target

# Test: clean order without FA
contract = Stock("AAPL","SMART","USD")
ib.qualifyContracts(contract)

# Simple market order test
order = MarketOrder("BUY", 1)
scrub_fa(order)

print("Order FA fields after scrubbing:")
for field in ["faGroup", "faProfile", "faMethod", "faPercentage", "account"]:
    value = getattr(order, field, "NOT_SET")
    print(f"  {field}: {value}")

# Try to place the order
try:
    trade = ib.placeOrder(contract, order)
    print("✅ Order placed successfully!")
    print(f"Order ID: {trade.order.orderId}")
except Exception as e:
    print(f"❌ Order failed: {e}")

ib.disconnect()
print("Disconnected.")
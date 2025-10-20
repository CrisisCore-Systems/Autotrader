#!/usr/bin/env python3
"""
IBKR Paper Trading Smoke Test

Clean test that connects to IBKR, fetches account data reliably,
and places a tiny test order without FA fields.

Based on the fix for:
- "Group name cannot be null" (FA allocation fields)
- "positions/account updates timed out" (async data fetching)

Usage:
    python ibkr_smoke_test.py
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from ib_insync import IB, Stock, MarketOrder

HOST = '127.0.0.1'
PORT = 7497          # paper
CLIENT_ID = 1

async def main():
    print("🔗 IBKR Paper Trading Smoke Test")
    print("=" * 40)

    ib = IB()
    try:
        # Connect
        ib.connect(HOST, PORT, clientId=CLIENT_ID)
        print("✅ Connected to IBKR")

        # 1) Discover account ID
        accounts = ib.managedAccounts()
        assert accounts, "No accounts returned"
        acct = accounts[0]  # e.g., 'DU0071381'
        print(f"📊 Account: {acct}")

        # 2) Reliable account summary
        tags = ['NetLiquidation', 'TotalCashValue', 'AvailableFunds']
        vals = await ib.accountSummaryAsync(acct)
        snap = {v.tag: v.value for v in vals if v.tag in tags}
        print(f"💰 Account Summary: {snap}")

        # 3) Positions
        positions = await ib.reqPositionsAsync()
        acct_positions = [p for p in positions if p.account == acct]
        print(f"📈 Positions: {len(acct_positions)}")
        for p in acct_positions[:3]:  # Show first 3
            print(f"   {p.contract.symbol}: {p.position} @ ${p.avgCost:.2f}")

        # 4) Tiny test trade (1 share) - NO FA fields
        print("\n🛒 Placing tiny test trade...")
        contract = Stock('AAPL', 'SMART', 'USD')
        [contract] = await ib.qualifyContractsAsync(contract)

        order = MarketOrder('BUY', 1)  # Just 1 share for testing
        order.account = acct            # Explicitly target account (no FA groups)

        trade = ib.placeOrder(contract, order)
        await trade.completedEvent.wait(timeout=10)  # Wait for completion

        print(f"✅ Order placed: {trade.order.orderId}")
        print(f"   Status: {trade.orderStatus.status}")
        print(f"   Filled: {trade.orderStatus.filled}")

        # Clean up - cancel if not filled
        if trade.orderStatus.status not in ['Filled', 'Cancelled']:
            ib.cancelOrder(trade.order)
            print("🧹 Cancelled test order")

        print("\n🎉 Smoke test passed! IBKR integration working correctly.")

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        ib.disconnect()
        print("🔌 Disconnected from IBKR")

    return True

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
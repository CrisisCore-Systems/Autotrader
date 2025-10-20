#!/usr/bin/env python3
"""
Test IBKR Order Placement with FA Scrubbing
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from bouncehunter.broker import create_broker

def test_order_placement():
    """Test actual order placement with FA scrubbing."""
    print("🔗 Testing IBKR Order Placement with FA Scrubbing...")
    print("-" * 50)

    try:
        # Create broker
        broker = create_broker("ibkr")
        print("✅ Broker created")

        # Test market order (should work with FA scrubbing)
        print("\n📈 Testing Market Order...")
        order = broker.place_order(
            ticker="AAPL",
            side="BUY",  # Using string for simplicity
            quantity=1,
            order_type="MARKET"
        )
        print(f"✅ Market order placed: {order.order_id}")
        print(f"   Status: {order.status}")
        print(f"   Ticker: {order.ticker}")
        print(f"   Quantity: {order.quantity}")

        # Test limit order
        print("\n📊 Testing Limit Order...")
        limit_order = broker.place_order(
            ticker="MSFT",
            side="BUY",
            quantity=1,
            order_type="LIMIT",
            limit_price=400.00
        )
        print(f"✅ Limit order placed: {limit_order.order_id}")
        print(f"   Status: {limit_order.status}")
        print(f"   Ticker: {limit_order.ticker}")
        print(f"   Limit Price: ${limit_order.limit_price}")

        print("\n🎉 All order tests passed! FA scrubbing is working.")
        return True

    except Exception as e:
        print(f"❌ Order test failed: {e}")
        return False

if __name__ == "__main__":
    success = test_order_placement()
    sys.exit(0 if success else 1)
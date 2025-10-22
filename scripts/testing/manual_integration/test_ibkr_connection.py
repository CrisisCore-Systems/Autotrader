#!/usr/bin/env python3
"""
Quick IBKR Connection Test

Run this to verify your IBKR paper trading setup is working.

Usage:
    python test_ibkr_connection.py
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

try:
    from bouncehunter.broker import create_broker
    print("✅ AutoTrader imports successful")
except ImportError as e:
    print(f"❌ Import failed: {e}")
    sys.exit(1)

def test_connection():
    """Test IBKR connection."""
    print("\n🔗 Testing IBKR Connection...")
    print("-" * 30)

    try:
        # Create broker using config file
        broker = create_broker("ibkr")
        print("✅ Broker created successfully")

        # Test account access with async methods
        account = broker.get_account()
        print("✅ Account access successful")
        print(f"Account Value: ${account.portfolio_value:,.2f}")
        print(f"Cash: ${account.cash:,.2f}")
        print(f"Buying Power: ${account.buying_power:,.2f}")
        print(f"Positions: {len(account.positions)}")
        return True

    except Exception as e:
        print(f"❌ Connection failed: {e}")
        print("\n🔧 Troubleshooting:")
        print("1. Ensure TWS is running on port 7497")
        print("2. Enable API in TWS: Configure > API Settings")
        print("3. UNCHECK 'Use Account Groups with Allocation Methods'")
        print("4. Check ib_insync is installed")
        return False

if __name__ == "__main__":
    success = test_connection()
    sys.exit(0 if success else 1)
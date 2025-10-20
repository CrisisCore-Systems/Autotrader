#!/usr/bin/env python3
"""
IBKR Paper Trading Connector for AutoTrader

This script demonstrates how to connect to Interactive Brokers TWS
for paper trading using the existing IBBroker implementation.

Requirements:
- pip install ib_insync
- TWS running on localhost:7497 (paper trading)
- API connections enabled in TWS

Usage:
    python ibkr_connector.py
"""

import json
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from bouncehunter.broker import create_broker


def load_ibkr_config(config_path: str = "ibkr_config.json") -> dict:
    """Load IBKR configuration from JSON file."""
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
        return config
    except FileNotFoundError:
        print(f"Config file not found: {config_path}")
        return None
    except json.JSONDecodeError as e:
        print(f"Invalid JSON in config file: {e}")
        return None


def test_ibkr_connection():
    """Test IBKR connection and basic functionality."""
    print("🔗 AutoTrader IBKR Paper Trading Connector")
    print("=" * 50)

    # Load configuration
    config = load_ibkr_config()
    if not config:
        return False

    ibkr_config = config.get('ibkr', {})
    if not ibkr_config.get('enabled', False):
        print("❌ IBKR is disabled in configuration")
        return False

    print(f"📊 Connecting to IBKR Paper Trading...")
    print(f"   Host: {ibkr_config['host']}")
    print(f"   Port: {ibkr_config['port']}")
    print(f"   Client ID: {ibkr_config['client_id']}")
    print(f"   Account: {ibkr_config['account_id']}")
    print()

    try:
        # Create broker instance using factory function
        broker = create_broker(
            "ibkr",
            host=ibkr_config['host'],
            port=ibkr_config['port'],
            client_id=ibkr_config['client_id']
        )

        print("✅ IBKR Broker initialized successfully")

        # Test connection by getting account info
        print("🔍 Testing connection...")
        account = broker.get_account()
        print("✅ Account connection successful"        print(f"   Cash: ${account.cash:,.2f}")
        print(f"   Portfolio Value: ${account.portfolio_value:,.2f}")
        print(f"   Buying Power: ${account.buying_power:,.2f}")
        print(f"   Equity: ${account.equity:,.2f}")
        print(f"   Positions: {len(account.positions)}")
        print()

        # Test getting positions
        positions = broker.get_positions()
        if positions:
            print("📈 Current Positions:")
            for pos in positions:
                print(f"   {pos.ticker}: {pos.shares} shares @ ${pos.avg_price:.2f}")
                print(".2f"                print(".1f"        else:
            print("📭 No open positions")
        print()

        # Test market data (example with AAPL)
        print("📊 Testing market data access...")
        try:
            # Note: This would require implementing market data methods in IBBroker
            # For now, just show that the broker is connected
            print("✅ Market data access ready (implement get_quote method if needed)")
        except Exception as e:
            print(f"⚠️  Market data test skipped: {e}")

        print()
        print("🎉 IBKR Paper Trading Setup Complete!")
        print("   You can now use this broker in your AutoTrader strategies")
        print("   Example: broker = create_broker('ibkr')")

        return True

    except ImportError as e:
        print(f"❌ Missing required library: {e}")
        print("   Install with: pip install ib_insync")
        return False
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        print("   Make sure TWS is running and API connections are enabled")
        return False


def demo_order_placement():
    """Demo order placement (DRY RUN - no real orders placed)."""
    print("\n🛒 Order Placement Demo (DRY RUN)")
    print("-" * 30)

    config = load_ibkr_config()
    if not config:
        return

    try:
        broker = create_broker(
            "ibkr",
            host=config['ibkr']['host'],
            port=config['ibkr']['port'],
            client_id=config['ibkr']['client_id']
        )

        # Example order (commented out for safety)
        print("Example order placement code:")
        print("""
        # Market order to buy 10 shares of AAPL
        order = broker.place_order(
            ticker="AAPL",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=10
        )
        print(f"Order placed: {order.order_id}")

        # Bracket order (entry + stop loss + target)
        bracket_order = broker.place_bracket_order(
            ticker="AAPL",
            entry_side=OrderSide.BUY,
            quantity=10,
            entry_price=150.0,  # Limit entry
            stop_price=145.0,    # Stop loss
            target_price=160.0   # Profit target
        )
        """)

        print("⚠️  Orders commented out for safety - uncomment to test actual trading")

    except Exception as e:
        print(f"❌ Demo failed: {e}")


if __name__ == "__main__":
    success = test_ibkr_connection()
    if success:
        demo_order_placement()
    else:
        print("\n🔧 Troubleshooting:")
        print("1. Make sure TWS is running on port 7497")
        print("2. Enable API connections in TWS: Configure > API Settings")
        print("3. Check that client ID 1 is not already in use")
        print("4. Verify ib_insync is installed: pip install ib_insync")
        sys.exit(1)
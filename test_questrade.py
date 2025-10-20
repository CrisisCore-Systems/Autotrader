"""Test Questrade connection with your refresh token."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from bouncehunter.broker import create_broker

def test_questrade_connection():
    """Test Questrade broker connection."""
    print("=" * 60)
    print(" QUESTRADE CONNECTION TEST")
    print("=" * 60)
    print()
    
    try:
        # Create broker (will auto-load credentials from YAML)
        print("📡 Connecting to Questrade...")
        broker = create_broker("questrade")
        print("✅ Broker created successfully!")
        print()
        
        # Test account balance
        print("💰 Fetching account balance...")
        balance = broker.get_account_balance()
        print(f"✅ Account Balance: ${balance:,.2f}")
        print()
        
        # Test positions
        print("📊 Fetching current positions...")
        positions = broker.get_positions()
        if positions:
            print(f"✅ Found {len(positions)} position(s):")
            for pos in positions:
                print(f"   - {pos.ticker}: {pos.shares} shares @ ${pos.avg_price:.2f}")
                print(f"     Current: ${pos.current_price:.2f} | P&L: ${pos.unrealized_pnl:+,.2f} ({pos.unrealized_pnl_pct:+.2f}%)")
        else:
            print("✅ No open positions (ready to trade!)")
        print()
        
        print("=" * 60)
        print(" ✅ ALL TESTS PASSED!")
        print("=" * 60)
        print()
        print("Your Questrade integration is working correctly!")
        print("Next steps:")
        print("  1. Review TFSA config: configs/canadian_tfsa.yaml")
        print("  2. Run a test scan: python src/bouncehunter/agentic_cli.py --broker questrade --dry-run")
        print("  3. Check full docs: docs/CANADIAN_BROKERS.md")
        
        return True
        
    except FileNotFoundError as e:
        print("❌ ERROR: Credentials file not found")
        print(f"   {e}")
        print()
        print("   Solution: Your refresh token is already saved in:")
        print("             configs/broker_credentials.yaml")
        return False
        
    except KeyError as e:
        print("❌ ERROR: Missing credential")
        print(f"   {e}")
        return False
        
    except Exception as e:
        print(f"❌ ERROR: Connection failed")
        print(f"   Type: {type(e).__name__}")
        print(f"   Message: {e}")
        print()
        print("   Common causes:")
        print("   - Refresh token expired (check expiry: Oct 24, 2025)")
        print("   - API access not enabled in Questrade account")
        print("   - Network connectivity issues")
        print()
        print("   Next steps:")
        print("   1. Check token in configs/broker_credentials.yaml")
        print("   2. Verify API access in Questrade Account Management")
        print("   3. See troubleshooting: QUESTRADE_SETUP.md")
        return False

if __name__ == "__main__":
    success = test_questrade_connection()
    sys.exit(0 if success else 1)

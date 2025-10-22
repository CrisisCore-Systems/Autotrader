"""Quick test of Yahoo VIX provider - works immediately, no IBKR setup needed"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from core.providers.vix.yahoo_vix_provider import YahooVIXProvider

print("=" * 60)
print("Testing Yahoo VIX Provider (No IBKR Required)")
print("=" * 60)

try:
    provider = YahooVIXProvider()
    print("[OK] Provider initialized")
    
    # Check availability
    available = provider.is_available()
    print(f"[OK] API Status: {'Available' if available else 'Degraded'}")
    
    # Get VIX
    vix = provider.get_vix()
    print(f"[OK] Current VIX: {vix:.2f}")
    
    # Get volatility level
    level = provider.get_volatility_level(vix)
    print(f"[OK] Volatility Level: {level}")
    
    # Classification
    if vix < 15:
        desc = "LOW (calm market)"
    elif vix < 25:
        desc = "NORMAL"
    elif vix < 35:
        desc = "HIGH (elevated volatility)"
    else:
        desc = "EXTREME (crisis mode)"
    
    print(f"[OK] Market State: {desc}")
    
    print("=" * 60)
    print("✅ Yahoo VIX Provider Working!")
    print("=" * 60)
    print()
    print("Next Steps:")
    print("1. Review docs/QUICK_START_CANADA.md")
    print("2. Set up IBKR TWS/Gateway (see docs/IBKR_SETUP_GUIDE.md)")
    print("3. Run: python scripts/test_paper_trading_ibkr.py")
    
except Exception as e:
    print(f"[X] Error: {e}")
    print()
    print("Troubleshooting:")
    print("- Check internet connection")
    print("- Verify yfinance installed: pip install yfinance")
    print("- Try again in a few seconds (Yahoo rate limit)")

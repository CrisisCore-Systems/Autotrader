#!/usr/bin/env python
"""
Quick verification script for CLI enhancements.
Run: python verify_cli.py
"""

import sys

def main():
    print("=" * 60)
    print("AutoTrader CLI Enhancements - Quick Verification")
    print("=" * 60)
    print()
    
    # Check main CLI is available
    try:
        from src.cli.main import cli_main
        print("✅ CLI main module available")
    except ImportError as e:
        print(f"❌ Cannot import CLI: {e}")
        return 1
    
    # Check all modules
    modules = [
        "src.cli.config",
        "src.cli.metrics", 
        "src.cli.runtime",
        "src.cli.plugins",
        "src.cli.deterministic",
        "src.cli.exit_codes",
    ]
    
    print("\nChecking CLI modules:")
    for module in modules:
        try:
            __import__(module)
            print(f"  ✅ {module}")
        except ImportError as e:
            print(f"  ❌ {module}: {e}")
            return 1
    
    # Check pyproject.toml entry
    print("\nChecking entry points:")
    try:
        from importlib.metadata import entry_points
        eps = entry_points()
        if hasattr(eps, 'select'):
            scripts = eps.select(group='console_scripts')
        else:
            scripts = eps.get('console_scripts', [])
        
        found = False
        for ep in scripts:
            if ep.name == 'autotrader-scan':
                print(f"  ✅ autotrader-scan → {ep.value}")
                found = True
                break
        
        if not found:
            print("  ⚠️  autotrader-scan not registered (run: pip install -e .)")
    except Exception as e:
        print(f"  ⚠️  Could not check entry points: {e}")
    
    print("\n" + "=" * 60)
    print("✅ CLI enhancements installed successfully!")
    print("=" * 60)
    print()
    print("Next steps:")
    print("  1. Review CLI_GUIDE.md for full documentation")
    print("  2. Try: autotrader-scan --help")
    print("  3. Try: autotrader-scan --list-strategies")
    print("  4. Try: autotrader-scan --list-exit-codes")
    print("  5. Try: autotrader-scan --config configs/example.yaml --dry-run")
    print()
    
    return 0

if __name__ == "__main__":
    sys.exit(main())

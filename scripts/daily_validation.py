#!/usr/bin/env python3
"""
Simple wrapper script to run daily paper trading and check validation status.

This combines the two steps into one command for convenience.

Usage:
    python scripts/daily_validation.py
"""

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent


def run_command(cmd: list, description: str) -> bool:
    """Run a command and return success status."""
    print(f"\n{'='*70}")
    print(f"{description}")
    print(f"{'='*70}\n")
    
    result = subprocess.run(cmd, cwd=PROJECT_ROOT)
    return result.returncode == 0


def main():
    """Run daily paper trading and check validation status."""
    
    # Step 1: Run daily paper trading
    success = run_command(
        [sys.executable, "scripts/daily_pennyhunter.py"],
        "STEP 1: Running Daily Paper Trading"
    )
    
    if not success:
        print("\n⚠️  Warning: Paper trading failed or returned non-zero exit code")
        print("Continuing to validation check...\n")
    
    # Step 2: Check validation status
    run_command(
        [sys.executable, "scripts/check_validation_status.py"],
        "STEP 2: Checking Validation Status"
    )
    
    print("\n" + "="*70)
    print("✅ DAILY VALIDATION COMPLETE")
    print("="*70)


if __name__ == "__main__":
    main()

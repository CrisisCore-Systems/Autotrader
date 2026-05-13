"""
Quick start script for training with simplified 3-action space.

Automatically configures environment and launches training with optimal settings.
"""

import subprocess
import sys
from pathlib import Path

def main():
    print("=" * 70)
    print("🚀 SIMPLIFIED ACTION SPACE TRAINING")
    print("=" * 70)
    print()
    print("Configuration:")
    print("  • Action Space: 3 discrete actions (FLAT, LONG, SHORT)")
    print("  • Position Size: Fixed 100 shares")
    print("  • Symbol: SPY")
    print("  • Duration: 30 days historical data")
    print("  • Timesteps: 50,000 (target: 55%+ win rate)")
    print()
    print("Expected Results:")
    print("  • Convergence: 30-50K steps (vs 100K previously)")
    print("  • Win Rate: 55%+ (vs 45% baseline)")
    print("  • Training Time: ~2-4 hours on CPU")
    print()
    
    # Confirm start
    response = input("Start training? (y/n): ").strip().lower()
    if response != 'y':
        print("❌ Training cancelled.")
        return
    
    print()
    print("=" * 70)
    print("🎯 Starting training...")
    print("=" * 70)
    print()
    
    # Build command
    python_exe = Path(__file__).parent.parent / ".venv-2" / "Scripts" / "python.exe"
    script_path = Path(__file__).parent / "scripts" / "train_intraday_ppo.py"
    
    cmd = [
        str(python_exe),
        str(script_path),
        "--symbol", "SPY",
        "--duration", "30 D",
        "--timesteps", "50000",
    ]
    
    print(f"Command: {' '.join(cmd)}")
    print()
    
    # Run training
    try:
        subprocess.run(cmd, check=True)
        print()
        print("=" * 70)
        print("✅ TRAINING COMPLETE")
        print("=" * 70)
        print()
        print("Next steps:")
        print("  1. Check logs/ directory for training metrics")
        print("  2. Monitor win rate progression")
        print("  3. If win rate >55%, graduate to position sizing (Phase 2)")
        print("  4. If win rate <50%, continue training to 100K steps")
        print()
    except subprocess.CalledProcessError as e:
        print()
        print("=" * 70)
        print("❌ TRAINING FAILED")
        print("=" * 70)
        print(f"Error: {e}")
        print()
        print("Troubleshooting:")
        print("  1. Check that IBKR Gateway is running (if using live data)")
        print("  2. Verify Python environment is activated")
        print("  3. Review logs/ directory for error details")
        print()
        sys.exit(1)

if __name__ == "__main__":
    main()

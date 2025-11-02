"""
Quick Training Status Checker

Reads the most recent log directory and displays training progress.
"""

import argparse
from pathlib import Path
import json
from datetime import datetime

def check_latest_run():
    """Check the latest training run status."""
    logs_dir = Path("logs")
    
    if not logs_dir.exists():
        print("❌ No logs directory found")
        return
    
    # Find most recent log directory
    log_dirs = sorted(logs_dir.glob("ppo_SPY_*"), key=lambda x: x.stat().st_mtime, reverse=True)
    
    if not log_dirs:
        print("❌ No training runs found")
        return
    
    latest = log_dirs[0]
    print(f"\n📊 Latest Training Run: {latest.name}")
    print(f"{'='*70}")
    
    # Check for final model
    final_model = latest / "final_model.zip"
    if final_model.exists():
        print(f"✅ Training COMPLETE")
        print(f"   Model: {final_model}")
    else:
        print(f"🔄 Training IN PROGRESS or INTERRUPTED")
    
    # Check for checkpoints
    ckpt_dir = Path("models/ckpts")
    if ckpt_dir.exists():
        checkpoints = sorted(ckpt_dir.glob(f"ppo_*.zip"))
        if checkpoints:
            print(f"\n📁 Checkpoints found: {len(checkpoints)}")
            for ckpt in checkpoints[-3:]:  # Show last 3
                steps = ckpt.stem.split('_')[-2]
                print(f"   - {ckpt.name} ({steps} steps)")
    
    # Check TensorBoard event files
    event_files = list(latest.rglob("events.out.tfevents.*"))
    if event_files:
        latest_event = max(event_files, key=lambda x: x.stat().st_mtime)
        size_mb = latest_event.stat().st_size / (1024 * 1024)
        modified = datetime.fromtimestamp(latest_event.stat().st_mtime)
        print(f"\n📈 TensorBoard logs:")
        print(f"   Latest: {latest_event.name[:50]}...")
        print(f"   Size: {size_mb:.2f} MB")
        print(f"   Last modified: {modified.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Check if recently modified (training active)
        age_seconds = (datetime.now() - modified).total_seconds()
        if age_seconds < 60:
            print(f"   ✅ ACTIVE (updated {age_seconds:.0f}s ago)")
        elif age_seconds < 300:
            print(f"   ⚠️  Possibly stalled (updated {age_seconds/60:.1f}min ago)")
        else:
            print(f"   ❌ STALE (updated {age_seconds/60:.1f}min ago)")
    
    print(f"\n💡 To view TensorBoard:")
    print(f"   tensorboard --logdir {latest}")
    print(f"{'='*70}\n")


def main():
    parser = argparse.ArgumentParser(description="Check training status")
    parser.add_argument("--watch", action="store_true", help="Watch mode (refresh every 10s)")
    args = parser.parse_args()
    
    if args.watch:
        import time
        try:
            while True:
                check_latest_run()
                time.sleep(10)
                print("\n" * 2)
        except KeyboardInterrupt:
            print("\n👋 Stopped watching")
    else:
        check_latest_run()


if __name__ == "__main__":
    main()

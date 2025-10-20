#!/usr/bin/env python3
"""
Quick validation status checker for Phase 2 out-of-sample testing.

This script:
1. Loads cumulative trade history
2. Identifies trades from Phase 2 optimization deployment (2025-10-20 onwards)
3. Calculates win rate and validates against milestones
4. Provides clear go/no-go decision for Phase 2.5

Usage:
    python scripts/check_validation_status.py
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple

# Project root
PROJECT_ROOT = Path(__file__).parent.parent
HISTORY_FILE = PROJECT_ROOT / "reports" / "pennyhunter_cumulative_history.json"
PAPER_TRADES_FILE = PROJECT_ROOT / "reports" / "pennyhunter_paper_trades.json"

# Phase 2 optimization deployment date
PHASE2_DEPLOYMENT_DATE = "2025-10-20"

# Validation milestones
MILESTONES = {
    5: {"target_wr": 0.60, "min_wins": 3, "name": "Initial Validation"},
    10: {"target_wr": 0.70, "min_wins": 7, "name": "Intermediate Validation"},
    20: {"target_wr": 0.70, "min_wins": 14, "name": "Phase 2.5 Approval"},
}


def load_trades() -> List[Dict]:
    """Load cumulative trade history and current paper trades."""
    all_trades = []
    
    # Load historical cumulative trades
    if HISTORY_FILE.exists():
        with open(HISTORY_FILE, 'r') as f:
            data = json.load(f)
        all_trades.extend(data.get('trades', []))
    
    # Load current paper trades (may have TODAY's trades not yet in cumulative)
    if PAPER_TRADES_FILE.exists():
        with open(PAPER_TRADES_FILE, 'r') as f:
            paper_data = json.load(f)
        paper_trades = paper_data.get('trades', [])
        
        # Only add if not duplicates (check by ticker + entry_time)
        existing_keys = {(t.get('ticker'), t.get('entry_time')) for t in all_trades if t.get('ticker')}
        for pt in paper_trades:
            key = (pt.get('ticker'), pt.get('entry_time'))
            if key not in existing_keys:
                all_trades.append(pt)
    
    return all_trades


def filter_post_optimization_trades(trades: List[Dict]) -> List[Dict]:
    """Filter trades from Phase 2 optimization deployment onwards."""
    deployment_dt = datetime.fromisoformat(PHASE2_DEPLOYMENT_DATE)
    
    post_opt_trades = []
    for trade in trades:
        # Skip session markers
        if trade.get('type') == 'session_marker':
            continue
        
        # Check entry time
        entry_time = trade.get('entry_time')
        if not entry_time:
            continue
        
        try:
            # Parse trade datetime and strip timezone for comparison
            trade_dt_str = entry_time.replace('Z', '+00:00')
            trade_dt = datetime.fromisoformat(trade_dt_str)
            
            # Convert to naive datetime for comparison
            if trade_dt.tzinfo is not None:
                trade_dt = trade_dt.replace(tzinfo=None)
            
            if trade_dt >= deployment_dt:
                post_opt_trades.append(trade)
        except Exception as e:
            # Silently skip unparseable dates (likely old format)
            continue
    
    return post_opt_trades


def analyze_trades(trades: List[Dict]) -> Tuple[int, int, int, float]:
    """
    Analyze trades and return (completed, wins, losses, win_rate).
    
    Returns:
        Tuple of (completed_count, wins, losses, win_rate)
    """
    completed = [t for t in trades if t.get('status') == 'completed']
    wins = sum(1 for t in completed if t.get('pnl', 0) > 0)
    losses = sum(1 for t in completed if t.get('pnl', 0) <= 0)
    
    win_rate = wins / len(completed) if completed else 0.0
    
    return len(completed), wins, losses, win_rate


def check_milestone(completed: int, wins: int, win_rate: float) -> Dict:
    """Check current progress against milestones."""
    # Find the highest milestone we've reached
    reached_milestone = None
    next_milestone = None
    
    for trades_needed in sorted(MILESTONES.keys()):
        if completed >= trades_needed:
            reached_milestone = trades_needed
        elif next_milestone is None:
            next_milestone = trades_needed
            break
    
    # Check if we passed the milestone
    result = {
        'reached': reached_milestone,
        'next': next_milestone,
        'passed': False,
        'message': ''
    }
    
    if reached_milestone:
        milestone = MILESTONES[reached_milestone]
        target_wr = milestone['target_wr']
        min_wins = milestone['min_wins']
        
        if win_rate >= target_wr and wins >= min_wins:
            result['passed'] = True
            result['message'] = f"✅ {milestone['name']} PASSED ({wins}/{reached_milestone} wins = {win_rate*100:.1f}%)"
        else:
            result['passed'] = False
            result['message'] = f"❌ {milestone['name']} FAILED ({wins}/{reached_milestone} wins = {win_rate*100:.1f}% vs {target_wr*100:.0f}% target)"
    
    return result


def print_summary(trades: List[Dict], completed: int, wins: int, losses: int, win_rate: float):
    """Print validation summary."""
    active = [t for t in trades if t.get('status') == 'active']
    
    print("=" * 70)
    print("PHASE 2 OUT-OF-SAMPLE VALIDATION STATUS")
    print("=" * 70)
    print(f"Deployment Date: {PHASE2_DEPLOYMENT_DATE}")
    print(f"Check Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    print("📊 TRADE STATISTICS")
    print(f"   Total Trades: {len(trades)}")
    print(f"   Completed: {completed}")
    print(f"   Active: {len(active)}")
    print(f"   Wins: {wins}")
    print(f"   Losses: {losses}")
    print(f"   Win Rate: {win_rate*100:.1f}%")
    print()
    
    # Show active positions
    if active:
        print("🔄 ACTIVE POSITIONS")
        for trade in active:
            ticker = trade.get('ticker')
            entry = trade.get('entry_price', 0)
            shares = trade.get('shares', 0)
            gap = trade.get('gap_pct', 0)
            vol = trade.get('vol_mult', 0)
            print(f"   {ticker}: {shares} shares @ ${entry:.2f} (Gap {gap:.1f}%, Vol {vol:.1f}x)")
        print()
    
    # Check milestones
    print("🎯 MILESTONE PROGRESS")
    milestone_result = check_milestone(completed, wins, win_rate)
    
    for trades_needed in sorted(MILESTONES.keys()):
        milestone = MILESTONES[trades_needed]
        target_wr = milestone['target_wr']
        min_wins = milestone['min_wins']
        
        if completed >= trades_needed:
            # Reached this milestone
            if win_rate >= target_wr and wins >= min_wins:
                status = "✅ PASSED"
            else:
                status = "❌ FAILED"
            progress = 100
        else:
            status = "⏳ PENDING"
            progress = int((completed / trades_needed) * 100)
        
        bar_length = 30
        filled = int(bar_length * progress / 100)
        bar = "█" * filled + "░" * (bar_length - filled)
        
        print(f"   {milestone['name']}: [{bar}] {progress}%")
        print(f"      {completed}/{trades_needed} trades, {wins} wins ({win_rate*100:.1f}% vs {target_wr*100:.0f}% target) {status}")
    
    print()
    
    # Decision
    print("=" * 70)
    if completed >= 20:
        if win_rate >= 0.70 and wins >= 14:
            print("🎉 PHASE 2.5 APPROVED!")
            print("   ✅ 20 trades completed")
            print(f"   ✅ {win_rate*100:.1f}% win rate (≥70% target)")
            print(f"   ✅ {wins} wins (≥14 required)")
            print()
            print("📋 NEXT STEPS:")
            print("   1. Implement Phase 2.5 agentic memory system")
            print("   2. Add ticker performance tracking")
            print("   3. Implement auto-ejection logic (<40% WR after 10 trades)")
            print("   4. Add context-aware filtering")
            print("   5. Implement regime-based adjustments")
        else:
            print("⚠️  PHASE 2 VALIDATION INCOMPLETE")
            print(f"   ❌ Win rate {win_rate*100:.1f}% below 70% target")
            print()
            print("📋 NEXT STEPS:")
            print("   1. Analyze losing trades for patterns")
            print("   2. Review if gap/volume filters need adjustment")
            print("   3. Check if market regime shifted")
            print("   4. Consider expanding ticker universe")
    elif completed >= 10:
        milestone = check_milestone(completed, wins, win_rate)
        if milestone['passed']:
            print(f"✅ INTERMEDIATE VALIDATION PASSED ({wins}/{completed} wins = {win_rate*100:.1f}%)")
            print("   System is performing well - continue accumulating trades")
            print()
            print("📋 NEXT STEPS:")
            print(f"   Continue daily trading to reach 20 trades ({20-completed} more needed)")
        else:
            print(f"⚠️  INTERMEDIATE VALIDATION CONCERNS ({wins}/{completed} wins = {win_rate*100:.1f}%)")
            print("   Win rate below target - may need adjustment")
            print()
            print("📋 NEXT STEPS:")
            print("   1. Monitor next few trades closely")
            print("   2. If win rate continues below 60%, re-analyze filters")
    elif completed >= 5:
        milestone = check_milestone(completed, wins, win_rate)
        if milestone['passed']:
            print(f"✅ INITIAL VALIDATION PASSED ({wins}/{completed} wins = {win_rate*100:.1f}%)")
            print("   Filters showing promise - continue accumulating trades")
            print()
            print("📋 NEXT STEPS:")
            print(f"   Continue daily trading to reach 20 trades ({20-completed} more needed)")
        else:
            print(f"⚠️  INITIAL VALIDATION CONCERNS ({wins}/{completed} wins = {win_rate*100:.1f}%)")
            print("   Win rate below 60% - filters may need review")
            print()
            print("📋 NEXT STEPS:")
            print("   1. Review losing trades for common patterns")
            print("   2. Check if gap/volume ranges need adjustment")
    else:
        print(f"🔄 VALIDATION IN PROGRESS ({completed}/5 trades for initial check)")
        print()
        print("📋 NEXT STEPS:")
        print(f"   Continue daily trading to reach 5 trades ({5-completed} more needed)")
    
    print("=" * 70)


def main():
    """Main validation check."""
    print("\nLoading trade history...\n")
    
    # Load all trades
    all_trades = load_trades()
    if not all_trades:
        print("❌ No trades found")
        return
    
    # Filter to post-optimization trades only
    post_opt_trades = filter_post_optimization_trades(all_trades)
    
    if not post_opt_trades:
        print(f"❌ No trades found after {PHASE2_DEPLOYMENT_DATE}")
        print("\n📋 NEXT STEPS:")
        print("   Run daily paper trading: python scripts/daily_pennyhunter.py")
        return
    
    # Analyze
    completed, wins, losses, win_rate = analyze_trades(post_opt_trades)
    
    # Print summary
    print_summary(post_opt_trades, completed, wins, losses, win_rate)


if __name__ == "__main__":
    main()

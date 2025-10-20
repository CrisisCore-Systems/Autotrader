#!/usr/bin/env python
"""
Daily PennyHunter Automation Script

Simple one-liner to run PennyHunter paper trading daily and accumulate results.

Usage:
    python scripts/daily_pennyhunter.py
    python scripts/daily_pennyhunter.py --tickers INTR,ADT,SAN,COMP
    
Features:
- Scans under-$10 candidates
- Executes paper trades with quality gates
- Appends to cumulative trade history
- Shows daily summary + cumulative stats
- Tracks progress toward 20+ trade goal
"""

import sys
import json
import logging
from pathlib import Path
from datetime import datetime
import subprocess

# Setup paths
PROJECT_ROOT = Path(__file__).parent.parent
RESULTS_FILE = PROJECT_ROOT / "reports" / "pennyhunter_paper_trades.json"
CUMULATIVE_FILE = PROJECT_ROOT / "reports" / "pennyhunter_cumulative_history.json"
TICKERS_DEFAULT = "ADT,SAN,COMP,INTR,CLOV,EVGO"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_cumulative_history():
    """Load all historical trades from cumulative file"""
    if not CUMULATIVE_FILE.exists():
        return {
            'first_trade_date': None,
            'last_updated': None,
            'total_sessions': 0,
            'trades': [],
            'metadata': {
                'phase': '2',
                'goal': 'Accumulate 20+ trades to validate 65-75% win rate',
                'current_milestone': 'Phase 2 validation in progress'
            }
        }
    
    with open(CUMULATIVE_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_cumulative_history(history):
    """Save updated cumulative history"""
    CUMULATIVE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CUMULATIVE_FILE, 'w', encoding='utf-8') as f:
        json.dump(history, f, indent=2, ensure_ascii=False)
    logger.info(f"Updated cumulative history: {CUMULATIVE_FILE}")


def run_paper_trading(tickers):
    """Run paper trading scanner"""
    logger.info(f"Running PennyHunter paper trading...")
    
    cmd = [
        sys.executable,
        str(PROJECT_ROOT / "run_pennyhunter_paper.py"),
        "--tickers", tickers,
        "--account-size", "200",
        "--max-risk", "5",
        "--output", str(RESULTS_FILE)
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=PROJECT_ROOT)
    
    if result.returncode != 0:
        logger.error(f"Paper trading failed: {result.stderr}")
        return None
    
    # Load today's results
    if not RESULTS_FILE.exists():
        logger.warning("No results file generated")
        return None
        
    with open(RESULTS_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def merge_results(history, daily_results):
    """Merge today's results into cumulative history"""
    if not daily_results:
        return history
    
    today = datetime.now().isoformat()
    
    # Update metadata
    if not history['first_trade_date'] and daily_results['trades']:
        history['first_trade_date'] = today
    history['last_updated'] = today
    history['total_sessions'] += 1
    
    # Add session marker
    session_marker = {
        'session_id': history['total_sessions'],
        'date': today,
        'type': 'session_marker'
    }
    history['trades'].append(session_marker)
    
    # Append new trades
    for trade in daily_results.get('trades', []):
        trade['session_id'] = history['total_sessions']
        history['trades'].append(trade)
    
    return history


def calculate_cumulative_stats(history):
    """Calculate stats from all historical trades"""
    all_trades = [t for t in history['trades'] if t.get('type') != 'session_marker']
    
    if not all_trades:
        return {
            'total_trades': 0,
            'completed_trades': 0,
            'active_trades': 0,
            'wins': 0,
            'losses': 0,
            'win_rate_pct': 0.0,
            'total_pnl': 0.0,
            'avg_win': 0.0,
            'avg_loss': 0.0,
            'profit_factor': 0.0,
            'progress_to_goal': 0.0
        }
    
    completed_trades = [t for t in all_trades if t.get('status') == 'closed']
    active_trades = [t for t in all_trades if t.get('status') == 'active']
    
    wins = [t for t in completed_trades if t.get('pnl', 0) > 0]
    losses = [t for t in completed_trades if t.get('pnl', 0) < 0]
    
    win_rate = (len(wins) / len(completed_trades) * 100) if completed_trades else 0
    total_pnl = sum(t.get('pnl', 0) for t in completed_trades)
    avg_win = sum(t['pnl'] for t in wins) / len(wins) if wins else 0
    avg_loss = sum(t['pnl'] for t in losses) / len(losses) if losses else 0
    profit_factor = abs(avg_win / avg_loss) if avg_loss != 0 else 0
    
    # Progress toward 20+ trade goal
    progress = (len(completed_trades) / 20.0 * 100) if len(completed_trades) < 20 else 100
    
    return {
        'total_trades': len(all_trades),
        'completed_trades': len(completed_trades),
        'active_trades': len(active_trades),
        'wins': len(wins),
        'losses': len(losses),
        'win_rate_pct': win_rate,
        'total_pnl': total_pnl,
        'avg_win': avg_win,
        'avg_loss': avg_loss,
        'profit_factor': profit_factor,
        'progress_to_goal': progress
    }


def print_daily_summary(daily_results, cumulative_stats):
    """Print summary of today's trading + cumulative stats"""
    print("\n" + "="*70)
    print("PENNYHUNTER DAILY PAPER TRADING SUMMARY")
    print("="*70)
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    if daily_results:
        print("TODAY'S SESSION:")
        daily_trades = len(daily_results.get('trades', []))
        print(f"  Signals Found: {daily_trades}")
        print(f"  Trades Executed: {daily_results.get('trading_stats', {}).get('total_trades', 0)}")
        print(f"  Active Positions: {daily_results.get('trading_stats', {}).get('active_trades', 0)}")
    else:
        print("TODAY'S SESSION: No trading activity")
    
    print()
    print("CUMULATIVE STATISTICS (ALL TIME):")
    print(f"  Total Trades: {cumulative_stats['total_trades']}")
    print(f"  Completed: {cumulative_stats['completed_trades']} | Active: {cumulative_stats['active_trades']}")
    print(f"  Wins: {cumulative_stats['wins']} | Losses: {cumulative_stats['losses']}")
    print(f"  Win Rate: {cumulative_stats['win_rate_pct']:.1f}%")
    
    if cumulative_stats['completed_trades'] > 0:
        print(f"  Total P&L: ${cumulative_stats['total_pnl']:.2f}")
        print(f"  Avg Win: ${cumulative_stats['avg_win']:.2f} | Avg Loss: ${cumulative_stats['avg_loss']:.2f}")
        print(f"  Profit Factor: {cumulative_stats['profit_factor']:.2f}")
    
    print()
    print("PHASE 2 VALIDATION PROGRESS:")
    progress = cumulative_stats['progress_to_goal']
    completed = cumulative_stats['completed_trades']
    bar_length = 40
    filled = int(bar_length * progress / 100)
    bar = '=' * filled + '-' * (bar_length - filled)
    print(f"  [{bar}] {progress:.0f}%")
    print(f"  {completed}/20 trades completed")
    
    if progress >= 100:
        print()
        print("  MILESTONE REACHED: 20+ trades collected!")
        print("  READY to validate 65-75% win rate target")
        print("  Next: Run analysis dashboard and proceed to Phase 2.5")
    else:
        remaining = 20 - completed
        print(f"  {remaining} more trades needed for Phase 2 validation")
    
    print("="*70 + "\n")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Daily PennyHunter Paper Trading')
    parser.add_argument('--tickers', default=TICKERS_DEFAULT,
                       help=f'Comma-separated tickers (default: {TICKERS_DEFAULT})')
    args = parser.parse_args()
    
    print("\n" + "="*70)
    print("PENNYHUNTER DAILY AUTOMATION - PHASE 2 VALIDATION")
    print("="*70)
    print(f"Goal: Accumulate 20+ trades to validate 65-75% win rate")
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70 + "\n")
    
    # Step 1: Load cumulative history
    logger.info("Loading cumulative trade history...")
    history = load_cumulative_history()
    logger.info(f"Found {len([t for t in history['trades'] if t.get('type') != 'session_marker'])} historical trades")
    
    # Step 2: Run today's paper trading
    logger.info("Executing paper trading session...")
    daily_results = run_paper_trading(args.tickers)
    
    # Step 3: Merge results
    logger.info("Merging results into cumulative history...")
    history = merge_results(history, daily_results)
    save_cumulative_history(history)
    
    # Step 4: Calculate cumulative stats
    cumulative_stats = calculate_cumulative_stats(history)
    
    # Step 5: Print summary
    print_daily_summary(daily_results, cumulative_stats)
    
    # Step 6: Check if ready for Phase 2.5
    if cumulative_stats['completed_trades'] >= 20:
        print("\n🎉 PHASE 2 VALIDATION COMPLETE!")
        print("Next steps:")
        print("  1. Run: python scripts/analyze_pennyhunter_results.py")
        print("  2. Review win rate vs 65-75% target")
        print("  3. If validated, proceed to Phase 2.5 (lightweight agentic memory)")
        print()
    
    return 0


if __name__ == '__main__':
    sys.exit(main())

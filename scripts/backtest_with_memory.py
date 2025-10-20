#!/usr/bin/env python
"""
Re-run Backtest with Memory-Based Auto-Ejection

Runs backtest with memory system enabled to validate Phase 2.5 improvements.
Should show win rate improvement from 61.2% to 65-70% by ejecting underperformers.

Usage:
    python scripts/backtest_with_memory.py
    python scripts/backtest_with_memory.py --tickers ADT,COMP,INTR,EVGO,NIO
"""

import sys
import json
import logging
import argparse
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from bouncehunter.pennyhunter_memory import PennyHunterMemory

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent
CUMULATIVE_HISTORY = PROJECT_ROOT / "reports" / "pennyhunter_cumulative_history.json"


def analyze_with_memory_filtering(memory: PennyHunterMemory, history_file: Path):
    """
    Analyze backtest results with memory-based filtering.

    Simulates what would have happened if memory was used during backtest.
    """
    # Load cumulative history
    with open(history_file, 'r', encoding='utf-8') as f:
        history = json.load(f)

    # Extract trades
    trades = [t for t in history.get('trades', []) if 'ticker' in t and 'pnl' in t]

    logger.info(f"\n{'='*70}")
    logger.info("BACKTEST WITH MEMORY-BASED AUTO-EJECTION")
    logger.info(f"{'='*70}")
    logger.info(f"Total trades in backtest: {len(trades)}")

    # Simulate filtering
    filtered_trades = []
    ejected_trades = []

    for trade in trades:
        ticker = trade['ticker']

        # Check if ticker would be allowed
        check = memory.should_trade_ticker(ticker)

        if check['allowed']:
            filtered_trades.append(trade)
        else:
            ejected_trades.append(trade)
            logger.debug(f"  BLOCKED {ticker}: {check['reason']}")

    # Calculate stats
    filtered_wins = [t for t in filtered_trades if t['pnl'] > 0]
    filtered_losses = [t for t in filtered_trades if t['pnl'] <= 0]
    filtered_win_rate = len(filtered_wins) / len(filtered_trades) * 100 if filtered_trades else 0

    ejected_wins = [t for t in ejected_trades if t['pnl'] > 0]
    ejected_losses = [t for t in ejected_trades if t['pnl'] <= 0]
    ejected_win_rate = len(ejected_wins) / len(ejected_trades) * 100 if ejected_trades else 0

    original_wins = len(filtered_wins) + len(ejected_wins)
    original_losses = len(filtered_losses) + len(ejected_losses)
    original_win_rate = original_wins / len(trades) * 100 if trades else 0

    logger.info(f"\n📊 RESULTS:")
    logger.info(f"{'='*70}")
    logger.info("\nORIGINAL (No Memory):")
    logger.info(f"  Total Trades: {len(trades)}")
    logger.info(f"  Wins: {original_wins} | Losses: {original_losses}")
    logger.info(f"  Win Rate: {original_win_rate:.1f}%")

    logger.info("\nWITH MEMORY-BASED FILTERING:")
    logger.info(f"  Allowed Trades: {len(filtered_trades)}")
    logger.info(f"  Wins: {len(filtered_wins)} | Losses: {len(filtered_losses)}")
    logger.info(f"  Win Rate: {filtered_win_rate:.1f}%")

    logger.info("\nEJECTED TRADES (Would Not Be Taken):")
    logger.info(f"  Blocked Trades: {len(ejected_trades)}")
    logger.info(f"  Wins: {len(ejected_wins)} | Losses: {len(ejected_losses)}")
    logger.info(f"  Win Rate: {ejected_win_rate:.1f}%")

    improvement = filtered_win_rate - original_win_rate
    logger.info(f"\n✨ WIN RATE IMPROVEMENT: {improvement:+.1f}% ({original_win_rate:.1f}% → {filtered_win_rate:.1f}%)")

    # Detailed ejected trades
    if ejected_trades:
        logger.info(f"\n❌ EJECTED TRADES BREAKDOWN:")
        ejected_by_ticker = {}
        for trade in ejected_trades:
            ticker = trade['ticker']
            if ticker not in ejected_by_ticker:
                ejected_by_ticker[ticker] = {'wins': 0, 'losses': 0, 'pnl': 0}

            if trade['pnl'] > 0:
                ejected_by_ticker[ticker]['wins'] += 1
            else:
                ejected_by_ticker[ticker]['losses'] += 1
            ejected_by_ticker[ticker]['pnl'] += trade['pnl']

        for ticker, stats in ejected_by_ticker.items():
            total = stats['wins'] + stats['losses']
            wr = stats['wins'] / total * 100 if total > 0 else 0
            logger.info(f"  {ticker}: {stats['wins']}W/{stats['losses']}L ({wr:.1f}% WR), P&L: ${stats['pnl']:.2f}")

    # Phase 2 validation
    logger.info(f"\n{'='*70}")
    logger.info("PHASE 2.5 VALIDATION:")
    logger.info(f"{'='*70}")

    if len(filtered_trades) >= 20:
        logger.info(f"  Sample Size: {len(filtered_trades)} trades (>= 20) ✅")
    else:
        logger.info(f"  Sample Size: {len(filtered_trades)} trades (< 20) ⚠️")

    if filtered_win_rate >= 65:
        logger.info(f"  Win Rate: {filtered_win_rate:.1f}% (>= 65% target) ✅")
        logger.info(f"\n  ✅ PHASE 2.5 VALIDATED - Memory system working!")
        logger.info(f"  Auto-ejection improved win rate by {improvement:+.1f}%")
    elif filtered_win_rate >= 55:
        logger.info(f"  Win Rate: {filtered_win_rate:.1f}% (Phase 1 level) ⚠️")
        logger.info(f"\n  ⚠️ Improvement seen ({improvement:+.1f}%), but below Phase 2 target")
    else:
        logger.info(f"  Win Rate: {filtered_win_rate:.1f}% (< 55%) ❌")
        logger.info(f"\n  ❌ Below Phase 1 target")

    logger.info(f"{'='*70}\n")


def main():
    parser = argparse.ArgumentParser(description='Backtest with Memory Auto-Ejection')
    parser.add_argument('--history-file', default=str(CUMULATIVE_HISTORY),
                       help='Path to cumulative history JSON')

    args = parser.parse_args()

    # Load memory (should be pre-seeded)
    memory = PennyHunterMemory()

    # Check if memory is seeded
    all_stats = memory.get_all_ticker_stats()
    if not all_stats:
        logger.error("❌ Memory database is empty!")
        logger.error("Run first: python scripts/seed_memory_from_cumulative.py")
        return 1

    logger.info(f"Memory loaded with {len(all_stats)} tickers tracked")

    # Print memory status
    memory.print_summary()

    # Analyze with filtering
    analyze_with_memory_filtering(memory, Path(args.history_file))

    return 0


if __name__ == '__main__':
    sys.exit(main())

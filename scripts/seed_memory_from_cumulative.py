#!/usr/bin/env python
"""
Seed PennyHunter Memory from Cumulative History

Seeds memory from all accumulated trades including multiple backtest sessions.

Usage:
    python scripts/seed_memory_from_cumulative.py
"""

import sys
import json
import logging
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


def main():
    # Initialize memory
    memory = PennyHunterMemory()

    # Reset database
    logger.warning("Resetting memory database...")
    memory.reset_database()

    # Load cumulative history
    if not CUMULATIVE_HISTORY.exists():
        logger.error(f"Cumulative history not found: {CUMULATIVE_HISTORY}")
        return 1

    with open(CUMULATIVE_HISTORY, 'r', encoding='utf-8') as f:
        history = json.load(f)

    # Extract trades (skip session markers)
    trades = [t for t in history.get('trades', []) if 'ticker' in t and 'pnl' in t]

    logger.info(f"Found {len(trades)} trades in cumulative history")

    # Seed memory
    for trade in trades:
        ticker = trade['ticker']
        pnl = trade['pnl']
        won = pnl > 0
        trade_date = trade.get('entry_time', trade.get('date'))

        memory.record_trade_outcome(ticker, won, pnl, trade_date)

    logger.info(f"✅ Seeded memory with {len(trades)} trades")

    # Print summary
    memory.print_summary()

    # Test ticker checks
    logger.info("\n" + "="*70)
    logger.info("TESTING TICKER CHECKS")
    logger.info("="*70)

    test_tickers = ['ADT', 'COMP', 'INTR', 'EVGO', 'NIO', 'CLOV', 'SNAP']
    for ticker in test_tickers:
        result = memory.should_trade_ticker(ticker)
        status_icon = "✅" if result['allowed'] else "❌"
        logger.info(f"{status_icon} {ticker}: {result['reason']}")

    logger.info("="*70 + "\n")

    return 0


if __name__ == '__main__':
    sys.exit(main())

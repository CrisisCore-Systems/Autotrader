#!/usr/bin/env python
"""
Seed PennyHunter Memory from Backtest Results

Loads historical backtest data and seeds the memory system.
This allows the auto-ejection logic to work on historical performance.

Usage:
    python scripts/seed_pennyhunter_memory.py
    python scripts/seed_pennyhunter_memory.py --reset  # Clear and reseed
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
BACKTEST_RESULTS = PROJECT_ROOT / "reports" / "pennyhunter_backtest_results.json"


def main():
    parser = argparse.ArgumentParser(description='Seed PennyHunter Memory from Backtest')
    parser.add_argument('--reset', action='store_true',
                       help='Reset database before seeding')
    parser.add_argument('--backtest-file', default=str(BACKTEST_RESULTS),
                       help='Path to backtest results JSON')

    args = parser.parse_args()

    # Initialize memory
    memory = PennyHunterMemory()

    # Reset if requested
    if args.reset:
        logger.warning("Resetting memory database...")
        memory.reset_database()

    # Load backtest results
    backtest_file = Path(args.backtest_file)
    if not backtest_file.exists():
        logger.error(f"Backtest results not found: {backtest_file}")
        logger.error("Run backtest first: python scripts/backtest_pennyhunter_3yr.py")
        return 1

    with open(backtest_file, 'r', encoding='utf-8') as f:
        backtest_results = json.load(f)

    # Seed memory
    memory.seed_from_backtest(backtest_results)

    # Test ticker checks
    logger.info("\n" + "="*70)
    logger.info("TESTING TICKER CHECKS")
    logger.info("="*70)

    test_tickers = ['ADT', 'COMP', 'INTR', 'EVGO', 'NIO']
    for ticker in test_tickers:
        result = memory.should_trade_ticker(ticker)
        status_icon = "✅" if result['allowed'] else "❌"
        logger.info(f"{status_icon} {ticker}: {result['reason']}")

    logger.info("="*70 + "\n")

    logger.info("✅ Memory seeded successfully!")
    logger.info(f"Database: {memory.db_path}")

    return 0


if __name__ == '__main__':
    sys.exit(main())

"""
PennyHunter Memory System (Phase 2.5)

Lightweight memory system that tracks ticker performance and auto-ejects
chronic underperformers to improve win rate from 61% to 65-70%+.

Key Features:
- SQLite-based ticker stats tracking
- Auto-ejection for tickers <40% win rate after 10+ trades
- Seed with historical backtest data
- Integrates with paper trading system

Author: BounceHunter Team
"""

import sqlite3
import logging
from pathlib import Path
from typing import Optional, Dict, List
from datetime import datetime
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class TickerStats:
    """Statistics for a single ticker"""
    ticker: str
    total_trades: int
    wins: int
    losses: int
    win_rate: float
    total_pnl: float
    avg_win: float
    avg_loss: float
    last_trade_date: str
    status: str  # 'active', 'ejected', 'monitored'
    ejection_reason: Optional[str] = None


class PennyHunterMemory:
    """
    Lightweight memory system for PennyHunter.

    Tracks ticker performance and auto-ejects chronic underperformers.
    Similar to BounceHunter's agentic memory but simpler.
    """

    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize memory system.

        Args:
            db_path: Path to SQLite database (default: reports/pennyhunter_memory.db)
        """
        if db_path is None:
            db_path = Path(__file__).parent.parent.parent / "reports" / "pennyhunter_memory.db"

        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Configuration
        self.min_trades_for_ejection = 4  # Minimum trades before considering ejection
        self.ejection_win_rate_threshold = 0.35  # Eject if <35% win rate (was 0.40)
        self.monitor_win_rate_threshold = 0.45  # Monitor if <45% win rate (was 0.50)

        # Initialize database
        self._init_database()

        logger.info(f"PennyHunterMemory initialized: {self.db_path}")
        logger.info(f"  Ejection: <{self.ejection_win_rate_threshold*100:.0f}% win rate after {self.min_trades_for_ejection}+ trades")
        logger.info(f"  Monitor: <{self.monitor_win_rate_threshold*100:.0f}% win rate")

    def _init_database(self):
        """Initialize SQLite database with ticker_stats table"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ticker_stats (
                ticker TEXT PRIMARY KEY,
                total_trades INTEGER DEFAULT 0,
                wins INTEGER DEFAULT 0,
                losses INTEGER DEFAULT 0,
                total_pnl REAL DEFAULT 0.0,
                sum_wins REAL DEFAULT 0.0,
                sum_losses REAL DEFAULT 0.0,
                last_trade_date TEXT,
                status TEXT DEFAULT 'active',
                ejection_reason TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.commit()
        conn.close()

    def record_trade_outcome(
        self,
        ticker: str,
        won: bool,
        pnl: float,
        trade_date: Optional[str] = None
    ):
        """
        Record a trade outcome for a ticker.

        Args:
            ticker: Stock ticker symbol
            won: True if trade was profitable
            pnl: Profit/loss amount
            trade_date: Trade date (ISO format, defaults to now)
        """
        if trade_date is None:
            trade_date = datetime.now().isoformat()

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Check if ticker exists
        cursor.execute("SELECT ticker FROM ticker_stats WHERE ticker = ?", (ticker,))
        exists = cursor.fetchone() is not None

        if exists:
            # Update existing ticker
            if won:
                cursor.execute("""
                    UPDATE ticker_stats
                    SET total_trades = total_trades + 1,
                        wins = wins + 1,
                        total_pnl = total_pnl + ?,
                        sum_wins = sum_wins + ?,
                        last_trade_date = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE ticker = ?
                """, (pnl, pnl, trade_date, ticker))
            else:
                cursor.execute("""
                    UPDATE ticker_stats
                    SET total_trades = total_trades + 1,
                        losses = losses + 1,
                        total_pnl = total_pnl + ?,
                        sum_losses = sum_losses + ?,
                        last_trade_date = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE ticker = ?
                """, (pnl, abs(pnl), trade_date, ticker))
        else:
            # Insert new ticker
            cursor.execute("""
                INSERT INTO ticker_stats
                (ticker, total_trades, wins, losses, total_pnl, sum_wins, sum_losses, last_trade_date)
                VALUES (?, 1, ?, ?, ?, ?, ?, ?)
            """, (
                ticker,
                1 if won else 0,
                0 if won else 1,
                pnl,
                pnl if won else 0.0,
                abs(pnl) if not won else 0.0,
                trade_date
            ))

        conn.commit()

        # Check if ticker should be ejected
        self._update_ticker_status(ticker, cursor)

        conn.commit()
        conn.close()

        logger.info(f"📝 Recorded trade: {ticker} {'WIN' if won else 'LOSS'} ${pnl:.2f}")

    def _update_ticker_status(self, ticker: str, cursor: sqlite3.Cursor):
        """Update ticker status based on performance"""
        cursor.execute("""
            SELECT total_trades, wins, losses, status
            FROM ticker_stats
            WHERE ticker = ?
        """, (ticker,))

        row = cursor.fetchone()
        if not row:
            return

        total_trades, wins, losses, current_status = row
        win_rate = wins / total_trades if total_trades > 0 else 0.0

        new_status = current_status
        ejection_reason = None

        # Check for ejection
        if total_trades >= self.min_trades_for_ejection and win_rate < self.ejection_win_rate_threshold:
            if current_status != 'ejected':
                new_status = 'ejected'
                ejection_reason = f"<{self.ejection_win_rate_threshold*100:.0f}% win rate after {total_trades} trades ({wins}W/{losses}L)"
                logger.warning(f"⚠️ AUTO-EJECTING {ticker}: {win_rate*100:.1f}% win rate after {total_trades} trades")

        # Check for monitoring
        elif total_trades >= 2 and win_rate < self.monitor_win_rate_threshold:
            if current_status == 'active':
                new_status = 'monitored'
                logger.info(f"👁️ MONITORING {ticker}: {win_rate*100:.1f}% win rate after {total_trades} trades")

        # Re-activate if improving
        elif current_status == 'monitored' and win_rate >= self.monitor_win_rate_threshold:
            new_status = 'active'
            logger.info(f"✅ RE-ACTIVATING {ticker}: Improved to {win_rate*100:.1f}% win rate")

        # Update status if changed
        if new_status != current_status:
            cursor.execute("""
                UPDATE ticker_stats
                SET status = ?, ejection_reason = ?, updated_at = CURRENT_TIMESTAMP
                WHERE ticker = ?
            """, (new_status, ejection_reason, ticker))

    def should_trade_ticker(self, ticker: str) -> Dict:
        """
        Check if ticker should be traded based on memory.

        Args:
            ticker: Stock ticker symbol

        Returns:
            Dict with keys:
                - allowed (bool): Whether to trade ticker
                - reason (str): Explanation
                - stats (TickerStats): Ticker statistics if available
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT ticker, total_trades, wins, losses, total_pnl,
                   sum_wins, sum_losses, last_trade_date, status, ejection_reason
            FROM ticker_stats
            WHERE ticker = ?
        """, (ticker,))

        row = cursor.fetchone()
        conn.close()

        # New ticker - allow
        if not row:
            return {
                'allowed': True,
                'reason': 'New ticker (no history)',
                'stats': None
            }

        # Parse stats
        (ticker, total_trades, wins, losses, total_pnl,
         sum_wins, sum_losses, last_trade_date, status, ejection_reason) = row

        win_rate = wins / total_trades if total_trades > 0 else 0.0
        avg_win = sum_wins / wins if wins > 0 else 0.0
        avg_loss = -sum_losses / losses if losses > 0 else 0.0

        stats = TickerStats(
            ticker=ticker,
            total_trades=total_trades,
            wins=wins,
            losses=losses,
            win_rate=win_rate,
            total_pnl=total_pnl,
            avg_win=avg_win,
            avg_loss=avg_loss,
            last_trade_date=last_trade_date,
            status=status,
            ejection_reason=ejection_reason
        )

        # Check ejection
        if status == 'ejected':
            return {
                'allowed': False,
                'reason': f'Ejected: {ejection_reason}',
                'stats': stats
            }

        # Allow but warn if monitored
        if status == 'monitored':
            return {
                'allowed': True,
                'reason': f'Monitored: {win_rate*100:.1f}% win rate ({wins}W/{losses}L)',
                'stats': stats
            }

        # Active - allow
        return {
            'allowed': True,
            'reason': f'Active: {win_rate*100:.1f}% win rate ({wins}W/{losses}L)',
            'stats': stats
        }

    def get_ticker_stats(self, ticker: str) -> Optional[TickerStats]:
        """Get statistics for a specific ticker"""
        result = self.should_trade_ticker(ticker)
        return result.get('stats')

    def get_all_ticker_stats(self, status_filter: Optional[str] = None) -> List[TickerStats]:
        """
        Get statistics for all tickers.

        Args:
            status_filter: Filter by status ('active', 'monitored', 'ejected')

        Returns:
            List of TickerStats ordered by total_trades desc
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        if status_filter:
            cursor.execute("""
                SELECT ticker, total_trades, wins, losses, total_pnl,
                       sum_wins, sum_losses, last_trade_date, status, ejection_reason
                FROM ticker_stats
                WHERE status = ?
                ORDER BY total_trades DESC
            """, (status_filter,))
        else:
            cursor.execute("""
                SELECT ticker, total_trades, wins, losses, total_pnl,
                       sum_wins, sum_losses, last_trade_date, status, ejection_reason
                FROM ticker_stats
                ORDER BY total_trades DESC
            """)

        rows = cursor.fetchall()
        conn.close()

        stats_list = []
        for row in rows:
            (ticker, total_trades, wins, losses, total_pnl,
             sum_wins, sum_losses, last_trade_date, status, ejection_reason) = row

            win_rate = wins / total_trades if total_trades > 0 else 0.0
            avg_win = sum_wins / wins if wins > 0 else 0.0
            avg_loss = -sum_losses / losses if losses > 0 else 0.0

            stats_list.append(TickerStats(
                ticker=ticker,
                total_trades=total_trades,
                wins=wins,
                losses=losses,
                win_rate=win_rate,
                total_pnl=total_pnl,
                avg_win=avg_win,
                avg_loss=avg_loss,
                last_trade_date=last_trade_date,
                status=status,
                ejection_reason=ejection_reason
            ))

        return stats_list

    def seed_from_backtest(self, backtest_results: Dict):
        """
        Seed memory database from backtest results.

        Args:
            backtest_results: Dict from backtest JSON with 'trades' key
        """
        if 'trades' not in backtest_results:
            logger.warning("No trades found in backtest results")
            return

        trades = backtest_results['trades']
        trades_by_ticker = {}

        # Group trades by ticker
        for trade in trades:
            if 'ticker' not in trade or 'pnl' not in trade:
                continue

            ticker = trade['ticker']
            if ticker not in trades_by_ticker:
                trades_by_ticker[ticker] = []
            trades_by_ticker[ticker].append(trade)

        # Record each trade
        logger.info(f"Seeding memory from {len(trades)} backtest trades...")
        for ticker, ticker_trades in trades_by_ticker.items():
            for trade in ticker_trades:
                pnl = trade.get('pnl', 0.0)
                won = pnl > 0
                trade_date = trade.get('entry_time', datetime.now().isoformat())

                self.record_trade_outcome(ticker, won, pnl, trade_date)

        logger.info(f"✅ Seeded memory with {len(trades)} trades across {len(trades_by_ticker)} tickers")

        # Print summary
        self.print_summary()

    def print_summary(self):
        """Print memory summary statistics"""
        active = self.get_all_ticker_stats('active')
        monitored = self.get_all_ticker_stats('monitored')
        ejected = self.get_all_ticker_stats('ejected')

        logger.info("\n" + "="*70)
        logger.info("PENNYHUNTER MEMORY SUMMARY")
        logger.info("="*70)
        logger.info(f"Active Tickers: {len(active)}")
        logger.info(f"Monitored Tickers: {len(monitored)}")
        logger.info(f"Ejected Tickers: {len(ejected)}")
        logger.info("="*70)

        if ejected:
            logger.info("\n❌ EJECTED TICKERS:")
            for stats in ejected:
                logger.info(f"  {stats.ticker}: {stats.win_rate*100:.1f}% WR ({stats.wins}W/{stats.losses}L) - {stats.ejection_reason}")

        if monitored:
            logger.info("\n👁️ MONITORED TICKERS:")
            for stats in monitored:
                logger.info(f"  {stats.ticker}: {stats.win_rate*100:.1f}% WR ({stats.wins}W/{stats.losses}L)")

        if active:
            logger.info("\n✅ ACTIVE TICKERS:")
            for stats in active:
                logger.info(f"  {stats.ticker}: {stats.win_rate*100:.1f}% WR ({stats.wins}W/{stats.losses}L), P&L: ${stats.total_pnl:.2f}")

        logger.info("="*70 + "\n")

    def reset_database(self):
        """Clear all data from database (use with caution)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM ticker_stats")
        conn.commit()
        conn.close()
        logger.warning("⚠️ Database reset - all ticker stats cleared")

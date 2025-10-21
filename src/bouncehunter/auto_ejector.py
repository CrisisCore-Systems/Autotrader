"""
Auto-Ejector - Phase 2.5 Ticker Management

Automatic ejection system for consistently underperforming tickers.
Prevents capital allocation to statistically poor setups.

Ejection Criteria:
- Win rate < 40% over ≥ 5 completed trades
- Configurable thresholds for regime-specific performance
- Grace period for new tickers (minimum sample size)

Usage:
    from bouncehunter.auto_ejector import AutoEjector
    
    ejector = AutoEjector(min_trades=5, wr_threshold=0.40)
    ejector.evaluate_all()
    ejector.eject_ticker('AAPL', reason='Persistent low WR')
"""

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass


@dataclass
class EjectionCandidate:
    """Ticker eligible for ejection."""
    ticker: str
    total_trades: int
    win_rate: float
    normal_wr: float
    highvix_wr: float
    avg_return: float
    profit_factor: float
    reason: str


class AutoEjector:
    """
    Automatic ticker ejection system.
    
    Maintains the quality of the trading universe by removing
    persistently underperforming tickers from consideration.
    """
    
    def __init__(
        self,
        db_path: str = None,
        min_trades: int = 5,
        wr_threshold: float = 0.40,
        regime_threshold: float = 0.35
    ):
        """
        Initialize auto-ejector.
        
        Args:
            db_path: Path to database (default: bouncehunter_memory.db)
            min_trades: Minimum trades before ejection consideration
            wr_threshold: Overall win rate threshold
            regime_threshold: Regime-specific win rate threshold
        """
        if db_path is None:
            db_path = Path(__file__).parent.parent.parent / "bouncehunter_memory.db"
        
        self.db_path = Path(db_path)
        self.min_trades = min_trades
        self.wr_threshold = wr_threshold
        self.regime_threshold = regime_threshold
    
    def evaluate_all(self) -> List[EjectionCandidate]:
        """
        Evaluate all tickers and identify ejection candidates.
        
        Returns list of tickers meeting ejection criteria.
        """
        candidates = []
        
        with sqlite3.connect(self.db_path) as conn:
            # Get all tickers with sufficient trade history
            tickers = conn.execute("""
                SELECT DISTINCT ticker 
                FROM outcomes 
                GROUP BY ticker 
                HAVING COUNT(*) >= ?
            """, (self.min_trades,)).fetchall()
            
            for (ticker,) in tickers:
                candidate = self._evaluate_ticker(ticker, conn)
                if candidate:
                    candidates.append(candidate)
        
        return candidates
    
    def _evaluate_ticker(
        self, 
        ticker: str, 
        conn: sqlite3.Connection
    ) -> Optional[EjectionCandidate]:
        """Evaluate a single ticker for ejection."""
        # Get comprehensive stats
        outcomes = conn.execute("""
            SELECT 
                o.return_pct,
                f.regime
            FROM outcomes o
            JOIN fills f ON o.fill_id = f.fill_id
            WHERE o.ticker = ?
        """, (ticker,)).fetchall()
        
        if len(outcomes) < self.min_trades:
            return None
        
        # Calculate statistics
        total_trades = len(outcomes)
        winners = [o for o in outcomes if o[0] > 0]
        losers = [o for o in outcomes if o[0] <= 0]
        
        win_rate = len(winners) / total_trades
        avg_return = sum(o[0] for o in outcomes) / total_trades
        
        avg_win = sum(w[0] for w in winners) / len(winners) if winners else 0
        avg_loss = sum(l[0] for l in losers) / len(losers) if losers else 0
        profit_factor = abs(avg_win / avg_loss) if avg_loss != 0 else 0
        
        # Regime-specific analysis
        normal_outcomes = [o for o in outcomes if o[1] == 'normal']
        highvix_outcomes = [o for o in outcomes if o[1] == 'highvix']
        
        normal_wr = (
            len([o for o in normal_outcomes if o[0] > 0]) / len(normal_outcomes)
            if normal_outcomes else 0
        )
        highvix_wr = (
            len([o for o in highvix_outcomes if o[0] > 0]) / len(highvix_outcomes)
            if highvix_outcomes else 0
        )
        
        # Determine ejection reason
        reason = None
        
        if win_rate < self.wr_threshold:
            reason = f"Overall WR {win_rate:.1%} < {self.wr_threshold:.1%}"
        elif normal_wr < self.regime_threshold and len(normal_outcomes) >= 3:
            reason = f"Normal regime WR {normal_wr:.1%} < {self.regime_threshold:.1%}"
        elif highvix_wr < self.regime_threshold and len(highvix_outcomes) >= 3:
            reason = f"HighVIX regime WR {highvix_wr:.1%} < {self.regime_threshold:.1%}"
        elif profit_factor < 0.5:
            reason = f"Profit factor {profit_factor:.2f} < 0.5"
        
        if reason:
            return EjectionCandidate(
                ticker=ticker,
                total_trades=total_trades,
                win_rate=win_rate,
                normal_wr=normal_wr,
                highvix_wr=highvix_wr,
                avg_return=avg_return,
                profit_factor=profit_factor,
                reason=reason
            )
        
        return None
    
    def eject_ticker(self, ticker: str, reason: str) -> bool:
        """
        Eject a ticker from active consideration.
        
        Marks ticker as ejected in ticker_stats table.
        
        Args:
            ticker: Ticker symbol to eject
            reason: Ejection reason for audit trail
        
        Returns:
            True if ejection successful, False if ticker not found
        """
        with sqlite3.connect(self.db_path) as conn:
            # Check if ticker exists in ticker_stats
            exists = conn.execute("""
                SELECT COUNT(*) FROM ticker_stats WHERE ticker = ?
            """, (ticker,)).fetchone()[0]
            
            if not exists:
                # Create entry if doesn't exist
                conn.execute("""
                    INSERT INTO ticker_stats (
                        ticker, last_updated, ejected, eject_reason
                    ) VALUES (?, ?, 1, ?)
                """, (ticker, datetime.now().isoformat(), reason))
            else:
                # Update existing entry
                conn.execute("""
                    UPDATE ticker_stats 
                    SET ejected = 1, eject_reason = ?, last_updated = ?
                    WHERE ticker = ?
                """, (reason, datetime.now().isoformat(), ticker))
            
            return True
    
    def reinstate_ticker(self, ticker: str) -> bool:
        """
        Reinstate a previously ejected ticker.
        
        Useful for tickers that may have improved or for manual override.
        
        Args:
            ticker: Ticker symbol to reinstate
        
        Returns:
            True if reinstatement successful, False if ticker not found
        """
        with sqlite3.connect(self.db_path) as conn:
            result = conn.execute("""
                UPDATE ticker_stats 
                SET ejected = 0, eject_reason = NULL, last_updated = ?
                WHERE ticker = ?
            """, (datetime.now().isoformat(), ticker))
            
            return result.rowcount > 0
    
    def get_ejected_tickers(self) -> List[Dict]:
        """Get all currently ejected tickers."""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute("""
                SELECT ticker, eject_reason, last_updated
                FROM ticker_stats
                WHERE ejected = 1
                ORDER BY last_updated DESC
            """).fetchall()
            
            return [
                {
                    'ticker': r[0],
                    'reason': r[1],
                    'ejected_at': r[2]
                }
                for r in rows
            ]
    
    def auto_eject_all(self, dry_run: bool = False) -> Dict:
        """
        Automatically eject all candidates meeting criteria.
        
        Args:
            dry_run: If True, return candidates without ejecting
        
        Returns:
            Dict with 'ejected' count and 'candidates' list
        """
        candidates = self.evaluate_all()
        
        if dry_run:
            return {
                'ejected': 0,
                'candidates': [
                    {
                        'ticker': c.ticker,
                        'total_trades': c.total_trades,
                        'win_rate': c.win_rate,
                        'reason': c.reason
                    }
                    for c in candidates
                ]
            }
        
        # Execute ejections
        for candidate in candidates:
            self.eject_ticker(candidate.ticker, candidate.reason)
        
        return {
            'ejected': len(candidates),
            'candidates': [
                {
                    'ticker': c.ticker,
                    'total_trades': c.total_trades,
                    'win_rate': c.win_rate,
                    'reason': c.reason
                }
                for c in candidates
            ]
        }


if __name__ == '__main__':
    # Validation test and dry-run
    print("🚫 Auto-Ejector - Phase 2.5 Ticker Management")
    print("=" * 60)
    
    ejector = AutoEjector(min_trades=5, wr_threshold=0.40)
    
    # Dry run to see candidates
    result = ejector.auto_eject_all(dry_run=True)
    
    print(f"\nEjection Candidates: {len(result['candidates'])}")
    
    if result['candidates']:
        print("\n⚠️  Would eject:")
        for c in result['candidates']:
            print(f"  - {c['ticker']}: {c['win_rate']:.1%} WR over {c['total_trades']} trades")
            print(f"    Reason: {c['reason']}")
    else:
        print("\n✓ No ejection candidates (all tickers performing)")
    
    # Show currently ejected tickers
    ejected = ejector.get_ejected_tickers()
    if ejected:
        print(f"\n🔒 Currently ejected: {len(ejected)} tickers")
        for e in ejected:
            print(f"  - {e['ticker']}: {e['reason']}")
    else:
        print("\n✓ No tickers currently ejected")
    
    print("\n" + "=" * 60)
    print("Module ready. Run with dry_run=False to execute ejections.")

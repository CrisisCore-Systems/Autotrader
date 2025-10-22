"""
Memory Tracker - Phase 2.5 Bootstrap Module

Continuous learning loop that records trade → outcome → regime relationships
and feeds the memory system for adaptive ticker management.

Key Features:
- Signal quality scoring (perfect/good/marginal/poor)
- Regime correlation tracking (normal/highvix)
- Trade outcome annotation
- Automatic statistical accumulation
- Integration with existing agentic.py schema

Usage:
    from bouncehunter.memory_tracker import MemoryTracker
    
    tracker = MemoryTracker()
    tracker.log_signal_quality(signal, quality='perfect')
    tracker.update_outcome(fill_id, outcome, regime='normal')
    tracker.analyze_ticker_performance(ticker)
"""

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List
from dataclasses import dataclass


@dataclass
class TradeMetrics:
    """Comprehensive trade performance metrics."""
    ticker: str
    total_trades: int
    win_rate: float
    avg_return: float
    avg_win: float
    avg_loss: float
    profit_factor: float
    normal_regime_wr: float
    highvix_regime_wr: float
    perfect_signal_wr: float
    good_signal_wr: float


class MemoryTracker:
    """
    Phase 2.5 memory tracking system.
    
    Bridges the gap between Phase 2 validation and Phase 3 agentic operations
    by maintaining a continuous learning loop without neural network overhead.
    """
    
    def __init__(self, db_path: str = None):
        """Initialize memory tracker with database connection."""
        if db_path is None:
            db_path = Path(__file__).parent.parent.parent / "bouncehunter_memory.db"
        
        self.db_path = Path(db_path)
        self._ensure_schema()
    
    def _ensure_schema(self):
        """Ensure tracking tables exist (extends agentic.py schema)."""
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript("""
                -- Signal quality annotations (extends signals table)
                CREATE TABLE IF NOT EXISTS signal_quality (
                    signal_id TEXT PRIMARY KEY,
                    quality TEXT NOT NULL CHECK(quality IN ('perfect', 'good', 'marginal', 'poor')),
                    gap_flag TEXT,
                    volume_flag TEXT,
                    regime_at_signal TEXT NOT NULL,
                    vix_level REAL,
                    spy_state TEXT,
                    timestamp TEXT NOT NULL,
                    FOREIGN KEY (signal_id) REFERENCES signals(signal_id)
                );
                
                -- Regime state tracking for correlation analysis
                CREATE TABLE IF NOT EXISTS regime_snapshots (
                    snapshot_id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    spy_close REAL,
                    spy_regime TEXT,
                    vix_close REAL,
                    vix_regime TEXT,
                    market_state TEXT,
                    notes TEXT
                );
                
                -- Enhanced ticker statistics (complements ticker_stats)
                CREATE TABLE IF NOT EXISTS ticker_performance (
                    ticker TEXT PRIMARY KEY,
                    last_updated TEXT NOT NULL,
                    total_signals INTEGER DEFAULT 0,
                    total_fills INTEGER DEFAULT 0,
                    total_outcomes INTEGER DEFAULT 0,
                    perfect_signal_count INTEGER DEFAULT 0,
                    perfect_signal_wr REAL DEFAULT 0.0,
                    good_signal_count INTEGER DEFAULT 0,
                    good_signal_wr REAL DEFAULT 0.0,
                    normal_regime_count INTEGER DEFAULT 0,
                    normal_regime_wr REAL DEFAULT 0.0,
                    highvix_regime_count INTEGER DEFAULT 0,
                    highvix_regime_wr REAL DEFAULT 0.0,
                    avg_return REAL DEFAULT 0.0,
                    profit_factor REAL DEFAULT 0.0,
                    max_drawdown REAL DEFAULT 0.0,
                    ejection_eligible INTEGER DEFAULT 0,
                    ejection_reason TEXT
                );
                
                CREATE INDEX IF NOT EXISTS idx_signal_quality_ticker 
                    ON signal_quality(signal_id);
                CREATE INDEX IF NOT EXISTS idx_regime_snapshots_timestamp 
                    ON regime_snapshots(timestamp);
                CREATE INDEX IF NOT EXISTS idx_ticker_performance_updated 
                    ON ticker_performance(last_updated);
            """)
    
    def log_signal_quality(
        self,
        signal_id: str,
        ticker: str,
        quality: str,
        gap_pct: float,
        volume_ratio: float,
        regime: str,
        vix_level: Optional[float] = None,
        spy_state: Optional[str] = None
    ) -> None:
        """
        Log signal quality with risk flags.
        
        Args:
            signal_id: Unique signal identifier
            ticker: Ticker symbol
            quality: Signal quality (perfect/good/marginal/poor)
            gap_pct: Gap percentage
            volume_ratio: Volume ratio vs average
            regime: Market regime at signal
            vix_level: VIX level at signal time
            spy_state: SPY market state
        """
        # Risk flagging logic
        gap_flag = None
        if gap_pct < 10 or gap_pct > 15:
            gap_flag = 'out_of_optimal_range'
        
        volume_flag = None
        if volume_ratio < 4:
            volume_flag = 'low_vol'
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO signal_quality (
                    signal_id, quality, gap_flag, volume_flag, 
                    regime_at_signal, vix_level, spy_state, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                signal_id, quality, gap_flag, volume_flag,
                regime, vix_level, spy_state, datetime.now().isoformat()
            ))
    
    def capture_regime_snapshot(
        self,
        spy_close: float,
        spy_regime: str,
        vix_close: float,
        vix_regime: str,
        market_state: str = 'open',
        notes: Optional[str] = None
    ) -> str:
        """
        Capture market regime state for correlation analysis.
        
        Returns snapshot_id for later reference.
        """
        snapshot_id = f"regime_{datetime.now().timestamp()}"
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO regime_snapshots (
                    snapshot_id, timestamp, spy_close, spy_regime,
                    vix_close, vix_regime, market_state, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                snapshot_id, datetime.now().isoformat(),
                spy_close, spy_regime, vix_close, vix_regime,
                market_state, notes
            ))
        
        return snapshot_id
    
    def update_ticker_performance(self, ticker: str) -> None:
        """
        Recalculate comprehensive performance metrics for a ticker.
        
        Aggregates data from signals, fills, outcomes, and signal_quality tables.
        """
        with sqlite3.connect(self.db_path) as conn:
            # Get all outcomes for this ticker with quality annotations
            outcomes = conn.execute("""
                SELECT 
                    o.return_pct,
                    o.hit_target,
                    o.hit_stop,
                    f.regime,
                    sq.quality
                FROM outcomes o
                JOIN fills f ON o.fill_id = f.fill_id
                LEFT JOIN signal_quality sq ON f.signal_id = sq.signal_id
                WHERE o.ticker = ?
            """, (ticker,)).fetchall()
            
            if not outcomes:
                return
            
            # Calculate comprehensive statistics
            total_outcomes = len(outcomes)
            winners = [o for o in outcomes if o[0] > 0]
            losers = [o for o in outcomes if o[0] <= 0]
            
            win_rate = len(winners) / total_outcomes if total_outcomes > 0 else 0
            avg_return = sum(o[0] for o in outcomes) / total_outcomes
            
            avg_win = sum(w[0] for w in winners) / len(winners) if winners else 0
            avg_loss = sum(l[0] for l in losers) / len(losers) if losers else 0
            
            profit_factor = abs(avg_win / avg_loss) if avg_loss != 0 else 0
            
            # Regime-specific stats
            normal_outcomes = [o for o in outcomes if o[3] == 'normal']
            highvix_outcomes = [o for o in outcomes if o[3] == 'highvix']
            
            normal_wr = (
                len([o for o in normal_outcomes if o[0] > 0]) / len(normal_outcomes)
                if normal_outcomes else 0
            )
            highvix_wr = (
                len([o for o in highvix_outcomes if o[0] > 0]) / len(highvix_outcomes)
                if highvix_outcomes else 0
            )
            
            # Signal quality stats
            perfect_outcomes = [o for o in outcomes if o[4] == 'perfect']
            good_outcomes = [o for o in outcomes if o[4] == 'good']
            
            perfect_wr = (
                len([o for o in perfect_outcomes if o[0] > 0]) / len(perfect_outcomes)
                if perfect_outcomes else 0
            )
            good_wr = (
                len([o for o in good_outcomes if o[0] > 0]) / len(good_outcomes)
                if good_outcomes else 0
            )
            
            # Ejection eligibility (< 40% WR and > 5 trades)
            ejection_eligible = 1 if win_rate < 0.40 and total_outcomes >= 5 else 0
            ejection_reason = None
            if ejection_eligible:
                ejection_reason = f"Low WR: {win_rate:.1%} over {total_outcomes} trades"
            
            # Update ticker_performance table
            conn.execute("""
                INSERT OR REPLACE INTO ticker_performance (
                    ticker, last_updated, total_outcomes,
                    perfect_signal_count, perfect_signal_wr,
                    good_signal_count, good_signal_wr,
                    normal_regime_count, normal_regime_wr,
                    highvix_regime_count, highvix_regime_wr,
                    avg_return, profit_factor,
                    ejection_eligible, ejection_reason
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                ticker, datetime.now().isoformat(), total_outcomes,
                len(perfect_outcomes), perfect_wr,
                len(good_outcomes), good_wr,
                len(normal_outcomes), normal_wr,
                len(highvix_outcomes), highvix_wr,
                avg_return, profit_factor,
                ejection_eligible, ejection_reason
            ))
    
    def get_ticker_metrics(self, ticker: str) -> Optional[TradeMetrics]:
        """Retrieve comprehensive ticker performance metrics."""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute("""
                SELECT 
                    ticker, total_outcomes, normal_regime_wr, highvix_regime_wr,
                    perfect_signal_wr, good_signal_wr, avg_return, profit_factor
                FROM ticker_performance
                WHERE ticker = ?
            """, (ticker,)).fetchone()
            
            if not row:
                return None
            
            # Also get win rate and loss stats from outcomes
            outcomes = conn.execute("""
                SELECT return_pct FROM outcomes WHERE ticker = ?
            """, (ticker,)).fetchall()
            
            if not outcomes:
                return None
            
            winners = [o[0] for o in outcomes if o[0] > 0]
            losers = [o[0] for o in outcomes if o[0] <= 0]
            
            win_rate = len(winners) / len(outcomes) if outcomes else 0
            avg_win = sum(winners) / len(winners) if winners else 0
            avg_loss = sum(losers) / len(losers) if losers else 0
            
            return TradeMetrics(
                ticker=row[0],
                total_trades=row[1],
                win_rate=win_rate,
                avg_return=row[6],
                avg_win=avg_win,
                avg_loss=avg_loss,
                profit_factor=row[7],
                normal_regime_wr=row[2],
                highvix_regime_wr=row[3],
                perfect_signal_wr=row[4],
                good_signal_wr=row[5]
            )
    
    def get_ejection_candidates(self) -> List[Dict]:
        """Get all tickers eligible for ejection."""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute("""
                SELECT 
                    ticker, total_outcomes, normal_regime_wr, 
                    highvix_regime_wr, avg_return, ejection_reason
                FROM ticker_performance
                WHERE ejection_eligible = 1
                ORDER BY normal_regime_wr ASC
            """).fetchall()
            
            return [
                {
                    'ticker': r[0],
                    'total_trades': r[1],
                    'normal_wr': r[2],
                    'highvix_wr': r[3],
                    'avg_return': r[4],
                    'reason': r[5]
                }
                for r in rows
            ]
    
    def update_all_tickers(self) -> int:
        """
        Recalculate performance for all tickers with outcomes.
        
        Returns count of tickers updated.
        """
        with sqlite3.connect(self.db_path) as conn:
            tickers = conn.execute("""
                SELECT DISTINCT ticker FROM outcomes
            """).fetchall()
        
        for (ticker,) in tickers:
            self.update_ticker_performance(ticker)
        
        return len(tickers)
    
    def get_quality_stats(self, quality: str) -> Dict:
        """
        Get statistics for a specific signal quality tier.
        
        Phase 2.5 Dashboard Support - Returns aggregated stats for
        perfect/good/marginal/poor signals.
        
        Args:
            quality: 'perfect', 'good', 'marginal', or 'poor'
        
        Returns:
            Dict with total_signals, total_wins, win_rate
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Check if signal_quality table exists
                cursor = conn.execute("""
                    SELECT name FROM sqlite_master 
                    WHERE type='table' AND name='signal_quality'
                """)
                
                if not cursor.fetchone():
                    # Table doesn't exist yet - return zeros
                    return {
                        'total_signals': 0,
                        'total_wins': 0,
                        'win_rate': 0
                    }
                
                # Join signal_quality with outcomes to get win/loss data
                cursor = conn.execute("""
                    SELECT 
                        COUNT(*) as total_signals,
                        SUM(CASE WHEN o.return_pct > 0 THEN 1 ELSE 0 END) as total_wins
                    FROM signal_quality sq
                    JOIN fills f ON sq.signal_id = f.signal_id
                    JOIN outcomes o ON f.fill_id = o.fill_id
                    WHERE sq.quality = ?
                """, (quality,))
                
                row = cursor.fetchone()
                
                if row and row[0]:
                    total = row[0] or 0
                    wins = row[1] or 0
                    return {
                        'total_signals': total,
                        'total_wins': wins,
                        'win_rate': (wins / total * 100) if total > 0 else 0
                    }
                
                return {
                    'total_signals': 0,
                    'total_wins': 0,
                    'win_rate': 0
                }
                
        except Exception as e:
            print(f"Error in get_quality_stats: {e}")
            return {
                'total_signals': 0,
                'total_wins': 0,
                'win_rate': 0
            }
    
    def classify_signal_quality(self, signal: Dict) -> str:
        """
        Classify a signal into quality tiers for Phase 2.5.
        
        Args:
            signal: Dict with gap_pct, volume_ratio, regime
        
        Returns:
            'perfect', 'good', 'marginal', or 'poor'
        """
        gap_pct = signal.get('gap_pct', 0)
        volume_ratio = signal.get('volume_ratio', 0)
        regime = signal.get('regime', 'normal')
        
        # Perfect: 10-15% gap, 4-10x vol, normal regime
        if (10 <= gap_pct <= 15 and 
            4 <= volume_ratio <= 10 and 
            regime == 'normal'):
            return 'perfect'
        
        # Good: One metric slightly outside optimal
        good_conditions = 0
        if 8 <= gap_pct <= 17:
            good_conditions += 1
        if volume_ratio >= 3:
            good_conditions += 1
        if regime == 'normal':
            good_conditions += 1
        
        if good_conditions >= 2:
            return 'good'
        
        # Marginal: Some red flags but tradeable
        if gap_pct >= 5 and volume_ratio >= 2:
            return 'marginal'
        
        # Poor: Multiple failures
        return 'poor'
    
    def record_signal(self, signal_id: str, signal: Dict, quality: str):
        """
        Record a new signal for Phase 2.5 tracking.
        
        Note: Current schema doesn't have signal_tracking table.
        This is a placeholder for future integration.
        
        Args:
            signal_id: Unique signal identifier
            signal: Signal data dict
            quality: Quality classification
        """
        # Placeholder - would insert into signal_tracking table
        # For now, just pass (signals tracked via fills table)
        pass
    
    def update_after_trade(self, signal_id: str, outcome: str, return_pct: float):
        """
        Update memory system after a trade closes.
        
        Note: Current schema tracks via fills/outcomes tables.
        This is a placeholder for signal_tracking integration.
        
        Args:
            signal_id: Signal identifier
            outcome: 'win' or 'loss'
            return_pct: Return percentage
        """
        # Placeholder - would update signal_tracking table
        # For now, ticker_performance updates happen via update_ticker_performance()
        pass
    
    def get_regime_correlation(self) -> Dict:
        """
        Get win rates by regime for Phase 2.5 dashboard.
        
        Returns:
            Dict with normal_wr, highvix_wr stats
        """
        # Placeholder - would query signal_tracking by regime
        # For now, return empty stats
        return {
            'normal': {'total': 0, 'wins': 0, 'wr': 0},
            'highvix': {'total': 0, 'wins': 0, 'wr': 0}
        }


def risk_flag(gap_pct: float, volume_ratio: float) -> Optional[str]:
    """
    Utility function for risk flagging signals.
    
    Args:
        gap_pct: Gap percentage
        volume_ratio: Volume ratio vs average
    
    Returns:
        Risk flag string or None if signal is clean
    """
    flags = []
    
    if gap_pct < 10 or gap_pct > 15:
        flags.append('out_of_optimal_range')
    
    if volume_ratio < 4:
        flags.append('low_vol')
    
    return ', '.join(flags) if flags else None


if __name__ == '__main__':
    # Quick validation test
    print("🧠 Memory Tracker - Phase 2.5 Bootstrap")
    print("=" * 60)
    
    tracker = MemoryTracker()
    print("✓ Schema initialized")
    
    updated = tracker.update_all_tickers()
    print(f"✓ Updated {updated} tickers")
    
    candidates = tracker.get_ejection_candidates()
    if candidates:
        print(f"\n⚠️  {len(candidates)} ejection candidates:")
        for c in candidates:
            print(f"  - {c['ticker']}: {c['normal_wr']:.1%} WR ({c['reason']})")
    else:
        print("\n✓ No ejection candidates (all tickers performing)")
    
    print("\n" + "=" * 60)
    print("Module ready for integration.")

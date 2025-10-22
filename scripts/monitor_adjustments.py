#!/usr/bin/env python3
"""
Monitor Adjustments - Real-time Monitoring for Intelligent Adjustment System

Tracks adjustment effectiveness during paper trading:
- Win rate by adjustment range
- VIX provider availability
- Regime detector accuracy
- Adjustment calculation performance
- Symbol-specific learning data

Run periodically to collect metrics for weekly reports.
"""

import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple
import yaml

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class AdjustmentMonitor:
    """Monitor intelligent adjustment system performance."""
    
    def __init__(self, db_path: str = "bouncehunter_memory.db", config_path: str = "configs/my_paper_config.yaml"):
        """Initialize monitor.
        
        Args:
            db_path: Path to BounceHunter memory database
            config_path: Path to paper trading configuration
        """
        self.db_path = Path(db_path)
        self.config_path = Path(config_path)
        
        if not self.db_path.exists():
            raise FileNotFoundError(f"Database not found: {self.db_path}")
        if not self.config_path.exists():
            raise FileNotFoundError(f"Config not found: {self.config_path}")
            
        # Load configuration
        with open(self.config_path) as f:
            self.config = yaml.safe_load(f)
            
        logger.info(f"Monitor initialized: DB={self.db_path}, Config={self.config_path}")
    
    def _table_exists(self, conn: sqlite3.Connection, table_name: str) -> bool:
        """Check if a table exists in the database.
        
        Args:
            conn: Database connection
            table_name: Name of table to check
            
        Returns:
            True if table exists, False otherwise
        """
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
        return cursor.fetchone() is not None
    
    def get_recent_exits(self, hours: int = 24) -> List[Dict]:
        """Get recent position exits with adjustment data.
        
        Args:
            hours: Number of hours to look back
            
        Returns:
            List of exit records with adjustment information
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
        
        # Check if table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='position_exits'")
        if not cursor.fetchone():
            logger.warning("Table 'position_exits' does not exist yet (no trades recorded)")
            conn.close()
            return []
        
        query = """
        SELECT 
            symbol,
            entry_time,
            exit_time,
            entry_price,
            exit_price,
            tier,
            exit_reason,
            pnl_percent,
            base_target,
            adjusted_target,
            volatility_adjustment,
            time_adjustment,
            regime_adjustment,
            vix_level,
            market_regime
        FROM position_exits
        WHERE exit_time > ?
        ORDER BY exit_time DESC
        """
        
        try:
            cursor.execute(query, (cutoff,))
            exits = [dict(row) for row in cursor.fetchall()]
            logger.info(f"Retrieved {len(exits)} exits from last {hours} hours")
        except sqlite3.OperationalError as e:
            logger.warning(f"Error querying position_exits: {e}")
            exits = []
        finally:
            conn.close()
        
        return exits
    
    def calculate_win_rate_by_adjustment(self, exits: List[Dict]) -> Dict[str, Dict]:
        """Calculate win rate by adjustment range.
        
        Args:
            exits: List of exit records
            
        Returns:
            Dict mapping adjustment ranges to win rates
        """
        # Group by adjustment range
        ranges = {
            "high_increase": [],  # +0.5% or more
            "moderate_increase": [],  # +0.1% to +0.5%
            "neutral": [],  # -0.1% to +0.1%
            "moderate_decrease": [],  # -0.5% to -0.1%
            "high_decrease": []  # -0.5% or less
        }
        
        for exit in exits:
            if not exit.get('adjusted_target') or not exit.get('base_target'):
                continue
                
            adjustment = exit['adjusted_target'] - exit['base_target']
            
            if adjustment >= 0.5:
                ranges["high_increase"].append(exit)
            elif adjustment >= 0.1:
                ranges["moderate_increase"].append(exit)
            elif adjustment >= -0.1:
                ranges["neutral"].append(exit)
            elif adjustment >= -0.5:
                ranges["moderate_decrease"].append(exit)
            else:
                ranges["high_decrease"].append(exit)
        
        # Calculate win rates
        results = {}
        for range_name, range_exits in ranges.items():
            if not range_exits:
                results[range_name] = {
                    "count": 0,
                    "wins": 0,
                    "win_rate": 0.0,
                    "avg_pnl": 0.0
                }
                continue
            
            wins = sum(1 for e in range_exits if e.get('pnl_percent', 0) > 0)
            avg_pnl = sum(e.get('pnl_percent', 0) for e in range_exits) / len(range_exits)
            
            results[range_name] = {
                "count": len(range_exits),
                "wins": wins,
                "win_rate": (wins / len(range_exits)) * 100,
                "avg_pnl": avg_pnl
            }
        
        return results
    
    def check_vix_provider_health(self) -> Dict:
        """Check VIX provider availability and accuracy.
        
        Returns:
            Dict with VIX provider metrics
        """
        conn = sqlite3.connect(self.db_path)
        
        # Check if table exists
        if not self._table_exists(conn, 'position_exits'):
            conn.close()
            return {
                "total_exits": 0,
                "exits_with_vix": 0,
                "availability_pct": 0,
                "health": "NO DATA"
            }
        
        cursor = conn.cursor()
        
        # Check recent VIX data points (last 24h)
        cutoff = (datetime.now() - timedelta(hours=24)).isoformat()
        
        query = """
        SELECT COUNT(*) as total,
               SUM(CASE WHEN vix_level IS NOT NULL THEN 1 ELSE 0 END) as with_vix
        FROM position_exits
        WHERE exit_time > ?
        """
        
        cursor.execute(query, (cutoff,))
        row = cursor.fetchone()
        conn.close()
        
        total, with_vix = row
        availability = (with_vix / total * 100) if total > 0 else 0
        
        return {
            "total_exits": total,
            "exits_with_vix": with_vix,
            "availability_pct": availability,
            "health": "GOOD" if availability >= 95 else "DEGRADED" if availability >= 80 else "POOR"
        }
    
    def check_regime_detector_health(self) -> Dict:
        """Check market regime detector accuracy.
        
        Returns:
            Dict with regime detector metrics
        """
        conn = sqlite3.connect(self.db_path)
        
        # Check if table exists
        if not self._table_exists(conn, 'position_exits'):
            conn.close()
            return {
                "total_exits": 0,
                "exits_with_regime": 0,
                "availability_pct": 0,
                "regime_distribution": {},
                "health": "NO DATA"
            }
        
        cursor = conn.cursor()
        
        # Check recent regime data (last 24h)
        cutoff = (datetime.now() - timedelta(hours=24)).isoformat()
        
        query = """
        SELECT COUNT(*) as total,
               SUM(CASE WHEN market_regime IS NOT NULL THEN 1 ELSE 0 END) as with_regime,
               market_regime,
               COUNT(*) as regime_count
        FROM position_exits
        WHERE exit_time > ?
        GROUP BY market_regime
        """
        
        cursor.execute(query, (cutoff,))
        rows = cursor.fetchall()
        conn.close()
        
        total = sum(row[3] for row in rows)
        with_regime = sum(row[1] for row in rows)
        availability = (with_regime / total * 100) if total > 0 else 0
        
        regime_distribution = {row[2]: row[3] for row in rows if row[2]}
        
        return {
            "total_exits": total,
            "exits_with_regime": with_regime,
            "availability_pct": availability,
            "regime_distribution": regime_distribution,
            "health": "GOOD" if availability >= 95 else "DEGRADED" if availability >= 80 else "POOR"
        }
    
    def get_symbol_learning_stats(self) -> Dict[str, Dict]:
        """Get symbol-specific learning statistics.
        
        Returns:
            Dict mapping symbols to their learning stats
        """
        conn = sqlite3.connect(self.db_path)
        
        # Check if table exists
        if not self._table_exists(conn, 'position_exits'):
            conn.close()
            return {}
        
        cursor = conn.cursor()
        
        query = """
        SELECT 
            symbol,
            COUNT(*) as total_exits,
            AVG(pnl_percent) as avg_pnl,
            AVG(adjusted_target - base_target) as avg_adjustment,
            SUM(CASE WHEN pnl_percent > 0 THEN 1 ELSE 0 END) as wins
        FROM position_exits
        WHERE adjusted_target IS NOT NULL
        GROUP BY symbol
        HAVING COUNT(*) >= 3
        ORDER BY total_exits DESC
        """
        
        cursor.execute(query)
        rows = cursor.fetchall()
        conn.close()
        
        stats = {}
        for row in rows:
            symbol, total, avg_pnl, avg_adj, wins = row
            win_rate = (wins / total * 100) if total > 0 else 0
            
            stats[symbol] = {
                "total_exits": total,
                "avg_pnl": avg_pnl,
                "avg_adjustment": avg_adj,
                "win_rate": win_rate,
                "learning_enabled": total >= self.config.get('adjustments', {}).get('symbol_learning', {}).get('min_exits', 3)
            }
        
        return stats
    
    def generate_report(self, hours: int = 24) -> str:
        """Generate monitoring report.
        
        Args:
            hours: Hours to look back
            
        Returns:
            Formatted report string
        """
        logger.info(f"Generating {hours}h monitoring report...")
        
        exits = self.get_recent_exits(hours)
        win_rates = self.calculate_win_rate_by_adjustment(exits)
        vix_health = self.check_vix_provider_health()
        regime_health = self.check_regime_detector_health()
        symbol_stats = self.get_symbol_learning_stats()
        
        report = []
        report.append("=" * 80)
        report.append(f"ADJUSTMENT MONITORING REPORT - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"Period: Last {hours} hours")
        report.append("=" * 80)
        report.append("")
        
        # Overall stats
        report.append("OVERALL STATISTICS")
        report.append("-" * 80)
        report.append(f"Total exits: {len(exits)}")
        total_wins = sum(1 for e in exits if e.get('pnl_percent', 0) > 0)
        overall_win_rate = (total_wins / len(exits) * 100) if exits else 0
        report.append(f"Overall win rate: {overall_win_rate:.1f}%")
        report.append("")
        
        # Win rate by adjustment
        report.append("WIN RATE BY ADJUSTMENT RANGE")
        report.append("-" * 80)
        for range_name, stats in win_rates.items():
            if stats['count'] == 0:
                continue
            report.append(f"{range_name:20s}: {stats['count']:3d} exits, {stats['win_rate']:5.1f}% win rate, {stats['avg_pnl']:+6.2f}% avg PnL")
        report.append("")
        
        # VIX provider health
        report.append("VIX PROVIDER HEALTH")
        report.append("-" * 80)
        report.append(f"Status: {vix_health['health']}")
        report.append(f"Availability: {vix_health['availability_pct']:.1f}% ({vix_health['exits_with_vix']}/{vix_health['total_exits']} exits)")
        report.append("")
        
        # Regime detector health
        report.append("REGIME DETECTOR HEALTH")
        report.append("-" * 80)
        report.append(f"Status: {regime_health['health']}")
        report.append(f"Availability: {regime_health['availability_pct']:.1f}% ({regime_health['exits_with_regime']}/{regime_health['total_exits']} exits)")
        if regime_health.get('regime_distribution'):
            report.append("Regime distribution:")
            for regime, count in regime_health['regime_distribution'].items():
                report.append(f"  {regime}: {count} exits")
        report.append("")
        
        # Symbol learning
        if symbol_stats:
            report.append("SYMBOL LEARNING STATUS")
            report.append("-" * 80)
            for symbol, stats in list(symbol_stats.items())[:10]:  # Top 10
                learning = "[LEARNING]" if stats['learning_enabled'] else "[BASELINE]"
                report.append(f"{symbol:8s} {learning:12s}: {stats['total_exits']:3d} exits, {stats['win_rate']:5.1f}% win, {stats['avg_adjustment']:+6.2f}% avg adj")
        report.append("")
        
        report.append("=" * 80)
        
        return "\n".join(report)


def main():
    """Run monitoring report."""
    try:
        monitor = AdjustmentMonitor()
        
        # Generate 24h report
        report = monitor.generate_report(hours=24)
        print(report)
        
        # Save to file
        report_file = Path("reports/adjustment_monitoring.txt")
        report_file.parent.mkdir(exist_ok=True)
        with open(report_file, "w") as f:
            f.write(report)
        
        logger.info(f"Report saved to {report_file}")
        
    except Exception as e:
        logger.error(f"Monitoring failed: {e}", exc_info=True)
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())

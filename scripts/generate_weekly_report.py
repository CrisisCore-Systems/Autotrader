#!/usr/bin/env python3
"""
Weekly Report Generator - Performance Analysis for Intelligent Adjustments

Generates comprehensive weekly reports analyzing:
- Overall win rate improvement vs baseline
- Adjustment effectiveness by component (volatility, time, regime)
- Symbol-specific learning performance
- VIX provider and regime detector reliability
- Recommendations for configuration tuning

Run weekly to track adjustment system performance.
"""

import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple
import yaml
from collections import defaultdict

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class WeeklyReportGenerator:
    """Generate weekly performance reports for intelligent adjustments."""
    
    def __init__(self, db_path: str = "bouncehunter_memory.db", config_path: str = "configs/my_paper_config.yaml"):
        """Initialize report generator.
        
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
            
        logger.info(f"Report generator initialized")
    
    def get_weekly_exits(self, weeks: int = 1) -> Tuple[List[Dict], List[Dict]]:
        """Get exits with and without adjustments from last N weeks.
        
        Args:
            weeks: Number of weeks to look back
            
        Returns:
            Tuple of (exits_with_adjustments, exits_without_adjustments)
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cutoff = (datetime.now() - timedelta(weeks=weeks)).isoformat()
        
        # Exits with adjustments
        query_adjusted = """
        SELECT *
        FROM position_exits
        WHERE exit_time > ?
        AND adjusted_target IS NOT NULL
        ORDER BY exit_time DESC
        """
        cursor.execute(query_adjusted, (cutoff,))
        adjusted_exits = [dict(row) for row in cursor.fetchall()]
        
        # Exits without adjustments (baseline)
        query_baseline = """
        SELECT *
        FROM position_exits
        WHERE exit_time > ?
        AND adjusted_target IS NULL
        ORDER BY exit_time DESC
        """
        cursor.execute(query_baseline, (cutoff,))
        baseline_exits = [dict(row) for row in cursor.fetchall()]
        
        conn.close()
        
        logger.info(f"Retrieved {len(adjusted_exits)} adjusted exits, {len(baseline_exits)} baseline exits")
        return adjusted_exits, baseline_exits
    
    def calculate_performance_metrics(self, exits: List[Dict]) -> Dict:
        """Calculate performance metrics for a set of exits.
        
        Args:
            exits: List of exit records
            
        Returns:
            Dict with performance metrics
        """
        if not exits:
            return {
                "total_exits": 0,
                "wins": 0,
                "losses": 0,
                "win_rate": 0.0,
                "avg_pnl": 0.0,
                "avg_win": 0.0,
                "avg_loss": 0.0,
                "best_pnl": 0.0,
                "worst_pnl": 0.0,
                "profit_factor": 0.0
            }
        
        wins = [e for e in exits if e.get('pnl_percent', 0) > 0]
        losses = [e for e in exits if e.get('pnl_percent', 0) <= 0]
        
        total_profit = sum(e['pnl_percent'] for e in wins) if wins else 0
        total_loss = abs(sum(e['pnl_percent'] for e in losses)) if losses else 0
        
        return {
            "total_exits": len(exits),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": (len(wins) / len(exits)) * 100,
            "avg_pnl": sum(e.get('pnl_percent', 0) for e in exits) / len(exits),
            "avg_win": sum(e['pnl_percent'] for e in wins) / len(wins) if wins else 0,
            "avg_loss": sum(e['pnl_percent'] for e in losses) / len(losses) if losses else 0,
            "best_pnl": max(e.get('pnl_percent', 0) for e in exits),
            "worst_pnl": min(e.get('pnl_percent', 0) for e in exits),
            "profit_factor": total_profit / total_loss if total_loss > 0 else 0
        }
    
    def analyze_adjustment_components(self, exits: List[Dict]) -> Dict:
        """Analyze effectiveness of individual adjustment components.
        
        Args:
            exits: List of exits with adjustments
            
        Returns:
            Dict with component analysis
        """
        volatility_adjustments = defaultdict(list)
        time_adjustments = defaultdict(list)
        regime_adjustments = defaultdict(list)
        
        for exit in exits:
            if not exit.get('adjusted_target'):
                continue
            
            pnl = exit.get('pnl_percent', 0)
            
            # Volatility component
            vol_adj = exit.get('volatility_adjustment', 0)
            if vol_adj != 0:
                key = "increased" if vol_adj > 0 else "decreased"
                volatility_adjustments[key].append(pnl)
            
            # Time component
            time_adj = exit.get('time_adjustment', 0)
            if time_adj != 0:
                key = "increased" if time_adj > 0 else "decreased"
                time_adjustments[key].append(pnl)
            
            # Regime component
            regime_adj = exit.get('regime_adjustment', 0)
            if regime_adj != 0:
                key = "increased" if regime_adj > 0 else "decreased"
                regime_adjustments[key].append(pnl)
        
        def analyze_component(adjustments: Dict[str, List[float]]) -> Dict:
            """Helper to analyze a component."""
            result = {}
            for key, pnls in adjustments.items():
                if pnls:
                    wins = sum(1 for p in pnls if p > 0)
                    result[key] = {
                        "count": len(pnls),
                        "win_rate": (wins / len(pnls)) * 100,
                        "avg_pnl": sum(pnls) / len(pnls)
                    }
            return result
        
        return {
            "volatility": analyze_component(volatility_adjustments),
            "time": analyze_component(time_adjustments),
            "regime": analyze_component(regime_adjustments)
        }
    
    def analyze_symbol_learning(self, exits: List[Dict]) -> Dict[str, Dict]:
        """Analyze symbol-specific learning performance.
        
        Args:
            exits: List of exits with adjustments
            
        Returns:
            Dict mapping symbols to learning metrics
        """
        symbol_data = defaultdict(list)
        
        for exit in exits:
            symbol = exit.get('symbol')
            if symbol and exit.get('adjusted_target'):
                symbol_data[symbol].append(exit)
        
        results = {}
        min_exits = self.config.get('adjustments', {}).get('symbol_learning', {}).get('min_exits', 3)
        
        for symbol, symbol_exits in symbol_data.items():
            if len(symbol_exits) >= min_exits:
                wins = sum(1 for e in symbol_exits if e.get('pnl_percent', 0) > 0)
                avg_pnl = sum(e.get('pnl_percent', 0) for e in symbol_exits) / len(symbol_exits)
                avg_adj = sum(e.get('adjusted_target', 0) - e.get('base_target', 0) for e in symbol_exits) / len(symbol_exits)
                
                results[symbol] = {
                    "total_exits": len(symbol_exits),
                    "win_rate": (wins / len(symbol_exits)) * 100,
                    "avg_pnl": avg_pnl,
                    "avg_adjustment": avg_adj,
                    "learning_active": len(symbol_exits) >= min_exits
                }
        
        return results
    
    def get_provider_reliability(self, weeks: int = 1) -> Dict:
        """Calculate provider reliability metrics.
        
        Args:
            weeks: Number of weeks to analyze
            
        Returns:
            Dict with reliability metrics
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cutoff = (datetime.now() - timedelta(weeks=weeks)).isoformat()
        
        # VIX provider
        query = """
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN vix_level IS NOT NULL THEN 1 ELSE 0 END) as with_vix,
            AVG(CASE WHEN vix_level IS NOT NULL THEN 1 ELSE 0 END) as vix_rate
        FROM position_exits
        WHERE exit_time > ?
        """
        cursor.execute(query, (cutoff,))
        vix_stats = cursor.fetchone()
        
        # Regime detector
        query = """
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN market_regime IS NOT NULL THEN 1 ELSE 0 END) as with_regime,
            AVG(CASE WHEN market_regime IS NOT NULL THEN 1 ELSE 0 END) as regime_rate
        FROM position_exits
        WHERE exit_time > ?
        """
        cursor.execute(query, (cutoff,))
        regime_stats = cursor.fetchone()
        
        conn.close()
        
        return {
            "vix_provider": {
                "total_exits": vix_stats[0],
                "available": vix_stats[1],
                "availability_pct": (vix_stats[1] / vix_stats[0] * 100) if vix_stats[0] > 0 else 0
            },
            "regime_detector": {
                "total_exits": regime_stats[0],
                "available": regime_stats[1],
                "availability_pct": (regime_stats[1] / regime_stats[0] * 100) if regime_stats[0] > 0 else 0
            }
        }
    
    def generate_recommendations(self, adjusted_metrics: Dict, baseline_metrics: Dict, component_analysis: Dict) -> List[str]:
        """Generate configuration tuning recommendations.
        
        Args:
            adjusted_metrics: Metrics for adjusted exits
            baseline_metrics: Metrics for baseline exits
            component_analysis: Component effectiveness analysis
            
        Returns:
            List of recommendation strings
        """
        recommendations = []
        
        # Win rate comparison
        win_rate_diff = adjusted_metrics['win_rate'] - baseline_metrics['win_rate']
        if win_rate_diff >= 5:
            recommendations.append(f"✓ Win rate improved by {win_rate_diff:.1f}% - adjustments are effective!")
        elif win_rate_diff >= 2:
            recommendations.append(f"○ Win rate improved by {win_rate_diff:.1f}% - moderate effectiveness")
        elif win_rate_diff < 0:
            recommendations.append(f"✗ Win rate decreased by {abs(win_rate_diff):.1f}% - review adjustment ranges")
        
        # Component effectiveness
        vol_analysis = component_analysis.get('volatility', {})
        if vol_analysis:
            if 'increased' in vol_analysis and 'decreased' in vol_analysis:
                inc_wr = vol_analysis['increased']['win_rate']
                dec_wr = vol_analysis['decreased']['win_rate']
                if inc_wr > dec_wr + 10:
                    recommendations.append("Consider increasing volatility_low adjustment (targets too conservative)")
                elif dec_wr > inc_wr + 10:
                    recommendations.append("Consider decreasing volatility_high adjustment (targets too aggressive)")
        
        # Profit factor
        if adjusted_metrics['profit_factor'] > baseline_metrics.get('profit_factor', 0):
            recommendations.append("✓ Profit factor improved - better risk/reward balance")
        
        # Average PnL
        avg_pnl_diff = adjusted_metrics['avg_pnl'] - baseline_metrics.get('avg_pnl', 0)
        if avg_pnl_diff > 0.5:
            recommendations.append(f"✓ Average PnL improved by {avg_pnl_diff:.2f}%")
        
        return recommendations
    
    def generate_report(self, weeks: int = 1) -> str:
        """Generate comprehensive weekly report.
        
        Args:
            weeks: Number of weeks to analyze
            
        Returns:
            Formatted report string
        """
        logger.info(f"Generating {weeks}-week performance report...")
        
        adjusted_exits, baseline_exits = self.get_weekly_exits(weeks)
        adjusted_metrics = self.calculate_performance_metrics(adjusted_exits)
        baseline_metrics = self.calculate_performance_metrics(baseline_exits)
        component_analysis = self.analyze_adjustment_components(adjusted_exits)
        symbol_learning = self.analyze_symbol_learning(adjusted_exits)
        reliability = self.get_provider_reliability(weeks)
        recommendations = self.generate_recommendations(adjusted_metrics, baseline_metrics, component_analysis)
        
        report = []
        report.append("=" * 100)
        report.append(f"WEEKLY PERFORMANCE REPORT - Intelligent Adjustments System")
        report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"Period: Last {weeks} week(s)")
        report.append("=" * 100)
        report.append("")
        
        # Executive Summary
        report.append("EXECUTIVE SUMMARY")
        report.append("-" * 100)
        win_rate_diff = adjusted_metrics['win_rate'] - baseline_metrics['win_rate']
        report.append(f"Win Rate Improvement: {win_rate_diff:+.1f}% ({baseline_metrics['win_rate']:.1f}% baseline → {adjusted_metrics['win_rate']:.1f}% adjusted)")
        report.append(f"Total Exits Analyzed: {adjusted_metrics['total_exits']} adjusted, {baseline_metrics['total_exits']} baseline")
        report.append(f"Average PnL: {adjusted_metrics['avg_pnl']:+.2f}% (adjusted) vs {baseline_metrics['avg_pnl']:+.2f}% (baseline)")
        report.append(f"Profit Factor: {adjusted_metrics['profit_factor']:.2f} (adjusted) vs {baseline_metrics['profit_factor']:.2f} (baseline)")
        report.append("")
        
        # Detailed Metrics - Adjusted
        report.append("ADJUSTED EXITS PERFORMANCE")
        report.append("-" * 100)
        report.append(f"Total exits: {adjusted_metrics['total_exits']} ({adjusted_metrics['wins']} wins, {adjusted_metrics['losses']} losses)")
        report.append(f"Win rate: {adjusted_metrics['win_rate']:.1f}%")
        report.append(f"Average PnL: {adjusted_metrics['avg_pnl']:+.2f}%")
        report.append(f"Average win: {adjusted_metrics['avg_win']:+.2f}%")
        report.append(f"Average loss: {adjusted_metrics['avg_loss']:+.2f}%")
        report.append(f"Best trade: {adjusted_metrics['best_pnl']:+.2f}%")
        report.append(f"Worst trade: {adjusted_metrics['worst_pnl']:+.2f}%")
        report.append(f"Profit factor: {adjusted_metrics['profit_factor']:.2f}")
        report.append("")
        
        # Baseline comparison
        if baseline_metrics['total_exits'] > 0:
            report.append("BASELINE EXITS PERFORMANCE")
            report.append("-" * 100)
            report.append(f"Total exits: {baseline_metrics['total_exits']} ({baseline_metrics['wins']} wins, {baseline_metrics['losses']} losses)")
            report.append(f"Win rate: {baseline_metrics['win_rate']:.1f}%")
            report.append(f"Average PnL: {baseline_metrics['avg_pnl']:+.2f}%")
            report.append("")
        
        # Component analysis
        report.append("ADJUSTMENT COMPONENT EFFECTIVENESS")
        report.append("-" * 100)
        
        if component_analysis.get('volatility'):
            report.append("Volatility adjustments:")
            for key, stats in component_analysis['volatility'].items():
                report.append(f"  {key:12s}: {stats['count']:3d} exits, {stats['win_rate']:5.1f}% win rate, {stats['avg_pnl']:+6.2f}% avg PnL")
        
        if component_analysis.get('time'):
            report.append("Time decay adjustments:")
            for key, stats in component_analysis['time'].items():
                report.append(f"  {key:12s}: {stats['count']:3d} exits, {stats['win_rate']:5.1f}% win rate, {stats['avg_pnl']:+6.2f}% avg PnL")
        
        if component_analysis.get('regime'):
            report.append("Regime adjustments:")
            for key, stats in component_analysis['regime'].items():
                report.append(f"  {key:12s}: {stats['count']:3d} exits, {stats['win_rate']:5.1f}% win rate, {stats['avg_pnl']:+6.2f}% avg PnL")
        report.append("")
        
        # Symbol learning
        if symbol_learning:
            report.append("SYMBOL-SPECIFIC LEARNING")
            report.append("-" * 100)
            sorted_symbols = sorted(symbol_learning.items(), key=lambda x: x[1]['total_exits'], reverse=True)
            for symbol, stats in sorted_symbols[:15]:  # Top 15
                status = "[ACTIVE]" if stats['learning_active'] else "[BASELINE]"
                report.append(f"{symbol:8s} {status:10s}: {stats['total_exits']:3d} exits, {stats['win_rate']:5.1f}% win, {stats['avg_pnl']:+6.2f}% PnL, {stats['avg_adjustment']:+6.2f}% avg adj")
            report.append("")
        
        # Provider reliability
        report.append("PROVIDER RELIABILITY")
        report.append("-" * 100)
        vix_rel = reliability['vix_provider']
        regime_rel = reliability['regime_detector']
        report.append(f"VIX Provider: {vix_rel['availability_pct']:.1f}% available ({vix_rel['available']}/{vix_rel['total_exits']} exits)")
        report.append(f"Regime Detector: {regime_rel['availability_pct']:.1f}% available ({regime_rel['available']}/{regime_rel['total_exits']} exits)")
        report.append("")
        
        # Recommendations
        report.append("RECOMMENDATIONS")
        report.append("-" * 100)
        if recommendations:
            for rec in recommendations:
                report.append(f"• {rec}")
        else:
            report.append("No specific recommendations at this time - continue monitoring")
        report.append("")
        
        report.append("=" * 100)
        
        return "\n".join(report)


def main():
    """Generate and save weekly report."""
    try:
        generator = WeeklyReportGenerator()
        
        # Generate 1-week report
        report = generator.generate_report(weeks=1)
        print(report)
        
        # Save to file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = Path(f"reports/weekly_adjustment_report_{timestamp}.txt")
        report_file.parent.mkdir(exist_ok=True)
        with open(report_file, "w") as f:
            f.write(report)
        
        logger.info(f"Report saved to {report_file}")
        
    except Exception as e:
        logger.error(f"Report generation failed: {e}", exc_info=True)
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())

#!/usr/bin/env python
"""
PennyHunter Nightly Audit - Paper Trading

Runs end-of-day audit:
- Updates agent performance based on completed trades
- Generates performance reports
- Checks for threshold adaptations
- Monitors system health

Schedule to run at 6:00 PM ET daily (after market close).
"""

import asyncio
import logging
import sys
import yaml
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from bouncehunter.pennyhunter_agentic import (
    AgenticMemory,
    AgenticPolicy,
    Auditor,
)
from bouncehunter.ib_broker import IBBroker
from bouncehunter.config import BounceHunterConfig

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/nightly_audit.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class NightlyAuditor:
    """End-of-day audit and reporting."""
    
    def __init__(self, config_path: str = "configs/paper_trading.yaml"):
        """Initialize auditor with configuration."""
        # Load config
        with open(config_path) as f:
            self.config = yaml.safe_load(f)
        
        # Initialize broker
        self.broker = IBBroker(
            host=self.config['broker']['host'],
            port=self.config['broker']['port'],
            client_id=self.config['broker']['client_id'],
            paper=self.config['broker']['paper_trading'],
            initial_capital=self.config['trading']['initial_capital'],
        )

        # Connect to IB
        self.broker.connect()
        
        # Initialize agentic system
        self.memory = AgenticMemory(
            agentic_db_path=self.config['database']['agentic_db'],
            base_db_path=self.config['database']['memory_db'],
        )
        
        self.policy = AgenticPolicy(
            config=BounceHunterConfig.from_yaml("configs/phase3.yaml"),
            live_trading=False,
            min_confidence=5.5,
            auto_adapt_thresholds=True,
        )
        
        logger.info(f"✅ NightlyAuditor initialized")
    
    async def run_audit(self) -> Dict:
        """
        Run nightly audit.
        
        Returns:
            Audit results
        """
        start_time = datetime.now()
        
        logger.info("="*80)
        logger.info(f"🔍 PENNYHUNTER NIGHTLY AUDIT - {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("="*80)
        
        # Get account status
        account = self.broker.get_account()
        positions = self.broker.get_positions()
        
        logger.info(f"\n💼 ACCOUNT STATUS:")
        logger.info(f"   Portfolio Value: ${account['portfolio_value']:,.0f}")
        logger.info(f"   Cash: ${account['cash']:,.0f}")
        logger.info(f"   Open Positions: {len(positions)}")
        
        # Check for stop/target hits
        logger.info(f"\n🎯 CHECKING POSITIONS...")
        
        actions = self.broker.check_stops_and_targets()
        
        if actions:
            logger.info(f"   Found {len(actions)} positions to close:")
            for action in actions:
                logger.info(f"   {action['ticker']}: {action['reason']} @ ${action['exit']:.2f} ({action['pnl_pct']:+.1f}%)")
                
                # Close position
                self.broker.close_position(action['ticker'], action['reason'])
        else:
            logger.info(f"   No positions to close")
        
        # Run Auditor agent
        logger.info(f"\n🤖 RUNNING AUDITOR AGENT...")
        
        auditor = Auditor(memory=self.memory, policy=self.policy)
        audit_results = await auditor.run({})
        
        logger.info(f"\n📊 AGENT PERFORMANCE:")
        agent_weights = audit_results.get('agent_weights', {})
        
        for agent_name, weight in agent_weights.items():
            logger.info(f"   {agent_name}: {weight:.2f}x")
        
        # Get overall performance
        overall_perf = self.memory.get_overall_performance()
        
        logger.info(f"\n📈 OVERALL PERFORMANCE:")
        logger.info(f"   Total Trades: {overall_perf['total_trades']}")
        logger.info(f"   Wins: {overall_perf['wins']}")
        logger.info(f"   Losses: {overall_perf['losses']}")
        logger.info(f"   Win Rate: {overall_perf['win_rate']:.1%}")
        logger.info(f"   Avg Return: {overall_perf.get('avg_return', 0):.2%}")
        
        # Check thresholds
        current_threshold = self.policy.min_confidence
        recommended_threshold = audit_results.get('recommended_threshold', current_threshold)
        
        logger.info(f"\n⚙️  THRESHOLD STATUS:")
        logger.info(f"   Current: {current_threshold:.1f}")
        logger.info(f"   Recommended: {recommended_threshold:.1f}")
        
        if recommended_threshold != current_threshold:
            logger.info(f"   ⚠️  Threshold adjustment recommended!")
        
        # Check circuit breakers
        logger.info(f"\n🚨 CIRCUIT BREAKER STATUS:")
        
        # Check consecutive losses
        consecutive_losses = self._check_consecutive_losses()
        max_consecutive = self.config['trading']['consecutive_loss_limit']
        
        if consecutive_losses >= max_consecutive:
            logger.warning(f"   ⚠️  CIRCUIT BREAKER: {consecutive_losses} consecutive losses!")
            logger.warning(f"   Recommend pausing trading until reviewed")
        else:
            logger.info(f"   Consecutive Losses: {consecutive_losses}/{max_consecutive} ✅")
        
        # Check drawdown
        drawdown_pct = self._check_drawdown(account['portfolio_value'])
        max_drawdown = self.config['trading']['max_drawdown_pct']
        
        if drawdown_pct >= max_drawdown:
            logger.warning(f"   ⚠️  CIRCUIT BREAKER: {drawdown_pct:.1%} drawdown!")
            logger.warning(f"   Recommend reducing position sizes")
        else:
            logger.info(f"   Drawdown: {drawdown_pct:.1%}/{max_drawdown:.1%} ✅")
        
        # Generate daily summary
        logger.info(f"\n📋 DAILY SUMMARY:")
        
        # Count today's trades
        today_trades = self._get_today_trades()
        
        logger.info(f"   Signals Today: {today_trades['signals']}")
        logger.info(f"   Trades Executed: {today_trades['executed']}")
        logger.info(f"   Trades Closed: {today_trades['closed']}")
        logger.info(f"   P&L Today: ${today_trades['pnl']:.0f} ({today_trades['pnl_pct']:+.1%})")
        
        # Summary
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        logger.info(f"\n{'='*80}")
        logger.info(f"✅ AUDIT COMPLETE ({duration:.1f}s)")
        logger.info(f"{'='*80}\n")
        
        return {
            'timestamp': start_time,
            'account': account,
            'positions': len(positions),
            'agent_weights': agent_weights,
            'overall_performance': overall_perf,
            'circuit_breakers': {
                'consecutive_losses': consecutive_losses,
                'drawdown_pct': drawdown_pct,
            },
            'today_summary': today_trades,
        }
    
    def _check_consecutive_losses(self) -> int:
        """Check number of consecutive losses."""
        # Query recent trades
        conn = self.memory.conn
        
        query = """
        SELECT hit_target
        FROM signal_results
        WHERE hit_target IS NOT NULL
        ORDER BY close_date DESC
        LIMIT 10
        """
        
        cursor = conn.execute(query)
        results = cursor.fetchall()
        
        consecutive = 0
        for (hit_target,) in results:
            if hit_target == 0:  # Loss
                consecutive += 1
            else:
                break
        
        return consecutive
    
    def _check_drawdown(self, current_value: float) -> float:
        """Calculate drawdown from peak."""
        # Get historical portfolio values
        # For now, use initial capital as peak
        peak_value = self.config['trading']['initial_capital']
        
        if current_value < peak_value:
            drawdown = (peak_value - current_value) / peak_value
            return drawdown
        
        return 0.0
    
    def _get_today_trades(self) -> Dict:
        """Get today's trading activity."""
        conn = self.memory.conn
        
        today = datetime.now().date()
        
        # Count signals
        query_signals = """
        SELECT COUNT(*)
        FROM signals
        WHERE DATE(created_at) = ?
        """
        
        cursor = conn.execute(query_signals, (today,))
        signals_count = cursor.fetchone()[0]
        
        # Count executed trades
        query_executed = """
        SELECT COUNT(*)
        FROM agent_decisions
        WHERE DATE(decision_time) = ?
        AND final_decision = 'APPROVED'
        """
        
        cursor = conn.execute(query_executed, (today,))
        executed_count = cursor.fetchone()[0]
        
        # Count closed trades
        query_closed = """
        SELECT COUNT(*), SUM(pnl), SUM(pnl_pct)
        FROM signal_results
        WHERE DATE(close_date) = ?
        """
        
        cursor = conn.execute(query_closed, (today,))
        result = cursor.fetchone()
        closed_count = result[0] or 0
        pnl = result[1] or 0.0
        pnl_pct = result[2] or 0.0
        
        return {
            'signals': signals_count,
            'executed': executed_count,
            'closed': closed_count,
            'pnl': pnl,
            'pnl_pct': pnl_pct / closed_count if closed_count > 0 else 0.0,
        }


async def main():
    """Main entry point."""
    try:
        # Create logs directory
        Path("logs").mkdir(exist_ok=True)
        
        # Initialize auditor
        auditor = NightlyAuditor()
        
        # Run audit
        results = await auditor.run_audit()
        
        # Success
        return 0
        
    except Exception as e:
        logger.error(f"\n❌ NIGHTLY AUDIT FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

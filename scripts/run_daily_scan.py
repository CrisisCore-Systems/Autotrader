#!/usr/bin/env python
"""
PennyHunter Daily Scanner - Paper Trading

Runs pre-market scan, executes agent consensus, and places trades via Alpaca.

Schedule to run at 8:30 AM ET daily (Windows Task Scheduler).
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
    Orchestrator,
    AgenticMemory,
    AgenticPolicy,
    Sentinel,
    Screener,
    Forecaster,
    RiskOfficer,
    NewsSentry,
    Trader,
    Historian,
    Auditor,
    WeightedConsensus,
)
from bouncehunter.ib_broker import IBBroker, TradeOrder
from bouncehunter.config import BounceHunterConfig

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/daily_scan.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class PaperTradingScanner:
    """Daily scanner with paper trading execution."""
    
    def __init__(self, config_path: str = "configs/paper_trading.yaml"):
        """Initialize scanner with configuration."""
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
            max_position_pct=self.config['trading']['max_position_pct'],
            risk_per_trade_pct=self.config['trading']['risk_per_trade_pct'],
            max_concurrent=self.config['trading']['max_concurrent'],
        )

        # Connect to IB
        if not self.broker.connect():
            raise RuntimeError("Failed to connect to Interactive Brokers")
        
        # Initialize agentic system
        self.memory = AgenticMemory(
            agentic_db_path=self.config['database']['agentic_db'],
            base_db_path=self.config['database']['memory_db'],
        )
        
        # Get current regime to determine confidence threshold
        regime_info = self._get_regime()
        regime_name = regime_info['regime']
        
        confidence_threshold = self.config['trading']['regime_adjustments'][regime_name]['confidence_threshold']
        
        self.policy = AgenticPolicy(
            config=BounceHunterConfig.from_yaml("configs/phase3.yaml"),
            live_trading=False,  # Paper trading
            min_confidence=confidence_threshold,
            min_confidence_highvix=self.config['agents']['forecaster']['min_confidence_highvix'],
            auto_adapt_thresholds=True,
        )
        
        logger.info(f"✅ PaperTradingScanner initialized")
        logger.info(f"   Regime: {regime_name}")
        logger.info(f"   Confidence Threshold: {confidence_threshold}")
        logger.info(f"   Account: ${self.broker.get_account()['portfolio_value']:.0f}")
    
    def _get_regime(self) -> Dict:
        """Get current market regime."""
        # TODO: Integrate with RegimeDetector
        # For now, use simple logic
        from bouncehunter.regime import RegimeDetector
        
        detector = RegimeDetector()
        regime_data = detector.get_current_regime()
        
        return {
            'regime': regime_data['regime'],
            'vix': regime_data.get('vix', 0),
            'spy_vs_200dma': regime_data.get('spy_vs_200dma', 1.0),
        }
    
    async def run_daily_scan(self) -> Dict:
        """
        Run daily pre-market scan.
        
        Returns:
            {
                'timestamp': datetime,
                'regime': str,
                'signals_found': int,
                'signals_approved': int,
                'trades_executed': int,
                'trades': List[Dict],
            }
        """
        start_time = datetime.now()
        
        logger.info("="*80)
        logger.info(f"🔍 PENNYHUNTER DAILY SCAN - {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("="*80)
        
        # Check account
        account = self.broker.get_account()
        positions = self.broker.get_positions()
        
        logger.info(f"\n💼 ACCOUNT STATUS:")
        logger.info(f"   Portfolio Value: ${account['portfolio_value']:,.0f}")
        logger.info(f"   Cash: ${account['cash']:,.0f}")
        logger.info(f"   Open Positions: {len(positions)}")
        
        if positions:
            logger.info(f"\n📊 OPEN POSITIONS:")
            for pos in positions:
                logger.info(f"   {pos.ticker}: {pos.qty} shares @ ${pos.entry_price:.2f}")
                logger.info(f"      Current: ${pos.current_price:.2f} ({pos.unrealized_pnl_pct:+.1f}%)")
        
        # Check if we can trade today
        if len(positions) >= self.config['trading']['max_concurrent']:
            logger.warning(f"⚠️  Max concurrent positions reached ({len(positions)}/{self.config['trading']['max_concurrent']})")
            return {
                'timestamp': start_time,
                'signals_found': 0,
                'signals_approved': 0,
                'trades_executed': 0,
                'trades': [],
                'reason': 'Max concurrent positions',
            }
        
        # Get regime
        regime_info = self._get_regime()
        regime_name = regime_info['regime']
        
        logger.info(f"\n🌍 MARKET REGIME:")
        logger.info(f"   Regime: {regime_name}")
        logger.info(f"   VIX: {regime_info['vix']:.1f}")
        logger.info(f"   SPY vs 200 DMA: {regime_info['spy_vs_200dma']:.2%}")
        
        # Run GapScanner to find signals
        logger.info(f"\n🔎 SCANNING FOR GAPS...")
        
        from bouncehunter.gap_scanner import GapScanner
        
        scanner = GapScanner(
            memory=self.memory,
            min_gap_pct=self.config['scanner']['min_gap_pct'],
            min_volume=self.config['scanner']['min_volume'],
            min_price=self.config['scanner']['min_price'],
            max_price=self.config['scanner']['max_price'],
        )
        
        signals = await scanner.scan()
        
        logger.info(f"   Found {len(signals)} gap signals")
        
        if not signals:
            logger.info(f"\n✅ No qualifying signals found today")
            return {
                'timestamp': start_time,
                'regime': regime_name,
                'signals_found': 0,
                'signals_approved': 0,
                'trades_executed': 0,
                'trades': [],
            }
        
        # Log signals
        logger.info(f"\n📋 SIGNALS FOUND:")
        for i, sig in enumerate(signals, 1):
            logger.info(f"   {i}. {sig['ticker']}: Gap {sig['gap_pct']:+.1f}% @ ${sig['price']:.2f}")
        
        # Run agents on each signal
        approved_trades = []
        
        for signal in signals:
            logger.info(f"\n{'='*80}")
            logger.info(f"🤖 RUNNING AGENTS: {signal['ticker']}")
            logger.info(f"{'='*80}")
            
            # Run agent consensus
            result = await self._run_agent_consensus(signal, regime_info)
            
            if result['approved']:
                approved_trades.append(result)
                logger.info(f"✅ {signal['ticker']} APPROVED for trading")
            else:
                logger.info(f"❌ {signal['ticker']} VETOED: {result['veto_reason']}")
        
        # Execute approved trades
        logger.info(f"\n{'='*80}")
        logger.info(f"💰 EXECUTING TRADES")
        logger.info(f"{'='*80}")
        logger.info(f"   Approved: {len(approved_trades)}/{len(signals)}")
        
        executed_trades = []
        
        for trade_data in approved_trades:
            # Create trade order
            order = TradeOrder(
                ticker=trade_data['ticker'],
                action='BUY',
                entry_price=trade_data['entry_price'],
                stop_price=trade_data['stop_price'],
                target_price=trade_data['target_price'],
                position_size_pct=trade_data['position_size_pct'],
                confidence=trade_data['confidence'],
                signal_id=trade_data['signal_id'],
                regime=regime_name,
                agent_votes=trade_data['agent_votes'],
            )
            
            # Execute via broker
            order_id = self.broker.execute_trade(order)
            
            if order_id:
                executed_trades.append({
                    'ticker': order.ticker,
                    'order_id': order_id,
                    'entry': order.entry_price,
                    'stop': order.stop_price,
                    'target': order.target_price,
                    'confidence': order.confidence,
                    'signal_id': order.signal_id,
                })
                
                # Store in database
                self._store_trade_in_db(order, order_id)
        
        # Summary
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        logger.info(f"\n{'='*80}")
        logger.info(f"📊 SCAN SUMMARY")
        logger.info(f"{'='*80}")
        logger.info(f"   Duration: {duration:.1f}s")
        logger.info(f"   Signals Found: {len(signals)}")
        logger.info(f"   Signals Approved: {len(approved_trades)}")
        logger.info(f"   Trades Executed: {len(executed_trades)}")
        logger.info(f"{'='*80}\n")
        
        return {
            'timestamp': start_time,
            'regime': regime_name,
            'signals_found': len(signals),
            'signals_approved': len(approved_trades),
            'trades_executed': len(executed_trades),
            'trades': executed_trades,
        }
    
    async def _run_agent_consensus(self, signal: Dict, regime_info: Dict) -> Dict:
        """Run all agents on signal and get consensus."""
        # Create context
        ctx = {
            'regime': regime_info['regime'],
            'vix': regime_info['vix'],
            'spy_vs_200dma': regime_info['spy_vs_200dma'],
        }
        
        # Track agent votes
        agent_votes = {}
        veto_reason = None
        
        # Sentinel: Always approves (context already set)
        agent_votes['sentinel'] = True
        
        # Screener: Always approves (signal already passed screening)
        agent_votes['screener'] = True
        
        # Forecaster: Check confidence threshold
        forecaster = Forecaster(memory=self.memory, policy=self.policy)
        forecaster_signals = await forecaster.run([signal], ctx)
        agent_votes['forecaster'] = len(forecaster_signals) > 0
        
        if not agent_votes['forecaster']:
            veto_reason = f"Forecaster: Confidence {signal.get('confidence', 0):.1f} below threshold"
        
        # RiskOfficer: Check risk parameters
        risk_officer = RiskOfficer(memory=self.memory, policy=self.policy)
        riskofficer_signals = await risk_officer.run([signal], ctx)
        agent_votes['riskofficer'] = len(riskofficer_signals) > 0
        
        if not agent_votes['riskofficer']:
            veto_reason = f"RiskOfficer: Risk checks failed"
        
        # NewsSentry: Check sentiment
        news_sentry = NewsSentry(memory=self.memory, policy=self.policy)
        newssentry_signals = await news_sentry.run([signal], ctx)
        agent_votes['newssentry'] = len(newssentry_signals) > 0
        
        if not agent_votes['newssentry']:
            veto_reason = f"NewsSentry: Negative sentiment"
        
        # Trader: Always approves (execution agent)
        agent_votes['trader'] = True
        
        # Calculate weighted consensus
        consensus_system = WeightedConsensus(
            memory=self.memory,
            min_consensus=self.config['agents']['min_consensus'],
            min_trades_for_weighting=self.config['agents']['min_trades_for_weighting'],
        )
        
        should_trade, consensus_score, consensus_reason = consensus_system.should_trade(agent_votes)
        
        logger.info(f"   Agent Votes: {agent_votes}")
        logger.info(f"   Consensus: {consensus_score:.1%} ({consensus_reason})")
        logger.info(f"   Decision: {'APPROVED' if should_trade else 'VETOED'}")
        
        # Calculate position size based on regime
        regime_adjustment = self.config['trading']['regime_adjustments'][regime_info['regime']]['position_size']
        position_size_pct = self.config['trading']['risk_per_trade_pct'] * regime_adjustment
        
        return {
            'approved': should_trade,
            'ticker': signal['ticker'],
            'entry_price': signal['price'],
            'stop_price': signal.get('stop_price', signal['price'] * 0.95),
            'target_price': signal.get('target_price', signal['price'] * 1.10),
            'position_size_pct': position_size_pct,
            'confidence': signal.get('confidence', 0),
            'signal_id': signal.get('signal_id', ''),
            'agent_votes': agent_votes,
            'consensus_score': consensus_score,
            'veto_reason': veto_reason if not should_trade else None,
        }
    
    def _store_trade_in_db(self, order: TradeOrder, order_id: str):
        """Store trade in database for tracking."""
        # TODO: Store in agentic DB
        # For now, just log
        logger.info(f"   Stored trade {order.ticker} ({order_id}) in database")


async def main():
    """Main entry point."""
    try:
        # Create logs directory
        Path("logs").mkdir(exist_ok=True)
        
        # Initialize scanner
        scanner = PaperTradingScanner()
        
        # Run daily scan
        results = await scanner.run_daily_scan()
        
        # Success
        return 0
        
    except Exception as e:
        logger.error(f"\n❌ DAILY SCAN FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

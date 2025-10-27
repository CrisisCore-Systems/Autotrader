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
    Signal,
    Action,
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
                    'consensus_score': trade_data['consensus_score'],
                })
                
                # Store in database
                self._store_trade_in_db(order, order_id, trade_data)
        
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

        entry_price = (
            signal.get('price')
            or signal.get('entry_price')
            or signal.get('open')
            or signal.get('close')
        )

        # Guard against missing pricing data
        if not entry_price or entry_price <= 0:
            logger.warning(
                "Signal %s missing entry price fields, defaulting to 0", signal.get('ticker', 'UNKNOWN')
            )
            entry_price = 0.0

        stop_price = signal.get('stop_price') or (entry_price * 0.95 if entry_price else 0.0)
        target_price = signal.get('target_price') or (entry_price * 1.10 if entry_price else 0.0)
        signal_date = signal.get('date') or datetime.utcnow().strftime('%Y-%m-%d')

        return {
            'approved': should_trade,
            'ticker': signal['ticker'],
            'entry_price': entry_price,
            'stop_price': stop_price,
            'target_price': target_price,
            'position_size_pct': position_size_pct,
            'confidence': signal.get('confidence', 0),
            'signal_id': signal.get('signal_id', ''),
            'agent_votes': agent_votes,
            'consensus_score': consensus_score,
            'consensus_reason': consensus_reason,
            'gap_pct': signal.get('gap_pct', 0.0),
            'probability': signal.get('probability', 0.0),
            'adv_usd': signal.get('adv_usd', 0.0),
            'sector': signal.get('sector', 'UNKNOWN'),
            'notes': signal.get('notes', ''),
            'signal_date': signal_date,
            'prev_close': signal.get('prev_close') or signal.get('close') or entry_price,
            'raw_signal': signal,
            'veto_reason': veto_reason if not should_trade else None,
        }
    
    def _store_trade_in_db(self, order: TradeOrder, order_id: str, trade_metadata: Dict):
        """Store executed trade in agentic datastore for telemetry."""
        try:
            raw_signal = trade_metadata.get('raw_signal', {}) or {}
            agent_votes = dict(order.agent_votes)

            # Ensure core agent votes are present
            agent_votes.setdefault('sentinel', True)
            agent_votes.setdefault('screener', True)
            agent_votes.setdefault('trader', True)

            signal_date = trade_metadata.get('signal_date') or datetime.utcnow().strftime('%Y-%m-%d')
            consensus_score = trade_metadata.get('consensus_score', 0.0)
            consensus_reason = trade_metadata.get('consensus_reason', 'Consensus approved')

            signal = Signal(
                ticker=order.ticker,
                date=signal_date,
                gap_pct=float(trade_metadata.get('gap_pct', raw_signal.get('gap_pct', 0.0)) or 0.0),
                close=float(trade_metadata.get('prev_close', raw_signal.get('prev_close', raw_signal.get('close', order.entry_price))) or order.entry_price),
                entry=float(order.entry_price),
                stop=float(order.stop_price),
                target=float(order.target_price),
                confidence=float(order.confidence),
                probability=float(trade_metadata.get('probability', raw_signal.get('probability', 0.0)) or 0.0),
                adv_usd=float(trade_metadata.get('adv_usd', raw_signal.get('adv_usd', 0.0)) or 0.0),
                sector=str(trade_metadata.get('sector', raw_signal.get('sector', 'UNKNOWN')) or 'UNKNOWN'),
                notes=str(trade_metadata.get('notes', raw_signal.get('notes', '')) or ''),
                agent_votes=agent_votes,
            )

            action = Action(
                signal_id=order.signal_id or trade_metadata.get('signal_id', ''),
                ticker=order.ticker,
                action='BUY',
                size_pct=float(order.position_size_pct),
                entry=float(order.entry_price),
                stop=float(order.stop_price),
                target=float(order.target_price),
                confidence=float(order.confidence),
                regime=order.regime,
                reason=f"Consensus {consensus_score:.1%} ({consensus_reason})",
                order_id=order_id,
            )

            signal_id = self.memory.record_signal_agentic(signal, action, agent_votes)

            # Update order with generated signal id for traceability
            if not order.signal_id:
                order.signal_id = signal_id

            account = self.broker.get_account() or {}
            portfolio_value = account.get('portfolio_value', self.config['trading']['initial_capital'])
            shares = float(self.broker.calculate_position_size(order, portfolio_value))

            entry_date = signal_date
            fill_id = self.memory.record_fill_agentic(
                signal_id=signal_id,
                ticker=order.ticker,
                entry_date=entry_date,
                entry_price=float(order.entry_price),
                shares=shares,
                size_pct=float(order.position_size_pct),
                regime=order.regime,
                is_paper=True,
            )

            logger.info(
                "   Agentic datastore updated: signal %s, fill %s (shares %.0f)",
                signal_id,
                fill_id,
                shares,
            )

        except Exception as exc:
            logger.exception(
                "   Failed to persist trade %s (%s): %s",
                order.ticker,
                order_id,
                exc,
            )


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

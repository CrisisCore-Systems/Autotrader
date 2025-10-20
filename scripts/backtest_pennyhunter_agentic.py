#!/usr/bin/env python
"""
Phase 3 Agentic Backtest for PennyHunter

Replays 6-year historical data (2019-2025) through the 8-agent agentic system.
Records all agent decisions (vetoes, approvals) and compares performance vs Phase 2.5.

Target Performance:
- Win Rate: 75-85% (vs 60% Phase 2.5 baseline)
- Sample Size: 20-30 high-quality trades (vs 85 Phase 2.5)
- Profit Factor: >3.5
- Strategy: Multi-agent consensus (any veto blocks trade)

Usage:
    python scripts/backtest_pennyhunter_agentic.py
    python scripts/backtest_pennyhunter_agentic.py --start-date 2019-01-01 --end-date 2025-01-01
    python scripts/backtest_pennyhunter_agentic.py --confidence-threshold 7.5
"""

import sys
import json
import logging
import argparse
import asyncio
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from bouncehunter.config import BounceHunterConfig
from bouncehunter.pennyhunter_agentic import (
    AgenticMemory,
    AgenticPolicy,
    Context,
    Signal,
    Action,
    Orchestrator,
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent
BACKTEST_RESULTS = PROJECT_ROOT / "reports" / "pennyhunter_backtest_results.json"
BACKTEST_DB = PROJECT_ROOT / "reports" / "pennyhunter_agentic_backtest.db"
RESULTS_FILE = PROJECT_ROOT / "reports" / "agentic_backtest_results.json"


@dataclass
class BacktestTrade:
    """Single trade result from agentic backtest."""
    ticker: str
    entry_date: str
    exit_date: str
    entry_price: float
    exit_price: float
    stop_price: float
    target_price: float
    return_pct: float
    hold_days: int
    hit_target: bool
    hit_stop: bool
    exit_reason: str
    confidence: float
    probability: float
    regime: str
    size_pct: float
    gap_pct: float
    sector: str
    
    # Agent decisions
    sentinel_approved: bool
    screener_approved: bool
    forecaster_approved: bool
    riskofficer_approved: bool
    newssentry_approved: bool
    trader_approved: bool
    
    # Agent notes
    veto_reason: Optional[str] = None
    forecaster_note: Optional[str] = None
    riskofficer_note: Optional[str] = None


@dataclass
class BacktestMetrics:
    """Aggregate performance metrics."""
    total_signals: int
    signals_after_forecaster: int
    signals_after_riskofficer: int
    signals_after_newssentry: int
    total_trades: int
    
    wins: int
    losses: int
    win_rate: float
    
    avg_return: float
    avg_win: float
    avg_loss: float
    profit_factor: float
    
    avg_hold_days: float
    avg_confidence: float
    
    # By regime
    trades_normal: int
    trades_high_vix: int
    trades_spy_stress: int
    
    # Veto analysis
    forecaster_vetoes: int
    riskofficer_vetoes: int
    newssentry_vetoes: int
    
    # Phase 2.5 comparison
    phase25_trades: int
    phase25_win_rate: float
    improvement_pct: float


class AgenticBacktester:
    """Backtest engine for Phase 3 agentic system."""
    
    def __init__(
        self,
        start_date: str = "2019-01-01",
        end_date: str = "2025-01-01",
        confidence_threshold: float = 7.0,
        confidence_threshold_highvix: float = 7.5,
    ):
        self.start_date = start_date
        self.end_date = end_date
        
        # Initialize config and policy
        self.config = BounceHunterConfig()
        self.policy = AgenticPolicy(
            config=self.config,
            live_trading=False,
            min_confidence=confidence_threshold,
            min_confidence_highvix=confidence_threshold_highvix,
            min_confidence_stress=confidence_threshold_highvix,
            risk_pct_normal=0.01,
            risk_pct_highvix=0.005,
            risk_pct_stress=0.005,
            max_concurrent=5,
            max_per_sector=2,
            allow_earnings=False,
            news_veto_enabled=False,
            auto_adapt_thresholds=True,
            base_rate_floor=0.50,
            min_sample_size=20,
        )
        
        # Initialize memory with backtest database
        self.memory = AgenticMemory(
            agentic_db_path=str(BACKTEST_DB),
            base_db_path=str(PROJECT_ROOT / "reports" / "pennyhunter_memory.db"),
        )
        
        # Initialize orchestrator
        self.orchestrator = Orchestrator(self.policy, self.memory)
        
        # Results storage
        self.trades: List[BacktestTrade] = []
        self.daily_logs: List[Dict[str, Any]] = []
        
    async def run(self) -> Dict[str, Any]:
        """Execute full backtest."""
        logger.info("="*70)
        logger.info("PHASE 3 AGENTIC BACKTEST")
        logger.info("="*70)
        logger.info(f"Period: {self.start_date} to {self.end_date}")
        logger.info(f"Confidence Threshold: {self.policy.min_confidence} (normal) / {self.policy.min_confidence_highvix} (high-vix)")
        logger.info(f"Memory DB: {BACKTEST_DB}")
        logger.info("")
        
        # Load Phase 2.5 cumulative history
        historical_signals = self._load_historical_signals()
        logger.info(f"Loaded {len(historical_signals)} historical signals from Phase 2.5")
        
        # Replay through agentic system
        logger.info("\nReplaying signals through 8-agent system...")
        await self._replay_signals(historical_signals)
        
        # Calculate metrics
        metrics = self._calculate_metrics(historical_signals)
        
        # Generate report
        results = {
            "backtest_info": {
                "start_date": self.start_date,
                "end_date": self.end_date,
                "confidence_threshold": self.policy.min_confidence,
                "confidence_threshold_highvix": self.policy.min_confidence_highvix,
                "run_timestamp": datetime.now().isoformat(),
            },
            "metrics": asdict(metrics),
            "trades": [asdict(t) for t in self.trades],
            "daily_logs": self.daily_logs,
        }
        
        # Save results
        with open(RESULTS_FILE, 'w') as f:
            json.dump(results, f, indent=2)
        
        logger.info(f"\n✅ Results saved to: {RESULTS_FILE}")
        
        # Print summary
        self._print_summary(metrics)
        
        return results
    
    def _load_historical_signals(self) -> List[Dict[str, Any]]:
        """Load historical signals from Phase 2.5 backtest results."""
        with open(BACKTEST_RESULTS, 'r') as f:
            history = json.load(f)
        
        # Extract trades (these were signals that became trades)
        trades = history.get('trades', [])
        
        # Convert entry_time/exit_time to entry_date/exit_date
        for trade in trades:
            if 'entry_time' in trade:
                # Parse ISO timestamp and extract date
                entry_dt = datetime.fromisoformat(trade['entry_time'].replace('Z', '+00:00'))
                trade['entry_date'] = entry_dt.strftime('%Y-%m-%d')
            if 'exit_time' in trade:
                exit_dt = datetime.fromisoformat(trade['exit_time'].replace('Z', '+00:00'))
                trade['exit_date'] = exit_dt.strftime('%Y-%m-%d')
            
            # Rename fields to match expected format
            if 'pnl_pct' in trade:
                trade['return_pct'] = trade['pnl_pct'] / 100.0  # Convert from % to decimal
        
        # Filter by date range
        filtered = []
        for trade in trades:
            trade_date = trade.get('entry_date', '')
            if self.start_date <= trade_date <= self.end_date:
                filtered.append(trade)
        
        return filtered
    
    async def _replay_signals(self, historical_signals: List[Dict[str, Any]]):
        """Replay each historical signal through the agentic system."""
        for i, signal_data in enumerate(historical_signals, 1):
            if i % 10 == 0:
                logger.info(f"Processing signal {i}/{len(historical_signals)}...")
            
            # Create Signal object from historical data
            signal = self._create_signal_from_history(signal_data)
            
            # Create context for signal date
            ctx = self._create_context(signal.date)
            
            # Run through all agents
            agent_results = await self._run_agents(signal, ctx)
            
            # Log daily result
            self.daily_logs.append({
                "date": signal.date,
                "ticker": signal.ticker,
                "agent_results": agent_results,
            })
            
            # If approved by all agents, simulate trade execution
            if agent_results["final_decision"] == "APPROVED":
                trade = self._simulate_trade(signal, signal_data, agent_results, ctx)
                self.trades.append(trade)
    
    def _create_signal_from_history(self, trade_data: Dict[str, Any]) -> Signal:
        """Convert historical trade data to Signal object."""
        entry_price = trade_data.get('entry_price', 0.0)
        stop_price = trade_data.get('stop_loss', entry_price * 0.95)
        target_price = trade_data.get('take_profit', entry_price * 1.10)
        
        return Signal(
            ticker=trade_data.get('ticker', ''),
            date=trade_data.get('entry_date', ''),
            gap_pct=trade_data.get('gap_pct', 0.0) / 100.0,  # Convert from % to decimal
            close=entry_price,
            entry=entry_price,
            stop=stop_price,
            target=target_price,
            confidence=trade_data.get('score', 0.0),  # Use original score as initial confidence
            probability=0.0,  # Will be calculated by Forecaster
            adv_usd=1_000_000,  # Default value
            sector=trade_data.get('sector', 'UNKNOWN'),
            notes=f"Historical signal from Phase 2.5 (score={trade_data.get('score', 0)})",
        )
    
    def _create_context(self, date_str: str) -> Context:
        """
        Create market context for given date.

        PRODUCTION VERSION - Uses real VIX and SPY data for regime detection.
        """
        from bouncehunter.market_regime import MarketRegimeDetector
        import yfinance as yf

        date = datetime.strptime(date_str, "%Y-%m-%d")

        # Get real market data for the signal date
        try:
            # Fetch VIX for the date (percentile calculation)
            vix_ticker = yf.Ticker("^VIX")
            vix_hist = vix_ticker.history(start=date_str, end=(date + timedelta(days=5)).strftime("%Y-%m-%d"))

            if not vix_hist.empty:
                vix_level = vix_hist['Close'].iloc[0]
                # Calculate VIX percentile (simplified: based on historical thresholds)
                # VIX < 15: low (0-30th percentile)
                # VIX 15-20: medium (30-70th percentile)
                # VIX 20-30: high (70-90th percentile)
                # VIX > 30: extreme (90-100th percentile)
                if vix_level < 15:
                    vix_pct = 0.20
                elif vix_level < 20:
                    vix_pct = 0.50
                elif vix_level < 30:
                    vix_pct = 0.80
                else:
                    vix_pct = 0.95
            else:
                vix_level = 20.0
                vix_pct = 0.50

            # Fetch SPY for 200 DMA distance
            spy_ticker = yf.Ticker("SPY")
            spy_hist = spy_ticker.history(start=(date - timedelta(days=250)).strftime("%Y-%m-%d"),
                                          end=(date + timedelta(days=5)).strftime("%Y-%m-%d"))

            if len(spy_hist) >= 200:
                # Get signal day SPY price
                signal_day_spy = spy_hist[spy_hist.index.date == date.date()]
                if not signal_day_spy.empty:
                    spy_price = signal_day_spy['Close'].iloc[0]
                else:
                    spy_price = spy_hist['Close'].iloc[-1]

                # Calculate 200 DMA
                spy_ma200 = spy_hist['Close'].rolling(200).mean().iloc[-1]
                spy_dist_200dma = ((spy_price - spy_ma200) / spy_ma200) * 100
            else:
                spy_dist_200dma = 0.0

            # Determine regime based on real market conditions
            # normal: VIX < 70th percentile, SPY > -5% from 200 DMA
            # high_vix: VIX >= 70th percentile
            # spy_stress: SPY < -5% from 200 DMA
            if vix_pct >= 0.70:
                regime = "high_vix"
            elif spy_dist_200dma < -5.0:
                regime = "spy_stress"
            else:
                regime = "normal"

            logger.debug(
                f"Context for {date_str}: regime={regime}, "
                f"VIX={vix_level:.1f} (pct={vix_pct:.2f}), "
                f"SPY {spy_dist_200dma:+.1f}% from 200DMA"
            )

        except Exception as e:
            logger.warning(f"Error fetching market data for {date_str}: {e}. Using defaults.")
            regime = "normal"
            vix_pct = 0.50
            spy_dist_200dma = 0.0

        return Context(
            dt=date_str,
            regime=regime,
            vix_percentile=vix_pct,
            spy_dist_200dma=spy_dist_200dma,
            is_market_hours=False,
            is_preclose=False,
        )
    
    async def _run_agents(self, signal: Signal, ctx: Context) -> Dict[str, Any]:
        """Run signal through all agents and record decisions."""
        from bouncehunter.pennyhunter_agentic import WeightedConsensus
        
        results = {
            "signal": signal.ticker,
            "date": signal.date,
            "agents": {},
            "final_decision": "PENDING",
            "consensus_score": 0.0,
        }
        
        # Agent votes dictionary for weighted consensus
        agent_votes = {}
        
        # Agent 1: Sentinel (always approves in backtest)
        results["agents"]["sentinel"] = {"approved": True, "note": f"Regime: {ctx.regime}"}
        agent_votes["sentinel"] = True
        
        # Agent 2: Screener (always approves - signal already exists)
        results["agents"]["screener"] = {"approved": True, "note": "Historical signal"}
        agent_votes["screener"] = True
        
        # Agent 3: Forecaster
        try:
            forecaster_signals = await self.orchestrator.forecaster.run([signal], ctx)
            if forecaster_signals:
                results["agents"]["forecaster"] = {
                    "approved": True,
                    "confidence": forecaster_signals[0].confidence,
                    "note": f"Confidence: {forecaster_signals[0].confidence:.1f}",
                }
                agent_votes["forecaster"] = True
                signal = forecaster_signals[0]  # Update with scored signal
            else:
                results["agents"]["forecaster"] = {
                    "approved": False,
                    "note": "Below confidence threshold",
                }
                agent_votes["forecaster"] = False
                # Don't return yet - let weighted consensus decide
        except Exception as e:
            logger.warning(f"Forecaster error for {signal.ticker}: {e}")
            results["agents"]["forecaster"] = {"approved": False, "note": f"Error: {e}"}
            agent_votes["forecaster"] = False
        
        # Agent 4: RiskOfficer
        try:
            riskofficer_signals = await self.orchestrator.risk_officer.run([signal], ctx)
            if riskofficer_signals:
                results["agents"]["riskofficer"] = {
                    "approved": True,
                    "note": "Passed risk checks",
                }
                agent_votes["riskofficer"] = True
            else:
                results["agents"]["riskofficer"] = {
                    "approved": False,
                    "note": signal.veto_reason or "Risk limits exceeded",
                }
                agent_votes["riskofficer"] = False
                # Don't return yet - let weighted consensus decide
        except Exception as e:
            logger.warning(f"RiskOfficer error for {signal.ticker}: {e}")
            results["agents"]["riskofficer"] = {"approved": False, "note": f"Error: {e}"}
            agent_votes["riskofficer"] = False
        
        # Agent 5: NewsSentry (stub - always approves)
        results["agents"]["newssentry"] = {"approved": True, "note": "No news veto"}
        agent_votes["newssentry"] = True
        
        # Agent 6: Trader (generates action)
        results["agents"]["trader"] = {"approved": True, "note": "Action generated"}
        agent_votes["trader"] = True
        
        # Calculate weighted consensus score
        # Adaptive consensus: binary until 20 trades, then weighted with 70% threshold
        consensus_system = WeightedConsensus(
            self.memory, 
            min_consensus=0.70,  # Weighted threshold after 20 trades
            min_trades_for_weighting=20  # Binary mode until 20 trades
        )
        should_trade, consensus_score, reason = consensus_system.should_trade(agent_votes)
        
        results["consensus_score"] = consensus_score
        
        if should_trade:
            results["final_decision"] = "APPROVED"
            results["consensus_note"] = reason
        else:
            results["final_decision"] = "VETOED_CONSENSUS"
            results["consensus_note"] = reason
        
        return results
    
    def _simulate_trade(
        self,
        signal: Signal,
        historical_data: Dict[str, Any],
        agent_results: Dict[str, Any],
        ctx: Context,
    ) -> BacktestTrade:
        """Simulate trade execution and outcome."""
        # Extract actual outcome from historical data
        pnl_pct = historical_data.get('pnl_pct', 0.0)
        exit_reason = historical_data.get('exit_reason', 'UNKNOWN')
        
        return BacktestTrade(
            ticker=signal.ticker,
            entry_date=historical_data.get('entry_date', ''),
            exit_date=historical_data.get('exit_date', ''),
            entry_price=historical_data.get('entry_price', 0.0),
            exit_price=historical_data.get('exit_price', 0.0),
            stop_price=signal.stop,
            target_price=signal.target,
            return_pct=pnl_pct / 100.0 if pnl_pct else 0.0,  # Convert from % to decimal
            hold_days=historical_data.get('hold_days', 0),
            hit_target=(exit_reason == "TARGET"),
            hit_stop=(exit_reason == "STOP"),
            exit_reason=exit_reason,
            confidence=signal.confidence,
            probability=signal.probability,
            regime=ctx.regime,
            size_pct=self.policy.risk_pct_normal if ctx.regime == "normal" else self.policy.risk_pct_highvix,
            gap_pct=signal.gap_pct,
            sector=signal.sector,
            sentinel_approved=agent_results["agents"]["sentinel"]["approved"],
            screener_approved=agent_results["agents"]["screener"]["approved"],
            forecaster_approved=agent_results["agents"]["forecaster"]["approved"],
            riskofficer_approved=agent_results["agents"]["riskofficer"]["approved"],
            newssentry_approved=agent_results["agents"]["newssentry"]["approved"],
            trader_approved=agent_results["agents"]["trader"]["approved"],
            veto_reason=None,
            forecaster_note=agent_results["agents"]["forecaster"].get("note"),
            riskofficer_note=agent_results["agents"]["riskofficer"].get("note"),
        )
    
    def _calculate_metrics(self, historical_signals: List[Dict[str, Any]]) -> BacktestMetrics:
        """Calculate aggregate performance metrics."""
        # Count agent decisions
        total_signals = len(historical_signals)
        
        forecaster_vetoes = sum(
            1 for log in self.daily_logs 
            if "FORECASTER" in log["agent_results"].get("final_decision", "")
        )
        
        riskofficer_vetoes = sum(
            1 for log in self.daily_logs 
            if "RISKOFFICER" in log["agent_results"].get("final_decision", "")
        )
        
        newssentry_vetoes = 0  # Stub always approves
        
        signals_after_forecaster = total_signals - forecaster_vetoes
        signals_after_riskofficer = signals_after_forecaster - riskofficer_vetoes
        signals_after_newssentry = signals_after_riskofficer - newssentry_vetoes
        
        # Trade statistics
        total_trades = len(self.trades)
        wins = sum(1 for t in self.trades if t.return_pct > 0)
        losses = total_trades - wins
        win_rate = wins / total_trades if total_trades > 0 else 0.0
        
        # Returns
        returns = [t.return_pct for t in self.trades]
        avg_return = sum(returns) / len(returns) if returns else 0.0
        
        winning_returns = [t.return_pct for t in self.trades if t.return_pct > 0]
        losing_returns = [t.return_pct for t in self.trades if t.return_pct <= 0]
        
        avg_win = sum(winning_returns) / len(winning_returns) if winning_returns else 0.0
        avg_loss = sum(losing_returns) / len(losing_returns) if losing_returns else 0.0
        
        # Profit factor
        total_wins = sum(winning_returns)
        total_losses = abs(sum(losing_returns))
        profit_factor = total_wins / total_losses if total_losses > 0 else 0.0
        
        # Hold time and confidence
        avg_hold_days = sum(t.hold_days for t in self.trades) / total_trades if total_trades > 0 else 0.0
        avg_confidence = sum(t.confidence for t in self.trades) / total_trades if total_trades > 0 else 0.0
        
        # By regime
        trades_normal = sum(1 for t in self.trades if t.regime == "normal")
        trades_high_vix = sum(1 for t in self.trades if t.regime == "high_vix")
        trades_spy_stress = sum(1 for t in self.trades if t.regime == "spy_stress")
        
        # Phase 2.5 comparison
        phase25_wins = sum(1 for s in historical_signals if s.get('pnl', 0) > 0)
        phase25_trades = len(historical_signals)
        phase25_win_rate = phase25_wins / phase25_trades if phase25_trades > 0 else 0.0
        
        improvement_pct = ((win_rate - phase25_win_rate) / phase25_win_rate * 100) if phase25_win_rate > 0 else 0.0
        
        return BacktestMetrics(
            total_signals=total_signals,
            signals_after_forecaster=signals_after_forecaster,
            signals_after_riskofficer=signals_after_riskofficer,
            signals_after_newssentry=signals_after_newssentry,
            total_trades=total_trades,
            wins=wins,
            losses=losses,
            win_rate=win_rate,
            avg_return=avg_return,
            avg_win=avg_win,
            avg_loss=avg_loss,
            profit_factor=profit_factor,
            avg_hold_days=avg_hold_days,
            avg_confidence=avg_confidence,
            trades_normal=trades_normal,
            trades_high_vix=trades_high_vix,
            trades_spy_stress=trades_spy_stress,
            forecaster_vetoes=forecaster_vetoes,
            riskofficer_vetoes=riskofficer_vetoes,
            newssentry_vetoes=newssentry_vetoes,
            phase25_trades=phase25_trades,
            phase25_win_rate=phase25_win_rate,
            improvement_pct=improvement_pct,
        )
    
    def _print_summary(self, metrics: BacktestMetrics):
        """Print backtest summary."""
        logger.info("\n" + "="*70)
        logger.info("BACKTEST RESULTS SUMMARY")
        logger.info("="*70)
        
        logger.info("\n📊 SIGNAL FLOW:")
        logger.info(f"  Total Signals (Phase 2.5):        {metrics.total_signals}")
        logger.info(f"  After Forecaster:                 {metrics.signals_after_forecaster} (-{metrics.forecaster_vetoes} vetoed)")
        logger.info(f"  After RiskOfficer:                {metrics.signals_after_riskofficer} (-{metrics.riskofficer_vetoes} vetoed)")
        logger.info(f"  After NewsSentry:                 {metrics.signals_after_newssentry} (-{metrics.newssentry_vetoes} vetoed)")
        logger.info(f"  ➤ FINAL TRADES:                   {metrics.total_trades}")
        
        logger.info("\n🎯 PERFORMANCE:")
        logger.info(f"  Trades:                           {metrics.total_trades}")
        logger.info(f"  Wins:                             {metrics.wins}")
        logger.info(f"  Losses:                           {metrics.losses}")
        logger.info(f"  ➤ WIN RATE:                       {metrics.win_rate*100:.1f}%")
        logger.info(f"  Avg Return:                       {metrics.avg_return*100:+.2f}%")
        logger.info(f"  Avg Win:                          {metrics.avg_win*100:+.2f}%")
        logger.info(f"  Avg Loss:                         {metrics.avg_loss*100:+.2f}%")
        logger.info(f"  ➤ PROFIT FACTOR:                  {metrics.profit_factor:.2f}x")
        logger.info(f"  Avg Hold Days:                    {metrics.avg_hold_days:.1f}")
        logger.info(f"  Avg Confidence:                   {metrics.avg_confidence:.1f}")
        
        logger.info("\n🌐 BY REGIME:")
        logger.info(f"  Normal:                           {metrics.trades_normal} trades")
        logger.info(f"  High VIX:                         {metrics.trades_high_vix} trades")
        logger.info(f"  SPY Stress:                       {metrics.trades_spy_stress} trades")
        
        logger.info("\n📈 PHASE 2.5 COMPARISON:")
        logger.info(f"  Phase 2.5 Trades:                 {metrics.phase25_trades}")
        logger.info(f"  Phase 2.5 Win Rate:               {metrics.phase25_win_rate*100:.1f}%")
        logger.info(f"  Phase 3 Trades:                   {metrics.total_trades}")
        logger.info(f"  Phase 3 Win Rate:                 {metrics.win_rate*100:.1f}%")
        logger.info(f"  ➤ IMPROVEMENT:                    {metrics.improvement_pct:+.1f}%")
        
        logger.info("\n" + "="*70)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Phase 3 Agentic Backtest for PennyHunter")
    parser.add_argument(
        "--start-date",
        type=str,
        default="2019-01-01",
        help="Backtest start date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--end-date",
        type=str,
        default="2025-01-01",
        help="Backtest end date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--confidence-threshold",
        type=float,
        default=7.0,
        help="Minimum confidence score (normal regime)",
    )
    parser.add_argument(
        "--confidence-threshold-highvix",
        type=float,
        default=7.5,
        help="Minimum confidence score (high-vix regime)",
    )
    
    args = parser.parse_args()
    
    # Create backtester
    backtester = AgenticBacktester(
        start_date=args.start_date,
        end_date=args.end_date,
        confidence_threshold=args.confidence_threshold,
        confidence_threshold_highvix=args.confidence_threshold_highvix,
    )
    
    # Run backtest
    try:
        results = asyncio.run(backtester.run())
        logger.info(f"\n✅ Backtest complete!")
        logger.info(f"Results saved to: {RESULTS_FILE}")
        return 0
    except Exception as e:
        logger.error(f"\n❌ Backtest failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())

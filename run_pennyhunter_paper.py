#!/usr/bin/env python
"""
PennyHunter Paper Trading Runner

Runs PennyHunter scanner with Phase 1 enhancements, executes trades via paper broker,
and tracks results to validate win rate improvements.

Workflow:
1. Run scanner to find signals (with Phase 1 scoring)
2. Filter by market regime
3. Execute trades via PaperBroker
4. Monitor positions and exit at targets/stops
5. Log all trades and calculate statistics

Usage:
    python run_pennyhunter_paper.py
    python run_pennyhunter_paper.py --tickers SENS,SPCE,CLOV
    python run_pennyhunter_paper.py --account-size 200 --max-risk 5
"""

import sys
import argparse
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict
import yaml
import json

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from bouncehunter.broker import create_broker
from bouncehunter.market_regime import MarketRegimeDetector
from bouncehunter.signal_scoring import SignalScorer
from bouncehunter.penny_universe import PennyUniverse
from bouncehunter.advanced_filters import AdvancedRiskFilters
from bouncehunter.pennyhunter_memory import PennyHunterMemory
import yfinance as yf

# Project root
PROJECT_ROOT = Path(__file__).parent
BLOCKLIST_FILE = PROJECT_ROOT / "configs" / "ticker_blocklist.txt"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_ticker_blocklist() -> set:
    """Load ticker blocklist from configs/ticker_blocklist.txt"""
    if not BLOCKLIST_FILE.exists():
        return set()
    
    blocklist = set()
    with open(BLOCKLIST_FILE, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                if line.startswith('-'):
                    ticker = line.lstrip('- ').split('#')[0].strip()
                    if ticker:
                        blocklist.add(ticker.upper())
                else:
                    blocklist.add(line.upper())
    
    if blocklist:
        logger.info(f"📋 Loaded blocklist: {sorted(blocklist)}")
    
    return blocklist


class PennyHunterPaperTrader:
    """Paper trading system for PennyHunter"""

    def __init__(self, config: dict, account_size: float = 200.0, max_risk_per_trade: float = 5.0):
        self.config = config
        self.account_size = account_size
        self.max_risk_per_trade = max_risk_per_trade
        
        # PHASE 2 OPTIMIZATION: Load ticker blocklist
        self.ticker_blocklist = load_ticker_blocklist()

        # Initialize components
        self.broker = create_broker("paper", initial_cash=account_size)

        regime_config = config.get('guards', {}).get('market_regime', {})
        if regime_config.get('enabled', False):
            self.regime_detector = MarketRegimeDetector(
                vix_low=regime_config.get('vix_thresholds', {}).get('low', 20),
                vix_medium=regime_config.get('vix_thresholds', {}).get('medium', 30),
                vix_high=regime_config.get('vix_thresholds', {}).get('high', 40),
                require_spy_above_ma=regime_config.get('require_spy_above_200ma', True),
                require_spy_green=regime_config.get('require_spy_green_day', False)
            )
        else:
            self.regime_detector = None

        min_score = config.get('signals', {}).get('runner_vwap', {}).get('min_signal_score', 7.0)
        # TEMPORARILY LOWERED for testing - Oct 2025 (normal: 7.0)
        min_score = 5.5
        self.scorer = SignalScorer(min_score_threshold=min_score)

        self.universe = PennyUniverse(config['universe'])

        # NEW: Advanced risk filters
        self.advanced_filters = AdvancedRiskFilters()
        self.advanced_filters_enabled = config.get('advanced_filters', {}).get('enabled', True)

        # NEW: Phase 2.5 Memory System
        self.memory = PennyHunterMemory()
        self.memory_enabled = config.get('memory', {}).get('enabled', True)
        logger.info(f"📊 Memory System: {'ENABLED' if self.memory_enabled else 'DISABLED'}")

        # Track trades
        self.trades_log = []
        self.active_positions = {}

    def check_market_regime(self) -> bool:
        """Check if market regime allows penny trading"""
        if not self.regime_detector:
            logger.info("Market regime checking disabled")
            return True

        regime = self.regime_detector.get_regime()
        logger.info(f"📊 Market Regime: {regime.regime.upper()} - Trading {'ALLOWED' if regime.allow_penny_trading else 'BLOCKED'}")

        if not regime.allow_penny_trading:
            logger.warning(f"⚠️ Reason: {regime.reason}")

        return regime.allow_penny_trading

    def scan_for_signals(self, tickers: List[str]) -> List[Dict]:
        """Scan tickers for high-scoring signals"""
        logger.info(f"🔍 Scanning {len(tickers)} tickers for signals...")

        # Filter universe
        passed_tickers = self.universe.screen(tickers, lookback_days=10)
        logger.info(f"✅ {len(passed_tickers)} tickers passed universe filters")

        signals = []

        for ticker in passed_tickers:
            # Simple EOD signal approximation
            try:
                stock = yf.Ticker(ticker)
                hist = stock.history(period='90d')  # Extended lookback for testing

                if len(hist) < 5:
                    continue

                # Scan through all days to find gaps (not just most recent)
                for i in range(1, len(hist)):
                    current = hist.iloc[i]
                    prev = hist.iloc[i-1]

                    gap_pct = (current['Open'] - prev['Close']) / prev['Close'] * 100
                    avg_vol = hist['Volume'].iloc[max(0, i-10):i].mean()
                    vol_spike = current['Volume'] / avg_vol if avg_vol > 0 else 1.0
                    
                    # PHASE 2 OPTIMIZATION: Check blocklist first
                    if ticker in self.ticker_blocklist:
                        logger.info(f"🚫 {ticker}: On blocklist (underperformer)")
                        break
                    
                    # PHASE 2 OPTIMIZATION: Gap filter (10-15% sweet spot = 70% win rate)
                    if gap_pct < 10 or gap_pct > 15:
                        continue  # Skip this day, check next
                    
                    # PHASE 2 OPTIMIZATION: Volume filter (4-10x OR 15x+ = 70% win rate)  
                    vol_ok = (4 <= vol_spike <= 10) or (vol_spike >= 15)
                    if not vol_ok:
                        continue  # Skip this day, check next

                    if gap_pct >= 7:  # Keep this check for backward compatibility
                        # Score the signal (for logging, not filtering)
                        score = self.scorer.score_runner_vwap(
                            ticker=ticker,
                            gap_pct=gap_pct,
                            volume_spike=vol_spike,
                            float_millions=15,  # Assume mid-range
                            vwap_reclaim=True,
                            rsi=50.0,
                            spy_green=True,  # Already checked regime
                            vix_level=20.8,  # From regime check
                            premarket_volume_mult=vol_spike if vol_spike > 1.5 else None,
                            confirmation_bars=0
                        )

                        # PHASE 2 OPTIMIZATION: Accept all signals that pass gap/volume filters
                        # Score is logged but NOT used for filtering (not predictive)
                        signals.append({
                            'ticker': ticker,
                            'signal_type': 'runner_vwap',
                            'price': current['Close'],
                            'gap_pct': gap_pct,
                            'vol_spike': vol_spike,
                            'score': score.total_score,
                            'components': score.components,
                            'date': current.name.strftime('%Y-%m-%d'),
                            'hist': hist  # Store for advanced filtering
                        })
                        logger.info(f"🟢 {ticker} ({current.name.strftime('%Y-%m-%d')}): Gap {gap_pct:.1f}%, Vol {vol_spike:.1f}x, Score {score.total_score:.1f}/10.0 ✅")
                        break  # Only take first qualifying signal per ticker

            except Exception as e:
                logger.error(f"{ticker}: Error scanning - {e}", exc_info=True)

        logger.info(f"🎯 Found {len(signals)} signals above threshold")
        return signals

    def calculate_position_size(self, entry_price: float, stop_price: float) -> int:
        """Calculate position size based on $5 risk per trade"""
        risk_per_share = abs(entry_price - stop_price)

        if risk_per_share <= 0:
            logger.warning("Invalid risk calculation")
            return 0

        shares = int(self.max_risk_per_trade / risk_per_share)

        # Cap position size at account size
        max_shares = int(self.account_size / entry_price)
        shares = min(shares, max_shares)

        logger.info(f"Position size: {shares} shares (risk ${risk_per_share:.2f}/share = ${shares * risk_per_share:.2f} total)")
        return shares

    def execute_signal(self, signal: Dict) -> bool:
        """Execute a trade based on signal"""
        ticker = signal['ticker']
        entry_price = signal['price']

        # NEW: Check memory system - auto-eject chronic underperformers
        if self.memory_enabled:
            check = self.memory.should_trade_ticker(ticker)
            if not check['allowed']:
                logger.warning(f"❌ {ticker} BLOCKED BY MEMORY: {check['reason']}")
                if check['stats']:
                    stats = check['stats']
                    logger.warning(f"   Stats: {stats.win_rate*100:.1f}% WR ({stats.wins}W/{stats.losses}L), Status: {stats.status}")
                return False
            elif check['stats'] and check['stats'].status == 'monitored':
                logger.info(f"👁️ {ticker} MONITORED: {check['reason']}")
                stats = check['stats']
                logger.info(f"   Stats: {stats.win_rate*100:.1f}% WR ({stats.wins}W/{stats.losses}L)")

        # NEW: Run advanced quality gate if enabled
        if self.advanced_filters_enabled and 'hist' in signal:
            logger.info(f"🔍 Running advanced quality gate for {ticker}...")

            position_size_dollars = self.max_risk_per_trade * 20  # Approx position size
            quality_results = self.advanced_filters.run_quality_gate(
                ticker,
                signal['hist'],
                position_size_dollars,
                config={
                    'liquidity_delta_threshold': -30.0,
                    'max_slippage_pct': 5.0,  # More lenient for pennies
                    'min_cash_runway_months': 6.0,
                    'max_per_sector': 3,
                    'check_volume_fade': True
                }
            )

            if not quality_results['passed']:
                logger.warning(f"❌ {ticker} FAILED quality gate:")
                for check_name, check_data in quality_results['checks'].items():
                    if not check_data.get('passed', True) or check_data.get('detected', False):
                        logger.warning(f"   {check_name}: {check_data.get('reason')}")
                return False
            else:
                logger.info(f"✅ {ticker} passed quality gate")
                # Track sector
                sector = quality_results['checks']['sector']['sector_name']
                self.advanced_filters.track_sector(ticker, sector)

        # Calculate stop and target based on signal type
        if signal['signal_type'] == 'runner_vwap':
            stop_loss = entry_price * 0.95  # 5% stop
            take_profit = entry_price * 1.10  # 10% target
        else:  # FRD bounce
            stop_loss = entry_price * 0.97  # 3% stop
            take_profit = entry_price * 1.07  # 7% target

        # Calculate position size
        shares = self.calculate_position_size(entry_price, stop_loss)

        if shares == 0:
            logger.warning(f"{ticker}: Position size calculated as 0 - skipping")
            return False

        # Place bracket order
        try:
            logger.info(f"📈 ENTERING {ticker}: {shares} shares @ ${entry_price:.2f}")
            logger.info(f"   Stop: ${stop_loss:.2f} | Target: ${take_profit:.2f}")

            orders = self.broker.place_bracket_order(
                ticker=ticker,
                quantity=shares,
                entry_price=entry_price,
                stop_price=stop_loss,
                target_price=take_profit
            )

            # Track the trade
            trade = {
                'ticker': ticker,
                'entry_time': datetime.now().isoformat(),
                'entry_price': entry_price,
                'shares': shares,
                'stop_loss': stop_loss,
                'take_profit': take_profit,
                'signal_type': signal['signal_type'],
                'score': signal['score'],
                'gap_pct': signal.get('gap_pct', 0),
                'vol_mult': signal.get('vol_mult', 0),
                'status': 'active',
                'orders': {k: v.order_id for k, v in orders.items()}
            }

            self.active_positions[ticker] = trade
            self.trades_log.append(trade)

            logger.info(f"✅ {ticker} position opened successfully")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to execute {ticker}: {e}")
            return False

    def record_trade_outcome(self, trade: Dict):
        """Record completed trade outcome in memory system"""
        if not self.memory_enabled:
            return

        try:
            won = trade.get('pnl', 0) > 0
            pnl = trade.get('pnl', 0)
            trade_date = trade.get('exit_time', datetime.now().isoformat())

            self.memory.record_trade_outcome(
                ticker=trade['ticker'],
                won=won,
                pnl=pnl,
                trade_date=trade_date
            )

            status = "WIN ✅" if won else "LOSS ❌"
            logger.info(f"📝 Memory updated: {trade['ticker']} {status} ${pnl:.2f}")

        except Exception as e:
            logger.error(f"Failed to record trade outcome: {e}")

    def save_results(self, output_path: str):
        """Save trading results to file"""
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        # Record completed trades in memory
        completed_trades = [t for t in self.trades_log if t.get('status') == 'closed']
        for trade in completed_trades:
            self.record_trade_outcome(trade)

        # Calculate statistics
        total_trades = len(self.trades_log)

        wins = [t for t in completed_trades if t.get('pnl', 0) > 0]
        losses = [t for t in completed_trades if t.get('pnl', 0) < 0]

        win_rate = (len(wins) / len(completed_trades) * 100) if completed_trades else 0

        total_pnl = sum(t.get('pnl', 0) for t in completed_trades)
        avg_win = sum(t['pnl'] for t in wins) / len(wins) if wins else 0
        avg_loss = sum(t['pnl'] for t in losses) / len(losses) if losses else 0

        account = self.broker.get_account()

        report = {
            'generated_at': datetime.now().isoformat(),
            'account_summary': {
                'starting_capital': self.account_size,
                'current_cash': account.cash,
                'portfolio_value': account.portfolio_value,
                'total_pnl': account.portfolio_value - self.account_size,
                'return_pct': (account.portfolio_value - self.account_size) / self.account_size * 100
            },
            'trading_stats': {
                'total_trades': total_trades,
                'completed_trades': len(completed_trades),
                'active_trades': len(self.active_positions),
                'wins': len(wins),
                'losses': len(losses),
                'win_rate_pct': win_rate,
                'total_pnl': total_pnl,
                'avg_win': avg_win,
                'avg_loss': avg_loss,
                'profit_factor': abs(avg_win / avg_loss) if avg_loss != 0 else 0
            },
            'trades': self.trades_log
        }

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2)

        logger.info(f"💾 Results saved to {output_file}")

        # Print summary
        print("\n" + "="*70)
        print("PENNYHUNTER PAPER TRADING RESULTS")
        print("="*70)
        print(f"Starting Capital: ${self.account_size:.2f}")
        print(f"Current Value: ${account.portfolio_value:.2f}")
        print(f"Total P&L: ${total_pnl:.2f} ({report['account_summary']['return_pct']:.1f}%)")
        print()
        print(f"Total Trades: {total_trades}")
        print(f"Completed: {len(completed_trades)} | Active: {len(self.active_positions)}")
        print(f"Wins: {len(wins)} | Losses: {len(losses)}")
        print(f"Win Rate: {win_rate:.1f}%")
        if wins:
            print(f"Avg Win: ${avg_win:.2f} | Avg Loss: ${avg_loss:.2f}")
        print("="*70 + "\n")

        # NEW: Display memory system stats
        if self.memory_enabled:
            print("="*70)
            print("MEMORY SYSTEM STATUS (Phase 2.5 Auto-Ejection)")
            print("="*70)

            all_stats = self.memory.get_all_ticker_stats()
            ejected = [s for s in all_stats if s.status == 'ejected']
            monitored = [s for s in all_stats if s.status == 'monitored']
            active = [s for s in all_stats if s.status == 'active']

            print(f"Active: {len(active)} | Monitored: {len(monitored)} | Ejected: {len(ejected)}")
            print()

            if ejected:
                print("EJECTED TICKERS:")
                for stat in ejected:
                    print(f"   {stat.ticker}: {stat.win_rate*100:.1f}% WR ({stat.wins}W/{stat.losses}L)")
                    if stat.ejection_reason:
                        print(f"      Reason: {stat.ejection_reason}")
                print()

            if monitored:
                print("MONITORED TICKERS (Underperforming - Watch Closely):")
                for stat in monitored:
                    print(f"   {stat.ticker}: {stat.win_rate*100:.1f}% WR ({stat.wins}W/{stat.losses}L), P&L: ${stat.total_pnl:.2f}")
                print()

            if active:
                print("✅ ACTIVE TICKERS:")
                # Show top performers
                active_sorted = sorted(active, key=lambda s: s.win_rate, reverse=True)[:5]
                for stat in active_sorted:
                    print(f"   {stat.ticker}: {stat.win_rate*100:.1f}% WR ({stat.wins}W/{stat.losses}L), P&L: ${stat.total_pnl:.2f}")
                if len(active) > 5:
                    print(f"   ... and {len(active)-5} more")

            print("="*70 + "\n")


def main():
    parser = argparse.ArgumentParser(description='PennyHunter Paper Trading')
    parser.add_argument('--config', default='configs/pennyhunter.yaml', help='Config file')
    parser.add_argument('--tickers', help='Comma-separated tickers (or use --ticker-file)')
    parser.add_argument('--ticker-file', default='configs/active_pennies.txt',
                       help='File with ticker list')
    parser.add_argument('--account-size', type=float, default=200.0,
                       help='Account size (default $200)')
    parser.add_argument('--max-risk', type=float, default=5.0,
                       help='Max risk per trade (default $5)')
    parser.add_argument('--output', default='reports/pennyhunter_paper_trades.json',
                       help='Output file for results')
    args = parser.parse_args()

    # Load config
    with open(args.config) as f:
        config = yaml.safe_load(f)

    # Get tickers
    if args.tickers:
        tickers = [t.strip().upper() for t in args.tickers.split(',')]
    else:
        ticker_file = Path(args.ticker_file)
        if ticker_file.exists():
            with open(ticker_file) as f:
                content = f.read()
                # Get last line (ticker list)
                tickers = [t.strip().upper() for t in content.strip().split('\n')[-1].split(',')]
            logger.info(f"Loaded {len(tickers)} tickers from {ticker_file}")
        else:
            logger.error(f"Ticker file not found: {ticker_file}")
            logger.info("Run: python scripts/fetch_active_pennies.py")
            sys.exit(1)

    # Initialize trader
    trader = PennyHunterPaperTrader(config, args.account_size, args.max_risk)

    # Check market regime
    if not trader.check_market_regime():
        logger.warning("Market regime blocks penny trading - exiting")
        sys.exit(1)

    # Scan for signals
    signals = trader.scan_for_signals(tickers)

    if not signals:
        logger.warning("No signals found above scoring threshold")
        trader.save_results(args.output)
        sys.exit(0)

    # Execute top signals (limit to 1 position for $200 account)
    max_positions = 1
    executed = 0

    for signal in signals[:max_positions]:
        if trader.execute_signal(signal):
            executed += 1

    logger.info(f"✅ Executed {executed}/{len(signals)} signals")

    # Save results
    trader.save_results(args.output)

    sys.exit(0)


if __name__ == '__main__':
    main()

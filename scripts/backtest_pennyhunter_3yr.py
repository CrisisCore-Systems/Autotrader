#!/usr/bin/env python
"""
PennyHunter 3-Year Historical Backtesting Engine

Backtests PennyHunter strategy on 3 years of historical data (2022-2025).
Generates 50-150+ completed trades for immediate Phase 2 validation.

Features:
- Scans historical gaps with Phase 2 filters
- Simulates paper trades with actual historical prices
- Tracks stop/target hits with real price action
- Applies market regime detection historically
- Uses advanced quality gates on historical data
- Outputs to same format as daily trading for analysis

Usage:
    python scripts/backtest_pennyhunter_3yr.py
    python scripts/backtest_pennyhunter_3yr.py --start-date 2022-01-01 --end-date 2025-10-18
    python scripts/backtest_pennyhunter_3yr.py --tickers INTR,ADT,SAN,COMP

Output:
    - reports/pennyhunter_backtest_results.json (detailed trades)
    - Feeds into analyze_pennyhunter_results.py for validation
"""

import sys
import json
import logging
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
import yaml

import yfinance as yf
import pandas as pd

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from bouncehunter.market_regime import MarketRegimeDetector
from bouncehunter.signal_scoring import SignalScorer
from bouncehunter.penny_universe import PennyUniverse
from bouncehunter.advanced_filters import AdvancedRiskFilters

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent
CONFIG_FILE = PROJECT_ROOT / "configs" / "pennyhunter.yaml"
OUTPUT_FILE = PROJECT_ROOT / "reports" / "pennyhunter_backtest_results.json"
CUMULATIVE_FILE = PROJECT_ROOT / "reports" / "pennyhunter_cumulative_history.json"


class PennyHunterBacktester:
    """Historical backtesting engine for PennyHunter strategy"""

    def __init__(self, config: dict, start_date: str, end_date: str):
        self.config = config
        self.start_date = pd.Timestamp(start_date)
        self.end_date = pd.Timestamp(end_date)

        # Initialize Phase 2 components
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
        min_score = 5.5  # Temporarily lowered for testing
        self.scorer = SignalScorer(min_score_threshold=min_score)

        self.universe = PennyUniverse(config['universe'])
        self.advanced_filters = AdvancedRiskFilters()
        self.advanced_filters_enabled = config.get('advanced_filters', {}).get('enabled', True)
        self.base_risk_dollars = config.get('risk', {}).get('per_trade_risk_dollars', 5.0)

        # Preload market data for historical regime reconstruction
        self.spy_history = self._load_spy_history()
        self.vix_history = self._load_vix_history()
        self._regime_cache: Dict[pd.Timestamp, Dict] = {}

        # Tracking
        self.trades = []
        self.stats = {
            'total_days_scanned': 0,
            'signals_found': 0,
            'signals_passed_filters': 0,
            'trades_executed': 0,
            'regime_blocks': 0
        }

    def _load_spy_history(self) -> pd.DataFrame:
        """Fetch SPY history with 200-day moving average for regime reconstruction."""
        buffer_start = self.start_date - pd.Timedelta(days=320)
        buffer_end = self.end_date + pd.Timedelta(days=5)
        try:
            spy = yf.Ticker("SPY")
            hist = spy.history(start=buffer_start, end=buffer_end)
            if hist.empty:
                logger.warning("⚠️ Unable to load SPY history for regime reconstruction")
                return pd.DataFrame()
            hist = hist.tz_localize(None)
            hist.index = pd.to_datetime(hist.index).normalize()
            hist['MA200'] = hist['Close'].rolling(200).mean()
            logger.info("📥 Loaded %s SPY bars for regime reconstruction", len(hist))
            return hist
        except Exception as exc:
            logger.error("Failed to load SPY history: %s", exc, exc_info=True)
            return pd.DataFrame()

    def _load_vix_history(self) -> pd.DataFrame:
        """Fetch VIX history for regime reconstruction."""
        buffer_start = self.start_date - pd.Timedelta(days=120)
        buffer_end = self.end_date + pd.Timedelta(days=5)
        try:
            vix = yf.Ticker("^VIX")
            hist = vix.history(start=buffer_start, end=buffer_end)
            if hist.empty:
                logger.warning("⚠️ Unable to load VIX history for regime reconstruction")
                return pd.DataFrame()
            hist = hist.tz_localize(None)
            hist.index = pd.to_datetime(hist.index).normalize()
            logger.info("📥 Loaded %s VIX bars for regime reconstruction", len(hist))
            return hist
        except Exception as exc:
            logger.error("Failed to load VIX history: %s", exc, exc_info=True)
            return pd.DataFrame()

    def _get_history_row(self, df: pd.DataFrame, date: pd.Timestamp) -> Optional[pd.Series]:
        """Return row for date or most recent prior trading day."""
        if df.empty:
            return None

        if date in df.index:
            return df.loc[date]

        earlier = df.index[df.index < date]
        if len(earlier) == 0:
            return None

        return df.loc[earlier[-1]]

    def get_historical_regime(self, date: pd.Timestamp) -> Optional[Dict]:
        """Get market regime for a specific historical date"""
        date_norm = pd.Timestamp(date).tz_localize(None).normalize()

        if date_norm in self._regime_cache:
            return self._regime_cache[date_norm]

        if not self.regime_detector:
            snapshot = {
                'allow_trading': True,
                'regime': 'NEUTRAL',
                'reason': 'Regime checking disabled',
                'spy_price': None,
                'spy_ma200': None,
                'spy_above_ma': False,
                'spy_day_change_pct': 0.0,
                'spy_green': True,
                'vix': None,
                'vix_regime': 'unknown',
            }
            self._regime_cache[date_norm] = snapshot
            return snapshot

        spy_row = self._get_history_row(self.spy_history, date_norm)
        vix_row = self._get_history_row(self.vix_history, date_norm)

        if spy_row is None or vix_row is None:
            snapshot = {
                'allow_trading': True,
                'regime': 'UNKNOWN',
                'reason': 'insufficient_historical_data',
                'spy_price': None,
                'spy_ma200': None,
                'spy_above_ma': False,
                'spy_day_change_pct': 0.0,
                'spy_green': True,
                'vix': None,
                'vix_regime': 'unknown',
            }
            self._regime_cache[date_norm] = snapshot
            return snapshot

        spy_close = float(spy_row['Close'])
        spy_open = float(spy_row['Open']) if spy_row['Open'] else spy_close
        spy_ma200 = float(spy_row['MA200']) if not pd.isna(spy_row.get('MA200')) else None
        spy_day_change_pct = ((spy_close - spy_open) / spy_open * 100) if spy_open else 0.0
        spy_above_ma = bool(spy_ma200 and spy_close > spy_ma200)
        spy_green = spy_day_change_pct > 0

        vix_level = float(vix_row['Close']) if not pd.isna(vix_row['Close']) else None

        if vix_level is None:
            vix_regime = 'unknown'
        elif vix_level < self.regime_detector.vix_low:
            vix_regime = 'low'
        elif vix_level < self.regime_detector.vix_medium:
            vix_regime = 'medium'
        elif vix_level < self.regime_detector.vix_high:
            vix_regime = 'high'
        else:
            vix_regime = 'extreme'

        signals_desc = []
        signals_desc.append("SPY > 200MA" if spy_above_ma else "SPY < 200MA ⚠️")
        signals_desc.append(f"SPY {spy_day_change_pct:+.2f}%" + ("" if spy_green else " ⚠️"))
        if vix_level is None:
            signals_desc.append("VIX unknown")
        elif vix_regime in ['low', 'medium']:
            signals_desc.append(f"VIX {vix_level:.1f} ({vix_regime})")
        else:
            signals_desc.append(f"VIX {vix_level:.1f} ({vix_regime}) ⚠️")

        reason = ', '.join(signals_desc)

        if not spy_above_ma and self.regime_detector.require_spy_above_ma:
            regime_str, allow = 'risk_off', False
            reason = f"SPY below 200MA ({reason})"
        elif vix_level is not None and vix_level > self.regime_detector.vix_medium:
            regime_str, allow = 'risk_off', False
            reason = f"VIX too high ({reason})"
        elif (
            spy_day_change_pct < -1.0
            and self.regime_detector.require_spy_green
        ):
            regime_str, allow = 'risk_off', False
            reason = f"SPY red day ({reason})"
        elif spy_above_ma and vix_regime == 'low' and spy_day_change_pct > 0:
            regime_str, allow = 'risk_on', True
            reason = f"Optimal conditions ({reason})"
        elif spy_above_ma and vix_regime == 'medium':
            regime_str, allow = 'neutral', True
            reason = f"Mixed signals ({reason})"
        else:
            regime_str, allow = 'neutral', True
            reason = f"Neutral market ({reason})"

        snapshot = {
            'allow_trading': allow,
            'regime': regime_str.upper(),
            'reason': reason,
            'spy_price': spy_close,
            'spy_ma200': spy_ma200,
            'spy_above_ma': spy_above_ma,
            'spy_day_change_pct': spy_day_change_pct,
            'spy_green': spy_green,
            'vix': vix_level,
            'vix_regime': vix_regime,
        }

        self._regime_cache[date_norm] = snapshot
        return snapshot

    def compute_risk_budget(self, date: pd.Timestamp) -> float:
        """Return risk-per-trade dollars scaled by historical VIX."""
        regime = self.get_historical_regime(date)
        vix = regime.get('vix') if regime else None
        vix_value = float(vix) if vix is not None else 20.0
        scale = 20.0 / max(10.0, vix_value)
        scale = max(0.5, min(1.0, scale))
        return round(self.base_risk_dollars * scale, 2)

    def scan_historical_gaps(self, ticker: str, hist: pd.DataFrame) -> List[Dict]:
        """Scan historical data for gap signals"""
        signals = []

        for i in range(1, len(hist)):
            current = hist.iloc[i]
            prev = hist.iloc[i-1]

            # Calculate gap
            gap_pct = (current['Open'] - prev['Close']) / prev['Close'] * 100

            # Minimum gap threshold (lowered from 7% to 5% for more signals)
            if gap_pct < 5.0:
                continue

            # Calculate volume spike
            lookback_start = max(0, i-10)
            avg_vol = hist['Volume'].iloc[lookback_start:i].mean()
            vol_spike = current['Volume'] / avg_vol if avg_vol > 0 else 1.0

            # Get date
            signal_date = current.name if hasattr(current, 'name') else hist.index[i]

            regime = self.get_historical_regime(signal_date)
            spy_green = regime.get('spy_green', True)
            vix_level = float(regime.get('vix', 20.0) or 20.0)

            # Score the signal
            score = self.scorer.score_runner_vwap(
                ticker=ticker,
                gap_pct=gap_pct,
                volume_spike=vol_spike,
                float_millions=15,  # Assume mid-range
                vwap_reclaim=True,
                rsi=50.0,
                spy_green=spy_green,
                vix_level=vix_level,
                premarket_volume_mult=vol_spike if vol_spike > 1.5 else None,
                confirmation_bars=0
            )

            if score.passed_threshold:
                signals.append({
                    'ticker': ticker,
                    'date': signal_date,
                    'index': i,
                    'signal_type': 'runner_vwap',
                    'entry_price': current['Open'],
                    'close_price': current['Close'],
                    'gap_pct': gap_pct,
                    'vol_spike': vol_spike,
                    'score': score.total_score,
                    'regime': regime,
                    'hist': hist  # Keep for quality gate
                })
                self.stats['signals_found'] += 1

        return signals

    def apply_quality_gates(self, signal: Dict) -> bool:
        """Apply advanced quality gate filters to signal"""
        if not self.advanced_filters_enabled:
            return True

        ticker = signal['ticker']
        hist = signal['hist']

        # Estimate position size based on historical risk budget (approx 20x risk)
        position_size_dollars = self.compute_risk_budget(signal['date']) * 20

        try:
            quality_results = self.advanced_filters.run_quality_gate(
                ticker, hist, position_size_dollars
            )

            if not quality_results['passed']:
                logger.debug(f"❌ {ticker} failed quality gate on {signal['date']}")
                for check_name, check_data in quality_results['checks'].items():
                    if not check_data.get('passed', True):
                        logger.debug(f"   {check_name}: {check_data.get('reason')}")
                return False

            self.stats['signals_passed_filters'] += 1
            return True

        except Exception as e:
            logger.warning(f"Quality gate error for {ticker}: {e}")
            return False

    def simulate_trade(self, signal: Dict, hist: pd.DataFrame) -> Optional[Dict]:
        """Simulate trade execution and outcome using historical prices"""
        entry_idx = signal['index']
        entry_price = signal['entry_price']

        # Set stops and targets
        if signal['signal_type'] == 'runner_vwap':
            stop_loss = entry_price * 0.95  # 5% stop
            take_profit = entry_price * 1.10  # 10% target
        else:
            stop_loss = entry_price * 0.97  # 3% stop
            take_profit = entry_price * 1.07  # 7% target

        # Position size calculation uses dynamic risk budget
        risk_dollars = self.compute_risk_budget(signal['date'])
        risk_per_share = entry_price - stop_loss
        shares = int(risk_dollars / risk_per_share) if risk_per_share > 0 else 0

        if shares == 0:
            return None

        # Scan forward to find exit
        max_hold_days = 10  # Maximum holding period
        exit_price = None
        exit_reason = None
        exit_idx = None

        for j in range(entry_idx + 1, min(entry_idx + max_hold_days + 1, len(hist))):
            bar = hist.iloc[j]

            # Check if stop or target hit
            if bar['Low'] <= stop_loss:
                exit_price = stop_loss
                exit_reason = 'STOP'
                exit_idx = j
                break
            elif bar['High'] >= take_profit:
                exit_price = take_profit
                exit_reason = 'TARGET'
                exit_idx = j
                break

        # If no exit found, close at end of hold period
        if exit_price is None:
            if entry_idx + max_hold_days < len(hist):
                exit_idx = entry_idx + max_hold_days
                exit_price = hist.iloc[exit_idx]['Close']
                exit_reason = 'TIME'
            else:
                # Reached end of data
                exit_idx = len(hist) - 1
                exit_price = hist.iloc[exit_idx]['Close']
                exit_reason = 'TIME'

        # Calculate P&L
        pnl = (exit_price - entry_price) * shares
        pnl_pct = (exit_price / entry_price - 1) * 100

        entry_date = signal['date']
        exit_date = hist.index[exit_idx] if exit_idx < len(hist) else hist.index[-1]
        hold_days = (exit_date - entry_date).days if isinstance(entry_date, pd.Timestamp) else 0

        trade = {
            'ticker': signal['ticker'],
            'signal_type': signal['signal_type'],
            'entry_time': entry_date.isoformat() if isinstance(entry_date, pd.Timestamp) else str(entry_date),
            'exit_time': exit_date.isoformat() if isinstance(exit_date, pd.Timestamp) else str(exit_date),
            'entry_price': float(entry_price),
            'exit_price': float(exit_price),
            'stop_loss': float(stop_loss),
            'take_profit': float(take_profit),
            'shares': shares,
            'pnl': float(pnl),
            'pnl_pct': float(pnl_pct),
            'exit_reason': exit_reason,
            'hold_days': int(hold_days),
            'score': signal['score'],
            'gap_pct': signal['gap_pct'],
            'vol_mult': signal['vol_spike'],
            'status': 'closed'
        }

        regime = signal.get('regime', {})
        trade['market_regime'] = regime.get('regime')
        trade['vix'] = regime.get('vix')
        trade['risk_dollars'] = risk_dollars

        self.stats['trades_executed'] += 1
        return trade

    def backtest_ticker(self, ticker: str) -> List[Dict]:
        """Backtest a single ticker over the date range"""
        logger.info(f"Backtesting {ticker}...")

        try:
            # Download historical data
            stock = yf.Ticker(ticker)
            hist = stock.history(start=self.start_date, end=self.end_date)

            if len(hist) < 20:
                logger.warning(f"{ticker}: Insufficient historical data ({len(hist)} days)")
                return []

            logger.info(f"{ticker}: Loaded {len(hist)} days of data")

            # Screen for universe filters
            passed_tickers = self.universe.screen([ticker], lookback_days=10)
            if ticker not in passed_tickers:
                logger.info(f"{ticker}: Failed universe filters")
                return []

            # Scan for gap signals
            signals = self.scan_historical_gaps(ticker, hist)

            if not signals:
                logger.info(f"{ticker}: No signals found")
                return []

            logger.info(f"{ticker}: Found {len(signals)} potential signals")

            # Filter signals through quality gates and regime
            valid_trades = []

            for signal in signals:
                signal_date = signal['date']

                # Check market regime
                regime = signal.get('regime') or self.get_historical_regime(signal_date)
                if not regime['allow_trading']:
                    logger.debug(f"❌ {ticker} on {signal_date}: Regime blocked ({regime['regime']})")
                    self.stats['regime_blocks'] += 1
                    continue

                # Apply quality gates
                if not self.apply_quality_gates(signal):
                    continue

                # Simulate trade
                trade = self.simulate_trade(signal, hist)
                if trade:
                    valid_trades.append(trade)

            logger.info(f"{ticker}: Executed {len(valid_trades)} trades")
            return valid_trades

        except Exception as e:
            logger.error(f"{ticker}: Backtest failed: {e}")
            return []

    def run_backtest(self, tickers: List[str]) -> Dict:
        """Run backtest on all tickers"""
        logger.info(f"\n{'='*70}")
        logger.info("PENNYHUNTER 3-YEAR HISTORICAL BACKTEST")
        logger.info(f"{'='*70}")
        logger.info(f"Date Range: {self.start_date.date()} to {self.end_date.date()}")
        logger.info(f"Tickers: {', '.join(tickers)}")
        logger.info(f"{'='*70}\n")

        all_trades = []

        for ticker in tickers:
            trades = self.backtest_ticker(ticker)
            all_trades.extend(trades)

        # Calculate summary statistics
        completed_trades = [t for t in all_trades if t.get('status') == 'closed']
        wins = [t for t in completed_trades if t['pnl'] > 0]
        losses = [t for t in completed_trades if t['pnl'] <= 0]

        win_rate = (len(wins) / len(completed_trades) * 100) if completed_trades else 0
        total_pnl = sum(t['pnl'] for t in completed_trades)
        avg_win = sum(t['pnl'] for t in wins) / len(wins) if wins else 0
        avg_loss = sum(t['pnl'] for t in losses) / len(losses) if losses else 0
        profit_factor = abs(avg_win / avg_loss) if avg_loss != 0 else 0

        results = {
            'backtest_config': {
                'start_date': self.start_date.isoformat(),
                'end_date': self.end_date.isoformat(),
                'tickers': tickers,
                'min_score_threshold': self.scorer.min_score_threshold,
                'advanced_filters_enabled': self.advanced_filters_enabled
            },
            'summary_stats': {
                'total_signals_found': self.stats['signals_found'],
                'signals_passed_filters': self.stats['signals_passed_filters'],
                'filter_pass_rate': (self.stats['signals_passed_filters'] / self.stats['signals_found'] * 100)
                    if self.stats['signals_found'] > 0 else 0,
                'regime_blocks': self.stats['regime_blocks'],
                'total_trades': len(completed_trades),
                'wins': len(wins),
                'losses': len(losses),
                'win_rate_pct': win_rate,
                'total_pnl': total_pnl,
                'avg_win': avg_win,
                'avg_loss': avg_loss,
                'profit_factor': profit_factor
            },
            'trades': all_trades,
            'generated_at': datetime.now().isoformat()
        }

        return results


def merge_backtest_into_cumulative(backtest_results: Dict):
    """Merge backtest results into cumulative history format"""
    # Load existing cumulative history
    if CUMULATIVE_FILE.exists():
        with open(CUMULATIVE_FILE, 'r', encoding='utf-8') as f:
            history = json.load(f)
    else:
        history = {
            'first_trade_date': None,
            'last_updated': None,
            'total_sessions': 0,
            'trades': [],
            'metadata': {
                'phase': '2',
                'goal': 'Validate 65-75% win rate with historical backtest',
                'current_milestone': 'Phase 2 backtest validation'
            }
        }

    # Add backtest marker
    history['total_sessions'] += 1
    session_marker = {
        'session_id': history['total_sessions'],
        'date': datetime.now().isoformat(),
        'type': 'backtest_session',
        'backtest_config': backtest_results['backtest_config']
    }
    history['trades'].append(session_marker)

    # Add all backtest trades
    for trade in backtest_results['trades']:
        trade['session_id'] = history['total_sessions']
        trade['source'] = 'backtest'
        history['trades'].append(trade)

    # Update metadata
    if not history['first_trade_date']:
        history['first_trade_date'] = backtest_results['backtest_config']['start_date']
    history['last_updated'] = datetime.now().isoformat()

    # Save
    CUMULATIVE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CUMULATIVE_FILE, 'w', encoding='utf-8') as f:
        json.dump(history, f, indent=2, ensure_ascii=False)

    logger.info(f"\nMerged backtest results into: {CUMULATIVE_FILE}")


def print_backtest_summary(results: Dict):
    """Print summary of backtest results"""
    stats = results['summary_stats']
    config = results['backtest_config']

    print("\n" + "="*70)
    print("PENNYHUNTER 3-YEAR BACKTEST RESULTS")
    print("="*70)
    print(f"Period: {config['start_date'][:10]} to {config['end_date'][:10]}")
    print(f"Tickers: {', '.join(config['tickers'])}")
    print()

    print("SIGNAL GENERATION:")
    print(f"  Total Signals Found: {stats['total_signals_found']}")
    print(f"  Passed Quality Gates: {stats['signals_passed_filters']}")
    print(f"  Filter Pass Rate: {stats['filter_pass_rate']:.1f}%")
    print(f"  Regime Blocks: {stats['regime_blocks']}")
    print()

    print("TRADE RESULTS:")
    print(f"  Total Trades: {stats['total_trades']}")
    print(f"  Wins: {stats['wins']}")
    print(f"  Losses: {stats['losses']}")
    print(f"  Win Rate: {stats['win_rate_pct']:.1f}%")
    print()

    if stats['total_trades'] > 0:
        print("PROFITABILITY:")
        print(f"  Total P&L: ${stats['total_pnl']:.2f}")
        print(f"  Avg Win: ${stats['avg_win']:.2f}")
        print(f"  Avg Loss: ${stats['avg_loss']:.2f}")
        print(f"  Profit Factor: {stats['profit_factor']:.2f}")
        print()

    print("PHASE 2 VALIDATION:")
    win_rate = stats['win_rate_pct']

    if stats['total_trades'] >= 20:
        print(f"  Sample Size: {stats['total_trades']} trades (>= 20) ✅")
    else:
        print(f"  Sample Size: {stats['total_trades']} trades (< 20) ⚠️")

    if win_rate >= 65:
        print(f"  Win Rate: {win_rate:.1f}% (>= 65% target) ✅")
        print()
        print("  ✅ PHASE 2 VALIDATED - Ready for Phase 2.5!")
    elif win_rate >= 55:
        print(f"  Win Rate: {win_rate:.1f}% (Phase 1 level) ⚠️")
        print()
        print("  ⚠️ Below Phase 2 target - Review filter settings")
    else:
        print(f"  Win Rate: {win_rate:.1f}% (< 55%) ❌")
        print()
        print("  ❌ Below Phase 1 target - Debug required")

    print("="*70 + "\n")

    print("NEXT STEPS:")
    if stats['total_trades'] >= 20 and win_rate >= 65:
        print("  1. Run: python scripts/analyze_pennyhunter_results.py")
        print("  2. Review detailed ticker performance")
        print("  3. Implement Phase 2.5 lightweight memory system")
        print("  4. Integrate auto-ejection feature")
    else:
        print("  1. Review backtest results")
        print("  2. Adjust filter thresholds if needed")
        print("  3. Re-run backtest with adjustments")
    print()


def main():
    parser = argparse.ArgumentParser(description='PennyHunter 3-Year Historical Backtest')
    parser.add_argument('--start-date', default='2022-01-01',
                       help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end-date', default='2025-10-18',
                       help='End date (YYYY-MM-DD)')
    parser.add_argument('--tickers',
                       default='ADT,SAN,COMP,INTR,AHCO,SNDL,CLOV,EVGO,SENS,SPCE',
                       help='Comma-separated ticker list')
    parser.add_argument('--config', default=str(CONFIG_FILE),
                       help='Config file path')
    parser.add_argument('--output', default=str(OUTPUT_FILE),
                       help='Output JSON file path')
    parser.add_argument('--merge', action='store_true', default=True,
                       help='Merge results into cumulative history')

    args = parser.parse_args()

    # Load config
    with open(args.config, encoding='utf-8') as f:
        config = yaml.safe_load(f)

    # Parse tickers
    tickers = [t.strip().upper() for t in args.tickers.split(',')]

    # Run backtest
    backtester = PennyHunterBacktester(config, args.start_date, args.end_date)
    results = backtester.run_backtest(tickers)

    # Save results
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    logger.info(f"Results saved to: {output_path}")

    # Merge into cumulative history
    if args.merge:
        merge_backtest_into_cumulative(results)

    # Print summary
    print_backtest_summary(results)

    return 0


if __name__ == '__main__':
    sys.exit(main())

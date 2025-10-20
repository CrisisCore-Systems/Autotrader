#!/usr/bin/env python
"""
PennyHunter Nightly Scanner

EOD approximation of Runner VWAP and FRD Bounce signals.
Run this daily after market close to get tomorrow's watchlist.

Usage:
    python run_pennyhunter_nightly.py
    python run_pennyhunter_nightly.py --config configs/pennyhunter.yaml
    python run_pennyhunter_nightly.py --tickers PLUG,SNDL,MARA,RIOT
"""

import sys
import os
import argparse
import logging
from pathlib import Path
from datetime import datetime, timedelta
import yaml
import yfinance as yf
import numpy as np
import pandas as pd

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from bouncehunter.penny_universe import PennyUniverse
from bouncehunter.market_regime import MarketRegimeDetector
from bouncehunter.signal_scoring import SignalScorer

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def calculate_rsi(prices: pd.Series, period: int = 2) -> pd.Series:
    """Calculate RSI indicator"""
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()

    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def check_runner_setup(ticker: str, lookback_days: int = 30) -> dict:
    """
    Check if ticker has Runner VWAP setup (EOD approximation).

    Looks for:
    - Recent gap up ≥20%
    - Strong volume
    - Price holding near highs
    """
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period=f"{lookback_days}d")

        if len(hist) < 5:
            return {'setup': False, 'reason': 'insufficient data'}

        # Check last 5 days for gap ups
        for i in range(-5, 0):
            if abs(i) > len(hist):
                continue

            today = hist.iloc[i]
            yesterday = hist.iloc[i-1]

            gap_pct = (today['Open'] - yesterday['Close']) / yesterday['Close'] * 100

            # Gap up ≥20%?
            if gap_pct >= 20:
                # Volume spike?
                avg_vol = hist['Volume'].iloc[-10:-1].mean()
                vol_spike = today['Volume'] / avg_vol if avg_vol > 0 else 1.0

                # Price strength (close in top 30% of range)?
                range_pos = (today['Close'] - today['Low']) / (today['High'] - today['Low']) if today['High'] > today['Low'] else 0.5

                if vol_spike >= 1.5 and range_pos >= 0.3:
                    return {
                        'setup': True,
                        'signal': 'runner_vwap',
                        'gap_pct': gap_pct,
                        'vol_spike': vol_spike,
                        'range_pos': range_pos,
                        'price': today['Close'],
                        'date': today.name.strftime('%Y-%m-%d'),
                        'reason': f"Gap up +{gap_pct:.1f}%, vol {vol_spike:.1f}x, strong close"
                    }

        return {'setup': False, 'reason': 'no recent gap up ≥20%'}

    except Exception as e:
        logger.warning(f"{ticker}: Error checking runner setup - {e}")
        return {'setup': False, 'reason': f'error: {e}'}


def check_frd_setup(ticker: str, lookback_days: int = 30) -> dict:
    """
    Check if ticker has FRD Bounce setup (First Red Day).

    Looks for:
    - Prior day large range (>2.5× ATR)
    - Prior day close in top 30%
    - Today gap down
    - Extreme RSI(2) < 10
    """
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period=f"{lookback_days}d")

        if len(hist) < 15:
            return {'setup': False, 'reason': 'insufficient data'}

        # Calculate ATR(14)
        tr1 = hist['High'] - hist['Low']
        tr2 = abs(hist['High'] - hist['Close'].shift())
        tr3 = abs(hist['Low'] - hist['Close'].shift())
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(14).mean()

        # Calculate RSI(2)
        rsi2 = calculate_rsi(hist['Close'], period=2)

        # Check last 3 days for FRD setup
        for i in range(-3, 0):
            if abs(i) > len(hist) or abs(i-1) > len(hist):
                continue

            today = hist.iloc[i]
            yesterday = hist.iloc[i-1]

            # Prior day range > 2.5× ATR?
            yesterday_range = yesterday['High'] - yesterday['Low']
            yesterday_atr = atr.iloc[i-1]

            if yesterday_atr == 0:
                continue

            range_mult = yesterday_range / yesterday_atr

            # Prior day close in top 30%?
            yesterday_range_pos = (yesterday['Close'] - yesterday['Low']) / yesterday_range if yesterday_range > 0 else 0.5

            # Today gap down?
            gap_pct = (today['Open'] - yesterday['Close']) / yesterday['Close'] * 100

            # RSI(2) < 10?
            today_rsi = rsi2.iloc[i]

            if (range_mult >= 2.5 and
                yesterday_range_pos >= 0.3 and
                gap_pct < -5 and
                today_rsi < 10):

                return {
                    'setup': True,
                    'signal': 'frd_bounce',
                    'prior_range_mult': range_mult,
                    'gap_pct': gap_pct,
                    'rsi2': today_rsi,
                    'price': today['Close'],
                    'date': today.name.strftime('%Y-%m-%d'),
                    'reason': f"FRD: prior range {range_mult:.1f}×ATR, gap {gap_pct:.1f}%, RSI {today_rsi:.1f}"
                }

        return {'setup': False, 'reason': 'no FRD setup found'}

    except Exception as e:
        logger.warning(f"{ticker}: Error checking FRD setup - {e}")
        return {'setup': False, 'reason': f'error: {e}'}


def scan_pennies(tickers: list, config: dict) -> dict:
    """
    Scan tickers for PennyHunter signals with Phase 1 enhancements.

    Returns:
        Dict with regime info and signal list
    """
    logger.info(f"🔍 Scanning {len(tickers)} tickers for PennyHunter signals...")

    # Phase 1: Check market regime first
    regime_config = config.get('guards', {}).get('market_regime', {})
    if regime_config.get('enabled', False):
        regime_detector = MarketRegimeDetector(
            vix_low=regime_config.get('vix_thresholds', {}).get('low', 20),
            vix_medium=regime_config.get('vix_thresholds', {}).get('medium', 30),
            vix_high=regime_config.get('vix_thresholds', {}).get('high', 40),
            require_spy_above_ma=regime_config.get('require_spy_above_200ma', True),
            require_spy_green=regime_config.get('require_spy_green_day', False)
        )
        regime = regime_detector.get_regime()

        if not regime.allow_penny_trading:
            logger.warning(f"⚠️  Market regime {regime.regime.upper()} - penny trading blocked")
            logger.warning(f"    Reason: {regime.reason}")
            return {'regime': regime, 'signals': []}
        else:
            logger.info(f"✅ Market regime {regime.regime.upper()} - penny trading allowed")
    else:
        regime = None
        logger.info("ℹ️  Market regime checking disabled")

    # Initialize signal scorer
    min_score = config.get('signals', {}).get('runner_vwap', {}).get('min_signal_score', 7.0)
    scorer = SignalScorer(min_score_threshold=min_score)

    # Filter universe first
    universe = PennyUniverse(config['universe'])
    passed_tickers = universe.screen(tickers, lookback_days=10)

    logger.info(f"✅ {len(passed_tickers)} tickers passed universe filters")

    signals = []

    for ticker in passed_tickers:
        # Check for Runner VWAP setup
        runner = check_runner_setup(ticker, lookback_days=30)
        if runner['setup']:
            # Phase 1: Score the signal
            score = scorer.score_runner_vwap(
                gap_pct=runner['gap_pct'],
                volume_mult=runner['vol_spike'],
                float_millions=20,  # Assume mid-range for EOD scan
                vwap_reclaim=True,  # Approximated by strong close
                rsi_value=50,  # Neutral assumption for EOD
                market_regime_ok=regime.allow_penny_trading if regime else True,
                has_pm_volume=runner['vol_spike'] > 1.5,
                confirmation_bars=0  # EOD scan can't verify this
            )

            if score.passed_threshold:
                signals.append({
                    'ticker': ticker,
                    'signal': runner['signal'],
                    'price': runner['price'],
                    'date': runner['date'],
                    'score': score,
                    'details': runner
                })
                logger.info(f"🟢 {ticker}: {runner['reason']} | Score: {score.total_score:.1f}/10.0 ✅")
            else:
                logger.info(f"⚪ {ticker}: {runner['reason']} | Score: {score.total_score:.1f}/10.0 ❌ (below threshold)")

        # Check for FRD Bounce setup
        frd = check_frd_setup(ticker, lookback_days=30)
        if frd['setup']:
            # Phase 1: Score the signal
            score = scorer.score_frd_bounce(
                prior_range_mult=frd['prior_range_mult'],
                gap_pct=abs(frd['gap_pct']),
                rsi2_value=frd['rsi2'],
                at_vwap_band=True,  # Assume -2σ from setup
                volume_climax=True,  # Flush implied by setup
                float_millions=20,  # Assume mid-range for EOD scan
                has_support=False,  # Can't verify EOD
                market_regime_ok=regime.allow_penny_trading if regime else True,
                confirmation_bars=0  # EOD scan can't verify this
            )

            if score.passed_threshold:
                signals.append({
                    'ticker': ticker,
                    'signal': frd['signal'],
                    'price': frd['price'],
                    'date': frd['date'],
                    'score': score,
                    'details': frd
                })
                logger.info(f"🟡 {ticker}: {frd['reason']} | Score: {score.total_score:.1f}/10.0 ✅")
            else:
                logger.info(f"⚪ {ticker}: {frd['reason']} | Score: {score.total_score:.1f}/10.0 ❌ (below threshold)")

    return {'regime': regime, 'signals': signals}


def format_report(scan_result: dict) -> str:
    """Format signals as a report with Phase 1 enhancements"""
    regime = scan_result.get('regime')
    signals = scan_result.get('signals', [])

    report = []
    report.append("\n" + "="*70)
    report.append("PENNYHUNTER NIGHTLY SCAN - Phase 1 Enhanced")
    report.append(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    report.append("="*70)

    # Market regime section
    if regime:
        report.append("\n📊 MARKET REGIME:")
        report.append("-" * 70)
        status_emoji = "✅" if regime.allow_penny_trading else "❌"
        report.append(f"  Status: {regime.regime.upper()} {status_emoji}")
        report.append(f"  SPY: ${regime.spy_price:.2f} {'>' if regime.spy_above_ma else '<'} 200MA ${regime.spy_ma200:.2f}")
        report.append(f"  SPY Day: {regime.spy_day_change_pct:+.2f}%")
        report.append(f"  VIX: {regime.vix_level:.1f} ({regime.vix_regime})")
        report.append(f"  Trading Allowed: {'YES' if regime.allow_penny_trading else 'NO'}")
        if not regime.allow_penny_trading:
            report.append(f"  Reason: {regime.reason}")
            report.append("\n" + "="*70 + "\n")
            return "\n".join(report)

    if not signals:
        report.append("\n❌ No PennyHunter signals found (none passed scoring threshold).\n")
        report.append("="*70 + "\n")
        return "\n".join(report)

    report.append(f"\n🎯 Found {len(signals)} signals (scored ≥7.0/10.0):\n")

    # Group by signal type
    runners = [s for s in signals if s['signal'] == 'runner_vwap']
    frds = [s for s in signals if s['signal'] == 'frd_bounce']

    if runners:
        report.append("\n🚀 RUNNER VWAP (Gap & Go):")
        report.append("-" * 70)
        for sig in runners:
            details = sig['details']
            score = sig['score']
            confidence_emoji = "🔥" if score.confidence_pct >= 100 else "✅" if score.confidence_pct >= 80 else "⚠️"
            report.append(f"\n{sig['ticker']}  ${sig['price']:.2f}  |  Score: {score.total_score:.1f}/10.0 ({score.confidence_pct:.0f}%) {confidence_emoji}")
            report.append(f"  Gap: +{details['gap_pct']:.1f}%  |  Vol: {details['vol_spike']:.1f}x  |  Close: top {details['range_pos']*100:.0f}%")
            report.append(f"  Top Components: {', '.join([f'{k}={v:.1f}' for k, v in sorted(score.components.items(), key=lambda x: x[1], reverse=True)[:3]])}")
            report.append(f"  Date: {sig['date']}")

    if frds:
        report.append("\n\n📉 FRD BOUNCE (First Red Day):")
        report.append("-" * 70)
        for sig in frds:
            details = sig['details']
            score = sig['score']
            confidence_emoji = "🔥" if score.confidence_pct >= 100 else "✅" if score.confidence_pct >= 80 else "⚠️"
            report.append(f"\n{sig['ticker']}  ${sig['price']:.2f}  |  Score: {score.total_score:.1f}/10.0 ({score.confidence_pct:.0f}%) {confidence_emoji}")
            report.append(f"  Prior Range: {details['prior_range_mult']:.1f}×ATR  |  Gap: {details['gap_pct']:.1f}%  |  RSI(2): {details['rsi2']:.1f}")
            report.append(f"  Top Components: {', '.join([f'{k}={v:.1f}' for k, v in sorted(score.components.items(), key=lambda x: x[1], reverse=True)[:3]])}")
            report.append(f"  Date: {sig['date']}")

    report.append("\n" + "="*70)
    report.append("\n⚠️  IMPORTANT NOTES:")
    report.append("  • Phase 1 Enhanced: Market regime + signal scoring filters applied")
    report.append("  • This is EOD approximation - intraday confirmation required")
    report.append("  • Verify float, spread, halts, and news before entering")
    report.append("  • Max $5 risk per trade with $200 account")
    report.append("  • Only trade signals scored ≥7.0/10.0")
    report.append("  • Use limit orders only")
    report.append("="*70 + "\n")

    return "\n".join(report)


def main():
    parser = argparse.ArgumentParser(description='PennyHunter Nightly Scanner')
    parser.add_argument('--config', default='configs/pennyhunter.yaml', help='Path to config file')
    parser.add_argument('--tickers', help='Comma-separated tickers (overrides config)')
    parser.add_argument('--output', help='Save report to file')
    args = parser.parse_args()

    # Load config
    config_path = Path(args.config)
    if not config_path.exists():
        logger.error(f"Config file not found: {config_path}")
        sys.exit(1)

    with open(config_path) as f:
        config = yaml.safe_load(f)

    # Get tickers
    if args.tickers:
        tickers = [t.strip().upper() for t in args.tickers.split(',')]
    else:
        # Use sample penny stocks for testing
        # TODO: Integrate with screener API for production
        tickers = [
            'PLUG', 'SNDL', 'MARA', 'RIOT', 'GEVO', 'ATOS', 'NAKD',
            'ZOM', 'OCGN', 'TELL', 'SOS', 'CLSK', 'ANY', 'GNUS',
            'CTRM', 'SHIP', 'NCTY', 'EBON', 'BTBT', 'CAN'
        ]
        logger.info(f"Using sample tickers (override with --tickers)")

    # Run scan with Phase 1 enhancements
    scan_result = scan_pennies(tickers, config)

    # Generate report
    report = format_report(scan_result)
    print(report)

    # Save to file if requested
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(report)
        logger.info(f"💾 Report saved to {output_path}")

    # Return exit code
    signals = scan_result.get('signals', [])
    regime = scan_result.get('regime')
    regime_allows = regime.allow_penny_trading if regime else True
    sys.exit(0 if (signals and regime_allows) else 1)


if __name__ == '__main__':
    main()

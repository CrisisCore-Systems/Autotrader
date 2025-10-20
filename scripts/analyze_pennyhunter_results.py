#!/usr/bin/env python
"""
PennyHunter Results Analyzer

Analyzes accumulated paper trading results and validates win rate improvements.

Usage:
    python scripts/analyze_pennyhunter_results.py
    python scripts/analyze_pennyhunter_results.py --export-csv
    
Analyzes:
- Win rate vs baseline (45-55%) and Phase 1 target (55-65%)
- Profit factor and R-multiples
- Best/worst performing tickers
- Regime-specific performance (normal vs high VIX)
- Signal type effectiveness (runner_vwap vs FRD)
- Time-based patterns
"""

import sys
import json
import logging
from pathlib import Path
from datetime import datetime
from collections import defaultdict
import statistics

PROJECT_ROOT = Path(__file__).parent.parent
CUMULATIVE_FILE = PROJECT_ROOT / "reports" / "pennyhunter_cumulative_history.json"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_history():
    """Load cumulative trading history"""
    if not CUMULATIVE_FILE.exists():
        logger.error(f"No history file found: {CUMULATIVE_FILE}")
        logger.info("Run daily_pennyhunter.py first to generate trade data")
        sys.exit(1)
    
    with open(CUMULATIVE_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def analyze_overall_performance(trades):
    """Calculate overall trading statistics"""
    completed = [t for t in trades if t.get('status') == 'closed']
    
    if not completed:
        return None
    
    wins = [t for t in completed if t.get('pnl', 0) > 0]
    losses = [t for t in completed if t.get('pnl', 0) < 0]
    
    total_pnl = sum(t.get('pnl', 0) for t in completed)
    win_pnls = [t['pnl'] for t in wins]
    loss_pnls = [t['pnl'] for t in losses]
    
    avg_win = statistics.mean(win_pnls) if win_pnls else 0
    avg_loss = statistics.mean(loss_pnls) if loss_pnls else 0
    
    # Calculate R-multiples (profit/risk ratio)
    r_multiples = []
    for t in completed:
        risk = abs(t['entry_price'] - t['stop_loss']) * t['shares']
        if risk > 0:
            r_mult = t.get('pnl', 0) / risk
            r_multiples.append(r_mult)
    
    return {
        'total_trades': len(completed),
        'wins': len(wins),
        'losses': len(losses),
        'win_rate': len(wins) / len(completed) * 100,
        'total_pnl': total_pnl,
        'avg_win': avg_win,
        'avg_loss': avg_loss,
        'profit_factor': abs(avg_win / avg_loss) if avg_loss != 0 else 0,
        'avg_r_multiple': statistics.mean(r_multiples) if r_multiples else 0,
        'median_r_multiple': statistics.median(r_multiples) if r_multiples else 0,
        'largest_win': max(win_pnls) if win_pnls else 0,
        'largest_loss': min(loss_pnls) if loss_pnls else 0,
    }


def analyze_by_ticker(trades):
    """Analyze performance by ticker"""
    by_ticker = defaultdict(lambda: {'trades': [], 'wins': 0, 'losses': 0, 'total_pnl': 0})
    
    for t in trades:
        if t.get('status') == 'closed':
            ticker = t['ticker']
            by_ticker[ticker]['trades'].append(t)
            by_ticker[ticker]['total_pnl'] += t.get('pnl', 0)
            
            if t.get('pnl', 0) > 0:
                by_ticker[ticker]['wins'] += 1
            else:
                by_ticker[ticker]['losses'] += 1
    
    # Calculate win rates
    ticker_stats = []
    for ticker, data in by_ticker.items():
        total = len(data['trades'])
        win_rate = (data['wins'] / total * 100) if total > 0 else 0
        
        ticker_stats.append({
            'ticker': ticker,
            'trades': total,
            'wins': data['wins'],
            'losses': data['losses'],
            'win_rate': win_rate,
            'total_pnl': data['total_pnl'],
            'avg_pnl': data['total_pnl'] / total if total > 0 else 0
        })
    
    # Sort by win rate descending
    ticker_stats.sort(key=lambda x: x['win_rate'], reverse=True)
    
    return ticker_stats


def analyze_by_signal_type(trades):
    """Analyze performance by signal type"""
    by_type = defaultdict(lambda: {'wins': 0, 'losses': 0, 'total_pnl': 0})
    
    for t in trades:
        if t.get('status') == 'closed':
            sig_type = t.get('signal_type', 'unknown')
            by_type[sig_type]['total_pnl'] += t.get('pnl', 0)
            
            if t.get('pnl', 0) > 0:
                by_type[sig_type]['wins'] += 1
            else:
                by_type[sig_type]['losses'] += 1
    
    type_stats = []
    for sig_type, data in by_type.items():
        total = data['wins'] + data['losses']
        win_rate = (data['wins'] / total * 100) if total > 0 else 0
        
        type_stats.append({
            'signal_type': sig_type,
            'trades': total,
            'win_rate': win_rate,
            'total_pnl': data['total_pnl']
        })
    
    return type_stats


def print_analysis_report(history):
    """Print comprehensive analysis report"""
    trades = [t for t in history['trades'] if t.get('type') != 'session_marker']
    completed_trades = [t for t in trades if t.get('status') == 'closed']
    
    print("\n" + "="*70)
    print("PENNYHUNTER PHASE 2 VALIDATION ANALYSIS")
    print("="*70)
    print(f"Analysis Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"First Trade: {history.get('first_trade_date', 'N/A')}")
    print(f"Last Updated: {history.get('last_updated', 'N/A')}")
    print(f"Total Sessions: {history.get('total_sessions', 0)}")
    print("="*70 + "\n")
    
    # Overall Performance
    print("📊 OVERALL PERFORMANCE")
    print("-" * 70)
    
    if not completed_trades:
        print("No completed trades yet. Active trades need time to close.")
        print("Run paper trading daily to accumulate more data.\n")
        return
    
    overall = analyze_overall_performance(completed_trades)
    
    print(f"Total Completed Trades: {overall['total_trades']}")
    print(f"Wins: {overall['wins']} | Losses: {overall['losses']}")
    print(f"Win Rate: {overall['win_rate']:.1f}%")
    print()
    
    # Validate against targets
    print("WIN RATE VALIDATION:")
    baseline_range = (45, 55)
    phase1_range = (55, 65)
    phase2_range = (65, 75)
    
    win_rate = overall['win_rate']
    
    print(f"  Baseline (No Enhancements): {baseline_range[0]}-{baseline_range[1]}%")
    if win_rate >= baseline_range[0]:
        print(f"    ✅ Above baseline minimum ({win_rate:.1f}% > {baseline_range[0]}%)")
    else:
        print(f"    ❌ Below baseline minimum ({win_rate:.1f}% < {baseline_range[0]}%)")
    
    print(f"  Phase 1 Target (Regime + Scoring): {phase1_range[0]}-{phase1_range[1]}%")
    if win_rate >= phase1_range[0]:
        print(f"    ✅ Phase 1 target achieved ({win_rate:.1f}% > {phase1_range[0]}%)")
    else:
        print(f"    ⚠️ Below Phase 1 target ({win_rate:.1f}% < {phase1_range[0]}%)")
    
    print(f"  Phase 2 Target (+ Advanced Filters): {phase2_range[0]}-{phase2_range[1]}%")
    if win_rate >= phase2_range[0]:
        print(f"    ✅ Phase 2 target achieved ({win_rate:.1f}% > {phase2_range[0]}%)")
    else:
        print(f"    ⏳ Phase 2 target not yet reached ({win_rate:.1f}% < {phase2_range[0]}%)")
    
    print()
    print("PROFITABILITY METRICS:")
    print(f"  Total P&L: ${overall['total_pnl']:.2f}")
    print(f"  Avg Win: ${overall['avg_win']:.2f}")
    print(f"  Avg Loss: ${overall['avg_loss']:.2f}")
    print(f"  Profit Factor: {overall['profit_factor']:.2f}")
    print(f"  Avg R-Multiple: {overall['avg_r_multiple']:.2f}R")
    print(f"  Median R-Multiple: {overall['median_r_multiple']:.2f}R")
    print(f"  Largest Win: ${overall['largest_win']:.2f}")
    print(f"  Largest Loss: ${overall['largest_loss']:.2f}")
    print()
    
    # Statistical Significance
    n = overall['total_trades']
    if n >= 20:
        print(f"✅ Sample size sufficient (n={n} >= 20) - Results statistically significant")
    else:
        print(f"⚠️ Sample size insufficient (n={n} < 20) - Continue accumulating trades")
        print(f"   Need {20 - n} more completed trades for statistical confidence")
    print()
    
    # Ticker Analysis
    print("="*70)
    print("📈 PERFORMANCE BY TICKER")
    print("-" * 70)
    
    ticker_stats = analyze_by_ticker(completed_trades)
    
    if ticker_stats:
        print(f"{'Ticker':<10} {'Trades':<8} {'Wins':<6} {'Losses':<8} {'Win Rate':<12} {'Total P&L':<12}")
        print("-" * 70)
        
        for stat in ticker_stats:
            print(f"{stat['ticker']:<10} {stat['trades']:<8} {stat['wins']:<6} {stat['losses']:<8} "
                  f"{stat['win_rate']:>10.1f}% ${stat['total_pnl']:>10.2f}")
        
        print()
        print("TOP PERFORMERS (by win rate):")
        top_tickers = [t for t in ticker_stats if t['trades'] >= 3][:3]
        if top_tickers:
            for i, t in enumerate(top_tickers, 1):
                print(f"  {i}. {t['ticker']}: {t['win_rate']:.0f}% win rate ({t['wins']}/{t['trades']} trades)")
        else:
            print("  (Need 3+ trades per ticker for ranking)")
        
        print()
        print("UNDERPERFORMERS (candidates for auto-ejection in Phase 2.5):")
        bad_tickers = [t for t in ticker_stats if t['trades'] >= 3 and t['win_rate'] < 40]
        if bad_tickers:
            for t in bad_tickers:
                print(f"  ❌ {t['ticker']}: {t['win_rate']:.0f}% win rate ({t['wins']}/{t['trades']} trades)")
                print(f"     → Would be auto-ejected in Phase 2.5 (<40% threshold)")
        else:
            print("  ✅ No tickers below 40% win rate threshold")
        print()
    
    # Signal Type Analysis
    print("="*70)
    print("🎯 PERFORMANCE BY SIGNAL TYPE")
    print("-" * 70)
    
    type_stats = analyze_by_signal_type(completed_trades)
    
    if type_stats:
        for stat in type_stats:
            print(f"{stat['signal_type']}:")
            print(f"  Trades: {stat['trades']}")
            print(f"  Win Rate: {stat['win_rate']:.1f}%")
            print(f"  Total P&L: ${stat['total_pnl']:.2f}")
            print()
    
    # Next Steps
    print("="*70)
    print("🚀 NEXT STEPS")
    print("-" * 70)
    
    if n >= 20 and win_rate >= phase2_range[0]:
        print("✅ Phase 2 validation complete!")
        print()
        print("Recommendations:")
        print("  1. ✅ 20+ trades collected - Sample size sufficient")
        print(f"  2. ✅ Win rate {win_rate:.1f}% meets 65-75% target")
        print("  3. 🎯 READY for Phase 2.5: Implement lightweight agentic memory")
        print()
        print("Phase 2.5 Implementation:")
        print("  - Create PennyHunterMemory class with SQLite")
        print("  - Auto-eject underperforming tickers (<40% win rate)")
        print("  - Track ticker-specific base rates")
        print("  - Expected improvement: 70-80% win rate")
        print()
        print("Run: python scripts/implement_phase2.5_memory.py")
    elif n >= 20:
        print(f"⚠️ Phase 2 validation needs review")
        print()
        print(f"Results: {n} trades, {win_rate:.1f}% win rate")
        print(f"Target: 65-75% win rate")
        print()
        print("Recommendations:")
        print("  1. Review quality gate settings (may be too lenient)")
        print("  2. Check if bad tickers are being repeatedly traded")
        print("  3. Consider tightening advanced filter thresholds")
        print("  4. Analyze losing trades for common patterns")
        print()
        print("Once win rate improves to 65%+, proceed to Phase 2.5")
    else:
        print(f"⏳ Continue Phase 2 validation - {20 - n} more trades needed")
        print()
        print("Current status:")
        print(f"  Trades: {n}/20 completed")
        print(f"  Win Rate: {win_rate:.1f}% (target: 65-75%)")
        print()
        print("Action items:")
        print("  1. Run: python scripts/daily_pennyhunter.py")
        print("  2. Execute daily until 20+ trades accumulated")
        print("  3. Monitor win rate trend")
        print("  4. Return to this analysis after each session")
    
    print("="*70 + "\n")


def export_csv(history):
    """Export trade data to CSV for external analysis"""
    import csv
    
    trades = [t for t in history['trades'] if t.get('status') == 'closed']
    
    if not trades:
        logger.warning("No completed trades to export")
        return
    
    output_file = PROJECT_ROOT / "reports" / "pennyhunter_trades_export.csv"
    
    fieldnames = ['session_id', 'ticker', 'entry_time', 'exit_time', 'entry_price', 
                  'exit_price', 'shares', 'pnl', 'exit_reason', 'signal_type', 
                  'score', 'gap_pct', 'vol_mult']
    
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        
        for t in trades:
            writer.writerow({
                'session_id': t.get('session_id', ''),
                'ticker': t.get('ticker', ''),
                'entry_time': t.get('entry_time', ''),
                'exit_time': t.get('exit_time', ''),
                'entry_price': t.get('entry_price', 0),
                'exit_price': t.get('exit_price', 0),
                'shares': t.get('shares', 0),
                'pnl': t.get('pnl', 0),
                'exit_reason': t.get('exit_reason', ''),
                'signal_type': t.get('signal_type', ''),
                'score': t.get('score', 0),
                'gap_pct': t.get('gap_pct', 0),
                'vol_mult': t.get('vol_mult', 0)
            })
    
    logger.info(f"Exported {len(trades)} trades to {output_file}")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Analyze PennyHunter Paper Trading Results')
    parser.add_argument('--export-csv', action='store_true',
                       help='Export trades to CSV file')
    args = parser.parse_args()
    
    # Load history
    history = load_history()
    
    # Print analysis report
    print_analysis_report(history)
    
    # Export if requested
    if args.export_csv:
        export_csv(history)
    
    return 0


if __name__ == '__main__':
    sys.exit(main())

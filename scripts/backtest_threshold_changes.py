"""
Backtest Validation: Test impact of raising score threshold to 7.0

This script re-evaluates the 126 historical trades to see what win rate
would have been achieved with different threshold settings.
"""
import json
from pathlib import Path
from collections import defaultdict

PROJECT_ROOT = Path(__file__).parent.parent
CUMULATIVE_FILE = PROJECT_ROOT / "reports" / "pennyhunter_cumulative_history.json"
BLOCKLIST_FILE = PROJECT_ROOT / "configs" / "ticker_blocklist.txt"


def load_blocklist():
    """Load ticker blocklist."""
    if not BLOCKLIST_FILE.exists():
        return set()
    
    with open(BLOCKLIST_FILE, 'r') as f:
        blocklist = set()
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and not line.startswith('-'):
                blocklist.add(line.upper())
            elif line.startswith('-'):
                # Handle YAML list format
                ticker = line.lstrip('- ').split('#')[0].strip()
                if ticker:
                    blocklist.add(ticker.upper())
        return blocklist


def load_cumulative_history():
    """Load cumulative trade history."""
    if not CUMULATIVE_FILE.exists():
        print(f"❌ No cumulative history file found at {CUMULATIVE_FILE}")
        return None
    
    with open(CUMULATIVE_FILE, 'r') as f:
        return json.load(f)


def backtest_threshold(trades, threshold, blocklist=None):
    """
    Simulate trading with given threshold.
    
    Args:
        trades: All closed trades
        threshold: Minimum score to trade
        blocklist: Set of tickers to exclude
    
    Returns:
        dict with filtered results and stats
    """
    if blocklist is None:
        blocklist = set()
    
    # Filter trades
    filtered_trades = []
    rejected_low_score = 0
    rejected_blocklist = 0
    
    for trade in trades:
        # Check blocklist
        if trade['ticker'] in blocklist:
            rejected_blocklist += 1
            continue
        
        # Check score threshold
        score = trade.get('score', 0)
        if score < threshold:
            rejected_low_score += 1
            continue
        
        filtered_trades.append(trade)
    
    # Calculate stats
    if not filtered_trades:
        return {
            'threshold': threshold,
            'total_trades': 0,
            'wins': 0,
            'losses': 0,
            'win_rate': 0,
            'total_pnl': 0,
            'avg_win': 0,
            'avg_loss': 0,
            'profit_factor': 0,
            'rejected_low_score': rejected_low_score,
            'rejected_blocklist': rejected_blocklist
        }
    
    wins = [t for t in filtered_trades if t.get('pnl', 0) > 0]
    losses = [t for t in filtered_trades if t.get('pnl', 0) < 0]
    
    win_count = len(wins)
    loss_count = len(losses)
    win_rate = (win_count / len(filtered_trades)) * 100 if filtered_trades else 0
    
    total_pnl = sum(t.get('pnl', 0) for t in filtered_trades)
    avg_win = sum(t.get('pnl', 0) for t in wins) / win_count if wins else 0
    avg_loss = sum(t.get('pnl', 0) for t in losses) / loss_count if losses else 0
    
    total_wins = sum(t.get('pnl', 0) for t in wins)
    total_losses = abs(sum(t.get('pnl', 0) for t in losses))
    profit_factor = total_wins / total_losses if total_losses > 0 else 0
    
    return {
        'threshold': threshold,
        'total_trades': len(filtered_trades),
        'wins': win_count,
        'losses': loss_count,
        'win_rate': win_rate,
        'total_pnl': total_pnl,
        'avg_win': avg_win,
        'avg_loss': avg_loss,
        'profit_factor': profit_factor,
        'rejected_low_score': rejected_low_score,
        'rejected_blocklist': rejected_blocklist,
        'trades': filtered_trades
    }


def compare_thresholds(trades, thresholds, blocklist=None):
    """Compare multiple threshold scenarios."""
    results = []
    
    for threshold in thresholds:
        result = backtest_threshold(trades, threshold, blocklist)
        results.append(result)
    
    return results


def print_comparison_table(results):
    """Print comparison table."""
    print(f"\n{'='*90}")
    print("THRESHOLD BACKTEST COMPARISON")
    print(f"{'='*90}\n")
    
    header = f"{'Threshold':<12} {'Trades':<10} {'Wins':<8} {'Losses':<8} {'Win Rate':<12} {'Total P&L':<12} {'PF':<8}"
    print(header)
    print("-" * 90)
    
    for result in results:
        threshold = result['threshold']
        total = result['total_trades']
        wins = result['wins']
        losses = result['losses']
        win_rate = result['win_rate']
        pnl = result['total_pnl']
        pf = result['profit_factor']
        
        row = f"{threshold:<12.1f} {total:<10} {wins:<8} {losses:<8} {win_rate:<11.1f}% ${pnl:<10.2f} {pf:<8.2f}"
        
        # Highlight optimal zone (65-75% win rate)
        if 65 <= win_rate <= 75:
            row = f"✅ {row}"
        elif 55 <= win_rate < 65:
            row = f"⚠️  {row}"
        else:
            row = f"   {row}"
        
        print(row)
    
    print(f"\n{'='*90}\n")


def print_detailed_analysis(baseline, optimized):
    """Print detailed before/after analysis."""
    print("DETAILED IMPROVEMENT ANALYSIS")
    print("-" * 90)
    
    print(f"\n📊 BASELINE (Threshold {baseline['threshold']}):")
    print(f"   Total trades: {baseline['total_trades']}")
    print(f"   Win rate: {baseline['win_rate']:.1f}%")
    print(f"   Total P&L: ${baseline['total_pnl']:.2f}")
    print(f"   Avg win: ${baseline['avg_win']:.2f} | Avg loss: ${baseline['avg_loss']:.2f}")
    print(f"   Profit factor: {baseline['profit_factor']:.2f}")
    
    print(f"\n📊 OPTIMIZED (Threshold {optimized['threshold']}):")
    print(f"   Total trades: {optimized['total_trades']}")
    print(f"   Win rate: {optimized['win_rate']:.1f}%")
    print(f"   Total P&L: ${optimized['total_pnl']:.2f}")
    print(f"   Avg win: ${optimized['avg_win']:.2f} | Avg loss: ${optimized['avg_loss']:.2f}")
    print(f"   Profit factor: {optimized['profit_factor']:.2f}")
    
    print(f"\n📈 IMPROVEMENTS:")
    trades_change = optimized['total_trades'] - baseline['total_trades']
    wr_change = optimized['win_rate'] - baseline['win_rate']
    pnl_change = optimized['total_pnl'] - baseline['total_pnl']
    pf_change = optimized['profit_factor'] - baseline['profit_factor']
    
    print(f"   Trades: {baseline['total_trades']} → {optimized['total_trades']} ({trades_change:+d}, {trades_change/baseline['total_trades']*100:+.1f}%)")
    print(f"   Win rate: {baseline['win_rate']:.1f}% → {optimized['win_rate']:.1f}% ({wr_change:+.1f} pp)")
    print(f"   Total P&L: ${baseline['total_pnl']:.2f} → ${optimized['total_pnl']:.2f} (${pnl_change:+.2f})")
    print(f"   Profit factor: {baseline['profit_factor']:.2f} → {optimized['profit_factor']:.2f} ({pf_change:+.2f})")
    
    # Quality assessment
    print(f"\n🎯 QUALITY ASSESSMENT:")
    if optimized['win_rate'] >= 65:
        print(f"   ✅ Win rate {optimized['win_rate']:.1f}% meets Phase 2 target (65-75%)")
    else:
        print(f"   ❌ Win rate {optimized['win_rate']:.1f}% below Phase 2 target (65-75%)")
        shortfall = 65 - optimized['win_rate']
        print(f"      Need {shortfall:.1f} percentage points improvement")
    
    if optimized['total_trades'] >= 20:
        print(f"   ✅ Sample size {optimized['total_trades']} sufficient for validation")
    else:
        print(f"   ⚠️  Sample size {optimized['total_trades']} below minimum (20)")
    
    if optimized['profit_factor'] >= 2.0:
        print(f"   ✅ Profit factor {optimized['profit_factor']:.2f} exceeds 2.0 target")
    
    print(f"\n🗑️  REJECTED TRADES:")
    print(f"   Low score (<{optimized['threshold']}): {optimized['rejected_low_score']}")
    print(f"   Blocklist: {optimized['rejected_blocklist']}")
    print(f"   Total filtered: {optimized['rejected_low_score'] + optimized['rejected_blocklist']}")


def main():
    """Run backtest validation."""
    # Load data
    history = load_cumulative_history()
    if not history:
        return
    
    blocklist = load_blocklist()
    print(f"Loaded blocklist: {blocklist if blocklist else 'None'}")
    
    trades = [t for t in history['trades'] if t.get('status') == 'closed']
    print(f"Loaded {len(trades)} closed trades\n")
    
    # Test multiple thresholds
    thresholds = [5.5, 6.0, 6.5, 7.0, 7.5, 8.0]
    
    print("Testing thresholds WITHOUT blocklist:")
    results_no_blocklist = compare_thresholds(trades, thresholds, blocklist=set())
    print_comparison_table(results_no_blocklist)
    
    if blocklist:
        print(f"\nTesting thresholds WITH blocklist ({blocklist}):")
        results_with_blocklist = compare_thresholds(trades, thresholds, blocklist=blocklist)
        print_comparison_table(results_with_blocklist)
    
    # Detailed analysis: baseline vs recommended
    print("\n" + "="*90)
    baseline = backtest_threshold(trades, 5.5, blocklist=set())  # Original threshold
    optimized = backtest_threshold(trades, 7.0, blocklist=blocklist)  # Recommended threshold
    
    print_detailed_analysis(baseline, optimized)
    
    print(f"\n{'='*90}")
    print("RECOMMENDATION")
    print(f"{'='*90}\n")
    
    if optimized['win_rate'] >= 65:
        print(f"✅ APPROVED: Threshold {optimized['threshold']} + blocklist achieves {optimized['win_rate']:.1f}% win rate")
        print("   Deploy these settings for Phase 2 validation")
    else:
        print(f"⚠️  NEEDS MORE WORK: Threshold {optimized['threshold']} achieves {optimized['win_rate']:.1f}% win rate")
        print("   Additional optimizations needed (volume filters, scoring overhaul)")
    
    print(f"\n{'='*90}\n")


if __name__ == '__main__':
    main()

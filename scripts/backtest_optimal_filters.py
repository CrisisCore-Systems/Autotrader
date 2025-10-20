"""
Backtest optimal filters discovered from component analysis.

KEY FINDINGS:
- Gap size 10-15%: 70.2% win rate ✅
- Volume 5-10x: 65.6% win rate ✅  
- Volume 15x+: 66.7% win rate ✅
- Score is NOT predictive (all ranges ~54%)

Strategy: Filter by gap and volume, ignore score threshold.
"""
import json
from pathlib import Path

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


def backtest_optimal_filters(trades, gap_min, gap_max, vol_ranges, blocklist=None):
    """
    Test optimal filter combination.
    
    Args:
        trades: All closed trades
        gap_min: Minimum gap %
        gap_max: Maximum gap %
        vol_ranges: List of (min, max) volume spike ranges (use None for no max)
        blocklist: Set of tickers to exclude
    
    Returns:
        dict with results
    """
    if blocklist is None:
        blocklist = set()
    
    filtered_trades = []
    rejected_gap = 0
    rejected_volume = 0
    rejected_blocklist = 0
    
    for trade in trades:
        # Check blocklist
        if trade['ticker'] in blocklist:
            rejected_blocklist += 1
            continue
        
        # Check gap range
        gap = abs(trade.get('gap_pct', 0))
        if gap < gap_min or gap > gap_max:
            rejected_gap += 1
            continue
        
        # Check volume range
        vol = trade.get('vol_mult', 0)
        vol_ok = False
        for vol_min, vol_max in vol_ranges:
            if vol_max is None:
                if vol >= vol_min:
                    vol_ok = True
                    break
            else:
                if vol_min <= vol < vol_max:
                    vol_ok = True
                    break
        
        if not vol_ok:
            rejected_volume += 1
            continue
        
        filtered_trades.append(trade)
    
    # Calculate stats
    if not filtered_trades:
        return {
            'total_trades': 0,
            'wins': 0,
            'losses': 0,
            'win_rate': 0,
            'total_pnl': 0,
            'rejected_gap': rejected_gap,
            'rejected_volume': rejected_volume,
            'rejected_blocklist': rejected_blocklist
        }
    
    wins = [t for t in filtered_trades if t.get('pnl', 0) > 0]
    losses = [t for t in filtered_trades if t.get('pnl', 0) < 0]
    
    win_count = len(wins)
    loss_count = len(losses)
    win_rate = (win_count / len(filtered_trades)) * 100
    
    total_pnl = sum(t.get('pnl', 0) for t in filtered_trades)
    avg_win = sum(t.get('pnl', 0) for t in wins) / win_count if wins else 0
    avg_loss = sum(t.get('pnl', 0) for t in losses) / loss_count if losses else 0
    
    total_wins = sum(t.get('pnl', 0) for t in wins)
    total_losses = abs(sum(t.get('pnl', 0) for t in losses))
    profit_factor = total_wins / total_losses if total_losses > 0 else 0
    
    return {
        'total_trades': len(filtered_trades),
        'wins': win_count,
        'losses': loss_count,
        'win_rate': win_rate,
        'total_pnl': total_pnl,
        'avg_win': avg_win,
        'avg_loss': avg_loss,
        'profit_factor': profit_factor,
        'rejected_gap': rejected_gap,
        'rejected_volume': rejected_volume,
        'rejected_blocklist': rejected_blocklist,
        'trades': filtered_trades
    }


def main():
    """Run optimal filter backtest."""
    history = load_cumulative_history()
    if not history:
        return
    
    blocklist = load_blocklist()
    trades = [t for t in history['trades'] if t.get('status') == 'closed']
    
    print(f"\n{'='*90}")
    print("OPTIMAL FILTER BACKTEST")
    print(f"{'='*90}\n")
    
    print(f"Total historical trades: {len(trades)}")
    print(f"Blocklist: {blocklist if blocklist else 'None'}\n")
    
    # Test different filter combinations
    scenarios = [
        {
            'name': 'BASELINE (No filters)',
            'gap_min': 0,
            'gap_max': 100,
            'vol_ranges': [(0, None)],
        },
        {
            'name': 'GAP ONLY (10-15%)',
            'gap_min': 10,
            'gap_max': 15,
            'vol_ranges': [(0, None)],
        },
        {
            'name': 'VOLUME ONLY (5-10x OR 15x+)',
            'gap_min': 0,
            'gap_max': 100,
            'vol_ranges': [(5, 10), (15, None)],
        },
        {
            'name': 'OPTIMAL (Gap 10-15% + Vol 5-10x/15x+)',
            'gap_min': 10,
            'gap_max': 15,
            'vol_ranges': [(5, 10), (15, None)],
        },
        {
            'name': 'CONSERVATIVE (Gap 10-15% + Vol 5-10x only)',
            'gap_min': 10,
            'gap_max': 15,
            'vol_ranges': [(5, 10)],
        },
    ]
    
    results = []
    for scenario in scenarios:
        result = backtest_optimal_filters(
            trades,
            gap_min=scenario['gap_min'],
            gap_max=scenario['gap_max'],
            vol_ranges=scenario['vol_ranges'],
            blocklist=blocklist
        )
        result['name'] = scenario['name']
        results.append(result)
    
    # Print comparison table
    print(f"{'Scenario':<45} {'Trades':<10} {'Win Rate':<12} {'P&L':<12} {'PF':<8}")
    print("-" * 90)
    
    for result in results:
        name = result['name']
        total = result['total_trades']
        wr = result['win_rate']
        pnl = result['total_pnl']
        pf = result['profit_factor']
        
        row = f"{name:<45} {total:<10} {wr:<11.1f}% ${pnl:<10.2f} {pf:<8.2f}"
        
        # Highlight Phase 2 target zone
        if 65 <= wr <= 75 and total >= 20:
            row = f"✅ {row}"
        elif wr >= 60:
            row = f"⚠️  {row}"
        else:
            row = f"   {row}"
        
        print(row)
    
    # Detailed analysis of optimal scenario
    optimal = results[3]  # OPTIMAL scenario
    
    print(f"\n{'='*90}")
    print("OPTIMAL FILTER DETAILED ANALYSIS")
    print(f"{'='*90}\n")
    
    print(f"Filter Configuration:")
    print(f"   Gap range: 10-15%")
    print(f"   Volume: 5-10x OR 15x+")
    print(f"   Blocklist: {blocklist if blocklist else 'None'}\n")
    
    print(f"Results:")
    print(f"   Total trades: {optimal['total_trades']}")
    print(f"   Wins: {optimal['wins']} | Losses: {optimal['losses']}")
    print(f"   Win rate: {optimal['win_rate']:.1f}%")
    print(f"   Total P&L: ${optimal['total_pnl']:.2f}")
    print(f"   Avg win: ${optimal['avg_win']:.2f} | Avg loss: ${optimal['avg_loss']:.2f}")
    print(f"   Profit factor: {optimal['profit_factor']:.2f}\n")
    
    print(f"Rejected trades:")
    print(f"   Gap filter: {optimal['rejected_gap']}")
    print(f"   Volume filter: {optimal['rejected_volume']}")
    print(f"   Blocklist: {optimal['rejected_blocklist']}")
    total_rejected = optimal['rejected_gap'] + optimal['rejected_volume'] + optimal['rejected_blocklist']
    print(f"   Total rejected: {total_rejected}\n")
    
    # Phase 2 validation
    print(f"{'='*90}")
    print("PHASE 2 VALIDATION STATUS")
    print(f"{'='*90}\n")
    
    if optimal['win_rate'] >= 65:
        print(f"✅ Win rate {optimal['win_rate']:.1f}% MEETS Phase 2 target (65-75%)")
    else:
        print(f"❌ Win rate {optimal['win_rate']:.1f}% BELOW Phase 2 target (65-75%)")
        shortfall = 65 - optimal['win_rate']
        print(f"   Shortfall: {shortfall:.1f} percentage points")
    
    if optimal['total_trades'] >= 20:
        print(f"✅ Sample size {optimal['total_trades']} sufficient for validation")
    else:
        print(f"⚠️  Sample size {optimal['total_trades']} below minimum (20)")
    
    if optimal['total_pnl'] > 0:
        print(f"✅ Profitable: ${optimal['total_pnl']:.2f}")
    
    if optimal['profit_factor'] >= 2.0:
        print(f"✅ Profit factor {optimal['profit_factor']:.2f} exceeds 2.0 target")
    
    print(f"\n{'='*90}")
    print("RECOMMENDATION")
    print(f"{'='*90}\n")
    
    if optimal['win_rate'] >= 65 and optimal['total_trades'] >= 20:
        print("✅ APPROVED FOR DEPLOYMENT")
        print("\nUpdate run_pennyhunter_nightly.py with:")
        print("   - Gap filter: 10-15%")
        print("   - Volume filter: 5-10x OR 15x+")
        print("   - Remove score-based filtering (not predictive)")
        print(f"   - Expected win rate: {optimal['win_rate']:.1f}%")
    else:
        print("⚠️  NEEDS REFINEMENT")
        if optimal['total_trades'] < 20:
            print("   - Sample size too small, consider widening filters slightly")
        if optimal['win_rate'] < 65:
            print(f"   - Win rate {optimal['win_rate']:.1f}% below target")
    
    print(f"\n{'='*90}\n")


if __name__ == '__main__':
    main()

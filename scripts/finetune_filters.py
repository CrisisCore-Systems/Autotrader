"""
Fine-tune optimal filters to get 20+ trades while maintaining 65%+ win rate.
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
        return None
    
    with open(CUMULATIVE_FILE, 'r') as f:
        return json.load(f)


def test_filter(trades, gap_min, gap_max, vol_ranges, blocklist):
    """Test a specific filter combination."""
    filtered = []
    for trade in trades:
        if trade['ticker'] in blocklist:
            continue
        gap = abs(trade.get('gap_pct', 0))
        if gap < gap_min or gap > gap_max:
            continue
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
            continue
        filtered.append(trade)
    
    wins = len([t for t in filtered if t.get('pnl', 0) > 0])
    losses = len([t for t in filtered if t.get('pnl', 0) < 0])
    win_rate = (wins / len(filtered) * 100) if filtered else 0
    total_pnl = sum(t.get('pnl', 0) for t in filtered)
    
    return {
        'count': len(filtered),
        'wins': wins,
        'losses': losses,
        'win_rate': win_rate,
        'pnl': total_pnl
    }


def main():
    """Test variations to find best 20+ trade filter."""
    history = load_cumulative_history()
    if not history:
        return
    
    blocklist = load_blocklist()
    trades = [t for t in history['trades'] if t.get('status') == 'closed']
    
    print(f"\n{'='*100}")
    print("FINE-TUNING OPTIMAL FILTERS")
    print(f"{'='*100}\n")
    
    # Test gap range variations
    scenarios = [
        ('Gap 10-15%, Vol 5-10x/15x+', 10, 15, [(5, 10), (15, None)]),
        ('Gap 9-15%, Vol 5-10x/15x+', 9, 15, [(5, 10), (15, None)]),
        ('Gap 8-15%, Vol 5-10x/15x+', 8, 15, [(5, 10), (15, None)]),
        ('Gap 10-16%, Vol 5-10x/15x+', 10, 16, [(5, 10), (15, None)]),
        ('Gap 9-16%, Vol 5-10x/15x+', 9, 16, [(5, 10), (15, None)]),
        ('Gap 10-15%, Vol 4-10x/15x+', 10, 15, [(4, 10), (15, None)]),
        ('Gap 10-15%, Vol 5-12x/15x+', 10, 15, [(5, 12), (15, None)]),
    ]
    
    print(f"{'Configuration':<35} {'Trades':<10} {'Wins':<8} {'Losses':<8} {'Win Rate':<12} {'P&L':<12} {'Status'}")
    print("-" * 100)
    
    best = None
    
    for name, gap_min, gap_max, vol_ranges in scenarios:
        result = test_filter(trades, gap_min, gap_max, vol_ranges, blocklist)
        
        status = ""
        if result['count'] >= 20 and 65 <= result['win_rate'] <= 90:
            status = "✅ APPROVED"
            if best is None or result['win_rate'] > best['win_rate']:
                best = {'name': name, **result, 'gap_min': gap_min, 'gap_max': gap_max, 'vol_ranges': vol_ranges}
        elif result['win_rate'] >= 65:
            status = "⚠️  Need more trades"
        else:
            status = "❌ Win rate too low"
        
        print(f"{name:<35} {result['count']:<10} {result['wins']:<8} {result['losses']:<8} {result['win_rate']:<11.1f}% ${result['pnl']:<10.2f} {status}")
    
    if best:
        print(f"\n{'='*100}")
        print("RECOMMENDED CONFIGURATION")
        print(f"{'='*100}\n")
        print(f"Filter: {best['name']}")
        print(f"   Gap range: {best['gap_min']}-{best['gap_max']}%")
        print(f"   Volume: 5-10x OR 15x+")
        print(f"   Blocklist: {blocklist}")
        print(f"\nExpected Performance:")
        print(f"   Trades: {best['count']}")
        print(f"   Win rate: {best['win_rate']:.1f}%")
        print(f"   Total P&L: ${best['pnl']:.2f}")
        print(f"\n✅ APPROVED FOR DEPLOYMENT\n")
        print(f"{'='*100}\n")
    else:
        print(f"\n❌ No configuration meets all criteria (20+ trades, 65-90% win rate)\n")


if __name__ == '__main__':
    main()

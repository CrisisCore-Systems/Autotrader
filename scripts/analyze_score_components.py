"""
Analyze score components to understand scoring inversion.

Why are higher-scored trades losing more? Let's break down each component.
"""
import json
from pathlib import Path
from collections import defaultdict
import statistics

PROJECT_ROOT = Path(__file__).parent.parent
CUMULATIVE_FILE = PROJECT_ROOT / "reports" / "pennyhunter_cumulative_history.json"


def load_cumulative_history():
    """Load cumulative trade history."""
    if not CUMULATIVE_FILE.exists():
        print(f"❌ No cumulative history file found at {CUMULATIVE_FILE}")
        return None
    
    with open(CUMULATIVE_FILE, 'r') as f:
        return json.load(f)


def analyze_score_components(trades):
    """Analyze which scoring components predict wins vs losses."""
    
    wins = [t for t in trades if t.get('pnl', 0) > 0]
    losses = [t for t in trades if t.get('pnl', 0) < 0]
    
    print(f"\n{'='*70}")
    print("SCORE COMPONENT ANALYSIS")
    print(f"{'='*70}\n")
    
    # Analyze each component
    components = ['score', 'gap_pct', 'vol_mult']
    
    for comp in components:
        print(f"📊 {comp.upper()}:")
        print("-" * 70)
        
        # Get values for wins and losses
        win_values = [abs(t.get(comp, 0)) for t in wins if t.get(comp) is not None]
        loss_values = [abs(t.get(comp, 0)) for t in losses if t.get(comp) is not None]
        
        if not win_values or not loss_values:
            print(f"   Insufficient data\n")
            continue
        
        # Calculate stats
        win_avg = statistics.mean(win_values)
        loss_avg = statistics.mean(loss_values)
        win_median = statistics.median(win_values)
        loss_median = statistics.median(loss_values)
        
        print(f"   Winners: avg={win_avg:.2f}, median={win_median:.2f}")
        print(f"   Losers:  avg={loss_avg:.2f}, median={loss_median:.2f}")
        print(f"   Delta:   {win_avg - loss_avg:+.2f} (positive = predicts wins)")
        
        # Determine predictiveness
        if win_avg > loss_avg + 0.5:
            print(f"   ✅ PREDICTIVE: Higher {comp} correlates with WINS")
        elif loss_avg > win_avg + 0.5:
            print(f"   ❌ INVERTED: Higher {comp} correlates with LOSSES!")
        else:
            print(f"   ⚪ NEUTRAL: {comp} not predictive")
        
        print()
    
    # Cross-tabulation analysis
    print(f"{'='*70}")
    print("CROSS-TABULATION: Score vs Gap Size")
    print(f"{'='*70}\n")
    
    # Bin by score and gap
    score_bins = {
        '5.5-6.5': {'wins': [], 'losses': []},
        '6.5-7.5': {'wins': [], 'losses': []},
        '7.5+': {'wins': [], 'losses': []}
    }
    
    gap_bins = {
        '5-10%': {'wins': [], 'losses': []},
        '10-15%': {'wins': [], 'losses': []},
        '15-20%': {'wins': [], 'losses': []},
        '20%+': {'wins': [], 'losses': []}
    }
    
    for trade in trades:
        score = trade.get('score', 0)
        gap = abs(trade.get('gap_pct', 0))
        is_win = trade.get('pnl', 0) > 0
        
        # Bin by score
        if score < 6.5:
            bin_key = '5.5-6.5'
        elif score < 7.5:
            bin_key = '6.5-7.5'
        else:
            bin_key = '7.5+'
        
        if is_win:
            score_bins[bin_key]['wins'].append(trade)
        else:
            score_bins[bin_key]['losses'].append(trade)
        
        # Bin by gap
        if gap < 10:
            gap_key = '5-10%'
        elif gap < 15:
            gap_key = '10-15%'
        elif gap < 20:
            gap_key = '15-20%'
        else:
            gap_key = '20%+'
        
        if is_win:
            gap_bins[gap_key]['wins'].append(trade)
        else:
            gap_bins[gap_key]['losses'].append(trade)
    
    # Print score bins
    print("BY SCORE RANGE:")
    print(f"{'Range':<12} {'Wins':<8} {'Losses':<8} {'Win Rate':<12} {'Verdict'}")
    print("-" * 70)
    
    for range_name, data in score_bins.items():
        wins = len(data['wins'])
        losses = len(data['losses'])
        total = wins + losses
        if total > 0:
            wr = (wins / total) * 100
            if wr >= 60:
                verdict = "✅ GOOD"
            elif wr >= 50:
                verdict = "⚪ NEUTRAL"
            else:
                verdict = "❌ BAD"
            print(f"{range_name:<12} {wins:<8} {losses:<8} {wr:<11.1f}% {verdict}")
    
    print(f"\nBY GAP SIZE:")
    print(f"{'Range':<12} {'Wins':<8} {'Losses':<8} {'Win Rate':<12} {'Verdict'}")
    print("-" * 70)
    
    for range_name, data in gap_bins.items():
        wins = len(data['wins'])
        losses = len(data['losses'])
        total = wins + losses
        if total > 0:
            wr = (wins / total) * 100
            if wr >= 60:
                verdict = "✅ GOOD"
            elif wr >= 50:
                verdict = "⚪ NEUTRAL"
            else:
                verdict = "❌ BAD"
            print(f"{range_name:<12} {wins:<8} {losses:<8} {wr:<11.1f}% {verdict}")
    
    # Volume analysis
    print(f"\n{'='*70}")
    print("VOLUME SPIKE ANALYSIS")
    print(f"{'='*70}\n")
    
    vol_bins = {
        '0-5x': {'wins': [], 'losses': []},
        '5-10x': {'wins': [], 'losses': []},
        '10-15x': {'wins': [], 'losses': []},
        '15x+': {'wins': [], 'losses': []}
    }
    
    for trade in trades:
        vol = trade.get('vol_mult', 0)
        is_win = trade.get('pnl', 0) > 0
        
        if vol < 5:
            bin_key = '0-5x'
        elif vol < 10:
            bin_key = '5-10x'
        elif vol < 15:
            bin_key = '10-15x'
        else:
            bin_key = '15x+'
        
        if is_win:
            vol_bins[bin_key]['wins'].append(trade)
        else:
            vol_bins[bin_key]['losses'].append(trade)
    
    print(f"{'Vol Range':<12} {'Wins':<8} {'Losses':<8} {'Win Rate':<12} {'Verdict'}")
    print("-" * 70)
    
    for range_name, data in vol_bins.items():
        wins = len(data['wins'])
        losses = len(data['losses'])
        total = wins + losses
        if total > 0:
            wr = (wins / total) * 100
            if wr >= 60:
                verdict = "✅ GOOD"
            elif wr >= 50:
                verdict = "⚪ NEUTRAL"
            else:
                verdict = "❌ BAD"
            print(f"{range_name:<12} {wins:<8} {losses:<8} {wr:<11.1f}% {verdict}")
    
    print(f"\n{'='*70}")
    print("KEY INSIGHTS")
    print(f"{'='*70}\n")
    
    # Calculate correlations
    win_scores = [abs(t.get('score', 0)) for t in wins]
    loss_scores = [abs(t.get('score', 0)) for t in losses]
    score_delta = statistics.mean(win_scores) - statistics.mean(loss_scores)
    
    win_gaps = [abs(t.get('gap_pct', 0)) for t in wins]
    loss_gaps = [abs(t.get('gap_pct', 0)) for t in losses]
    gap_delta = statistics.mean(win_gaps) - statistics.mean(loss_gaps)
    
    win_vols = [t.get('vol_mult', 0) for t in wins if t.get('vol_mult', 0) > 0]
    loss_vols = [t.get('vol_mult', 0) for t in losses if t.get('vol_mult', 0) > 0]
    vol_delta = statistics.mean(win_vols) - statistics.mean(loss_vols) if win_vols and loss_vols else 0
    
    print("Component Correlations (positive = predicts wins):")
    print(f"   Score:  {score_delta:+.2f} {'❌ INVERTED!' if score_delta < 0 else '✅'}")
    print(f"   Gap:    {gap_delta:+.2f} {'❌ INVERTED!' if gap_delta < 0 else '✅'}")
    print(f"   Volume: {vol_delta:+.2f} {'❌ INVERTED!' if vol_delta < 0 else '✅'}")
    
    print("\nRecommended Actions:")
    
    # Score recommendations
    best_score_range = max(score_bins.items(), 
                          key=lambda x: len(x[1]['wins']) / (len(x[1]['wins']) + len(x[1]['losses'])) 
                          if (len(x[1]['wins']) + len(x[1]['losses'])) > 10 else 0)
    
    print(f"1. SCORE: Best range is {best_score_range[0]}")
    
    # Gap recommendations
    best_gap_range = max(gap_bins.items(),
                        key=lambda x: len(x[1]['wins']) / (len(x[1]['wins']) + len(x[1]['losses']))
                        if (len(x[1]['wins']) + len(x[1]['losses'])) > 10 else 0)
    
    print(f"2. GAP: Best range is {best_gap_range[0]}")
    
    # Volume recommendations  
    best_vol_range = max(vol_bins.items(),
                        key=lambda x: len(x[1]['wins']) / (len(x[1]['wins']) + len(x[1]['losses']))
                        if (len(x[1]['wins']) + len(x[1]['losses'])) > 5 else 0)
    
    print(f"3. VOLUME: Best range is {best_vol_range[0]}")
    
    print(f"\n{'='*70}\n")


def main():
    """Run component analysis."""
    history = load_cumulative_history()
    if not history:
        return
    
    trades = [t for t in history['trades'] if t.get('status') == 'closed']
    
    if not trades:
        print("No closed trades to analyze")
        return
    
    analyze_score_components(trades)


if __name__ == '__main__':
    main()

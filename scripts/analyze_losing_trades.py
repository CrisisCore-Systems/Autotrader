"""
Analyze losing trades to identify failure patterns.
"""
import json
from pathlib import Path
from collections import defaultdict
from datetime import datetime

PROJECT_ROOT = Path(__file__).parent.parent
CUMULATIVE_FILE = PROJECT_ROOT / "reports" / "pennyhunter_cumulative_history.json"

def load_cumulative_history():
    """Load cumulative trade history."""
    if not CUMULATIVE_FILE.exists():
        print(f"❌ No cumulative history file found at {CUMULATIVE_FILE}")
        return None
    
    with open(CUMULATIVE_FILE, 'r') as f:
        return json.load(f)

def analyze_losing_trades(trades):
    """Deep dive into losing trade characteristics."""
    
    losses = [t for t in trades if t.get('pnl', 0) < 0]
    wins = [t for t in trades if t.get('pnl', 0) > 0]
    
    print(f"\n{'='*70}")
    print(f"LOSING TRADE ANALYSIS - {len(losses)} LOSSES")
    print(f"{'='*70}\n")
    
    # 1. Loss by ticker
    print("📊 LOSSES BY TICKER:")
    print("-" * 70)
    ticker_losses = defaultdict(lambda: {'count': 0, 'total_loss': 0, 'avg_loss': 0})
    
    for trade in losses:
        ticker = trade['ticker']
        pnl = trade.get('pnl', 0)
        ticker_losses[ticker]['count'] += 1
        ticker_losses[ticker]['total_loss'] += pnl
    
    for ticker, data in ticker_losses.items():
        data['avg_loss'] = data['total_loss'] / data['count']
    
    # Sort by count descending
    sorted_tickers = sorted(ticker_losses.items(), key=lambda x: x[1]['count'], reverse=True)
    
    print(f"{'Ticker':<8} {'Losses':<10} {'Total $':<12} {'Avg Loss':<12}")
    print("-" * 70)
    for ticker, data in sorted_tickers:
        print(f"{ticker:<8} {data['count']:<10} ${data['total_loss']:>10.2f} ${data['avg_loss']:>10.2f}")
    
    # 2. Loss by exit reason
    print(f"\n📊 LOSSES BY EXIT REASON:")
    print("-" * 70)
    exit_reasons = defaultdict(int)
    for trade in losses:
        reason = trade.get('exit_reason', 'UNKNOWN')
        exit_reasons[reason] += 1
    
    for reason, count in sorted(exit_reasons.items(), key=lambda x: x[1], reverse=True):
        pct = (count / len(losses)) * 100
        print(f"{reason:<15} {count:>5} ({pct:>5.1f}%)")
    
    # 3. Loss by score range
    print(f"\n📊 LOSSES BY SCORE RANGE:")
    print("-" * 70)
    score_ranges = {
        '5.5-6.0': [],
        '6.0-6.5': [],
        '6.5-7.0': [],
        '7.0-7.5': [],
        '7.5+': []
    }
    
    for trade in losses:
        score = trade.get('score', 0)
        if score < 6.0:
            score_ranges['5.5-6.0'].append(trade)
        elif score < 6.5:
            score_ranges['6.0-6.5'].append(trade)
        elif score < 7.0:
            score_ranges['6.5-7.0'].append(trade)
        elif score < 7.5:
            score_ranges['7.0-7.5'].append(trade)
        else:
            score_ranges['7.5+'].append(trade)
    
    for range_name, range_trades in score_ranges.items():
        if range_trades:
            count = len(range_trades)
            pct = (count / len(losses)) * 100
            avg_loss = sum(t.get('pnl', 0) for t in range_trades) / count
            print(f"{range_name:<12} {count:>5} losses ({pct:>5.1f}%) | Avg: ${avg_loss:>6.2f}")
    
    # 4. Loss by gap size
    print(f"\n📊 LOSSES BY GAP SIZE:")
    print("-" * 70)
    gap_ranges = {
        '5-8%': [],
        '8-10%': [],
        '10-15%': [],
        '15-20%': [],
        '20%+': []
    }
    
    for trade in losses:
        gap_pct = abs(trade.get('gap_pct', 0))
        if gap_pct < 8:
            gap_ranges['5-8%'].append(trade)
        elif gap_pct < 10:
            gap_ranges['8-10%'].append(trade)
        elif gap_pct < 15:
            gap_ranges['10-15%'].append(trade)
        elif gap_pct < 20:
            gap_ranges['15-20%'].append(trade)
        else:
            gap_ranges['20%+'].append(trade)
    
    for range_name, range_trades in gap_ranges.items():
        if range_trades:
            count = len(range_trades)
            pct = (count / len(losses)) * 100
            avg_loss = sum(t.get('pnl', 0) for t in range_trades) / count
            print(f"{range_name:<12} {count:>5} losses ({pct:>5.1f}%) | Avg: ${avg_loss:>6.2f}")
    
    # 5. Loss by volume multiple
    print(f"\n📊 LOSSES BY VOLUME MULTIPLE:")
    print("-" * 70)
    vol_ranges = {
        '0-5x': [],
        '5-10x': [],
        '10-15x': [],
        '15-20x': [],
        '20x+': []
    }
    
    for trade in losses:
        vol_mult = trade.get('vol_mult', 0)
        if vol_mult < 5:
            vol_ranges['0-5x'].append(trade)
        elif vol_mult < 10:
            vol_ranges['5-10x'].append(trade)
        elif vol_mult < 15:
            vol_ranges['10-15x'].append(trade)
        elif vol_mult < 20:
            vol_ranges['15-20x'].append(trade)
        else:
            vol_ranges['20x+'].append(trade)
    
    for range_name, range_trades in vol_ranges.items():
        if range_trades:
            count = len(range_trades)
            pct = (count / len(losses)) * 100
            avg_loss = sum(t.get('pnl', 0) for t in range_trades) / count
            print(f"{range_name:<12} {count:>5} losses ({pct:>5.1f}%) | Avg: ${avg_loss:>6.2f}")
    
    # 6. Hold time analysis
    print(f"\n📊 LOSSES BY HOLD TIME:")
    print("-" * 70)
    hold_ranges = {
        '0-3 days': [],
        '4-7 days': [],
        '8-14 days': [],
        '15+ days': []
    }
    
    for trade in losses:
        hold_days = trade.get('hold_days', 0)
        if hold_days <= 3:
            hold_ranges['0-3 days'].append(trade)
        elif hold_days <= 7:
            hold_ranges['4-7 days'].append(trade)
        elif hold_days <= 14:
            hold_ranges['8-14 days'].append(trade)
        else:
            hold_ranges['15+ days'].append(trade)
    
    for range_name, range_trades in hold_ranges.items():
        if range_trades:
            count = len(range_trades)
            pct = (count / len(losses)) * 100
            avg_loss = sum(t.get('pnl', 0) for t in range_trades) / count
            print(f"{range_name:<12} {count:>5} losses ({pct:>5.1f}%) | Avg: ${avg_loss:>6.2f}")
    
    # 7. Comparative analysis - worst losers vs best winners
    print(f"\n📊 COMPARATIVE ANALYSIS:")
    print("-" * 70)
    
    # Sort losses by PnL
    worst_losses = sorted(losses, key=lambda x: x.get('pnl', 0))[:10]
    best_wins = sorted(wins, key=lambda x: x.get('pnl', 0), reverse=True)[:10]
    
    print("\nWORST 10 LOSSES:")
    print(f"{'Ticker':<8} {'Date':<12} {'Score':<7} {'Gap%':<8} {'Vol':<8} {'Hold':<6} {'Exit':<8} {'P&L':<10}")
    print("-" * 70)
    for trade in worst_losses:
        ticker = trade['ticker']
        date = trade['entry_time'][:10]
        score = trade.get('score', 0)
        gap_pct = trade.get('gap_pct', 0)
        vol_mult = trade.get('vol_mult', 0)
        hold_days = trade.get('hold_days', 0)
        exit_reason = trade.get('exit_reason', 'N/A')
        pnl = trade.get('pnl', 0)
        print(f"{ticker:<8} {date:<12} {score:<7.1f} {gap_pct:<8.1f} {vol_mult:<8.1f} {hold_days:<6} {exit_reason:<8} ${pnl:>8.2f}")
    
    print("\nBEST 10 WINS (for comparison):")
    print(f"{'Ticker':<8} {'Date':<12} {'Score':<7} {'Gap%':<8} {'Vol':<8} {'Hold':<6} {'Exit':<8} {'P&L':<10}")
    print("-" * 70)
    for trade in best_wins:
        ticker = trade['ticker']
        date = trade['entry_time'][:10]
        score = trade.get('score', 0)
        gap_pct = trade.get('gap_pct', 0)
        vol_mult = trade.get('vol_mult', 0)
        hold_days = trade.get('hold_days', 0)
        exit_reason = trade.get('exit_reason', 'N/A')
        pnl = trade.get('pnl', 0)
        print(f"{ticker:<8} {date:<12} {score:<7.1f} {gap_pct:<8.1f} {vol_mult:<8.1f} {hold_days:<6} {exit_reason:<8} ${pnl:>8.2f}")
    
    # 8. Key insights
    print(f"\n🔍 KEY INSIGHTS:")
    print("-" * 70)
    
    # Which tickers have worst win rates?
    ticker_stats = defaultdict(lambda: {'wins': 0, 'losses': 0})
    for trade in trades:
        ticker = trade['ticker']
        if trade.get('pnl', 0) > 0:
            ticker_stats[ticker]['wins'] += 1
        else:
            ticker_stats[ticker]['losses'] += 1
    
    problem_tickers = []
    for ticker, stats in ticker_stats.items():
        total = stats['wins'] + stats['losses']
        if total >= 5:  # Only consider tickers with 5+ trades
            win_rate = (stats['wins'] / total) * 100
            if win_rate < 40:
                problem_tickers.append((ticker, win_rate, total))
    
    if problem_tickers:
        print("\n⚠️ Problem tickers (win rate < 40%, min 5 trades):")
        for ticker, win_rate, total in sorted(problem_tickers, key=lambda x: x[1]):
            print(f"   {ticker}: {win_rate:.1f}% win rate ({ticker_stats[ticker]['wins']}W-{ticker_stats[ticker]['losses']}L)")
    
    # Score effectiveness
    avg_loss_score = sum(t.get('score', 0) for t in losses) / len(losses) if losses else 0
    avg_win_score = sum(t.get('score', 0) for t in wins) / len(wins) if wins else 0
    print(f"\nAverage score of losses: {avg_loss_score:.2f}")
    print(f"Average score of wins: {avg_win_score:.2f}")
    print(f"Score differential: {avg_win_score - avg_loss_score:.2f} (higher = scoring is working)")
    
    # Exit reason patterns
    stop_losses = sum(1 for t in losses if t.get('exit_reason') == 'STOP')
    time_exits = sum(1 for t in losses if t.get('exit_reason') == 'TIME')
    print(f"\nStop loss hits: {stop_losses}/{len(losses)} ({(stop_losses/len(losses)*100):.1f}%)")
    print(f"Time-based exits: {time_exits}/{len(losses)} ({(time_exits/len(losses)*100):.1f}%)")
    
    return {
        'total_losses': len(losses),
        'ticker_losses': dict(ticker_losses),
        'exit_reasons': dict(exit_reasons),
        'problem_tickers': problem_tickers,
        'avg_loss_score': avg_loss_score,
        'avg_win_score': avg_win_score
    }

def main():
    """Main analysis."""
    history = load_cumulative_history()
    if not history:
        return
    
    trades = [t for t in history['trades'] if t.get('status') == 'closed']
    
    if not trades:
        print("No closed trades to analyze")
        return
    
    results = analyze_losing_trades(trades)
    
    print(f"\n{'='*70}")
    print("RECOMMENDATIONS")
    print(f"{'='*70}\n")
    
    if results['problem_tickers']:
        print("1. TICKER AUTO-EJECTION:")
        print("   Consider removing these underperformers:")
        for ticker, win_rate, total in results['problem_tickers']:
            print(f"      - {ticker} ({win_rate:.1f}% win rate)")
    
    score_diff = results['avg_win_score'] - results['avg_loss_score']
    if score_diff < 0.5:
        print("\n2. SCORING SYSTEM NEEDS WORK:")
        print(f"   Score differential is only {score_diff:.2f}")
        print("   Winners and losers have similar scores - scoring isn't predictive")
        print("   → Recommendation: Increase minimum score threshold from 5.5 to 6.5")
    else:
        print(f"\n2. SCORING SYSTEM IS WORKING:")
        print(f"   Score differential: {score_diff:.2f}")
        print("   Winners score higher than losers on average")
    
    print(f"\n{'='*70}\n")

if __name__ == '__main__':
    main()

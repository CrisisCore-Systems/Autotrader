"""
Daily Report Generator

Creates a concise daily summary of trading activity.
Used by EOD cleanup task and can be run manually.
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path


def generate_daily_report(date=None):
    """Generate daily trading report."""
    if date is None:
        date = datetime.now().strftime('%Y-%m-%d')
    
    print(f"\n{'='*70}")
    print(f"PennyHunter Daily Report - {date}")
    print(f"{'='*70}\n")
    
    # Connect to databases
    db_path = Path(__file__).parent.parent / "bouncehunter_memory.db"
    mem_db_path = Path(__file__).parent.parent / "reports" / "pennyhunter_memory.db"
    
    if not db_path.exists():
        print("❌ Database not found")
        return
    
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    # Get fills (positions opened) today
    opened_today = cur.execute('''
        SELECT 
            ticker,
            entry_date,
            entry_price,
            shares,
            size_pct,
            regime
        FROM fills
        WHERE entry_date LIKE ?
        ORDER BY entry_date
    ''', (f'{date}%',)).fetchall()
    
    # Get outcomes (positions closed) today
    closed_today = cur.execute('''
        SELECT 
            o.ticker,
            f.entry_date,
            o.exit_date,
            f.entry_price,
            o.exit_price,
            f.shares,
            (o.exit_price - f.entry_price) * f.shares as pnl,
            o.exit_reason,
            o.return_pct
        FROM outcomes o
        JOIN fills f ON o.fill_id = f.fill_id
        WHERE o.exit_date LIKE ?
        ORDER BY o.exit_date
    ''', (f'{date}%',)).fetchall()
    
    # Statistics for closed positions
    if closed_today:
        total_pnl = sum(t[6] for t in closed_today)
        winners = [t for t in closed_today if t[6] > 0]
        losers = [t for t in closed_today if t[6] <= 0]
        win_rate = len(winners) / len(closed_today) * 100
        
        print(f"📊 TRADING SUMMARY")
        print(f"{'─'*70}")
        print(f"Positions Opened: {len(opened_today)}")
        print(f"Positions Closed: {len(closed_today)}")
        print(f"Winners: {len(winners)} ({len(winners)/len(closed_today)*100:.1f}%)")
        print(f"Losers: {len(losers)} ({len(losers)/len(closed_today)*100:.1f}%)")
        print(f"Win Rate: {win_rate:.1f}%")
        print(f"Total P&L: ${total_pnl:+,.2f}")
        
        if winners:
            avg_win = sum(w[6] for w in winners) / len(winners)
            print(f"Avg Winner: ${avg_win:.2f}")
        
        if losers:
            avg_loss = sum(l[6] for l in losers) / len(losers)
            print(f"Avg Loser: ${avg_loss:.2f}")
        
        print()
    else:
        print(f"📊 TRADING SUMMARY")
        print(f"{'─'*70}")
        print(f"Positions Opened: {len(opened_today)}")
        print(f"Positions Closed: 0")
        print(f"No closed positions today")
        print()
    
    # Closed positions detail
    if closed_today:
        print(f"💰 CLOSED POSITIONS")
        print(f"{'─'*70}")
        print(f"{'Symbol':<8} {'Entry':>8} {'Exit':>8} {'Shares':>6} {'P&L':>10} {'Reason':<15}")
        print(f"{'─'*70}")
        
        for trade in closed_today:
            symbol = trade[0]
            entry = trade[3]
            exit_price = trade[4]
            shares = trade[5]
            pnl = trade[6]
            reason = trade[7] or 'N/A'
            
            pnl_str = f"${pnl:+.2f}"
            print(f"{symbol:<8} ${entry:>7.2f} ${exit_price:>7.2f} {shares:>6} {pnl_str:>10} {reason:<15}")
        
        print()
    
    # Open positions (fills without outcomes)
    open_positions = cur.execute('''
        SELECT f.ticker, f.shares, f.entry_price, f.entry_date, f.regime
        FROM fills f
        LEFT JOIN outcomes o ON f.fill_id = o.fill_id
        WHERE o.outcome_id IS NULL
    ''').fetchall()
    
    if open_positions:
        print(f"📈 OPEN POSITIONS")
        print(f"{'─'*70}")
        print(f"{'Symbol':<8} {'Shares':>6} {'Entry':>10} {'Regime':<10} {'Date':<12}")
        print(f"{'─'*70}")
        
        for pos in open_positions:
            symbol, shares, entry, date, regime = pos
            print(f"{symbol:<8} {shares:>6} ${entry:>9.2f} {regime:<10} {date:<12}")
        
        print()
    else:
        print(f"📈 OPEN POSITIONS: None\n")
    
    # Memory system stats (ticker_stats table)
    try:
        total_tickers = cur.execute('SELECT COUNT(*) FROM ticker_stats').fetchone()[0]
        active_tickers = cur.execute('SELECT COUNT(*) FROM ticker_stats WHERE ejected = 0').fetchone()[0]
        ejected_tickers = cur.execute('SELECT COUNT(*) FROM ticker_stats WHERE ejected = 1').fetchone()[0]
        
        print(f"💾 MEMORY SYSTEM")
        print(f"{'─'*70}")
        print(f"Total Tickers: {total_tickers}")
        print(f"Active: {active_tickers}")
        print(f"Ejected: {ejected_tickers}")
        print()
    except sqlite3.OperationalError:
        # Table might not exist yet
        pass
    
    # Phase 2 progress (from outcomes table)
    try:
        total_outcomes = cur.execute('SELECT COUNT(*) FROM outcomes').fetchone()[0]
        winners = cur.execute('SELECT COUNT(*) FROM outcomes WHERE return_pct > 0').fetchone()[0]
        win_rate = (winners / total_outcomes * 100) if total_outcomes > 0 else 0
        
        print(f"🎯 PHASE 2 VALIDATION")
        print(f"{'─'*70}")
        print(f"Completed Trades: {total_outcomes}/20")
        print(f"Win Rate: {win_rate:.1f}% (Target: 70%)")
        
        if total_outcomes >= 20:
            if win_rate >= 70:
                print(f"Status: ✅ VALIDATED - Ready for Phase 3!")
            else:
                print(f"Status: ⚠️  NEEDS IMPROVEMENT")
        else:
            remaining = 20 - total_outcomes
            print(f"Status: 🔄 In Progress ({remaining} trades remaining)")
        
        print()
    except sqlite3.OperationalError:
        # Table might not exist yet
        print(f"🎯 PHASE 2 VALIDATION")
        print(f"{'─'*70}")
        print(f"Status: Not started yet\n")
    
    conn.close()
    
    print(f"{'='*70}")
    print(f"Report generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*70}\n")


if __name__ == '__main__':
    import sys
    
    # Allow specifying date: python generate_daily_report.py 2025-10-21
    date = sys.argv[1] if len(sys.argv) > 1 else None
    generate_daily_report(date)

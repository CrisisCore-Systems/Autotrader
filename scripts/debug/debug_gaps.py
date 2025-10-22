"""Debug script to see actual gap percentages in our candidate tickers"""
import yfinance as yf
import pandas as pd

tickers = ['CLOV', 'TXMD', 'EVGO']

for ticker in tickers:
    print(f"\n{'='*60}")
    print(f"{ticker} - Gap Analysis (Last 90 days)")
    print(f"{'='*60}")
    
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period='90d')
        
        if len(hist) < 2:
            print(f"  ❌ Insufficient data")
            continue
        
        gaps = []
        for i in range(1, len(hist)):
            current = hist.iloc[i]
            prev = hist.iloc[i-1]
            gap_pct = (current['Open'] - prev['Close']) / prev['Close'] * 100
            
            if abs(gap_pct) > 3:  # Show gaps > 3%
                date = current.name.strftime('%Y-%m-%d')
                gaps.append((date, gap_pct, current['Volume']))
        
        if gaps:
            print(f"  Found {len(gaps)} gaps > 3%:")
            for date, gap, vol in sorted(gaps, key=lambda x: abs(x[1]), reverse=True)[:10]:
                print(f"    {date}: {gap:+6.2f}% | Vol: {vol:,.0f}")
        else:
            print(f"  ❌ No gaps > 3% found")
            
        # Show max gap
        max_gap = 0
        max_date = None
        for i in range(1, len(hist)):
            current = hist.iloc[i]
            prev = hist.iloc[i-1]
            gap_pct = (current['Open'] - prev['Close']) / prev['Close'] * 100
            if abs(gap_pct) > abs(max_gap):
                max_gap = gap_pct
                max_date = current.name.strftime('%Y-%m-%d')
        
        print(f"  Max gap: {max_gap:+.2f}% on {max_date}")
        
    except Exception as e:
        print(f"  ❌ Error: {e}")

print(f"\n{'='*60}")

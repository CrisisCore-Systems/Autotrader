"""Test BounceHunter mean-reversion scanner via API."""

import json
from datetime import datetime, timedelta

# Test with some tech stocks that often show mean-reversion
TEST_TICKERS = [
    "AAPL",  # Apple
    "MSFT",  # Microsoft
    "GOOGL", # Google
    "AMZN",  # Amazon
    "META",  # Meta
    "NVDA",  # Nvidia
    "TSLA",  # Tesla
    "AMD",   # AMD
    "INTC",  # Intel
    "NFLX",  # Netflix
]

print("=" * 80)
print("BounceHunter Mean-Reversion Scanner Test")
print("=" * 80)
print()
print(f"Testing with {len(TEST_TICKERS)} tickers: {', '.join(TEST_TICKERS)}")
print()
print("🚀 NEW: Model caching enabled for faster scans!")
print("   - First scan: Trains model (~30-60s)")
print("   - Subsequent scans: Uses cache (~5-10s)")
print("   - Auto-refresh after 24 hours")
print()

# Example PowerShell command to scan
print("PowerShell Command to Run Scan:")
print("-" * 80)
print("""
$json = @'
{
  "tickers": ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA", "AMD", "INTC", "NFLX"]
}
'@

Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/bouncehunter/scan' -Method POST -Body $json -ContentType 'application/json' | ConvertTo-Json -Depth 5
""")

print()
print("Expected Response Format:")
print("-" * 80)
print("""
{
  "scan_timestamp": "2025-10-28T23:30:00",
  "total_tickers_scanned": 10,
  "signals_found": 3,
  "signals": [
    {
      "ticker": "AAPL",
      "signal_date": "2025-10-28",
      "probability": 0.72,
      "z_score": -2.3,
      "rsi2": 15.4,
      "bb_deviation": -2.1,
      "distance_200ma": -0.05,
      "trend_63d": 0.15,
      "gap_down": true,
      "vix_regime": "high",
      "entry_price": 185.50,
      "target_price": 190.25,
      "stop_price": 182.00
    },
    ...
  ],
  "statistics": {
    "avg_probability": 0.65,
    "max_probability": 0.72,
    "min_probability": 0.58,
    "avg_z_score": -2.1,
    "gap_down_count": 2,
    "training_samples": 1250
  }
}
""")

print()
print("Signal Interpretation:")
print("-" * 80)
print("""
Key Metrics:
- probability: Model confidence (0-1) that bounce will occur
- z_score: Negative = oversold condition (more negative = more oversold)
- rsi2: 2-day RSI (< 20 = oversold)
- bb_deviation: How many std devs below Bollinger Band center
- distance_200ma: Distance from 200-day MA (negative = below)
- trend_63d: 63-day trend strength
- gap_down: Whether stock gapped down at open
- vix_regime: Market volatility (low/medium/high)

Trading Signals:
- entry_price: Suggested entry point
- target_price: Profit target (typically +2-5%)
- stop_price: Stop loss level (typically -3-5%)

Best Signals:
- High probability (> 0.65)
- Strong oversold (z_score < -2.0, rsi2 < 20)
- Gap down with positive trend_63d
- Low/medium VIX regime
""")

print()
print("Backtest Example:")
print("-" * 80)
print("""
$json = @'
{
  "tickers": ["AAPL", "MSFT", "GOOGL"],
  "start_date": "2024-01-01",
  "end_date": "2025-10-28",
  "initial_capital": 100000.0,
  "position_size": 0.10
}
'@

Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/bouncehunter/backtest' -Method POST -Body $json -ContentType 'application/json' | ConvertTo-Json -Depth 5
""")

print()
print("=" * 80)
print("Cache Management:")
print("=" * 80)
print("""
# Get cache information
Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/bouncehunter/cache/info' -Method GET | ConvertTo-Json -Depth 5

# List all cached models
Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/bouncehunter/cache/list' -Method GET | ConvertTo-Json -Depth 5

# Clear all cached models
Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/bouncehunter/cache/clear' -Method DELETE | ConvertTo-Json -Depth 5

# Clear models older than 7 days
Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/bouncehunter/cache/clear?older_than_days=7' -Method DELETE | ConvertTo-Json -Depth 5

# Force refresh (ignore cache)
$json = @'
{
  "tickers": ["AAPL", "MSFT"],
  "force_refresh": true
}
'@
Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/bouncehunter/scan' -Method POST -Body $json -ContentType 'application/json' | ConvertTo-Json -Depth 5

# Incremental training (add new tickers)
$json = @'
{
  "new_tickers": ["INTC", "CSCO", "ORCL"]
}
'@
Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/bouncehunter/train/incremental' -Method POST -Body $json -ContentType 'application/json' | ConvertTo-Json -Depth 5
""")

print()
print("=" * 80)
print("Notes:")
print("=" * 80)
print("""
1. BounceHunter requires yfinance for stock data (free, no API key)
2. First scan will take longer as it downloads historical data
3. Subsequent scans are faster due to caching
4. Works best with liquid stocks (> 500k avg volume)
5. Mean-reversion works best in range-bound markets
6. Combine with your own risk management rules
7. Paper trade first before using real capital!

🎯 Model Caching Benefits:
- First scan: ~30-60 seconds (downloads & trains)
- Cached scans: ~5-10 seconds (loads from disk)
- Models auto-refresh after 24 hours (configurable)
- Incremental updates for adding new tickers
- Persistent across API restarts
""")

print()
print("🚀 Ready to scan! Start the API and run the PowerShell commands above.")
print("=" * 80)

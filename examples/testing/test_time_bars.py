"""
Test TimeBarConstructor on real Dukascopy EUR/USD data.

This script validates:
1. Time bar construction for multiple intervals
2. OHLCV aggregation correctness
3. VWAP calculation
4. Bar statistics
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

import pandas as pd
from autotrader.data_prep.bars import TimeBarConstructor


def main():
    print("=" * 80)
    print("Testing TimeBarConstructor on Dukascopy EUR/USD Data")
    print("=" * 80)
    print()

    # Load cleaned data
    data_path = project_root / "data" / "cleaned" / "EURUSD_20241018_10_cleaned.parquet"
    
    if not data_path.exists():
        print(f"❌ Cleaned data not found: {data_path}")
        print("   Run test_cleaning_pipeline.py first to generate cleaned data.")
        return 1
    
    print(f"📂 Loading cleaned data from: {data_path}")
    df = pd.read_parquet(data_path)
    print(f"✅ Loaded {len(df)} ticks")
    print(f"   Timespan: {df['timestamp_utc'].min()} to {df['timestamp_utc'].max()}")
    print()

    # Test multiple intervals
    intervals = ["1min", "5min", "15min"]
    
    for interval in intervals:
        print(f"🔧 Constructing {interval} bars")
        print("-" * 80)
        
        constructor = TimeBarConstructor(interval=interval)
        bars = constructor.construct(
            df,
            timestamp_col="timestamp_utc",
            price_col="bid",  # Use bid price for Forex
            quantity_col="bid_vol"
        )
        
        print(f"   ✅ Created {len(bars)} bars")
        
        # Show first 3 bars
        print(f"\n   First 3 bars:")
        print(bars.head(3)[["timestamp", "open", "high", "low", "close", "volume", "vwap", "trades"]].to_string(index=False))
        
        # Show statistics
        stats = constructor.get_bar_statistics(bars)
        print(f"\n   Statistics:")
        print(f"      Total Bars: {stats['total_bars']}")
        print(f"      Timespan: {stats['timespan']['duration_seconds'] / 60:.1f} minutes")
        print(f"      Volume: {stats['volume']['total']:.0f} (mean: {stats['volume']['mean']:.0f})")
        print(f"      Trades: {stats['trades']['total']} (mean: {stats['trades']['mean']:.1f} per bar)")
        print(f"      Price Range: {stats['price']['low']:.5f} - {stats['price']['high']:.5f} ({stats['price']['range'] * 10000:.1f} pips)")
        print()

    # Test construct_multiple_intervals
    print("🔧 Testing construct_multiple_intervals()")
    print("-" * 80)
    
    all_intervals = ["1min", "5min", "15min", "1h"]
    constructor = TimeBarConstructor(interval="1min")  # Interval doesn't matter for this method
    bars_dict = constructor.construct_multiple_intervals(
        df,
        intervals=all_intervals,
        timestamp_col="timestamp_utc",
        price_col="bid",
        quantity_col="bid_vol"
    )
    
    for interval, bars in bars_dict.items():
        print(f"   {interval}: {len(bars)} bars")
    print()

    # Validate OHLCV logic
    print("🔧 Validating OHLCV logic")
    print("-" * 80)
    
    bars_1min = bars_dict["1min"]
    if not bars_1min.empty:
        first_bar = bars_1min.iloc[0]
        print(f"   First 1-minute bar:")
        print(f"      Timestamp: {first_bar['timestamp']}")
        print(f"      Open: {first_bar['open']:.5f}")
        print(f"      High: {first_bar['high']:.5f}")
        print(f"      Low: {first_bar['low']:.5f}")
        print(f"      Close: {first_bar['close']:.5f}")
        print(f"      Volume: {first_bar['volume']:.0f}")
        print(f"      VWAP: {first_bar['vwap']:.5f}")
        print(f"      Trades: {int(first_bar['trades'])}")
        
        # Validate H >= O, C and L <= O, C
        assert first_bar['high'] >= first_bar['open'], "High must be >= Open"
        assert first_bar['high'] >= first_bar['close'], "High must be >= Close"
        assert first_bar['low'] <= first_bar['open'], "Low must be <= Open"
        assert first_bar['low'] <= first_bar['close'], "Low must be <= Close"
        assert first_bar['high'] >= first_bar['low'], "High must be >= Low"
        
        print(f"      ✅ OHLC validation passed")
        
        # Validate VWAP is between low and high
        assert first_bar['low'] <= first_bar['vwap'] <= first_bar['high'], "VWAP must be between Low and High"
        print(f"      ✅ VWAP validation passed")
    print()

    # Save bars
    output_dir = project_root / "data" / "bars"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    for interval, bars in bars_dict.items():
        output_path = output_dir / f"EURUSD_20241018_{interval}_bars.parquet"
        bars.to_parquet(output_path)
        file_size_kb = output_path.stat().st_size / 1024
        print(f"💾 Saved {interval} bars: {output_path.name} ({file_size_kb:.2f} KB, {len(bars)} bars)")
    print()

    # Summary
    print("=" * 80)
    print("✅ TIME BAR CONSTRUCTOR TEST COMPLETE")
    print("=" * 80)
    print(f"   Tested intervals: {', '.join(all_intervals)}")
    print(f"   Total bars created: {sum(len(bars) for bars in bars_dict.values())}")
    print(f"   All validation checks passed!")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())

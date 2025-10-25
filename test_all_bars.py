"""
Comprehensive test script for all 6 bar types in Phase 3.

Tests each bar construction algorithm on real Dukascopy EUR/USD data:
1. Time bars (5min interval)
2. Tick bars (500 ticks per bar)
3. Volume bars (100,000 volume threshold)
4. Dollar bars (1,000,000 dollar threshold)
5. Imbalance bars (5,000 imbalance threshold)
6. Run bars (5 runs per bar)

Validates:
- OHLCV logic (High >= Open/Close, Low <= Open/Close)
- VWAP between Low and High
- Bar counts and volume distribution
- Output saved to Parquet

Usage:
    python test_all_bars.py
"""

import pandas as pd
from pathlib import Path
from autotrader.data_prep.bars import BarFactory


def validate_ohlcv(bars: pd.DataFrame, bar_type: str) -> bool:
    """Validate OHLCV logic for all bars."""
    print(f"\n  Validating {bar_type} bars OHLCV logic...")
    
    if bars.empty:
        print(f"    ❌ No bars created")
        return False
    
    # Check High >= Open, Close
    high_check = (bars["high"] >= bars["open"]) & (bars["high"] >= bars["close"])
    if not high_check.all():
        print(f"    ❌ High validation failed for {(~high_check).sum()} bars")
        return False
    
    # Check Low <= Open, Close
    low_check = (bars["low"] <= bars["open"]) & (bars["low"] <= bars["close"])
    if not low_check.all():
        print(f"    ❌ Low validation failed for {(~low_check).sum()} bars")
        return False
    
    # Check VWAP between Low and High
    vwap_check = (bars["vwap"] >= bars["low"]) & (bars["vwap"] <= bars["high"])
    if not vwap_check.all():
        print(f"    ❌ VWAP validation failed for {(~vwap_check).sum()} bars")
        return False
    
    print(f"    ✅ All {len(bars)} bars passed OHLCV validation")
    return True


def print_bar_summary(bars: pd.DataFrame, stats: dict, bar_type: str):
    """Print summary statistics for bars."""
    print(f"\n  {bar_type.upper()} BAR STATISTICS:")
    print(f"    Total bars: {stats['total_bars']}")
    print(f"    Timespan: {stats['timespan']['duration_seconds']:.1f} seconds")
    print(f"    Price range: {stats['price']['low']:.5f} - {stats['price']['high']:.5f}")
    print(f"    Total volume: {stats['volume']['total']:,.0f}")
    print(f"    Avg volume per bar: {stats['volume']['mean']:,.1f}")
    print(f"    Total trades: {stats['trades']['total']:,}")
    print(f"    Avg trades per bar: {stats['trades']['mean']:.1f}")


def main():
    """Test all 6 bar types on Dukascopy data."""
    print("=" * 70)
    print("COMPREHENSIVE BAR CONSTRUCTION TEST - ALL 6 TYPES")
    print("=" * 70)
    
    # Load cleaned Dukascopy data
    data_path = Path("data/cleaned/EURUSD_20241018_10_cleaned.parquet")
    
    if not data_path.exists():
        print(f"\n❌ ERROR: Cleaned data not found at {data_path}")
        print("Please run test_cleaning_pipeline.py first")
        return
    
    print(f"\nLoading cleaned data from: {data_path}")
    df = pd.read_parquet(data_path)
    print(f"✅ Loaded {len(df):,} ticks")
    
    # Handle Dukascopy Level 1 data (no trade quantity)
    # Use bid_vol as proxy for volume
    if "quantity" in df.columns and df["quantity"].sum() == 0:
        print("⚠️  No trade quantity in data, using bid_vol as proxy")
        if "bid_vol" in df.columns:
            df["quantity"] = df["bid_vol"]
        else:
            df["quantity"] = 1.0  # Fallback: treat each tick as 1 unit
    
    # Create output directory
    output_dir = Path("data/bars")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Track results
    results = []
    
    # ========================================================================
    # 1. TIME BARS (5min)
    # ========================================================================
    print("\n" + "-" * 70)
    print("1. TIME BARS (5min interval)")
    print("-" * 70)
    
    time_bars = BarFactory.create(
        bar_type="time",
        df=df,
        interval="5min"
    )
    
    time_valid = validate_ohlcv(time_bars, "time")
    time_stats = BarFactory.get_statistics("time", time_bars, interval="5min")
    print_bar_summary(time_bars, time_stats, "time")
    
    # Save
    time_output = output_dir / "EURUSD_20241018_5min_bars.parquet"
    time_bars.to_parquet(time_output)
    print(f"\n  💾 Saved to: {time_output}")
    
    results.append(("Time (5min)", len(time_bars), time_valid))
    
    # ========================================================================
    # 2. TICK BARS (500 ticks per bar)
    # ========================================================================
    print("\n" + "-" * 70)
    print("2. TICK BARS (500 ticks per bar)")
    print("-" * 70)
    
    tick_bars = BarFactory.create(
        bar_type="tick",
        df=df,
        num_ticks=500
    )
    
    tick_valid = validate_ohlcv(tick_bars, "tick")
    tick_stats = BarFactory.get_statistics("tick", tick_bars, num_ticks=500)
    print_bar_summary(tick_bars, tick_stats, "tick")
    
    # Save
    tick_output = output_dir / "EURUSD_20241018_500tick_bars.parquet"
    tick_bars.to_parquet(tick_output)
    print(f"\n  💾 Saved to: {tick_output}")
    
    results.append(("Tick (500)", len(tick_bars), tick_valid))
    
    # ========================================================================
    # 3. VOLUME BARS (100,000 threshold)
    # ========================================================================
    print("\n" + "-" * 70)
    print("3. VOLUME BARS (100,000 volume threshold)")
    print("-" * 70)
    
    volume_bars = BarFactory.create(
        bar_type="volume",
        df=df,
        volume_threshold=100_000
    )
    
    volume_valid = validate_ohlcv(volume_bars, "volume")
    volume_stats = BarFactory.get_statistics("volume", volume_bars, volume_threshold=100_000)
    print_bar_summary(volume_bars, volume_stats, "volume")
    
    # Save
    volume_output = output_dir / "EURUSD_20241018_100kvol_bars.parquet"
    volume_bars.to_parquet(volume_output)
    print(f"\n  💾 Saved to: {volume_output}")
    
    results.append(("Volume (100k)", len(volume_bars), volume_valid))
    
    # ========================================================================
    # 4. DOLLAR BARS (1,000,000 threshold)
    # ========================================================================
    print("\n" + "-" * 70)
    print("4. DOLLAR BARS ($1M dollar threshold)")
    print("-" * 70)
    
    dollar_bars = BarFactory.create(
        bar_type="dollar",
        df=df,
        dollar_threshold=1_000_000
    )
    
    dollar_valid = validate_ohlcv(dollar_bars, "dollar")
    dollar_stats = BarFactory.get_statistics("dollar", dollar_bars, dollar_threshold=1_000_000)
    print_bar_summary(dollar_bars, dollar_stats, "dollar")
    
    # Save
    dollar_output = output_dir / "EURUSD_20241018_1mdollar_bars.parquet"
    dollar_bars.to_parquet(dollar_output)
    print(f"\n  💾 Saved to: {dollar_output}")
    
    results.append(("Dollar ($1M)", len(dollar_bars), dollar_valid))
    
    # ========================================================================
    # 5. IMBALANCE BARS (5,000 threshold)
    # ========================================================================
    print("\n" + "-" * 70)
    print("5. IMBALANCE BARS (5,000 imbalance threshold)")
    print("-" * 70)
    
    imbalance_bars = BarFactory.create(
        bar_type="imbalance",
        df=df,
        imbalance_threshold=5_000
    )
    
    imbalance_valid = validate_ohlcv(imbalance_bars, "imbalance")
    imbalance_stats = BarFactory.get_statistics("imbalance", imbalance_bars, imbalance_threshold=5_000)
    print_bar_summary(imbalance_bars, imbalance_stats, "imbalance")
    
    # Additional imbalance metrics
    if not imbalance_bars.empty:
        print(f"    Imbalance mean: {imbalance_stats['imbalance']['mean']:,.1f}")
        print(f"    Imbalance std: {imbalance_stats['imbalance']['std']:,.1f}")
    
    # Save
    imbalance_output = output_dir / "EURUSD_20241018_5kimbalance_bars.parquet"
    imbalance_bars.to_parquet(imbalance_output)
    print(f"\n  💾 Saved to: {imbalance_output}")
    
    results.append(("Imbalance (5k)", len(imbalance_bars), imbalance_valid))
    
    # ========================================================================
    # 6. RUN BARS (5 runs per bar)
    # ========================================================================
    print("\n" + "-" * 70)
    print("6. RUN BARS (5 runs per bar)")
    print("-" * 70)
    
    run_bars = BarFactory.create(
        bar_type="run",
        df=df,
        num_runs=5
    )
    
    run_valid = validate_ohlcv(run_bars, "run")
    run_stats = BarFactory.get_statistics("run", run_bars, num_runs=5)
    print_bar_summary(run_bars, run_stats, "run")
    
    # Save
    run_output = output_dir / "EURUSD_20241018_5run_bars.parquet"
    run_bars.to_parquet(run_output)
    print(f"\n  💾 Saved to: {run_output}")
    
    results.append(("Run (5)", len(run_bars), run_valid))
    
    # ========================================================================
    # FINAL SUMMARY
    # ========================================================================
    print("\n" + "=" * 70)
    print("FINAL SUMMARY - ALL 6 BAR TYPES")
    print("=" * 70)
    
    print(f"\n{'Bar Type':<20} {'Bars Created':<15} {'Validation':<15}")
    print("-" * 50)
    for bar_type, count, valid in results:
        status = "✅ PASSED" if valid else "❌ FAILED"
        print(f"{bar_type:<20} {count:<15} {status:<15}")
    
    all_passed = all(valid for _, _, valid in results)
    
    print("\n" + "=" * 70)
    if all_passed:
        print("🎉 SUCCESS: All 6 bar types constructed and validated!")
        print("=" * 70)
    else:
        print("⚠️  FAILURE: Some bar types failed validation")
        print("=" * 70)
    
    print(f"\n📁 All bar files saved to: {output_dir.absolute()}")


if __name__ == "__main__":
    main()

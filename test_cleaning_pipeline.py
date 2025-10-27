"""
Test the data cleaning pipeline on real Dukascopy data.

This script validates:
1. TimezoneNormalizer - converts timestamps to UTC
2. SessionFilter - filters by forex trading hours
3. DataQualityChecker - detects outliers, duplicates, gaps
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

import pandas as pd
from autotrader.data_prep import TimezoneNormalizer, SessionFilter, DataQualityChecker


def main():
    print("=" * 80)
    print("Testing Data Cleaning Pipeline on Dukascopy EUR/USD Data")
    print("=" * 80)
    print()

    # Load Dukascopy data
    data_path = project_root / "data" / "historical" / "dukascopy" / "EURUSD_20241018_10.parquet"
    
    if not data_path.exists():
        print(f"❌ Data file not found: {data_path}")
        return 1
    
    print(f"📂 Loading data from: {data_path}")
    df = pd.read_parquet(data_path)
    print(f"✅ Loaded {len(df)} ticks")
    print(f"   Columns: {list(df.columns)}")
    print()

    # Step 1: Timezone Normalization
    print("🔧 Step 1: Timezone Normalization")
    print("-" * 80)
    
    normalizer = TimezoneNormalizer(venue_timezones={"DUKASCOPY": "UTC"})
    df_normalized = normalizer.normalize(df)
    
    validation = normalizer.validate(df_normalized)
    print(f"   Is Valid: {validation['is_valid']}")
    print(f"   Errors: {validation['errors']}")
    print(f"   Warnings: {validation['warnings']}")
    print(f"   Min Timestamp: {validation['stats']['min_timestamp']}")
    print(f"   Max Timestamp: {validation['stats']['max_timestamp']}")
    print()

    # Step 2: Session Filtering
    print("🔧 Step 2: Session Filtering")
    print("-" * 80)
    
    session_filter = SessionFilter(asset_class="FOREX", venue="DUKASCOPY")
    df_filtered = session_filter.filter_regular_hours(df_normalized)
    
    print(f"   Before filtering: {len(df_normalized)} ticks")
    print(f"   After filtering: {len(df_filtered)} ticks")
    print(f"   Removed: {len(df_normalized) - len(df_filtered)} ticks ({100 * (len(df_normalized) - len(df_filtered)) / len(df_normalized):.2f}%)")
    print()

    # Step 3: Data Quality Checks
    print("🔧 Step 3: Data Quality Checks")
    print("-" * 80)
    
    quality_checker = DataQualityChecker()
    
    # Get quality report (before cleaning)
    report_before = quality_checker.get_quality_report(df_filtered, price_col="bid", timestamp_col="timestamp_utc")
    print("   Quality Report (before cleaning):")
    print(f"      Total Rows: {report_before['total_rows']}")
    print(f"      Duplicates: {report_before['duplicates']}")
    print(f"      Outliers (Z-score > 5): {report_before['outliers']['zscore']}")
    print(f"      Outliers (IQR): {report_before['outliers']['iqr']}")
    print(f"      Gaps: {report_before['gaps']['count']}")
    if report_before['gaps']['count'] > 0:
        print(f"      Max Gap: {report_before['gaps']['max_gap_seconds']:.2f} seconds")
    print(f"      Price Stats:")
    print(f"         Mean: {report_before['price_stats']['mean']:.5f}")
    print(f"         Std: {report_before['price_stats']['std']:.5f}")
    print(f"         Min: {report_before['price_stats']['min']:.5f}")
    print(f"         Max: {report_before['price_stats']['max']:.5f}")
    print()

    # Remove duplicates
    df_clean = quality_checker.remove_duplicates(df_filtered)
    print(f"   Removed {len(df_filtered) - len(df_clean)} duplicates")
    
    # Detect outliers
    outliers_zscore = quality_checker.detect_outliers(df_clean, price_col="bid", method="zscore", threshold=5.0)
    print(f"   Detected {outliers_zscore.sum()} outliers (Z-score > 5)")
    
    # Remove outliers
    df_clean = df_clean[~outliers_zscore]
    print(f"   After outlier removal: {len(df_clean)} ticks")
    print()

    # Detect gaps
    gaps = quality_checker.detect_gaps(df_clean, timestamp_col="timestamp_utc", max_gap_seconds=5.0)
    print(f"   Detected {len(gaps)} gaps (> 5 seconds)")
    if not gaps.empty:
        print("   Largest gaps:")
        print(gaps.nlargest(5, "gap_seconds")[["timestamp_utc", "gap_seconds"]])
    print()

    # Final quality report
    report_after = quality_checker.get_quality_report(df_clean, price_col="bid", timestamp_col="timestamp_utc")
    print("   Quality Report (after cleaning):")
    print(f"      Total Rows: {report_after['total_rows']}")
    print(f"      Duplicates: {report_after['duplicates']}")
    print(f"      Outliers (Z-score > 5): {report_after['outliers']['zscore']}")
    print(f"      Price Stats:")
    print(f"         Mean: {report_after['price_stats']['mean']:.5f}")
    print(f"         Std: {report_after['price_stats']['std']:.5f}")
    print()

    # Save cleaned data
    output_path = project_root / "data" / "cleaned" / "EURUSD_20241018_10_cleaned.parquet"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df_clean.to_parquet(output_path)
    print(f"💾 Saved cleaned data to: {output_path}")
    print(f"   File size: {output_path.stat().st_size / 1024:.2f} KB")
    print()

    # Summary
    print("=" * 80)
    print("✅ CLEANING PIPELINE TEST COMPLETE")
    print("=" * 80)
    print(f"   Original: {len(df)} ticks")
    print(f"   After normalization: {len(df_normalized)} ticks")
    print(f"   After session filtering: {len(df_filtered)} ticks")
    print(f"   After quality checks: {len(df_clean)} ticks")
    print(f"   Total removed: {len(df) - len(df_clean)} ticks ({100 * (len(df) - len(df_clean)) / len(df):.2f}%)")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())

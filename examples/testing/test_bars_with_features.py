"""
Test script for bar construction with integrated order book features.

This script validates that BarFactory.create() can extract and attach
order book features to all 6 bar types (time, tick, volume, dollar, imbalance, run).
"""

import pandas as pd
from autotrader.data_prep.bars import BarFactory


def test_bars_with_features():
    """Test all bar types with feature extraction."""
    print("=" * 80)
    print("TEST: Bar Construction with Order Book Features")
    print("=" * 80)

    # Load cleaned Dukascopy data
    print("\n[1/7] Loading tick data...")
    tick_file = "data/cleaned/EURUSD_20241018_10_cleaned.parquet"
    df = pd.read_parquet(tick_file)
    print(f"[OK] Loaded {len(df):,} ticks from {tick_file}")
    print(f"     Columns: {list(df.columns)}")
    print(f"     Date range: {df['timestamp_utc'].min()} to {df['timestamp_utc'].max()}")

    # Test configuration
    test_configs = [
        {
            "bar_type": "time",
            "interval": "5min",
            "description": "5-minute time bars",
        },
        {
            "bar_type": "tick",
            "num_ticks": 500,
            "description": "500-tick bars",
        },
        {
            "bar_type": "volume",
            "volume_threshold": 100.0,
            "description": "100-volume bars",
        },
        {
            "bar_type": "dollar",
            "dollar_threshold": 10000.0,
            "description": "10K-dollar bars",
        },
        {
            "bar_type": "imbalance",
            "imbalance_threshold": 50.0,
            "description": "50-imbalance bars",
        },
        {
            "bar_type": "run",
            "num_runs": 10,
            "description": "10-run bars",
        },
    ]

    results = []

    for i, config in enumerate(test_configs, start=2):
        bar_type = config["bar_type"]
        description = config["description"]
        
        print(f"\n[{i}/7] Testing {description} WITH features...")

        try:
            # Create bars WITHOUT features (baseline)
            bars_no_features = BarFactory.create(
                bar_type=bar_type,
                df=df,
                timestamp_col="timestamp_utc",
                price_col="price",
                quantity_col="bid_vol",  # Use bid_vol as proxy for quantity
                extract_features=False,
                **{k: v for k, v in config.items() if k not in ["bar_type", "description"]}
            )

            # Create bars WITH features
            bars_with_features = BarFactory.create(
                bar_type=bar_type,
                df=df,
                timestamp_col="timestamp_utc",
                price_col="price",
                quantity_col="bid_vol",
                extract_features=True,
                bid_col="bid",
                ask_col="ask",
                side_col=None,  # Will infer from price changes
                **{k: v for k, v in config.items() if k not in ["bar_type", "description"]}
            )

            # Validate results
            num_bars = len(bars_with_features)
            num_features = len(bars_with_features.columns) - len(bars_no_features.columns)
            
            # Get feature columns
            feature_cols = [col for col in bars_with_features.columns 
                          if col not in bars_no_features.columns]

            # Check for NaN in features
            nan_counts = bars_with_features[feature_cols].isna().sum()
            total_nans = nan_counts.sum()
            non_nan_features = [col for col in feature_cols if bars_with_features[col].notna().any()]

            print(f"   [OK] SUCCESS: {num_bars} bars created")
            print(f"   [OK] Added {num_features} feature columns: {feature_cols[:3]}...")
            print(f"   [OK] Non-NaN features: {len(non_nan_features)}/{len(feature_cols)}")
            
            if total_nans > 0:
                print(f"   [WARN] Warning: {total_nans} NaN values in features (expected for rolling windows)")

            # Sample feature values (first non-NaN row)
            first_valid_idx = bars_with_features[feature_cols].dropna(how="all").index[0]
            sample_row = bars_with_features.loc[first_valid_idx]
            
            print(f"\n   Sample bar (index {first_valid_idx}):")
            print(f"      OHLCV: O={sample_row['open']:.5f}, H={sample_row['high']:.5f}, "
                  f"L={sample_row['low']:.5f}, C={sample_row['close']:.5f}, V={sample_row['volume']:.0f}")
            
            # Show sample feature values
            print(f"      Features (sample):")
            for col in feature_cols[:5]:  # Show first 5 features
                val = sample_row.get(col, float("nan"))
                if pd.notna(val):
                    print(f"         {col}: {val:.6f}")

            results.append({
                "bar_type": bar_type,
                "description": description,
                "num_bars": num_bars,
                "num_features": num_features,
                "status": "[PASS]",
            })

        except Exception as e:
            print(f"   [FAIL] FAILED: {str(e)}")
            results.append({
                "bar_type": bar_type,
                "description": description,
                "num_bars": 0,
                "num_features": 0,
                "status": f"[FAIL]: {str(e)}",
            })

    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    
    summary_df = pd.DataFrame(results)
    print(summary_df.to_string(index=False))
    
    passed = sum(1 for r in results if r["status"] == "[PASS]")
    total = len(results)
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("[OK] ALL TESTS PASSED")
    else:
        print("[FAIL] SOME TESTS FAILED")

    return passed == total


if __name__ == "__main__":
    success = test_bars_with_features()
    exit(0 if success else 1)

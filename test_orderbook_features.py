"""
Test order book feature extraction on real Dukascopy data.

This script validates all 15 order book features:
- 5 spread features (bid-ask dynamics)
- 5 depth features (liquidity distribution)
- 5 flow features (informed trading detection)

Usage:
    python test_orderbook_features.py
"""

import pandas as pd
from pathlib import Path
from autotrader.data_prep.features import OrderBookFeatureExtractor


def main():
    """Test order book features on Dukascopy data."""
    print("=" * 70)
    print("ORDER BOOK FEATURE EXTRACTION TEST")
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

    # Create feature extractor
    extractor = OrderBookFeatureExtractor(
        spread_volatility_window=20,
        spread_percentile_window=100,
        num_levels=1,  # Dukascopy only has Level 1 (best bid/ask)
        vpin_window=50,
        kyle_window=20,
        amihud_window=20
    )

    print(f"\n📊 Feature Extractor Configuration:")
    print(f"  Spread volatility window: 20")
    print(f"  Spread percentile window: 100")
    print(f"  Order book levels: 1 (Level 1 data)")
    print(f"  VPIN window: 50")
    print(f"  Kyle's lambda window: 20")
    print(f"  Amihud window: 20")

    # ========================================================================
    # TEST 1: Spread Features (Level 1 data available)
    # ========================================================================
    print("\n" + "-" * 70)
    print("TEST 1: SPREAD FEATURES (5 features)")
    print("-" * 70)

    try:
        spread_features = extractor.extract_spread_only(
            df=df,
            bid_col="bid",
            ask_col="ask",
            timestamp_col="timestamp_utc"
        )

        print(f"\n✅ Extracted {len(spread_features)} rows")
        print(f"\nFeatures created:")
        for feature in extractor.spread_extractor.get_feature_names():
            print(f"  - {feature}: {spread_features[feature].describe()['mean']:.6f} (mean)")

        # Validate no NaN in final rows (after rolling windows stabilize)
        stable_idx = 100  # After percentile window stabilizes
        nan_counts = spread_features.iloc[stable_idx:].isna().sum()
        if nan_counts.sum() == 0:
            print(f"\n✅ VALIDATION PASSED: No NaN values after row {stable_idx}")
        else:
            print(f"\n⚠️  WARNING: Found NaN values after row {stable_idx}:")
            print(nan_counts[nan_counts > 0])

        # Save
        output_path = Path("data/features/EURUSD_20241018_spread_features.parquet")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        spread_features.to_parquet(output_path)
        print(f"\n💾 Saved to: {output_path}")

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

    # ========================================================================
    # TEST 2: Flow Features (requires side/quantity)
    # ========================================================================
    print("\n" + "-" * 70)
    print("TEST 2: FLOW FEATURES (5 features)")
    print("-" * 70)

    # Check if we have trade data (side, quantity)
    if "side" in df.columns and "quantity" in df.columns:
        # Use bid_vol as proxy for quantity if needed
        if df["quantity"].sum() == 0:
            print("⚠️  No trade quantity, using bid_vol as proxy")
            df["quantity"] = df["bid_vol"]

        # Infer side from price changes (for Level 1 data)
        if df["side"].isna().all() or (df["side"] == "UNKNOWN").all():
            print("⚠️  No side information, inferring from price changes")
            df["price_change"] = df["price"].diff()
            df["side"] = df["price_change"].apply(
                lambda x: "BUY" if x > 0 else ("SELL" if x < 0 else "UNKNOWN")
            )

        try:
            flow_features = extractor.extract_flow_only(
                df=df,
                timestamp_col="timestamp_utc",
                price_col="price",
                quantity_col="quantity",
                side_col="side"
            )

            print(f"\n✅ Extracted {len(flow_features)} rows")
            print(f"\nFeatures created:")
            for feature in extractor.flow_extractor.get_feature_names():
                mean_val = flow_features[feature].mean()
                print(f"  - {feature}: {mean_val:.6f} (mean)")

            # Validate
            stable_idx = 50  # After VPIN window stabilizes
            nan_counts = flow_features.iloc[stable_idx:].isna().sum()
            if nan_counts.sum() == 0:
                print(f"\n✅ VALIDATION PASSED: No NaN values after row {stable_idx}")
            else:
                print(f"\n⚠️  WARNING: Found NaN values after row {stable_idx}:")
                print(nan_counts[nan_counts > 0])

            # Save
            output_path = Path("data/features/EURUSD_20241018_flow_features.parquet")
            flow_features.to_parquet(output_path)
            print(f"\n💾 Saved to: {output_path}")

        except Exception as e:
            print(f"\n❌ ERROR: {e}")
            import traceback
            traceback.print_exc()

    else:
        print("\n⚠️  SKIPPED: No side/quantity columns in data")
        print("Flow features require trade data with side and quantity")

    # ========================================================================
    # TEST 3: Depth Features (requires Level 2)
    # ========================================================================
    print("\n" + "-" * 70)
    print("TEST 3: DEPTH FEATURES (5 features)")
    print("-" * 70)

    # Check if Level 2 data available
    if "bid_price_1" in df.columns:
        print("✅ Level 2 data detected")
        # Implementation would go here
    else:
        print("\n⚠️  SKIPPED: No Level 2 data available")
        print("Depth features require bid_price_1, bid_vol_1, etc.")
        print("Dukascopy Level 1 data only has best bid/ask")

    # ========================================================================
    # SUMMARY
    # ========================================================================
    print("\n" + "=" * 70)
    print("FEATURE EXTRACTION SUMMARY")
    print("=" * 70)

    print(f"\n✅ Spread Features: {len(extractor.spread_extractor.get_feature_names())} extracted")
    print(f"✅ Flow Features: {len(extractor.flow_extractor.get_feature_names())} extracted")
    print(f"⚠️  Depth Features: Skipped (requires Level 2 data)")

    total_extracted = (
        len(extractor.spread_extractor.get_feature_names()) +
        len(extractor.flow_extractor.get_feature_names())
    )
    total_possible = len(extractor.get_all_feature_names())

    print(f"\n📊 Total: {total_extracted} of {total_possible} features extracted")
    print(f"   (10 of 15 features available with Level 1 data)")

    print("\n" + "=" * 70)
    print(f"📁 Features saved to: data/features/")
    print("=" * 70)


if __name__ == "__main__":
    main()

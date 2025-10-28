"""
Demo script: ML-ready feature matrix from bars with order book features.

This script demonstrates how to use BarFactory with extract_features=True
to create an ML-ready feature matrix for training trading models.
"""

import pandas as pd
from autotrader.data_prep.bars import BarFactory


def main():
    """Create ML-ready feature matrix from bars with features."""
    print("=" * 80)
    print("DEMO: ML-Ready Feature Matrix with Order Book Features")
    print("=" * 80)

    # Load tick data
    print("\n[1/5] Loading tick data...")
    tick_file = "data/cleaned/EURUSD_20241018_10_cleaned.parquet"
    df = pd.read_parquet(tick_file)
    print(f"[OK] Loaded {len(df):,} ticks")

    # Create tick bars with features
    print("\n[2/5] Creating 500-tick bars with order book features...")
    bars = BarFactory.create(
        bar_type="tick",
        df=df,
        num_ticks=500,
        timestamp_col="timestamp_utc",
        price_col="price",
        quantity_col="bid_vol",
        extract_features=True,
        bid_col="bid",
        ask_col="ask",
        side_col=None,  # Will infer from price changes
    )
    print(f"[OK] Created {len(bars)} bars")
    print(f"[OK] Total columns: {len(bars.columns)}")

    # Define feature columns
    feature_cols = [
        "spread_absolute",
        "mid_quote",
        "spread_relative",
        "spread_volatility",
        "spread_percentile",
        "vpin",
        "order_flow_imbalance",
        "trade_intensity",
        "kyle_lambda",
        "amihud_illiquidity",
    ]

    # Check which features are present
    available_features = [col for col in feature_cols if col in bars.columns]
    print(f"\n[3/5] Available features: {len(available_features)}/{len(feature_cols)}")
    for feat in available_features:
        print(f"   - {feat}")

    # Prepare feature matrix
    print("\n[4/5] Preparing feature matrix...")
    X = bars[available_features].copy()

    # Forward-fill NaN values (from rolling windows)
    X_filled = X.fillna(method="ffill").fillna(0)  # Fill remaining with 0

    # Create target labels (next-bar direction)
    y = (bars["close"].shift(-1) > bars["close"]).astype(int)
    y = y[:-1]  # Remove last row (no next bar)
    X_filled = X_filled[:-1]  # Match lengths

    print(f"[OK] Feature matrix shape: {X_filled.shape}")
    print(f"[OK] Target labels shape: {y.shape}")
    print(f"[OK] Target distribution: {y.value_counts().to_dict()}")

    # Show feature statistics
    print("\n[5/5] Feature Statistics:")
    print("-" * 80)
    stats = X_filled.describe().T[["mean", "std", "min", "max"]]
    print(stats.to_string())

    # Show sample data
    print("\n" + "=" * 80)
    print("Sample Data (first 3 bars):")
    print("=" * 80)
    sample = bars[["timestamp_start", "open", "high", "low", "close", "volume"] + available_features[:3]].head(3)
    print(sample.to_string())

    # Save feature matrix
    output_file = "data/features/EURUSD_20241018_ml_ready.parquet"
    ml_data = pd.concat([X_filled, y.rename("target")], axis=1)
    ml_data.to_parquet(output_file)
    print(f"\n[OK] Saved ML-ready data to {output_file}")
    print(f"[OK] Shape: {ml_data.shape}")

    print("\n" + "=" * 80)
    print("DEMO COMPLETE")
    print("=" * 80)
    print(f"\nML-ready feature matrix created with {len(available_features)} features")
    print(f"Ready for training with scikit-learn, XGBoost, LightGBM, etc.")


if __name__ == "__main__":
    main()

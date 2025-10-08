"""Example: Using the unified feature store for centralized feature management."""

import time
from pathlib import Path

from src.core.feature_store import (
    FeatureStore,
    FeatureMetadata,
    FeatureType,
    FeatureCategory,
    FeatureVector,
)
from src.services.feature_engineering import (
    FeatureEngineeringPipeline,
    register_standard_transforms,
    build_ml_ready_vector,
)


# ============================================================================
# Example 1: Basic Feature Store Usage
# ============================================================================

def example_basic_feature_store():
    """Example: Register features and write/read values."""
    print("=" * 60)
    print("EXAMPLE 1: Basic Feature Store Usage")
    print("=" * 60)

    # Initialize feature store (in-memory)
    fs = FeatureStore()

    # Register features in schema
    fs.register_feature(FeatureMetadata(
        name="price_usd",
        feature_type=FeatureType.NUMERIC,
        category=FeatureCategory.MARKET,
        description="Current price in USD",
        source="coingecko",
        unit="USD",
        min_value=0.0,
        tags=["price", "market"],
    ))

    fs.register_feature(FeatureMetadata(
        name="volume_24h_usd",
        feature_type=FeatureType.NUMERIC,
        category=FeatureCategory.MARKET,
        description="24-hour trading volume",
        source="coingecko",
        unit="USD",
        min_value=0.0,
        tags=["volume", "liquidity"],
    ))

    fs.register_feature(FeatureMetadata(
        name="sentiment_score",
        feature_type=FeatureType.NUMERIC,
        category=FeatureCategory.SENTIMENT,
        description="Twitter sentiment score (-1 to 1)",
        source="twitter",
        unit="score",
        min_value=-1.0,
        max_value=1.0,
        tags=["sentiment", "social"],
    ))

    print(f"✅ Registered {len(fs._schema)} features\n")

    # Write feature values
    token = "BTC"
    current_time = time.time()

    fs.write_feature("price_usd", 67500.0, token, current_time, confidence=0.98)
    fs.write_feature("volume_24h_usd", 28_500_000_000, token, current_time, confidence=0.95)
    fs.write_feature("sentiment_score", 0.65, token, current_time, confidence=0.82)

    print("📝 Wrote 3 feature values for BTC\n")

    # Read features back
    price = fs.read_feature("price_usd", token)
    volume = fs.read_feature("volume_24h_usd", token)
    sentiment = fs.read_feature("sentiment_score", token)

    print("📖 Read features:")
    print(f"  Price: ${price.value:,.2f} (confidence: {price.confidence:.2%})")
    print(f"  Volume: ${volume.value:,.0f} (confidence: {volume.confidence:.2%})")
    print(f"  Sentiment: {sentiment.value:.2f} (confidence: {sentiment.confidence:.2%})")

    # Get stats
    stats = fs.get_stats()
    print(f"\n📊 Store stats:")
    print(f"  Schema size: {stats['schema_size']}")
    print(f"  Total values: {stats['total_feature_values']}")


# ============================================================================
# Example 2: Time-Series Features
# ============================================================================

def example_time_series_features():
    """Example: Store and query time-series feature data."""
    print("\n\n" + "=" * 60)
    print("EXAMPLE 2: Time-Series Features")
    print("=" * 60)

    fs = FeatureStore()

    # Register feature
    fs.register_feature(FeatureMetadata(
        name="price_usd",
        feature_type=FeatureType.NUMERIC,
        category=FeatureCategory.MARKET,
        description="Current price in USD",
        source="coingecko",
        unit="USD",
    ))

    # Write time-series data
    token = "ETH"
    base_time = time.time()
    prices = [3200, 3215, 3190, 3205, 3220, 3230, 3225, 3240]

    for i, price in enumerate(prices):
        timestamp = base_time + (i * 300)  # 5-minute intervals
        fs.write_feature("price_usd", price, token, timestamp)

    print(f"✅ Wrote {len(prices)} time-series values for ETH\n")

    # Query latest value
    latest = fs.read_feature("price_usd", token)
    print(f"📖 Latest price: ${latest.value:.2f} at {time.ctime(latest.timestamp)}\n")

    # Query historical data
    history = fs.read_feature_history("price_usd", token, limit=5)
    print("📈 Last 5 prices:")
    for fv in history:
        print(f"  ${fv.value:.2f} at {time.ctime(fv.timestamp)}")

    # Point-in-time query (get price from 20 minutes ago)
    pit_timestamp = base_time + (4 * 300)  # 4th data point
    pit_value = fs.read_feature("price_usd", token, timestamp=pit_timestamp)
    print(f"\n⏰ Point-in-time (20min ago): ${pit_value.value:.2f}")


# ============================================================================
# Example 3: Feature Vectors
# ============================================================================

def example_feature_vectors():
    """Example: Build and store feature vectors."""
    print("\n\n" + "=" * 60)
    print("EXAMPLE 3: Feature Vectors")
    print("=" * 60)

    fs = FeatureStore()

    # Register features
    features_to_register = [
        ("price_usd", FeatureType.NUMERIC, FeatureCategory.MARKET, "Price in USD"),
        ("volume_24h_usd", FeatureType.NUMERIC, FeatureCategory.MARKET, "24h volume"),
        ("market_cap_usd", FeatureType.NUMERIC, FeatureCategory.MARKET, "Market cap"),
        ("liquidity_score", FeatureType.NUMERIC, FeatureCategory.SCORING, "Liquidity score"),
    ]

    for name, ftype, category, desc in features_to_register:
        fs.register_feature(FeatureMetadata(
            name=name,
            feature_type=ftype,
            category=category,
            description=desc,
            source="aggregated",
        ))

    # Create feature vector
    vector = FeatureVector(
        token_symbol="LINK",
        timestamp=time.time(),
        features={
            "price_usd": 14.50,
            "volume_24h_usd": 350_000_000,
            "market_cap_usd": 8_500_000_000,
            "liquidity_score": 72.5,
        },
        confidence_scores={
            "price_usd": 0.99,
            "volume_24h_usd": 0.95,
            "market_cap_usd": 0.98,
            "liquidity_score": 0.85,
        },
    )

    # Store vector
    fs.write_vector(vector)
    print("✅ Wrote feature vector for LINK\n")

    # Read vector back
    retrieved = fs.read_vector("LINK")
    print("📖 Retrieved feature vector:")
    print(f"  Token: {retrieved.token_symbol}")
    print(f"  Timestamp: {time.ctime(retrieved.timestamp)}")
    print(f"  Features: {len(retrieved.features)}")
    for name, value in retrieved.features.items():
        confidence = retrieved.confidence_scores.get(name, 1.0)
        print(f"    {name}: {value} (confidence: {confidence:.2%})")


# ============================================================================
# Example 4: Feature Engineering Pipeline
# ============================================================================

def example_feature_engineering():
    """Example: Use feature engineering pipeline for transformations."""
    print("\n\n" + "=" * 60)
    print("EXAMPLE 4: Feature Engineering Pipeline")
    print("=" * 60)

    fs = FeatureStore()

    # Register base features
    fs.register_feature(FeatureMetadata(
        name="market_cap_usd",
        feature_type=FeatureType.NUMERIC,
        category=FeatureCategory.MARKET,
        description="Market cap in USD",
        source="coingecko",
    ))

    fs.register_feature(FeatureMetadata(
        name="volume_24h_usd",
        feature_type=FeatureType.NUMERIC,
        category=FeatureCategory.MARKET,
        description="24h volume in USD",
        source="coingecko",
    ))

    # Write base feature values
    token = "UNI"
    fs.write_feature("market_cap_usd", 5_200_000_000, token)
    fs.write_feature("volume_24h_usd", 180_000_000, token)

    print("✅ Wrote base features for UNI\n")

    # Create pipeline and register transforms
    pipeline = FeatureEngineeringPipeline(fs)
    register_standard_transforms(pipeline)

    print(f"✅ Registered {len(pipeline._transforms)} standard transforms\n")

    # Apply transformation
    result = pipeline.apply_transform("market_cap_to_volume_ratio", token)
    print(f"🔄 Applied transform 'market_cap_to_volume_ratio'")
    print(f"   Result: {result:.2f}\n")

    # Read derived feature
    derived = fs.read_feature("market_cap_to_volume_ratio", token)
    print(f"📖 Derived feature stored:")
    print(f"   Value: {derived.value:.2f}")
    print(f"   Transform: {derived.metadata.get('transform')}")
    print(f"   Version: {derived.metadata.get('version')}")


# ============================================================================
# Example 5: ML-Ready Feature Vectors
# ============================================================================

def example_ml_ready_features():
    """Example: Build ML-ready feature vectors."""
    print("\n\n" + "=" * 60)
    print("EXAMPLE 5: ML-Ready Feature Vectors")
    print("=" * 60)

    fs = FeatureStore()
    pipeline = FeatureEngineeringPipeline(fs)
    register_standard_transforms(pipeline)

    # Register and populate all required features
    token = "AAVE"

    # Market features
    fs.register_feature(FeatureMetadata(
        name="price_usd", feature_type=FeatureType.NUMERIC,
        category=FeatureCategory.MARKET, description="Price", source="coingecko"
    ))
    fs.write_feature("price_usd", 95.50, token)

    fs.register_feature(FeatureMetadata(
        name="market_cap_usd", feature_type=FeatureType.NUMERIC,
        category=FeatureCategory.MARKET, description="Market cap", source="coingecko"
    ))
    fs.write_feature("market_cap_usd", 1_400_000_000, token)

    fs.register_feature(FeatureMetadata(
        name="volume_24h_usd", feature_type=FeatureType.NUMERIC,
        category=FeatureCategory.MARKET, description="Volume", source="coingecko"
    ))
    fs.write_feature("volume_24h_usd", 85_000_000, token)

    # Write historical price for momentum calculation
    fs.register_feature(FeatureMetadata(
        name="price_usd_1h_ago", feature_type=FeatureType.NUMERIC,
        category=FeatureCategory.MARKET, description="Price 1h ago", source="coingecko"
    ))
    fs.write_feature("price_usd_1h_ago", 93.80, token)

    # Liquidity features
    for name in ["best_bid_price", "best_ask_price", "total_bid_volume", "total_ask_volume"]:
        fs.register_feature(FeatureMetadata(
            name=name, feature_type=FeatureType.NUMERIC,
            category=FeatureCategory.LIQUIDITY, description=name, source="binance"
        ))

    fs.write_feature("best_bid_price", 95.48, token)
    fs.write_feature("best_ask_price", 95.52, token)
    fs.write_feature("total_bid_volume", 150_000, token)
    fs.write_feature("total_ask_volume", 145_000, token)

    # Sentiment features
    for name in ["sentiment_score", "sentiment_score_1h_ago", "tweet_volume"]:
        fs.register_feature(FeatureMetadata(
            name=name, feature_type=FeatureType.NUMERIC,
            category=FeatureCategory.SENTIMENT, description=name, source="twitter"
        ))

    fs.write_feature("sentiment_score", 0.58, token)
    fs.write_feature("sentiment_score_1h_ago", 0.52, token)
    fs.write_feature("tweet_volume", 1250, token)

    # Derivatives features (optional)
    for name in ["funding_rate", "open_interest_usd"]:
        fs.register_feature(FeatureMetadata(
            name=name, feature_type=FeatureType.NUMERIC,
            category=FeatureCategory.DERIVATIVES, description=name, source="bybit"
        ))

    fs.write_feature("funding_rate", 0.0005, token)
    fs.write_feature("open_interest_usd", 12_500_000, token)

    print(f"✅ Wrote all base features for {token}\n")

    # Apply transformations
    transforms_to_apply = [
        "market_cap_to_volume_ratio",
        "price_momentum_1h",
        "bid_ask_spread",
        "orderbook_imbalance",
        "sentiment_momentum",
        "liquidity_score",
        "momentum_score",
    ]

    pipeline.apply_pipeline(transforms_to_apply, token)
    print(f"🔄 Applied {len(transforms_to_apply)} transformations\n")

    # Build ML-ready vector
    ml_vector = build_ml_ready_vector(token, fs)

    if ml_vector:
        print(f"✅ Built ML-ready feature vector for {token}")
        print(f"   Features: {len(ml_vector['features'])}")
        print(f"   Sample features:")
        for name, value in list(ml_vector['features'].items())[:10]:
            conf = ml_vector['confidence_scores'].get(name, 1.0)
            print(f"     {name}: {value} (conf: {conf:.2%})")
    else:
        print("❌ Failed to build ML-ready vector (missing features)")


# ============================================================================
# Example 6: Feature Store Persistence
# ============================================================================

def example_persistence():
    """Example: Save and load feature store schema."""
    print("\n\n" + "=" * 60)
    print("EXAMPLE 6: Feature Store Persistence")
    print("=" * 60)

    storage_path = Path("./feature_store_data")

    # Create feature store with persistence
    fs = FeatureStore(storage_path=storage_path)

    # Register features
    fs.register_feature(FeatureMetadata(
        name="test_feature",
        feature_type=FeatureType.NUMERIC,
        category=FeatureCategory.MARKET,
        description="Test feature for persistence",
        source="test",
    ))

    print(f"✅ Created feature store with persistence at {storage_path}\n")
    print(f"📝 Registered 1 feature (schema saved to disk)\n")

    # Create new instance and load schema
    fs2 = FeatureStore(storage_path=storage_path)
    print(f"📖 Loaded schema from disk")
    print(f"   Schema size: {len(fs2._schema)}")

    metadata = fs2.get_feature_metadata("test_feature")
    if metadata:
        print(f"   Found feature: {metadata.name}")
        print(f"   Description: {metadata.description}")
        print(f"   Category: {metadata.category.value}")

    # Cleanup
    import shutil
    if storage_path.exists():
        shutil.rmtree(storage_path)
        print(f"\n🧹 Cleaned up test storage")


# ============================================================================
# Example 7: Query Features by Category/Tags
# ============================================================================

def example_feature_query():
    """Example: Query features by category and tags."""
    print("\n\n" + "=" * 60)
    print("EXAMPLE 7: Query Features by Category/Tags")
    print("=" * 60)

    fs = FeatureStore()
    pipeline = FeatureEngineeringPipeline(fs)
    register_standard_transforms(pipeline)

    # Register some custom features
    fs.register_feature(FeatureMetadata(
        name="custom_metric_1",
        feature_type=FeatureType.NUMERIC,
        category=FeatureCategory.TECHNICAL,
        description="Custom technical metric",
        source="custom",
        tags=["custom", "technical", "experimental"],
    ))

    print(f"✅ Registered {len(fs._schema)} features total\n")

    # Query by category
    market_features = fs.list_features(category=FeatureCategory.MARKET)
    print(f"📊 Market features: {len(market_features)}")
    for f in market_features[:3]:
        print(f"   - {f.name}: {f.description}")

    sentiment_features = fs.list_features(category=FeatureCategory.SENTIMENT)
    print(f"\n📊 Sentiment features: {len(sentiment_features)}")
    for f in sentiment_features[:3]:
        print(f"   - {f.name}: {f.description}")

    # Query by tags
    derived_features = fs.list_features(tags=["derived"])
    print(f"\n📊 Derived features: {len(derived_features)}")
    for f in derived_features[:3]:
        print(f"   - {f.name}: {f.description}")


# ============================================================================
# Main Entry Point
# ============================================================================

def main():
    """Run all examples."""
    print("=" * 60)
    print("UNIFIED FEATURE STORE DEMONSTRATION")
    print("=" * 60)

    example_basic_feature_store()
    example_time_series_features()
    example_feature_vectors()
    example_feature_engineering()
    example_ml_ready_features()
    example_persistence()
    example_feature_query()

    print("\n\n" + "=" * 60)
    print("✅ ALL EXAMPLES COMPLETED")
    print("=" * 60)


if __name__ == "__main__":
    main()

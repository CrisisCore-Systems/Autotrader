"""Examples demonstrating feature validation guardrails."""

import time
from src.core.feature_store import (
    FeatureStore,
    FeatureMetadata,
    FeatureType,
    FeatureCategory,
)
from src.core.feature_validation import (
    FeatureValidator,
    ValidationType,
    MonotonicDirection,
    ValidationError,
    add_validator,
    validate_feature,
)


def example_range_validation():
    """Example: Range validation for numeric features."""
    print("=" * 60)
    print("EXAMPLE 1: Range Validation")
    print("=" * 60)
    
    fs = FeatureStore(enable_validation=True)
    
    # Register feature
    fs.register_feature(FeatureMetadata(
        name="gem_score",
        feature_type=FeatureType.NUMERIC,
        category=FeatureCategory.SCORING,
        description="GemScore (0-100)",
    ))
    
    # Valid write
    print("\n✅ Writing valid gem_score=75.0")
    fs.write_feature("gem_score", 75.0, "PEPE")
    print("   Success!")
    
    # Invalid write - above max
    print("\n❌ Attempting invalid gem_score=150.0")
    try:
        fs.write_feature("gem_score", 150.0, "PEPE")
        print("   Unexpectedly succeeded!")
    except ValidationError as e:
        print(f"   Validation failed (expected): {e.errors[0]}")
    
    # Invalid write - below min
    print("\n❌ Attempting invalid gem_score=-10.0")
    try:
        fs.write_feature("gem_score", -10.0, "PEPE")
        print("   Unexpectedly succeeded!")
    except ValidationError as e:
        print(f"   Validation failed (expected): {e.errors[0]}")


def example_monotonic_validation():
    """Example: Monotonic validation for time-series data."""
    print("\n\n" + "=" * 60)
    print("EXAMPLE 2: Monotonic Validation")
    print("=" * 60)
    
    fs = FeatureStore(enable_validation=True)
    
    # Register cumulative counter feature
    fs.register_feature(FeatureMetadata(
        name="total_transactions",
        feature_type=FeatureType.NUMERIC,
        category=FeatureCategory.ONCHAIN,
        description="Cumulative transaction count",
    ))
    
    # Add monotonic validator
    add_validator(FeatureValidator(
        feature_name="total_transactions",
        validation_type=ValidationType.MONOTONIC,
        monotonic_direction=MonotonicDirection.STRICTLY_INCREASING,
        monotonic_window=5,
    ))
    
    # Write increasing values
    print("\n✅ Writing monotonically increasing values")
    token = "ETH"
    for i, count in enumerate([100, 150, 200, 250, 300]):
        fs.write_feature("total_transactions", count, token, timestamp=float(i))
        print(f"   Written: {count}")
    
    # Try to write decreasing value
    print("\n❌ Attempting to write decreasing value (280)")
    try:
        fs.write_feature("total_transactions", 280, token, timestamp=6.0)
        print("   Unexpectedly succeeded!")
    except ValidationError as e:
        print(f"   Validation failed (expected): {e.errors[0]}")


def example_freshness_validation():
    """Example: Freshness validation for time-sensitive data."""
    print("\n\n" + "=" * 60)
    print("EXAMPLE 3: Freshness Validation")
    print("=" * 60)
    
    fs = FeatureStore(enable_validation=True)
    
    # Register real-time orderflow feature
    fs.register_feature(FeatureMetadata(
        name="orderflow_imbalance",
        feature_type=FeatureType.NUMERIC,
        category=FeatureCategory.ORDERFLOW,
        description="Real-time orderflow imbalance",
    ))
    
    # Add freshness validator (60 second threshold)
    add_validator(FeatureValidator(
        feature_name="orderflow_imbalance",
        validation_type=ValidationType.FRESHNESS,
        max_age_seconds=60.0,
    ))
    
    current_time = time.time()
    
    # Write fresh data
    print("\n✅ Writing fresh data (10 seconds old)")
    fs.write_feature(
        "orderflow_imbalance",
        0.75,
        "BTC",
        timestamp=current_time - 10
    )
    print("   Success!")
    
    # Write stale data
    print("\n❌ Attempting to write stale data (120 seconds old)")
    try:
        fs.write_feature(
            "orderflow_imbalance",
            0.80,
            "BTC",
            timestamp=current_time - 120
        )
        print("   Unexpectedly succeeded!")
    except ValidationError as e:
        print(f"   Validation failed (expected): {e.errors[0]}")


def example_custom_validator():
    """Example: Custom validation logic."""
    print("\n\n" + "=" * 60)
    print("EXAMPLE 4: Custom Validator")
    print("=" * 60)
    
    fs = FeatureStore(enable_validation=True)
    
    # Register feature
    fs.register_feature(FeatureMetadata(
        name="risk_score",
        feature_type=FeatureType.NUMERIC,
        category=FeatureCategory.SCORING,
        description="Custom risk score",
    ))
    
    # Define custom validation logic
    def validate_risk_score(value):
        """Risk score must be positive and not in high-risk range."""
        if value < 0:
            return False, "Risk score must be non-negative"
        if 80 <= value <= 95:
            return False, "Value in high-risk range (80-95) - blocked"
        return True, None
    
    # Add custom validator
    add_validator(FeatureValidator(
        feature_name="risk_score",
        validation_type=ValidationType.CUSTOM,
        custom_validator=validate_risk_score,
    ))
    
    # Valid values
    print("\n✅ Writing valid risk_score=45.0")
    fs.write_feature("risk_score", 45.0, "TOKEN")
    print("   Success!")
    
    print("\n✅ Writing valid risk_score=70.0")
    fs.write_feature("risk_score", 70.0, "TOKEN")
    print("   Success!")
    
    # Invalid - high risk range
    print("\n❌ Attempting risk_score=85.0 (high-risk range)")
    try:
        fs.write_feature("risk_score", 85.0, "TOKEN")
        print("   Unexpectedly succeeded!")
    except ValidationError as e:
        print(f"   Validation failed (expected): {e.errors[0]}")
    
    # Invalid - negative
    print("\n❌ Attempting risk_score=-5.0 (negative)")
    try:
        fs.write_feature("risk_score", -5.0, "TOKEN")
        print("   Unexpectedly succeeded!")
    except ValidationError as e:
        print(f"   Validation failed (expected): {e.errors[0]}")


def example_batch_validation():
    """Example: Batch validation for multiple features."""
    print("\n\n" + "=" * 60)
    print("EXAMPLE 5: Batch Validation")
    print("=" * 60)
    
    fs = FeatureStore(enable_validation=True)
    
    # Register multiple features
    for name, category in [
        ("gem_score", FeatureCategory.SCORING),
        ("confidence", FeatureCategory.QUALITY),
        ("sentiment_score", FeatureCategory.SENTIMENT),
    ]:
        fs.register_feature(FeatureMetadata(
            name=name,
            feature_type=FeatureType.NUMERIC,
            category=category,
            description=f"{name} feature",
        ))
    
    # Valid batch
    print("\n✅ Writing valid batch of features")
    features = [
        ("gem_score", 75.0, "PEPE"),
        ("confidence", 0.85, "PEPE"),
        ("sentiment_score", 0.5, "PEPE"),
    ]
    fs.write_features_batch(features)
    print(f"   Successfully wrote {len(features)} features")
    
    # Invalid batch
    print("\n❌ Attempting invalid batch (gem_score=150.0)")
    invalid_features = [
        ("gem_score", 150.0, "SHIB"),  # Invalid - above max
        ("confidence", 0.90, "SHIB"),
        ("sentiment_score", 0.3, "SHIB"),
    ]
    try:
        fs.write_features_batch(invalid_features)
        print("   Unexpectedly succeeded!")
    except ValidationError as e:
        print(f"   Validation failed (expected):")
        for error in e.errors:
            print(f"     - {error}")


def example_validation_statistics():
    """Example: Monitoring validation statistics."""
    print("\n\n" + "=" * 60)
    print("EXAMPLE 6: Validation Statistics")
    print("=" * 60)
    
    fs = FeatureStore(enable_validation=True)
    
    # Register feature
    fs.register_feature(FeatureMetadata(
        name="price_usd",
        feature_type=FeatureType.NUMERIC,
        category=FeatureCategory.MARKET,
        description="Token price",
    ))
    
    # Perform various writes
    print("\n📊 Performing writes with validation...")
    
    # Valid writes
    for i in range(5):
        fs.write_feature("price_usd", 100.0 + i, "ETH")
    
    # Invalid writes
    for i in range(3):
        try:
            fs.write_feature("price_usd", -10.0 - i, "ETH")
        except ValidationError:
            pass  # Expected
    
    # Get statistics
    stats = fs.get_validation_stats()
    
    print(f"\n📈 Validation Statistics:")
    print(f"   Total validations: {stats['total_validations']}")
    print(f"   Failures: {stats['validation_failures']}")
    print(f"   Warnings: {stats['validation_warnings']}")
    print(f"   Success rate: {(stats['total_validations'] - stats['validation_failures']) / stats['total_validations']:.1%}")


def example_null_and_required():
    """Example: Null and required field validation."""
    print("\n\n" + "=" * 60)
    print("EXAMPLE 7: Null and Required Fields")
    print("=" * 60)
    
    fs = FeatureStore(enable_validation=True)
    
    # Register nullable feature
    fs.register_feature(FeatureMetadata(
        name="optional_score",
        feature_type=FeatureType.NUMERIC,
        category=FeatureCategory.SCORING,
        description="Optional score field",
    ))
    
    # Add validator (nullable, not required)
    add_validator(FeatureValidator(
        feature_name="optional_score",
        validation_type=ValidationType.RANGE,
        min_value=0.0,
        max_value=100.0,
        nullable=True,
        required=False,
    ))
    
    # Write None value - allowed
    print("\n✅ Writing None (nullable=True, required=False)")
    fs.write_feature("optional_score", None, "TOKEN")
    print("   Success!")
    
    # Register required feature
    fs.register_feature(FeatureMetadata(
        name="required_confidence",
        feature_type=FeatureType.NUMERIC,
        category=FeatureCategory.QUALITY,
        description="Required confidence field",
    ))
    
    # Add validator (not nullable, required)
    add_validator(FeatureValidator(
        feature_name="required_confidence",
        validation_type=ValidationType.RANGE,
        min_value=0.0,
        max_value=1.0,
        nullable=False,
        required=True,
    ))
    
    # Try to write None - not allowed
    print("\n❌ Attempting to write None (nullable=False, required=True)")
    try:
        fs.write_feature("required_confidence", None, "TOKEN")
        print("   Unexpectedly succeeded!")
    except ValidationError as e:
        print(f"   Validation failed (expected): {e.errors[0]}")


def example_enum_validation():
    """Example: Enum validation for categorical features."""
    print("\n\n" + "=" * 60)
    print("EXAMPLE 8: Enum Validation")
    print("=" * 60)
    
    fs = FeatureStore(enable_validation=True)
    
    # Register categorical feature
    fs.register_feature(FeatureMetadata(
        name="risk_level",
        feature_type=FeatureType.CATEGORICAL,
        category=FeatureCategory.SCORING,
        description="Risk level category",
    ))
    
    # Add enum validator
    add_validator(FeatureValidator(
        feature_name="risk_level",
        validation_type=ValidationType.ENUM,
        allowed_values=["low", "medium", "high"],
    ))
    
    # Valid values
    for level in ["low", "medium", "high"]:
        print(f"\n✅ Writing valid risk_level='{level}'")
        fs.write_feature("risk_level", level, "TOKEN")
        print("   Success!")
    
    # Invalid value
    print("\n❌ Attempting invalid risk_level='critical'")
    try:
        fs.write_feature("risk_level", "critical", "TOKEN")
        print("   Unexpectedly succeeded!")
    except ValidationError as e:
        print(f"   Validation failed (expected): {e.errors[0]}")


def main():
    """Run all examples."""
    print("\n" + "=" * 60)
    print("FEATURE VALIDATION EXAMPLES")
    print("=" * 60)
    
    example_range_validation()
    example_monotonic_validation()
    example_freshness_validation()
    example_custom_validator()
    example_batch_validation()
    example_validation_statistics()
    example_null_and_required()
    example_enum_validation()
    
    print("\n\n" + "=" * 60)
    print("ALL EXAMPLES COMPLETED")
    print("=" * 60)


if __name__ == "__main__":
    main()

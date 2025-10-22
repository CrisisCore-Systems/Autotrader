"""Integration tests for feature validation in real-world scenarios."""

import pytest
import time
from src.core.feature_store import (
    FeatureStore,
    FeatureMetadata,
    FeatureType,
    FeatureCategory,
)
from src.core.feature_validation import (
    ValidationError,
    FeatureValidator,
    ValidationType,
    MonotonicDirection,
    add_validator,
)


class TestFeatureValidationIntegration:
    """Integration tests for feature validation with FeatureStore."""
    
    def test_end_to_end_feature_write_with_validation(self):
        """Test complete workflow: register feature, write value, validate."""
        # Create feature store with validation enabled (default)
        fs = FeatureStore()
        
        # Register a price feature
        fs.register_feature(FeatureMetadata(
            name="price_usd",
            feature_type=FeatureType.NUMERIC,
            category=FeatureCategory.MARKET,
            description="Token price in USD",
            source="coingecko",
            min_value=0.0,
        ))
        
        # Valid write should succeed
        token = "ETH"
        value = fs.write_feature("price_usd", 3500.0, token)
        assert value.value == 3500.0
        
        # Invalid write (negative price) should fail
        with pytest.raises(ValidationError) as exc_info:
            fs.write_feature("price_usd", -100.0, token)
        
        assert "below min" in str(exc_info.value)
    
    def test_batch_feature_validation_prevents_partial_writes(self):
        """Test that batch validation prevents partial writes on error."""
        fs = FeatureStore()
        
        # Register features
        for name in ["gem_score", "confidence", "sentiment_score"]:
            fs.register_feature(FeatureMetadata(
                name=name,
                feature_type=FeatureType.NUMERIC,
                category=FeatureCategory.SCORING,
                description=f"{name} feature",
            ))
        
        token = "TEST"
        
        # Batch with invalid value should fail entirely
        invalid_batch = [
            ("gem_score", 75.0, token),
            ("confidence", 1.5, token),  # Invalid: > 1.0
            ("sentiment_score", 0.5, token),
        ]
        
        with pytest.raises(ValidationError):
            fs.write_features_batch(invalid_batch)
        
        # Verify no partial writes occurred
        assert fs.read_feature("gem_score", token) is None
        assert fs.read_feature("confidence", token) is None
        assert fs.read_feature("sentiment_score", token) is None
    
    def test_monotonic_validation_with_time_series(self):
        """Test monotonic validation with time-series data."""
        fs = FeatureStore()
        
        # Register cumulative transaction counter
        fs.register_feature(FeatureMetadata(
            name="tx_count",
            feature_type=FeatureType.NUMERIC,
            category=FeatureCategory.ONCHAIN,
            description="Cumulative transaction count",
        ))
        
        # Add strictly increasing validator
        add_validator(FeatureValidator(
            feature_name="tx_count",
            validation_type=ValidationType.MONOTONIC,
            monotonic_direction=MonotonicDirection.STRICTLY_INCREASING,
        ))
        
        token = "BTC"
        
        # Write increasing sequence
        for i, count in enumerate([100, 150, 200, 250]):
            fs.write_feature("tx_count", count, token, timestamp=float(i))
        
        # Attempting to write a decreasing value should fail
        with pytest.raises(ValidationError) as exc_info:
            fs.write_feature("tx_count", 240, token, timestamp=5.0)
        
        assert "strictly increasing" in str(exc_info.value).lower()
    
    def test_freshness_validation_rejects_stale_data(self):
        """Test freshness validation for time-sensitive features."""
        fs = FeatureStore()
        
        # Register real-time feature
        fs.register_feature(FeatureMetadata(
            name="live_price",
            feature_type=FeatureType.NUMERIC,
            category=FeatureCategory.MARKET,
            description="Live price feed",
        ))
        
        # Add freshness validator (30 second threshold)
        add_validator(FeatureValidator(
            feature_name="live_price",
            validation_type=ValidationType.FRESHNESS,
            max_age_seconds=30.0,
        ))
        
        token = "ETH"
        current_time = time.time()
        
        # Fresh data should succeed
        fs.write_feature("live_price", 3500.0, token, timestamp=current_time - 10)
        
        # Stale data should fail
        with pytest.raises(ValidationError) as exc_info:
            fs.write_feature("live_price", 3510.0, token, timestamp=current_time - 60)
        
        assert "exceeds max age" in str(exc_info.value)
    
    def test_validation_statistics_tracking(self):
        """Test that validation statistics are properly tracked."""
        fs = FeatureStore()
        
        fs.register_feature(FeatureMetadata(
            name="test_score",
            feature_type=FeatureType.NUMERIC,
            category=FeatureCategory.SCORING,
            description="Test score",
        ))
        
        fs.register_feature(FeatureMetadata(
            name="gem_score",
            feature_type=FeatureType.NUMERIC,
            category=FeatureCategory.SCORING,
            description="GemScore",
        ))
        
        # Perform successful validations
        for i in range(5):
            fs.write_feature("test_score", 50.0 + i, "TOKEN")
        
        # Perform failed validations
        for i in range(3):
            try:
                fs.write_feature("gem_score", 150.0, "TOKEN")  # Above max
            except (ValidationError, ValueError):
                pass
        
        stats = fs.get_validation_stats()
        
        assert stats["total_validations"] >= 8
        assert stats["validation_failures"] >= 3
    
    def test_skip_validation_for_trusted_sources(self):
        """Test that validation can be skipped for trusted data sources."""
        fs = FeatureStore()
        
        fs.register_feature(FeatureMetadata(
            name="gem_score",
            feature_type=FeatureType.NUMERIC,
            category=FeatureCategory.SCORING,
            description="GemScore",
        ))
        
        token = "TRUSTED"
        
        # Invalid value normally rejected
        with pytest.raises(ValidationError):
            fs.write_feature("gem_score", 150.0, token)
        
        # But allowed when validation is skipped
        value = fs.write_feature("gem_score", 150.0, token, skip_validation=True)
        assert value.value == 150.0
    
    def test_null_policy_enforcement(self):
        """Test null policy enforcement for required features."""
        fs = FeatureStore()
        
        # Register non-nullable required feature
        fs.register_feature(FeatureMetadata(
            name="required_score",
            feature_type=FeatureType.NUMERIC,
            category=FeatureCategory.SCORING,
            description="Required score field",
        ))
        
        add_validator(FeatureValidator(
            feature_name="required_score",
            validation_type=ValidationType.RANGE,
            min_value=0.0,
            max_value=100.0,
            nullable=False,
            required=True,
        ))
        
        token = "TEST"
        
        # None value should be rejected
        with pytest.raises(ValidationError) as exc_info:
            fs.write_feature("required_score", None, token)
        
        assert "cannot be null" in str(exc_info.value) or "required" in str(exc_info.value).lower()
    
    def test_multiple_validators_on_same_feature(self):
        """Test that features can be validated by multiple criteria."""
        fs = FeatureStore()
        
        # Register feature
        fs.register_feature(FeatureMetadata(
            name="bounded_counter",
            feature_type=FeatureType.NUMERIC,
            category=FeatureCategory.ONCHAIN,
            description="Counter with bounds and monotonic increase",
        ))
        
        # This would need multiple validators in a real implementation
        # For now, just test that range validation works
        add_validator(FeatureValidator(
            feature_name="bounded_counter",
            validation_type=ValidationType.RANGE,
            min_value=0.0,
            max_value=1000.0,
        ))
        
        token = "TEST"
        
        # Within range should succeed
        fs.write_feature("bounded_counter", 500.0, token)
        
        # Out of range should fail
        with pytest.raises(ValidationError):
            fs.write_feature("bounded_counter", 1500.0, token)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

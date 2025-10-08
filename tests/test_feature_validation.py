"""Tests for feature validation guardrails."""

import pytest
import time
from src.core.feature_validation import (
    FeatureValidator,
    ValidationType,
    MonotonicDirection,
    ValidationResult,
    ValidationError,
    validate_feature,
    validate_features_batch,
    add_validator,
    get_validator,
    FEATURE_VALIDATORS,
)


class TestRangeValidation:
    """Test range validation."""
    
    def test_range_validation_within_bounds(self):
        """Test value within valid range."""
        validator = FeatureValidator(
            feature_name="test_feature",
            validation_type=ValidationType.RANGE,
            min_value=0.0,
            max_value=100.0,
        )
        
        result = validator.validate(50.0)
        assert result.is_valid
        assert result.error_message is None
    
    def test_range_validation_below_min(self):
        """Test value below minimum."""
        validator = FeatureValidator(
            feature_name="test_feature",
            validation_type=ValidationType.RANGE,
            min_value=0.0,
            max_value=100.0,
        )
        
        result = validator.validate(-5.0)
        assert not result.is_valid
        assert "below min" in result.error_message
    
    def test_range_validation_above_max(self):
        """Test value above maximum."""
        validator = FeatureValidator(
            feature_name="test_feature",
            validation_type=ValidationType.RANGE,
            min_value=0.0,
            max_value=100.0,
        )
        
        result = validator.validate(150.0)
        assert not result.is_valid
        assert "above max" in result.error_message
    
    def test_range_validation_at_boundaries(self):
        """Test values at exact boundaries."""
        validator = FeatureValidator(
            feature_name="test_feature",
            validation_type=ValidationType.RANGE,
            min_value=0.0,
            max_value=100.0,
        )
        
        # Test minimum boundary
        result = validator.validate(0.0)
        assert result.is_valid
        
        # Test maximum boundary
        result = validator.validate(100.0)
        assert result.is_valid
    
    def test_range_validation_non_numeric(self):
        """Test with non-numeric value."""
        validator = FeatureValidator(
            feature_name="test_feature",
            validation_type=ValidationType.RANGE,
            min_value=0.0,
            max_value=100.0,
        )
        
        result = validator.validate("not a number")
        assert not result.is_valid
        assert "not numeric" in result.error_message


class TestMonotonicValidation:
    """Test monotonic validation."""
    
    def test_monotonic_increasing(self):
        """Test increasing monotonic validation."""
        validator = FeatureValidator(
            feature_name="test_feature",
            validation_type=ValidationType.MONOTONIC,
            monotonic_direction=MonotonicDirection.INCREASING,
        )
        
        history = [(1.0, 10.0), (2.0, 15.0), (3.0, 20.0)]
        result = validator.validate(25.0, history=history)
        assert result.is_valid
    
    def test_monotonic_increasing_violation(self):
        """Test increasing monotonic violation."""
        validator = FeatureValidator(
            feature_name="test_feature",
            validation_type=ValidationType.MONOTONIC,
            monotonic_direction=MonotonicDirection.INCREASING,
        )
        
        history = [(1.0, 10.0), (2.0, 15.0), (3.0, 20.0)]
        result = validator.validate(18.0, history=history)
        assert not result.is_valid
        assert "Expected increasing sequence" in result.error_message
    
    def test_monotonic_decreasing(self):
        """Test decreasing monotonic validation."""
        validator = FeatureValidator(
            feature_name="test_feature",
            validation_type=ValidationType.MONOTONIC,
            monotonic_direction=MonotonicDirection.DECREASING,
        )
        
        history = [(1.0, 100.0), (2.0, 80.0), (3.0, 60.0)]
        result = validator.validate(40.0, history=history)
        assert result.is_valid
    
    def test_monotonic_decreasing_violation(self):
        """Test decreasing monotonic violation."""
        validator = FeatureValidator(
            feature_name="test_feature",
            validation_type=ValidationType.MONOTONIC,
            monotonic_direction=MonotonicDirection.DECREASING,
        )
        
        history = [(1.0, 100.0), (2.0, 80.0), (3.0, 60.0)]
        result = validator.validate(70.0, history=history)
        assert not result.is_valid
        assert "Expected decreasing sequence" in result.error_message
    
    def test_monotonic_strictly_increasing(self):
        """Test strictly increasing monotonic validation."""
        validator = FeatureValidator(
            feature_name="test_feature",
            validation_type=ValidationType.MONOTONIC,
            monotonic_direction=MonotonicDirection.STRICTLY_INCREASING,
        )
        
        history = [(1.0, 10.0), (2.0, 15.0), (3.0, 20.0)]
        result = validator.validate(25.0, history=history)
        assert result.is_valid
        
        # Equal value should fail
        result = validator.validate(20.0, history=history)
        assert not result.is_valid
    
    def test_monotonic_insufficient_history(self):
        """Test monotonic with insufficient history."""
        validator = FeatureValidator(
            feature_name="test_feature",
            validation_type=ValidationType.MONOTONIC,
            monotonic_direction=MonotonicDirection.INCREASING,
        )
        
        # Empty history
        result = validator.validate(10.0, history=[])
        assert result.is_valid
        assert len(result.warnings) > 0
        
        # Single value in history
        result = validator.validate(10.0, history=[(1.0, 5.0)])
        assert result.is_valid
        assert len(result.warnings) > 0


class TestFreshnessValidation:
    """Test freshness validation."""
    
    def test_freshness_validation_fresh_data(self):
        """Test with fresh data."""
        validator = FeatureValidator(
            feature_name="test_feature",
            validation_type=ValidationType.FRESHNESS,
            max_age_seconds=60.0,
        )
        
        current_time = time.time()
        result = validator.validate(100.0, timestamp=current_time - 10)
        assert result.is_valid
    
    def test_freshness_validation_stale_data(self):
        """Test with stale data."""
        validator = FeatureValidator(
            feature_name="test_feature",
            validation_type=ValidationType.FRESHNESS,
            max_age_seconds=60.0,
        )
        
        current_time = time.time()
        result = validator.validate(100.0, timestamp=current_time - 120)
        assert not result.is_valid
        assert "exceeds max age" in result.error_message
    
    def test_freshness_validation_approaching_threshold(self):
        """Test warning when approaching staleness threshold."""
        validator = FeatureValidator(
            feature_name="test_feature",
            validation_type=ValidationType.FRESHNESS,
            max_age_seconds=100.0,
        )
        
        current_time = time.time()
        # 90 seconds old (90% of 100s threshold)
        result = validator.validate(100.0, timestamp=current_time - 90)
        assert result.is_valid
        assert len(result.warnings) > 0
        assert "approaching staleness" in result.warnings[0]
    
    def test_freshness_validation_missing_timestamp(self):
        """Test with missing timestamp."""
        validator = FeatureValidator(
            feature_name="test_feature",
            validation_type=ValidationType.FRESHNESS,
            max_age_seconds=60.0,
        )
        
        result = validator.validate(100.0, timestamp=None)
        assert not result.is_valid
        assert "Timestamp required" in result.error_message


class TestNullValidation:
    """Test null validation."""
    
    def test_null_validation_nullable_allowed(self):
        """Test None with nullable=True."""
        validator = FeatureValidator(
            feature_name="test_feature",
            validation_type=ValidationType.RANGE,
            nullable=True,
            required=False,
        )
        
        result = validator.validate(None)
        assert result.is_valid
    
    def test_null_validation_not_nullable(self):
        """Test None with nullable=False."""
        validator = FeatureValidator(
            feature_name="test_feature",
            validation_type=ValidationType.RANGE,
            nullable=False,
        )
        
        result = validator.validate(None)
        assert not result.is_valid
        assert "cannot be null" in result.error_message
    
    def test_null_validation_required(self):
        """Test None with required=True."""
        validator = FeatureValidator(
            feature_name="test_feature",
            validation_type=ValidationType.RANGE,
            nullable=True,
            required=True,
        )
        
        result = validator.validate(None)
        assert not result.is_valid
        assert "required" in result.error_message


class TestEnumValidation:
    """Test enum validation."""
    
    def test_enum_validation_valid_value(self):
        """Test with valid enum value."""
        validator = FeatureValidator(
            feature_name="test_feature",
            validation_type=ValidationType.ENUM,
            allowed_values=["red", "green", "blue"],
        )
        
        result = validator.validate("green")
        assert result.is_valid
    
    def test_enum_validation_invalid_value(self):
        """Test with invalid enum value."""
        validator = FeatureValidator(
            feature_name="test_feature",
            validation_type=ValidationType.ENUM,
            allowed_values=["red", "green", "blue"],
        )
        
        result = validator.validate("yellow")
        assert not result.is_valid
        assert "not in allowed values" in result.error_message
    
    def test_enum_validation_boolean(self):
        """Test enum with boolean values."""
        validator = FeatureValidator(
            feature_name="flagged",
            validation_type=ValidationType.ENUM,
            allowed_values=[True, False],
        )
        
        result = validator.validate(True)
        assert result.is_valid
        
        result = validator.validate(False)
        assert result.is_valid


class TestCustomValidation:
    """Test custom validation."""
    
    def test_custom_validation_success(self):
        """Test custom validator that passes."""
        def custom_check(value):
            return value % 2 == 0, None if value % 2 == 0 else "Value must be even"
        
        validator = FeatureValidator(
            feature_name="test_feature",
            validation_type=ValidationType.CUSTOM,
            custom_validator=custom_check,
        )
        
        result = validator.validate(10)
        assert result.is_valid
    
    def test_custom_validation_failure(self):
        """Test custom validator that fails."""
        def custom_check(value):
            return value % 2 == 0, None if value % 2 == 0 else "Value must be even"
        
        validator = FeatureValidator(
            feature_name="test_feature",
            validation_type=ValidationType.CUSTOM,
            custom_validator=custom_check,
        )
        
        result = validator.validate(11)
        assert not result.is_valid
        assert "Value must be even" in result.error_message


class TestBatchValidation:
    """Test batch validation."""
    
    def test_batch_validation_all_valid(self):
        """Test batch validation with all valid features."""
        features = {
            "gem_score": 85.0,
            "confidence": 0.9,
            "sentiment_score": 0.5,
        }
        
        is_valid, errors, warnings = validate_features_batch(
            features,
            raise_on_error=False
        )
        
        assert is_valid
        assert len(errors) == 0
    
    def test_batch_validation_with_errors(self):
        """Test batch validation with invalid features."""
        features = {
            "gem_score": 150.0,  # Above max
            "confidence": 1.5,   # Above max
            "sentiment_score": 0.5,
        }
        
        is_valid, errors, warnings = validate_features_batch(
            features,
            raise_on_error=False
        )
        
        assert not is_valid
        assert len(errors) > 0
    
    def test_batch_validation_raise_on_error(self):
        """Test batch validation raises exception."""
        features = {
            "gem_score": 150.0,  # Invalid
        }
        
        with pytest.raises(ValidationError) as exc_info:
            validate_features_batch(features, raise_on_error=True)
        
        assert len(exc_info.value.errors) > 0
    
    def test_batch_validation_missing_required(self):
        """Test batch validation with missing required features."""
        features = {
            "sentiment_score": 0.5,
        }
        
        is_valid, errors, warnings = validate_features_batch(
            features,
            raise_on_error=False
        )
        
        assert not is_valid
        # Should have errors for missing required features
        assert any("gem_score" in err for err in errors)
        assert any("confidence" in err for err in errors)


class TestValidatorRegistry:
    """Test validator registration and retrieval."""
    
    def test_get_registered_validator(self):
        """Test getting a pre-registered validator."""
        validator = get_validator("gem_score")
        assert validator is not None
        assert validator.feature_name == "gem_score"
    
    def test_get_unregistered_validator(self):
        """Test getting an unregistered validator."""
        validator = get_validator("nonexistent_feature")
        assert validator is None
    
    def test_add_custom_validator(self):
        """Test adding a custom validator."""
        custom_validator = FeatureValidator(
            feature_name="my_custom_feature",
            validation_type=ValidationType.RANGE,
            min_value=0.0,
            max_value=10.0,
        )
        
        add_validator(custom_validator)
        
        retrieved = get_validator("my_custom_feature")
        assert retrieved is not None
        assert retrieved.feature_name == "my_custom_feature"
        assert retrieved.min_value == 0.0
        assert retrieved.max_value == 10.0


class TestPreConfiguredValidators:
    """Test pre-configured validators."""
    
    def test_gem_score_validator(self):
        """Test gem_score validator."""
        result = validate_feature("gem_score", 75.0)
        assert result.is_valid
        
        result = validate_feature("gem_score", 150.0)
        assert not result.is_valid
    
    def test_confidence_validator(self):
        """Test confidence validator."""
        result = validate_feature("confidence", 0.85)
        assert result.is_valid
        
        result = validate_feature("confidence", 1.5)
        assert not result.is_valid
    
    def test_sentiment_score_validator(self):
        """Test sentiment_score validator."""
        result = validate_feature("sentiment_score", 0.0)
        assert result.is_valid
        
        result = validate_feature("sentiment_score", -0.5)
        assert result.is_valid
        
        result = validate_feature("sentiment_score", 0.8)
        assert result.is_valid
        
        result = validate_feature("sentiment_score", -1.5)
        assert not result.is_valid
        
        result = validate_feature("sentiment_score", 1.5)
        assert not result.is_valid
    
    def test_price_validator(self):
        """Test price_usd validator."""
        result = validate_feature("price_usd", 100.50)
        assert result.is_valid
        
        result = validate_feature("price_usd", -10.0)
        assert not result.is_valid


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

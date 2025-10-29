"""Feature validation guardrails for the unified feature store.

Provides validators for:
- Range checks (min/max values)
- Monotonic expectations (increasing/decreasing sequences)
- Freshness thresholds (data staleness)
- Null policies
- Custom validators

This prevents silent poisoning of model inputs by enforcing data quality invariants.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

# Import metrics (gracefully handle if not available)
try:
    from src.core.metrics import (
        record_validation_failure,
        record_validation_warning,
        record_validation_success,
    )
    METRICS_AVAILABLE = True
except ImportError:
    METRICS_AVAILABLE = False
    
    def record_validation_failure(*args, **kwargs):
        pass
    
    def record_validation_warning(*args, **kwargs):
        pass
    
    def record_validation_success(*args, **kwargs):
        pass


class ValidationType(Enum):
    """Types of validation rules."""
    RANGE = "range"
    MONOTONIC = "monotonic"
    FRESHNESS = "freshness"
    NON_NULL = "non_null"
    ENUM = "enum"
    REGEX = "regex"
    CUSTOM = "custom"


class MonotonicDirection(Enum):
    """Direction for monotonic validators."""
    INCREASING = "increasing"
    DECREASING = "decreasing"
    STRICTLY_INCREASING = "strictly_increasing"
    STRICTLY_DECREASING = "strictly_decreasing"


class ValidationError(Exception):
    """Exception raised when feature validation fails."""
    
    def __init__(self, errors: List[str]):
        """Initialize validation error.
        
        Args:
            errors: List of validation error messages
        """
        self.errors = errors
        super().__init__(f"Validation failed: {'; '.join(errors)}")


@dataclass
class ValidationResult:
    """Result of a validation check."""
    
    is_valid: bool
    error_message: Optional[str] = None
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FeatureValidator:
    """Validation rules for a feature.
    
    Supports multiple validation types:
    - RANGE: Min/max value constraints
    - MONOTONIC: Ensures values follow increasing/decreasing pattern
    - FRESHNESS: Ensures data is recent enough
    - NON_NULL: Ensures value is not None
    - ENUM: Value must be in allowed set
    - CUSTOM: User-defined validation function
    """
    
    feature_name: str
    validation_type: ValidationType
    
    # Range validation
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    
    # Enum validation
    allowed_values: Optional[List[Any]] = None
    
    # Monotonic validation
    monotonic_direction: Optional[MonotonicDirection] = None
    monotonic_window: int = 10  # Number of values to check
    
    # Freshness validation
    max_age_seconds: Optional[float] = None
    
    # General options
    required: bool = False
    nullable: bool = True
    custom_validator: Optional[Callable[[Any], Tuple[bool, Optional[str]]]] = None
    
    # Metadata
    description: Optional[str] = None
    severity: str = "error"  # "error" or "warning"
    
    def _check_null_validation(self, value: Any) -> Optional[ValidationResult]:
        """Check if null value is valid. Returns ValidationResult if validation should end, None otherwise."""
        if value is None:
            if not self.nullable:
                record_validation_failure(self.feature_name, "null_check", self.severity)
                return ValidationResult(
                    is_valid=False,
                    error_message=f"{self.feature_name} cannot be null"
                )
            if self.required:
                record_validation_failure(self.feature_name, "required_check", self.severity)
                return ValidationResult(
                    is_valid=False,
                    error_message=f"{self.feature_name} is required but got None"
                )
            # None is acceptable
            record_validation_success(self.feature_name)
            return ValidationResult(is_valid=True)
        return None
    
    def _perform_type_validation(
        self,
        value: Any,
        timestamp: Optional[float],
        history: Optional[List[Tuple[float, Any]]],
    ) -> ValidationResult:
        """Perform validation based on type."""
        validators = {
            ValidationType.RANGE: lambda: self._validate_range(value),
            ValidationType.MONOTONIC: lambda: self._validate_monotonic(value, history),
            ValidationType.FRESHNESS: lambda: self._validate_freshness(timestamp),
            ValidationType.NON_NULL: lambda: ValidationResult(is_valid=True),
            ValidationType.ENUM: lambda: self._validate_enum(value),
            ValidationType.CUSTOM: lambda: self._validate_custom(value),
        }
        
        validator = validators.get(self.validation_type)
        if validator is None:
            return ValidationResult(is_valid=True)
        
        return validator()
    
    def validate(
        self,
        value: Any,
        timestamp: Optional[float] = None,
        history: Optional[List[Tuple[float, Any]]] = None,
    ) -> ValidationResult:
        """Validate a feature value.
        
        Args:
            value: Value to validate
            timestamp: Timestamp of the value (for freshness checks)
            history: Historical values as list of (timestamp, value) tuples
        
        Returns:
            ValidationResult with validation outcome
        """
        # Check if value is None
        null_result = self._check_null_validation(value)
        if null_result is not None:
            return null_result
        
        # Perform validation based on type
        result = self._perform_type_validation(value, timestamp, history)
        
        # Record metrics
        if result.is_valid:
            record_validation_success(self.feature_name)
        else:
            record_validation_failure(
                self.feature_name,
                self.validation_type.value,
                self.severity
            )
        
        if result.warnings:
            for _ in result.warnings:
                record_validation_warning(
                    self.feature_name,
                    self.validation_type.value
                )
        
        return result
    
    def _validate_range(self, value: Any) -> ValidationResult:
        """Validate value is within range."""
        try:
            numeric_value = float(value)
        except (TypeError, ValueError):
            return ValidationResult(
                is_valid=False,
                error_message=f"{self.feature_name}={value} is not numeric"
            )
        
        if self.min_value is not None and numeric_value < self.min_value:
            return ValidationResult(
                is_valid=False,
                error_message=f"{self.feature_name}={numeric_value} below min {self.min_value}"
            )
        
        if self.max_value is not None and numeric_value > self.max_value:
            return ValidationResult(
                is_valid=False,
                error_message=f"{self.feature_name}={numeric_value} above max {self.max_value}"
            )
        
        return ValidationResult(is_valid=True)
    
    def _check_monotonic_sequence(
        self,
        sequence: List[float],
        direction: MonotonicDirection,
    ) -> Optional[str]:
        """Check if sequence follows monotonic direction.
        
        Returns error message if validation fails, None otherwise.
        """
        checkers = {
            MonotonicDirection.INCREASING: lambda i: sequence[i+1] < sequence[i],
            MonotonicDirection.DECREASING: lambda i: sequence[i+1] > sequence[i],
            MonotonicDirection.STRICTLY_INCREASING: lambda i: sequence[i+1] <= sequence[i],
            MonotonicDirection.STRICTLY_DECREASING: lambda i: sequence[i+1] >= sequence[i],
        }
        
        checker = checkers.get(direction)
        if checker is None:
            return None
        
        for i in range(len(sequence) - 1):
            if checker(i):
                direction_name = direction.name.lower().replace('_', ' ')
                return f"{self.feature_name}: Expected {direction_name} sequence, but {sequence[i+1]} violates at position {i+1}"
        
        return None
    
    def _validate_monotonic(
        self,
        value: Any,
        history: Optional[List[Tuple[float, Any]]] = None
    ) -> ValidationResult:
        """Validate value follows monotonic pattern."""
        if not history or len(history) < 2:
            # Not enough history to validate
            return ValidationResult(
                is_valid=True,
                warnings=["Insufficient history for monotonic validation"]
            )
        
        if not self.monotonic_direction:
            return ValidationResult(is_valid=True)
        
        try:
            numeric_value = float(value)
        except (TypeError, ValueError):
            return ValidationResult(
                is_valid=False,
                error_message=f"{self.feature_name}={value} is not numeric"
            )
        
        # Get recent history
        recent_history = sorted(history, key=lambda x: x[0], reverse=True)[:self.monotonic_window]
        recent_history = sorted(recent_history, key=lambda x: x[0])  # Sort ascending
        
        # Add current value
        sequence = [float(v) for _, v in recent_history] + [numeric_value]
        
        # Check monotonic property
        error_message = self._check_monotonic_sequence(sequence, self.monotonic_direction)
        if error_message:
            return ValidationResult(is_valid=False, error_message=error_message)
        
        return ValidationResult(is_valid=True)
        
        return ValidationResult(is_valid=True)
    
    def _validate_freshness(self, timestamp: Optional[float]) -> ValidationResult:
        """Validate data freshness."""
        if timestamp is None:
            return ValidationResult(
                is_valid=False,
                error_message=f"{self.feature_name}: Timestamp required for freshness validation"
            )
        
        if self.max_age_seconds is None:
            return ValidationResult(is_valid=True)
        
        age = time.time() - timestamp
        
        if age > self.max_age_seconds:
            return ValidationResult(
                is_valid=False,
                error_message=f"{self.feature_name}: Data is {age:.1f}s old, exceeds max age {self.max_age_seconds}s"
            )
        
        # Warning if approaching staleness (80% of threshold)
        warnings = []
        if age > self.max_age_seconds * 0.8:
            warnings.append(f"Data age {age:.1f}s approaching staleness threshold {self.max_age_seconds}s")
        
        return ValidationResult(is_valid=True, warnings=warnings)
    
    def _validate_enum(self, value: Any) -> ValidationResult:
        """Validate value is in allowed set."""
        if self.allowed_values is None:
            return ValidationResult(is_valid=True)
        
        if value not in self.allowed_values:
            return ValidationResult(
                is_valid=False,
                error_message=f"{self.feature_name}={value} not in allowed values {self.allowed_values}"
            )
        
        return ValidationResult(is_valid=True)
    
    def _validate_custom(self, value: Any) -> ValidationResult:
        """Run custom validation function."""
        if self.custom_validator is None:
            return ValidationResult(is_valid=True)
        
        try:
            is_valid, error_msg = self.custom_validator(value)
            return ValidationResult(
                is_valid=is_valid,
                error_message=error_msg
            )
        except Exception as e:
            return ValidationResult(
                is_valid=False,
                error_message=f"Custom validation failed: {str(e)}"
            )


# =============================================================================
# Pre-configured Validators for Common Features
# =============================================================================

# Standard feature validators
FEATURE_VALIDATORS: Dict[str, FeatureValidator] = {
    # Scoring features
    "gem_score": FeatureValidator(
        feature_name="gem_score",
        validation_type=ValidationType.RANGE,
        min_value=0.0,
        max_value=100.0,
        required=True,
        nullable=False,
        description="GemScore must be between 0 and 100"
    ),
    "confidence": FeatureValidator(
        feature_name="confidence",
        validation_type=ValidationType.RANGE,
        min_value=0.0,
        max_value=1.0,
        required=True,
        nullable=False,
        description="Confidence must be between 0 and 1"
    ),
    
    # Market features
    "price_usd": FeatureValidator(
        feature_name="price_usd",
        validation_type=ValidationType.RANGE,
        min_value=0.0,
        required=False,
        nullable=False,
        description="Price must be positive"
    ),
    "volume_24h_usd": FeatureValidator(
        feature_name="volume_24h_usd",
        validation_type=ValidationType.RANGE,
        min_value=0.0,
        required=False,
        nullable=False,
        description="Volume must be non-negative"
    ),
    "market_cap_usd": FeatureValidator(
        feature_name="market_cap_usd",
        validation_type=ValidationType.RANGE,
        min_value=0.0,
        required=False,
        description="Market cap must be non-negative"
    ),
    
    # Liquidity features
    "liquidity_usd": FeatureValidator(
        feature_name="liquidity_usd",
        validation_type=ValidationType.RANGE,
        min_value=0.0,
        required=False,
        description="Liquidity must be non-negative"
    ),
    
    # Sentiment features
    "sentiment_score": FeatureValidator(
        feature_name="sentiment_score",
        validation_type=ValidationType.RANGE,
        min_value=-1.0,
        max_value=1.0,
        required=False,
        description="Sentiment score must be between -1 and 1"
    ),
    
    # Quality features
    "quality_score": FeatureValidator(
        feature_name="quality_score",
        validation_type=ValidationType.RANGE,
        min_value=0.0,
        max_value=1.0,
        required=False,
        description="Quality score must be between 0 and 1"
    ),
    
    # Boolean features
    "flagged": FeatureValidator(
        feature_name="flagged",
        validation_type=ValidationType.ENUM,
        allowed_values=[True, False],
        required=False,
        nullable=False,
        description="Flagged must be boolean"
    ),
}


def add_validator(validator: FeatureValidator) -> None:
    """Register a custom validator.
    
    Args:
        validator: Validator to register
    """
    FEATURE_VALIDATORS[validator.feature_name] = validator


def get_validator(feature_name: str) -> Optional[FeatureValidator]:
    """Get validator for a feature.
    
    Args:
        feature_name: Name of the feature
    
    Returns:
        Validator if registered, None otherwise
    """
    return FEATURE_VALIDATORS.get(feature_name)


def validate_feature(
    feature_name: str,
    value: Any,
    timestamp: Optional[float] = None,
    history: Optional[List[Tuple[float, Any]]] = None,
) -> ValidationResult:
    """Validate a feature value using registered validator.
    
    Args:
        feature_name: Name of the feature
        value: Value to validate
        timestamp: Timestamp of the value
        history: Historical values for monotonic checks
    
    Returns:
        ValidationResult
    """
    validator = get_validator(feature_name)
    if validator is None:
        # No validator registered - allow by default
        return ValidationResult(is_valid=True)
    
    return validator.validate(value, timestamp, history)


def validate_features_batch(
    features: Dict[str, Any],
    timestamp: Optional[float] = None,
    histories: Optional[Dict[str, List[Tuple[float, Any]]]] = None,
    raise_on_error: bool = True,
) -> Tuple[bool, List[str], List[str]]:
    """Validate multiple features at once.
    
    Args:
        features: Dictionary of feature_name -> value
        timestamp: Timestamp for all features
        histories: Dictionary of feature_name -> historical values
        raise_on_error: Whether to raise ValidationError on failure
    
    Returns:
        Tuple of (all_valid, errors, warnings)
    
    Raises:
        ValidationError: If validation fails and raise_on_error is True
    """
    errors = []
    warnings = []
    
    for feature_name, value in features.items():
        history = histories.get(feature_name) if histories else None
        result = validate_feature(feature_name, value, timestamp, history)
        
        if not result.is_valid:
            errors.append(result.error_message or f"{feature_name} validation failed")
        
        warnings.extend(result.warnings)
    
    # Check for missing required features
    for validator in FEATURE_VALIDATORS.values():
        if validator.required and validator.feature_name not in features:
            errors.append(f"Required feature {validator.feature_name} missing")
    
    if errors and raise_on_error:
        raise ValidationError(errors)
    
    return (len(errors) == 0, errors, warnings)

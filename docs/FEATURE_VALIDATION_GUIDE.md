# Feature Validation Guardrails

## Overview

The Feature Validation system provides **data quality guardrails** to prevent silent poisoning of model inputs. It enforces invariants at write time through multiple validation strategies.

## Key Features

✅ **Range Validation** - Enforce min/max value constraints  
✅ **Monotonic Validation** - Ensure values follow increasing/decreasing patterns  
✅ **Freshness Validation** - Reject stale data based on age thresholds  
✅ **Null Policy Enforcement** - Control nullable and required fields  
✅ **Enum Validation** - Restrict values to allowed sets  
✅ **Custom Validators** - Define application-specific rules  
✅ **Prometheus Metrics** - Track validation failures and warnings  
✅ **Batch Validation** - Validate multiple features efficiently  

---

## Quick Start

### Basic Usage

```python
from src.core.feature_store import FeatureStore, FeatureMetadata, FeatureType, FeatureCategory
from src.core.feature_validation import ValidationError

# Create feature store with validation enabled (default)
fs = FeatureStore(enable_validation=True)

# Register a feature
fs.register_feature(FeatureMetadata(
    name="price_usd",
    feature_type=FeatureType.NUMERIC,
    category=FeatureCategory.MARKET,
    description="Token price in USD",
))

# Write valid data - succeeds
fs.write_feature("price_usd", 100.50, "ETH")

# Write invalid data - raises ValidationError
try:
    fs.write_feature("price_usd", -10.0, "ETH")  # Negative price
except ValidationError as e:
    print(f"Validation failed: {e.errors}")
```

---

## Validation Types

### 1. Range Validation

Ensures numeric values fall within specified bounds.

```python
from src.core.feature_validation import FeatureValidator, ValidationType

validator = FeatureValidator(
    feature_name="gem_score",
    validation_type=ValidationType.RANGE,
    min_value=0.0,
    max_value=100.0,
    nullable=False,
    required=True,
)

# Valid
result = validator.validate(75.0)
assert result.is_valid

# Invalid - above max
result = validator.validate(150.0)
assert not result.is_valid
```

**Pre-configured range validators:**
- `gem_score`: 0-100
- `confidence`: 0-1
- `sentiment_score`: -1 to 1
- `price_usd`: >= 0
- `volume_24h_usd`: >= 0
- `liquidity_usd`: >= 0

### 2. Monotonic Validation

Ensures time-series values follow expected patterns (e.g., cumulative counters should only increase).

```python
from src.core.feature_validation import MonotonicDirection

validator = FeatureValidator(
    feature_name="total_transactions",
    validation_type=ValidationType.MONOTONIC,
    monotonic_direction=MonotonicDirection.STRICTLY_INCREASING,
    monotonic_window=10,  # Check last 10 values
)

# Historical values: [(timestamp, value), ...]
history = [(1.0, 100), (2.0, 150), (3.0, 200)]

# Valid - continues increasing
result = validator.validate(250, history=history)
assert result.is_valid

# Invalid - decreased
result = validator.validate(180, history=history)
assert not result.is_valid
```

**Monotonic directions:**
- `INCREASING` - Values >= previous value
- `DECREASING` - Values <= previous value
- `STRICTLY_INCREASING` - Values > previous value
- `STRICTLY_DECREASING` - Values < previous value

### 3. Freshness Validation

Rejects data older than specified threshold.

```python
import time

validator = FeatureValidator(
    feature_name="orderflow_imbalance",
    validation_type=ValidationType.FRESHNESS,
    max_age_seconds=60.0,  # Data must be less than 60 seconds old
)

current_time = time.time()

# Valid - 30 seconds old
result = validator.validate(0.75, timestamp=current_time - 30)
assert result.is_valid

# Invalid - 120 seconds old
result = validator.validate(0.75, timestamp=current_time - 120)
assert not result.is_valid

# Warning - approaching threshold (90 seconds, 90% of 100s)
validator.max_age_seconds = 100.0
result = validator.validate(0.75, timestamp=current_time - 90)
assert result.is_valid
assert len(result.warnings) > 0  # Warning issued
```

### 4. Null Validation

Controls nullable and required fields.

```python
validator = FeatureValidator(
    feature_name="confidence",
    validation_type=ValidationType.NON_NULL,
    nullable=False,  # Cannot be None
    required=True,   # Must be present
)

# Invalid - None not allowed
result = validator.validate(None)
assert not result.is_valid
```

### 5. Enum Validation

Restricts values to allowed set.

```python
validator = FeatureValidator(
    feature_name="risk_level",
    validation_type=ValidationType.ENUM,
    allowed_values=["low", "medium", "high"],
)

# Valid
result = validator.validate("medium")
assert result.is_valid

# Invalid
result = validator.validate("critical")
assert not result.is_valid
```

### 6. Custom Validators

Define application-specific validation logic.

```python
def validate_even_number(value):
    """Custom validator: must be even."""
    if value % 2 == 0:
        return True, None
    else:
        return False, f"Value {value} must be even"

validator = FeatureValidator(
    feature_name="batch_size",
    validation_type=ValidationType.CUSTOM,
    custom_validator=validate_even_number,
)

result = validator.validate(10)
assert result.is_valid

result = validator.validate(11)
assert not result.is_valid
```

---

## Integration with FeatureStore

### Automatic Validation

Validation is **automatically applied** when writing features:

```python
fs = FeatureStore(enable_validation=True)

# Register feature with metadata
fs.register_feature(FeatureMetadata(
    name="gem_score",
    feature_type=FeatureType.NUMERIC,
    category=FeatureCategory.SCORING,
    description="GemScore",
))

# Write feature - automatically validated
try:
    fs.write_feature("gem_score", 150.0, "PEPE")  # Invalid - above max
except ValidationError as e:
    print(f"Validation errors: {e.errors}")
```

### Batch Validation

Validate multiple features efficiently:

```python
features = [
    ("gem_score", 75.0, "PEPE"),
    ("confidence", 0.85, "PEPE"),
    ("sentiment_score", 0.5, "PEPE"),
]

try:
    fs.write_features_batch(features)
except ValidationError as e:
    print(f"Batch validation failed: {e.errors}")
```

### Disabling Validation

For performance-critical paths or trusted data:

```python
# Disable globally
fs = FeatureStore(enable_validation=False)

# Or skip for specific write
fs.write_feature("price_usd", 100.0, "ETH", skip_validation=True)
```

---

## Custom Validators

### Registering Custom Validators

```python
from src.core.feature_validation import add_validator, FeatureValidator

# Define custom validator
custom_validator = FeatureValidator(
    feature_name="volatility_index",
    validation_type=ValidationType.RANGE,
    min_value=0.0,
    max_value=200.0,
    description="Volatility index must be 0-200",
)

# Register it
add_validator(custom_validator)

# Now it's automatically applied
result = validate_feature("volatility_index", 150.0)
assert result.is_valid
```

### Complex Validation Logic

Combine multiple validation types:

```python
from src.core.feature_validation import ValidationResult

def complex_validator(value):
    """Multi-condition validator."""
    # Must be positive
    if value <= 0:
        return False, "Value must be positive"
    
    # Must be less than 1000
    if value >= 1000:
        return False, "Value must be less than 1000"
    
    # Must not be in blacklisted range
    if 100 <= value <= 200:
        return False, "Value in blacklisted range 100-200"
    
    return True, None

validator = FeatureValidator(
    feature_name="custom_metric",
    validation_type=ValidationType.CUSTOM,
    custom_validator=complex_validator,
)
```

---

## Monitoring and Metrics

### Prometheus Metrics

The system exports Prometheus metrics for monitoring:

```python
from src.core.metrics import (
    FEATURE_VALIDATION_FAILURES,
    FEATURE_VALIDATION_WARNINGS,
    FEATURE_VALIDATION_SUCCESS,
)

# Metrics are automatically recorded during validation
# View them at your Prometheus endpoint

# Example queries:
# - rate(feature_validation_failures_total[5m])
# - feature_validation_success_total
# - feature_validation_warnings_total{feature_name="gem_score"}
```

**Available metrics:**
- `feature_validation_failures_total` - Total validation failures
- `feature_validation_warnings_total` - Total validation warnings
- `feature_validation_success_total` - Total successful validations
- `feature_value_distribution` - Distribution of feature values
- `feature_freshness_seconds` - Age of feature data
- `feature_write_duration_seconds` - Write operation duration

### Validation Statistics

Get validation stats from the feature store:

```python
stats = fs.get_validation_stats()
print(f"Total validations: {stats['total_validations']}")
print(f"Failures: {stats['validation_failures']}")
print(f"Warnings: {stats['validation_warnings']}")

# Also included in general stats
all_stats = fs.get_stats()
print(all_stats['validation_stats'])
```

---

## Best Practices

### 1. Define Validators Early

Register validators when setting up your feature store:

```python
def setup_feature_store():
    fs = FeatureStore(enable_validation=True)
    
    # Register all features with validators
    for feature in MY_FEATURES:
        fs.register_feature(feature.metadata)
        add_validator(feature.validator)
    
    return fs
```

### 2. Use Appropriate Validation Types

- **Range**: Numeric features with known bounds
- **Monotonic**: Cumulative counters, timestamps
- **Freshness**: Real-time data, time-sensitive features
- **Enum**: Categorical features with fixed values
- **Custom**: Complex business rules

### 3. Handle Validation Errors

Always handle `ValidationError` in production:

```python
try:
    fs.write_feature(name, value, token)
except ValidationError as e:
    logger.error("Feature validation failed", errors=e.errors)
    # Take corrective action
    # - Alert operators
    # - Use fallback value
    # - Skip feature
```

### 4. Monitor Validation Metrics

Set up alerts for validation failures:

```yaml
# Prometheus alert
- alert: HighFeatureValidationFailureRate
  expr: rate(feature_validation_failures_total[5m]) > 0.1
  annotations:
    summary: "High rate of feature validation failures"
```

### 5. Test Validators

Write tests for your custom validators:

```python
def test_my_custom_validator():
    result = validate_feature("my_feature", test_value)
    assert result.is_valid
    
    result = validate_feature("my_feature", invalid_value)
    assert not result.is_valid
```

---

## Performance Considerations

### Validation Overhead

- **Range validation**: ~0.01ms per feature
- **Monotonic validation**: ~0.1ms per feature (requires history lookup)
- **Freshness validation**: ~0.01ms per feature
- **Batch validation**: More efficient than individual validations

### Optimization Tips

1. **Use batch validation** for multiple features
2. **Limit monotonic window** size (default: 10 values)
3. **Disable validation** for trusted/internal data sources
4. **Cache validators** - use pre-configured validators when possible

---

## Troubleshooting

### Common Issues

**Issue**: Validation always passes even with invalid data  
**Solution**: Check that validation is enabled: `fs.enable_validation = True`

**Issue**: Monotonic validation fails with valid data  
**Solution**: Ensure history is sorted by timestamp and contains enough values

**Issue**: Freshness validation requires timestamp but none provided  
**Solution**: Always pass `timestamp` parameter for freshness checks

### Debugging

Enable debug logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Validation failures will be logged
fs.write_feature("gem_score", 150.0, "PEPE")
```

---

## API Reference

### FeatureValidator

```python
@dataclass
class FeatureValidator:
    feature_name: str
    validation_type: ValidationType
    
    # Range validation
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    
    # Enum validation
    allowed_values: Optional[List[Any]] = None
    
    # Monotonic validation
    monotonic_direction: Optional[MonotonicDirection] = None
    monotonic_window: int = 10
    
    # Freshness validation
    max_age_seconds: Optional[float] = None
    
    # General options
    required: bool = False
    nullable: bool = True
    custom_validator: Optional[Callable] = None
    description: Optional[str] = None
    severity: str = "error"
```

### Functions

**`validate_feature(feature_name, value, timestamp=None, history=None)`**  
Validate a single feature value.

**`validate_features_batch(features, timestamp=None, histories=None, raise_on_error=True)`**  
Validate multiple features at once.

**`add_validator(validator)`**  
Register a custom validator.

**`get_validator(feature_name)`**  
Retrieve a registered validator.

---

## Examples

See `examples/feature_validation_example.py` for comprehensive examples:
- Range validation
- Monotonic validation
- Freshness validation
- Custom validators
- Batch validation
- Error handling

---

## Related Documentation

- [Feature Store Implementation](FEATURE_STORE_IMPLEMENTATION.md)
- [Implementation Plan](../IMPLEMENTATION_PLAN_HIGH_PRIORITY.md)
- [GitHub Issue #28](../GITHUB_ISSUES.md)

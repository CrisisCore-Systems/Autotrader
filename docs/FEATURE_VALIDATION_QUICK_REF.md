# Feature Validation Quick Reference

## Installation

No additional dependencies required - validators are built-in.

Optional for metrics:
```bash
pip install prometheus-client
```

---

## Quick Start

```python
from src.core.feature_store import FeatureStore
from src.core.feature_validation import ValidationError

# Create feature store with validation enabled
fs = FeatureStore(enable_validation=True)

# Write features - automatically validated
try:
    fs.write_feature("gem_score", 75.0, "ETH")
except ValidationError as e:
    print(f"Validation failed: {e.errors}")
```

---

## Validation Types

### Range
```python
FeatureValidator(
    feature_name="price_usd",
    validation_type=ValidationType.RANGE,
    min_value=0.0,
    max_value=1000000.0,
)
```

### Monotonic
```python
FeatureValidator(
    feature_name="total_txs",
    validation_type=ValidationType.MONOTONIC,
    monotonic_direction=MonotonicDirection.STRICTLY_INCREASING,
    monotonic_window=10,
)
```

### Freshness
```python
FeatureValidator(
    feature_name="realtime_price",
    validation_type=ValidationType.FRESHNESS,
    max_age_seconds=60.0,
)
```

### Enum
```python
FeatureValidator(
    feature_name="status",
    validation_type=ValidationType.ENUM,
    allowed_values=["active", "paused", "stopped"],
)
```

### Custom
```python
def my_validator(value):
    return value > 0, "Must be positive"

FeatureValidator(
    feature_name="custom",
    validation_type=ValidationType.CUSTOM,
    custom_validator=my_validator,
)
```

---

## Pre-configured Validators

Already configured for common features:

| Feature | Range | Required |
|---------|-------|----------|
| `gem_score` | 0-100 | Yes |
| `confidence` | 0-1 | Yes |
| `sentiment_score` | -1 to 1 | No |
| `price_usd` | >= 0 | No |
| `volume_24h_usd` | >= 0 | No |
| `liquidity_usd` | >= 0 | No |

---

## Common Patterns

### Add Custom Validator
```python
from src.core.feature_validation import add_validator

add_validator(FeatureValidator(
    feature_name="my_feature",
    validation_type=ValidationType.RANGE,
    min_value=0.0,
    max_value=100.0,
))
```

### Batch Validation
```python
features = [
    ("gem_score", 75.0, "ETH"),
    ("confidence", 0.85, "ETH"),
]

fs.write_features_batch(features)
```

### Skip Validation
```python
# For trusted data sources
fs.write_feature("price", 100.0, "ETH", skip_validation=True)
```

### Check Statistics
```python
stats = fs.get_validation_stats()
print(f"Failures: {stats['validation_failures']}")
```

---

## Error Handling

```python
try:
    fs.write_feature("gem_score", 150.0, "ETH")
except ValidationError as e:
    # e.errors is a list of error messages
    for error in e.errors:
        print(f"Error: {error}")
```

---

## Metrics (Prometheus)

Exported metrics:
- `feature_validation_failures_total`
- `feature_validation_warnings_total`
- `feature_validation_success_total`
- `feature_value_distribution`
- `feature_freshness_seconds`

Query examples:
```promql
# Failure rate in last 5 minutes
rate(feature_validation_failures_total[5m])

# Success count by feature
feature_validation_success_total{feature_name="gem_score"}
```

---

## Testing

```python
# Unit test
def test_my_validator():
    result = validate_feature("my_feature", 50.0)
    assert result.is_valid
```

Run tests:
```bash
pytest tests/test_feature_validation.py -v
```

---

## Examples

See `examples/feature_validation_example.py` for:
- Range validation
- Monotonic validation  
- Freshness validation
- Custom validators
- Batch validation
- Error handling

Run:
```bash
python -c "import sys; sys.path.insert(0, '.'); from examples.feature_validation_example import main; main()"
```

---

## Files

| File | Purpose |
|------|---------|
| `src/core/feature_validation.py` | Validator implementations |
| `src/core/feature_store.py` | Integration with feature store |
| `src/crypto_pnd_detector/data/storage/feature_store.py` | Simple feature store with NaN/Inf validation |
| `src/core/metrics.py` | Prometheus metrics |
| `tests/test_feature_validation.py` | Unit tests |
| `tests/test_feature_validation_integration.py` | Integration tests |
| `tests/test_crypto_pnd_detector.py` | Tests for InMemoryFeatureStore validation |
| `examples/feature_validation_example.py` | Usage examples |
| `docs/FEATURE_VALIDATION_GUIDE.md` | Full documentation |

---

## InMemoryFeatureStore Validation

The crypto P&D detector uses a simplified `InMemoryFeatureStore` with basic validation:

```python
from src.crypto_pnd_detector.data.storage.feature_store import (
    InMemoryFeatureStore,
    FeatureRecord,
    FeatureValidationError,
)

# Create store with validation (enabled by default)
store = InMemoryFeatureStore(enable_validation=True)

# Put valid record
record = FeatureRecord(
    token_id="BTC",
    values={"momentum": 0.5, "volume_anomaly": 0.3}
)
store.put(record)

# Invalid record with NaN will be rejected
invalid_record = FeatureRecord(
    token_id="ETH",
    values={"momentum": float('nan')}
)
try:
    store.put(invalid_record)
except FeatureValidationError as e:
    print(f"Validation failed: {e}")
```

Validates:
- ✅ NaN values (rejected)
- ✅ Inf values (rejected)
- Can be disabled: `InMemoryFeatureStore(enable_validation=False)`

---

## Performance

Typical overhead per validation:
- Range: ~0.01ms
- Monotonic: ~0.1ms (requires history lookup)
- Freshness: ~0.01ms
- Enum: ~0.01ms
- Custom: Varies
- NaN/Inf check: ~0.001ms

Tips:
- Use batch validation for multiple features
- Limit monotonic window size (default: 10)
- Disable for trusted sources

---

## GitHub Issue

Addresses: **Issue #28 - Implement Data Validation Guardrails in Feature Store**

Status: ✅ **COMPLETE**

Features implemented:
- ✅ Range validation
- ✅ Monotonic expectations
- ✅ Freshness thresholds
- ✅ Null policies
- ✅ Enum validation
- ✅ Custom validators
- ✅ Prometheus metrics
- ✅ Comprehensive tests
- ✅ Documentation

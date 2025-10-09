# Metrics Validation Rules

Rules and patterns for metric naming and validation.

## Naming Patterns

AutoTrader enforces consistent metric naming patterns:

| Pattern | Type | Description |
|---------|------|-------------|
| `^[a-z_]+_total$` | counter | Counters must end with _total |
| `^[a-z_]+_(seconds|bytes|duration)$` | histogram | Histograms should indicate unit in name |
| `^[a-z_]+$` | labels | Labels must use snake_case |

## Validation Constraints

### Label Constraints

- **Maximum labels per metric**: N/A

**Forbidden label names**:

- `type`
- `status`
- `name`


## Deprecated Metrics

The following metrics are deprecated and will be removed in future versions:

*No deprecated metrics at this time.*


## Using the Registry

### Python Example

```python
from src.core.metrics_registry import MetricsRegistry

# Load registry
registry = MetricsRegistry()

# Validate a metric
try:
    registry.validate_metric(
        name="scan_duration_seconds",
        type="histogram",
        labels=["strategy", "status"]
    )
    print("✅ Metric is valid")
except ValueError as e:
    print(f"❌ Invalid metric: {e}")
```

### CLI Validation

```bash
# Validate all metrics in codebase
python -m src.core.metrics_registry --validate
```
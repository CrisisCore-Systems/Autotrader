# Schema Evolution and Migration Guide

## Overview

AutoTrader uses semantic versioning for output schemas to ensure compatibility and enable safe evolution.

**Current Version**: `1.0.0`

## Version Format

Schema versions follow semantic versioning: `MAJOR.MINOR.PATCH`

- **MAJOR**: Breaking changes (incompatible with previous versions)
- **MINOR**: Backward-compatible additions (new optional fields)
- **PATCH**: Bug fixes, documentation (no schema changes)

## Schema Metadata

All outputs now include schema metadata:

```json
{
  "schema_version": "1.0.0",
  "schema_type": "scan_result",
  "schema_generated_at": "2024-01-01T12:00:00Z",
  "token": "BTC",
  "gem_score": 85.0,
  ...
}
```

### Required Metadata Fields

| Field | Type | Description |
|-------|------|-------------|
| `schema_version` | string | Schema version (e.g., "1.0.0") |
| `schema_type` | string | Type of schema (e.g., "scan_result") |
| `schema_generated_at` | string | ISO 8601 timestamp of generation |

## Schema Types

| Type | Description |
|------|-------------|
| `scan_result` | Main scan output containing gem score and analysis |
| `market_snapshot` | Market data snapshot at point in time |
| `narrative_insight` | Narrative analysis results |
| `gem_score` | Detailed gem scoring breakdown |
| `safety_report` | Security and safety analysis |
| `alert` | Alert notification payload |
| `drift_detection` | Data drift detection results |
| `experiment_result` | A/B test experiment results |

## Version History

### v1.0.0 (Current) - 2024-01-01

**Initial stable schema release**

#### Scan Result Schema

Required fields:
- `token` (string): Token symbol
- `gem_score` (object): Gem score details
- `flag` (boolean): Whether token is flagged as gem
- `schema_version` (string): Schema version
- `schema_type` (string): Schema type

Optional fields:
- `market_snapshot` (object): Market data
- `narrative` (object): Narrative analysis
- `raw_features` (object): Raw feature values
- `adjusted_features` (object): Adjusted feature values
- `safety_report` (object): Safety analysis
- `debug` (object): Debug information
- `artifact_payload` (object): Additional artifacts
- `artifact_markdown` (string): Markdown report
- `artifact_html` (string): HTML report
- `news_items` (array): Related news
- `sentiment_metrics` (object): Sentiment scores
- `technical_metrics` (object): Technical indicators
- `security_metrics` (object): Security scores
- `final_score` (number): Final calculated score
- `github_events` (array): GitHub activity
- `social_posts` (array): Social media posts
- `tokenomics_metrics` (array): Tokenomics data
- `alerts` (array): Generated alerts

## Migration Process

### 1. Check Current Version

```python
import json

with open("output.json") as f:
    data = json.load(f)

current_version = data.get("schema_version", "0.0.0")
print(f"Current version: {current_version}")
```

### 2. Validate Schema

```python
from src.core.schema_versioning import validate_output, SchemaVersionError

try:
    validate_output(data, schema_type="scan_result")
    print("✅ Valid schema")
except SchemaVersionError as e:
    print(f"❌ Invalid schema: {e}")
```

### 3. Add Schema Metadata (if missing)

```python
from src.core.schema_versioning import add_schema_metadata

# Add metadata to existing output
data = add_schema_metadata(data, schema_type="scan_result")

# Save updated output
with open("output.json", "w") as f:
    json.dump(data, f, indent=2)
```

## Compatibility

### Forward Compatibility

**Rule**: Minor and patch version bumps are forward compatible.

- v1.0.0 → v1.1.0: ✅ Safe (new optional fields only)
- v1.1.0 → v1.2.0: ✅ Safe (new optional fields only)
- v1.0.0 → v2.0.0: ❌ Breaking changes (migration required)

### Backward Compatibility

**Rule**: Same major version is backward compatible.

- v1.2.0 → v1.0.0: ✅ Safe (extra fields ignored)
- v2.0.0 → v1.0.0: ❌ Not supported (downgrade not allowed)

## Testing Schema Changes

### 1. Schema Diff Test

Compare outputs from different versions:

```python
from src.core.schema_versioning import get_versioner

versioner = get_versioner()

# Load old and new outputs
with open("output_old.json") as f:
    old_data = json.load(f)

with open("output_new.json") as f:
    new_data = json.load(f)

# Compare schemas
diff = versioner.compare_schemas(old_data, new_data)

print("Added fields:", diff["added_fields"])
print("Removed fields:", diff["removed_fields"])
print("Breaking changes:", diff["breaking_changes"])
```

### 2. Fixture-Based Testing

Create test fixtures for each schema version:

```python
# tests/fixtures/scan_result_v1_0_0.json
{
  "schema_version": "1.0.0",
  "schema_type": "scan_result",
  "token": "BTC",
  "gem_score": {"value": 85.0},
  "flag": true
}
```

Run tests:

```python
import pytest
from src.core.schema_versioning import validate_output

def test_scan_result_v1_0_0():
    with open("tests/fixtures/scan_result_v1_0_0.json") as f:
        data = json.load(f)
    
    # Should validate successfully
    assert validate_output(data, "scan_result")
```

## Best Practices

### For Users

1. **Always check schema version** in outputs
2. **Handle unknown fields gracefully** (forward compatibility)
3. **Don't rely on field order** (use field names)
4. **Validate critical fields** exist before using them

### For Developers

1. **Never remove required fields** without major version bump
2. **New fields should be optional** (minor version bump)
3. **Document all schema changes** in this file
4. **Add migration guide** for breaking changes
5. **Test with previous version fixtures**

### Code Example

```python
from src.core.schema_versioning import add_schema_metadata, validate_output

# When creating output
def create_scan_output(token: str, score: float) -> dict:
    data = {
        "token": token,
        "gem_score": {"value": score},
        "flag": score >= 70.0,
    }
    
    # Add schema metadata
    data = add_schema_metadata(data, schema_type="scan_result")
    
    # Validate before returning
    validate_output(data, schema_type="scan_result")
    
    return data

# When reading output
def read_scan_output(filepath: str) -> dict:
    with open(filepath) as f:
        data = json.load(f)
    
    # Validate schema
    validate_output(data, schema_type="scan_result")
    
    # Check version compatibility
    version = data.get("schema_version", "0.0.0")
    major = int(version.split('.')[0])
    
    if major != 1:
        raise ValueError(f"Incompatible schema version: {version}")
    
    return data
```

## Future Changes

### Planned for v1.1.0 (Q2 2025)

- Add `risk_score` optional field
- Add `confidence_interval` optional field
- Add `data_sources` metadata array

### Planned for v2.0.0 (Q4 2025)

- ⚠️ **Breaking**: Rename `flag` → `is_gem`
- ⚠️ **Breaking**: Restructure `gem_score` to nested object
- Add required `timestamp` field
- Remove deprecated `debug` field

## Support

### Version Support Policy

| Version | Status | Support Until | Notes |
|---------|--------|---------------|-------|
| v1.0.0  | Active | Q4 2025       | Current stable |
| v0.x.x  | Deprecated | Q1 2025   | Migrate to v1.0.0 |

### Getting Help

- Check schema version: `autotrader-scan --print-schema-version`
- Validate file: `autotrader-scan --validate-schema output.json`
- Generate migration guide: `autotrader-scan --migration-guide 1.0.0 1.1.0`

## See Also

- [Exit Code Deprecation Guide](exit_codes.py)
- [Strategy API Versioning](plugins.py)
- [Metrics Registry](metrics_registry.yaml)

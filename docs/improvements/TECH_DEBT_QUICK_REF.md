# Technical Debt Resolution - Quick Reference

**Version**: 2.0.0 | **Date**: October 8, 2025

## What Changed?

### ✅ Exit Code Deprecation (v3.0.0 removal)

**Before**:
```python
sys.exit(ExitCode.SUCCESS)  # Works but deprecated
sys.exit(ExitCode.CONFIG_ERROR)  # Works but deprecated
```

**After**:
```python
sys.exit(ExitCode.OK)  # ✅ Recommended
sys.exit(ExitCode.CONFIG)  # ✅ Recommended
```

**Migration**: Replace all deprecated names before Q2 2026
```bash
# Check your code
grep -r "ExitCode\.(SUCCESS|CONFIG_ERROR|MISUSE|RUNTIME_ERROR|LOCK_ERROR|SIGINT)" .
```

---

### ✅ Strategy API Versioning

**Before**:
```python
class MyStrategy:
    def analyze(self, token_data):
        pass
```

**After**:
```python
class MyStrategy:
    STRATEGY_API_VERSION = "1.0"  # ✅ Required
    
    def analyze(self, token_data):
        pass
```

**Impact**: Core rejects strategies without version or major mismatch

---

### ✅ Metrics Registry

**Before**: Ad-hoc metric creation
```python
my_counter = Counter('my_metric', 'Description')
```

**After**: Validate against registry
```python
from src.core.metrics_registry import validate_metric

validate_metric("my_metric", "counter", ["label1", "label2"])
# Raises MetricsRegistryError if not in registry
```

**Check registry**: `config/metrics_registry.yaml`

---

### ✅ Schema Versioning

**Before**: Plain output
```json
{
  "token": "BTC",
  "gem_score": 85.0
}
```

**After**: Versioned output
```json
{
  "schema_version": "1.0.0",
  "schema_type": "scan_result",
  "token": "BTC",
  "gem_score": 85.0
}
```

**Usage**:
```python
from src.core.schema_versioning import add_schema_metadata, validate_output

# Add metadata
data = add_schema_metadata(data, schema_type="scan_result")

# Validate
validate_output(data, schema_type="scan_result")
```

---

### ✅ Lock File Enhancements

**Before**: Plain PID lock
```python
lock = FileLock(Path("/tmp/app.lock"), timeout=5.0)
```

**After**: TTL-aware lock
```python
lock = FileLock(
    Path("/tmp/app.lock"),
    timeout=5.0,
    lock_ttl=3600  # ✅ Expires after 1 hour
)
```

**Benefits**:
- Automatic stale lock cleanup
- PID + timestamp + hostname in lock file
- Better error messages

---

## Validation Commands

### Check Exit Codes
```python
python -c "from src.cli.exit_codes import print_deprecation_warnings; print_deprecation_warnings()"
```

### Validate Metrics
```python
python src/core/metrics_registry.py  # Shows summary + examples
```

### Check Schema Version
```python
python src/core/schema_versioning.py  # Test schema versioning
```

### Test Lock File
```python
python -c "
from pathlib import Path
from src.cli.runtime import FileLock

lock = FileLock(Path('/tmp/test.lock'), timeout=1.0, lock_ttl=60)
print('Acquiring lock...')
lock.acquire()
print('Lock acquired!')
lock.release()
print('Lock released!')
"
```

---

## Common Issues & Fixes

### Issue: DeprecationWarning on exit codes

**Fix**: Replace deprecated names
```bash
# Find usage
grep -r "ExitCode\.SUCCESS" .

# Replace (example)
sed -i 's/ExitCode\.SUCCESS/ExitCode.OK/g' *.py
```

---

### Issue: Strategy version error

**Error**: `StrategyAPIVersionError: Strategy requires API version X.X`

**Fix**: Add version to strategy class
```python
class MyStrategy:
    STRATEGY_API_VERSION = "1.0"  # Add this
```

---

### Issue: Metric not in registry

**Error**: `MetricsRegistryError: Metric 'my_metric' not found in registry`

**Fix**: Add to `config/metrics_registry.yaml` or use existing metric

---

### Issue: Schema validation failed

**Error**: `SchemaVersionError: Missing required field: schema_version`

**Fix**: Add schema metadata
```python
from src.core.schema_versioning import add_schema_metadata

data = add_schema_metadata(data, schema_type="scan_result")
```

---

### Issue: Lock timeout

**Error**: `Lock timeout after 5.0s: /tmp/app.lock. Lock owned by: PID 12345`

**Causes**:
1. Another instance still running
2. Stale lock (process crashed)

**Fix**:
```bash
# Check process
ps aux | grep 12345

# If dead, lock will auto-cleanup on next attempt (if TTL expired)
# Or manually remove: rm /tmp/app.lock
```

---

## Testing Checklist

Before committing code:

- [ ] No deprecated exit code aliases used
- [ ] Strategy classes have `STRATEGY_API_VERSION`
- [ ] New metrics registered in `metrics_registry.yaml`
- [ ] Outputs include schema metadata
- [ ] Lock files use TTL for long-running processes
- [ ] Tests pass: `python -m pytest tests/`

---

## Documentation

| Topic | Location |
|-------|----------|
| Exit Codes | `src/cli/exit_codes.py` |
| Strategy Plugins | `src/cli/plugins.py`, `examples/example_strategy_plugin.py` |
| Metrics Registry | `config/metrics_registry.yaml`, `src/core/metrics_registry.py` |
| Schema Versioning | `src/core/schema_versioning.py`, `SCHEMA_MIGRATION_GUIDE.md` |
| Lock Files | `src/cli/runtime.py` |
| Full Summary | `TECHNICAL_DEBT_RESOLUTION.md` |

---

## Timeline

| Version | Date | Changes |
|---------|------|---------|
| v2.0.0 | Oct 2025 | Initial improvements, deprecation warnings |
| v2.2.0 | Q1 2026 | Warnings become errors |
| v3.0.0 | Q2 2026 | Deprecated aliases removed |

---

## Support

Questions? Check:
1. Inline code documentation
2. `TECHNICAL_DEBT_RESOLUTION.md`
3. Individual module docstrings
4. Examples in `examples/` directory

**Report issues**: GitHub Issues or team chat

# AutoTrader Quick Reference Card

**Last Updated**: October 8, 2025

---

## 🚀 Quick Start

```bash
# Basic scan
autotrader-scan

# With reproducibility
autotrader-scan --enable-repro-stamp --deterministic --random-seed 42

# Debug configuration
autotrader-scan --print-effective-config
```

---

## 📖 Documentation

| Resource | Command | URL |
|----------|---------|-----|
| **Manpage** | `make manpage` | `dist/autotrader-scan.1` |
| **Docs Site** | `make docs-serve` | http://localhost:8000 |
| **CLI Docs** | `python scripts/gen_cli_docs.py` | `docs/cli/` |
| **Metrics Docs** | `python scripts/gen_metrics_docs.py` | `docs/metrics/` |

---

## 🔧 Configuration

### Precedence (lowest to highest)
```
Defaults → Config File → Environment → CLI Args
```

### Environment Variables
```bash
export AUTOTRADER_CONFIG=/path/to/config.yaml
export AUTOTRADER_LOG_LEVEL=DEBUG
export AUTOTRADER_DETERMINISTIC=true
export AUTOTRADER_LOCK_TTL=1800
```

### Debug Config
```bash
autotrader-scan --print-effective-config          # YAML output
autotrader-scan --print-effective-config --pretty  # Detailed
```

---

## 🔐 Reproducibility

### Enable Reproducibility Stamp
```bash
autotrader-scan \
    --enable-repro-stamp \
    --deterministic \
    --random-seed 42 \
    --output results.json
```

### Stamp Contents
- `git_commit`, `git_branch`, `git_dirty`
- `input_hashes` (SHA256, truncated)
- `config_hash`
- `python_version`, `platform`, `hostname`
- `random_seed`

---

## 🚪 Exit Codes

| Code | Name | Description |
|------|------|-------------|
| 0 | OK | Success |
| 1 | CONFIG | Configuration error |
| 2 | INPUT | Invalid input/arguments |
| 10 | RUNTIME | Execution error |
| 20 | TIMEOUT | Operation timed out |
| 21 | LOCKED | Lock acquisition failed |
| 30 | VALIDATION | Output validation failed |
| 130 | INTERRUPTED | User cancelled (Ctrl+C) |

---

## 🔒 File Locking

### With TTL
```bash
# Auto-cleanup after 30 minutes
autotrader-scan --lock-ttl 1800
```

### Disable (use with caution)
```bash
autotrader-scan --no-lock
```

### Lock Info
- **File**: `/var/lock/autotrader.lock` (or platform-specific)
- **Format**: JSON with PID, timestamp, hostname, TTL
- **Cleanup**: Automatic if process dead or TTL expired

---

## 📊 Metrics

### Registry
- **File**: `config/metrics_registry.yaml`
- **Count**: 40+ metrics
- **Categories**: 9 (validation, monitoring, scanning, etc.)

### Validation Rules
- Counters end with `_total`
- Max 5 labels per metric
- No generic labels (`type`, `status`, `name`)

### Prometheus Endpoint
```bash
autotrader-scan --metrics-port 9090

# Scrape at http://localhost:9090/metrics
```

---

## 📋 Schema Versioning

### Current Version
```python
SCHEMA_VERSION = "1.0.0"
```

### In Output
```json
{
  "_meta": {
    "schema_version": "1.0.0",
    "generated_at": "2025-10-08T12:00:00Z"
  }
}
```

### Migration
- See `../guides/SCHEMA_MIGRATION_GUIDE.md`
- Major version = breaking changes
- Minor version = new fields
- Patch version = bug fixes

---

## 🔌 Plugin API

### API Version
```python
STRATEGY_API_VERSION = "1.0"
```

### In Plugin
```python
class MyStrategy:
    STRATEGY_API_VERSION = "1.0"  # Must match
    
    def execute(self, data):
        ...
```

### Validation
- Major version must match exactly
- Minor version backward compatible

---

## 🛠️ Make Targets

```bash
make backtest          # Run backtesting pipeline
make coverage          # Run tests with coverage
make sbom              # Generate SBOM
make security          # Run security checks
make manpage           # Generate groff manpage
make manpage-md        # Generate Markdown manpage
make docs-gen          # Generate auto-docs
make docs-serve        # Serve docs locally
make docs-build        # Build static site
make docs              # Alias for docs-build
```

---

## 🧪 Testing

### Manpage Tests
```bash
python tests/test_manpage_generation.py
# ✅ 8/8 tests passing
```

### All Tests
```bash
pytest
pytest --cov=src --cov-report=term-missing
```

---

## 📝 Release Checklist

See `../checklists/RELEASE_CHECKLIST.md` for full process:

1. Pre-release checks (tests, security, docs)
2. Version bump (semantic versioning)
3. CHANGELOG update
4. Tag creation and push
5. Build and upload (PyPI)
6. Documentation deployment
7. Post-release monitoring

---

## 🔍 Debugging

### Print Deprecation Warnings
```bash
autotrader-scan --print-deprecation-warnings
```

### Validate Schema
```bash
autotrader-scan --validate-schema --schema-version 1.0.0
```

### Verbose Logging
```bash
autotrader-scan --log-level DEBUG --log-file debug.log
```

---

## 📚 Key Files

| File | Purpose |
|------|---------|
| `src/cli/manpage.py` | Manpage generator |
| `src/cli/effective_config.py` | Config debugger |
| `src/core/repro_stamper.py` | Reproducibility stamp |
| `src/core/schema_versioning.py` | Schema versioning |
| `src/core/metrics_registry.py` | Metrics validator |
| `config/metrics_registry.yaml` | Metrics definitions |
| `mkdocs.yml` | Documentation config |
| `../checklists/RELEASE_CHECKLIST.md` | Release process |

---

## 🐛 Common Issues

### "Lock held by another process"
```bash
# Wait or use TTL to auto-cleanup
autotrader-scan --lock-ttl 1800
```

### "Configuration error"
```bash
# Debug config precedence
autotrader-scan --print-effective-config
```

### "Deprecated exit code name"
```bash
# See migration guide
autotrader-scan --print-deprecation-warnings
```

---

## 🌐 Links

- **Repository**: https://github.com/CrisisCore-Systems/Autotrader
- **Documentation**: https://crisiscore-systems.github.io/Autotrader
- **Issues**: https://github.com/CrisisCore-Systems/Autotrader/issues

---

## ✨ New Features (v2.0)

- ✅ Reproducibility stamp (`--enable-repro-stamp`)
- ✅ Effective config printer (`--print-effective-config`)
- ✅ TTL-based lock cleanup (`--lock-ttl`)
- ✅ Schema versioning (SCHEMA_VERSION)
- ✅ Plugin API versioning (STRATEGY_API_VERSION)
- ✅ Metrics registry validation
- ✅ Manpage generation (`--generate-manpage`)
- ✅ Auto-generated documentation

---

**Print this card**: `lp QUICK_REF_CARD.md` or keep in browser for quick access!

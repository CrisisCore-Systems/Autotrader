# AutoTrader Platform

**Automated trading strategy scanner and backtesting platform with reproducibility guarantees**

---

## Welcome

AutoTrader is a comprehensive platform for scanning markets, identifying profitable trading strategies, and backtesting them against historical data with full reproducibility guarantees. Built with observability, versioning, and operational excellence in mind.

Looking for a specific guide? Start with the [Documentation Portal](documentation_portal.md) for a curated map of every major document in this repository.

## Key Features

### 🎯 **Strategy Scanning**
Automated discovery and evaluation of trading strategies across multiple markets and timeframes.

### 📊 **Reproducibility Guarantees**
Every scan includes a reproducibility stamp with git commit, input hashes, configuration hash, and environment details. Re-run any scan with confidence.

### 🔧 **Plugin Architecture**
Extensible strategy plugin system with API versioning. Write custom strategies and integrate them seamlessly.

### 📈 **Observability**
Complete metrics registry with Prometheus integration, distributed tracing support, and comprehensive logging.

### ⚙️ **Configuration Management**
Multi-source configuration (defaults → file → env → CLI) with origin tracking. Debug configuration issues with `--print-effective-config`.

### 🔒 **Concurrency Control**
File locking with automatic stale lock cleanup using TTL and process tracking.

### 📝 **Schema Versioning**
Semantic versioning for output schemas with migration guides and backward compatibility guarantees.

---

## Quick Start

### Installation

```bash
# From PyPI
pip install autotrader

# From source
git clone https://github.com/CrisisCore-Systems/Autotrader.git
cd Autotrader
pip install -r requirements.txt
```

### Basic Usage

```bash
# Run a basic scan
autotrader-scan

# Use custom configuration
autotrader-scan --config myconfig.yaml

# Enable reproducibility stamp
autotrader-scan --enable-repro-stamp --deterministic
```

### Check Configuration

```bash
# Print effective configuration with origins
autotrader-scan --print-effective-config

# Check deprecation warnings
autotrader-scan --print-deprecation-warnings
```

---

## Documentation Sections

### � **Start Here**
- [System Snapshot](overview/PROJECT_OVERVIEW.md)
- [Implementation Summary](IMPLEMENTATION_SUMMARY.md)
- [Feature Status](FEATURE_STATUS.md)

### �️ **Setup & Operations**
- [Setup Guide](install/SETUP_GUIDE.md)
- [Quickstart: New Signals](QUICKSTART_NEW_SIGNALS.md)
- [CLI Backtest Guide](CLI_BACKTEST_GUIDE.md)
- [Deployment Guide](deployment/DEPLOYMENT_GUIDE.md)

### 📈 **Reliability & Observability**
- [Reliability Implementation](RELIABILITY_IMPLEMENTATION.md)
- [Observability Guide](OBSERVABILITY_GUIDE.md)
- [Extended Backtest Metrics](EXTENDED_BACKTEST_METRICS.md)
- [Drift Monitoring Guide](DRIFT_MONITORING_GUIDE.md)

### 🤖 **AI & Narrative Intelligence**
- [LLM Validation Guide](LLM_VALIDATION_GUIDE.md)
- [LLM Validation Quick Reference](LLM_VALIDATION_QUICK_REF.md)
- [Groq Enhancements](llm/GROQ_ENHANCEMENTS.md)

### � **Reference Library**
- [Provider Rate Limits](provider_rate_limits.md)
- [Signal Coverage Audit](signal_coverage_audit.md)
- [Confidence Representation Standard](CONFIDENCE_REPRESENTATION_STANDARD.md)
- [Unified Logging Guide](UNIFIED_LOGGING_GUIDE.md)

---

## Architecture Highlights

### Reproducibility Stamp

Every scan can include a complete reproducibility stamp:

```json
{
  "repro_stamp": {
    "timestamp": "2025-10-08T12:00:00Z",
    "git_commit": "abc123def456...",
    "git_branch": "main",
    "git_dirty": false,
    "code_hash": "789abc...",
    "input_hashes": {
      "data.csv": "def456..."
    },
    "config_hash": "ghi789...",
    "python_version": "3.11.5",
    "platform": "Linux-5.15.0-x86_64",
    "hostname": "scanner-01",
    "random_seed": 42
  }
}
```

### Configuration Precedence

```
Defaults → Config File → Environment Variables → CLI Arguments
                                                   ↑
                                                highest
```

Use `--print-effective-config` to see the final merged configuration with origin tracking.

### Metrics Registry

All metrics are defined in `configs/metrics_registry.yaml` with validation rules:

- **Pattern enforcement**: Counters end with `_total`, histograms indicate unit
- **Label constraints**: Maximum 5 labels per metric
- **Type checking**: Validates metric types (counter, gauge, histogram, summary)

### Exit Codes

Simplified exit code scheme following Unix conventions:

| Code | Name | Description |
|------|------|-------------|
| 0 | OK | Success |
| 1 | CONFIG | Configuration error |
| 2 | INPUT | Invalid input/arguments |
| 10 | RUNTIME | Runtime execution error |
| 20 | TIMEOUT | Operation timed out |
| 21 | LOCKED | Lock acquisition failed |
| 30 | VALIDATION | Output validation failed |
| 130 | INTERRUPTED | User cancelled (Ctrl+C) |

---

## Project Status

| Feature | Status |
|---------|--------|
| Strategy Scanning | ✅ Stable |
| Reproducibility Stamp | ✅ Stable |
| Metrics Registry | ✅ Stable |
| Schema Versioning | ✅ Stable |
| File Locking with TTL | ✅ Stable |
| Effective Config Printer | ✅ Stable |
| Plugin API Versioning | ✅ Stable |
| Exit Code Deprecation | ⚠️ In Progress |
| MkDocs Site | 🚧 Beta |
| Integration Tests | 📋 Planned |

---

## Contributing

We welcome contributions! Please see our [Contributing Guide](https://github.com/CrisisCore-Systems/Autotrader/blob/main/CONTRIBUTING.md) for details.

### Development Setup

```bash
# Clone repository
git clone https://github.com/CrisisCore-Systems/Autotrader.git
cd Autotrader

# Install dependencies
pip install -r requirements.txt

# Run tests
pytest

# Run linting
make lint

# Generate documentation
make docs
```

---

## Support

- **Documentation**: [https://crisiscore-systems.github.io/Autotrader](https://crisiscore-systems.github.io/Autotrader)
- **Issues**: [GitHub Issues](https://github.com/CrisisCore-Systems/Autotrader/issues)
- **Discussions**: [GitHub Discussions](https://github.com/CrisisCore-Systems/Autotrader/discussions)

---

## License

Copyright © 2025 CrisisCore Systems

See [LICENSE](https://github.com/CrisisCore-Systems/Autotrader/blob/main/LICENSE) for details.

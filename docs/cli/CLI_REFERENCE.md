# AutoTrader CLI Reference

**Complete reference for the AutoTrader CLI scanner and backtest tools.**

Version: 0.1.0  
Last Updated: October 8, 2025

---

## Table of Contents

- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Command Reference](#command-reference)
- [Exit Codes](#exit-codes)
- [Strategies & Plugins](#strategies--plugins)
- [Metrics & Observability](#metrics--observability)
- [Best Practices](#best-practices)
- [Troubleshooting](#troubleshooting)

---

## Quick Start

### Installation

```bash
# Install in development mode
pip install -e .

# Verify installation
autotrader-scan --version
autotrader-scan --list-exit-codes
autotrader-scan --list-strategies
```

### Basic Usage

```bash
# Simple scan with config file
autotrader-scan --config configs/example.yaml

# Dry run to validate configuration (no execution)
autotrader-scan --config configs/example.yaml --dry-run

# Production run with all safeguards
autotrader-scan --config config.yaml \
  --deterministic --seed 42 \
  --max-duration-seconds 3600 \
  --lock-file /var/run/autotrader.lock \
  --emit-metrics statsd \
  --log-format json
```

---

## Configuration

### Configuration Precedence

**Configuration sources are merged in the following priority order (highest to lowest):**

1. **CLI Arguments** - Explicit command-line flags (highest priority)
2. **Environment Variables** - `AUTOTRADER_*` prefixed variables
3. **YAML File** - File specified via `--config` (lowest priority)

This means CLI arguments always override environment variables, which override file settings.

### YAML Configuration

Example `config.yaml`:

```yaml
# Scanner settings
scanner:
  liquidity_threshold: 75000

# API keys
etherscan_api_key: "YOUR_KEY_HERE"
coingecko_api_key: "YOUR_KEY_HERE"

# Tokens to scan
tokens:
  - symbol: VOID
    coingecko_id: void-token
    defillama_slug: void-protocol
    contract_address: "0x0000000000000000000000000000000000000000"
    narratives:
      - "VOID protocol announces mainnet launch"
    unlocks:
      - date: 2025-05-15T00:00:00
        percent_supply: 4.5

# Output settings
output: reports/scans

# Strategy selection
strategy: default

# Deterministic mode
deterministic: true
seed: 42
```

### Environment Variables

All configuration can be overridden via environment variables with the `AUTOTRADER_` prefix:

```bash
# Set via environment
export AUTOTRADER_LOG_LEVEL=DEBUG
export AUTOTRADER_OUTPUT=/tmp/results
export AUTOTRADER_ETHERSCAN_API_KEY="your_key"
export AUTOTRADER_DETERMINISTIC=true
export AUTOTRADER_SEED=42

# Then run
autotrader-scan --config config.yaml
```

**Common Environment Variables:**

| Variable | Type | Description |
|----------|------|-------------|
| `AUTOTRADER_LOG_LEVEL` | String | DEBUG, INFO, WARNING, ERROR, CRITICAL |
| `AUTOTRADER_LOG_FORMAT` | String | text, json |
| `AUTOTRADER_OUTPUT` | Path | Output directory |
| `AUTOTRADER_STRATEGY` | String | Strategy name |
| `AUTOTRADER_DETERMINISTIC` | Boolean | Enable deterministic mode |
| `AUTOTRADER_SEED` | Integer | Random seed |
| `AUTOTRADER_EMIT_METRICS` | String | none, stdout, statsd |
| `AUTOTRADER_ETHERSCAN_API_KEY` | String | Etherscan API key |
| `AUTOTRADER_COINGECKO_API_KEY` | String | CoinGecko API key |
| `PYTHONHASHSEED` | Integer | Python hash seed (required for deterministic mode) |

---

## Command Reference

### autotrader-scan

Main CLI tool for running token scans.

#### Core Options

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--config PATH` | Path | None | YAML configuration file (required) |
| `--output PATH` | Path | `reports/scans` | Output directory for results |
| `--dry-run` | Flag | False | Validate config without running |
| `--version` | Flag | - | Show version and exit |
| `--help` | Flag | - | Show help and exit |

#### Strategy Options

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--strategy NAME` | String | `default` | Strategy name or module path |
| `--list-strategies` | Flag | - | List available strategies and exit |

#### Deterministic Mode

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--deterministic` | Flag | False | Enable deterministic mode |
| `--seed N` | Integer | 42 | Random seed for reproducibility |

**⚠️ Important:** Deterministic mode only controls Python/NumPy/PyTorch random number generation. External data sources, HTTP fetches, and database query ordering remain nondeterministic unless explicitly pinned with snapshots.

**Example:**

```bash
# Full deterministic setup
PYTHONHASHSEED=0 autotrader-scan --config config.yaml --deterministic --seed 42
```

#### Logging Options

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--log-level LEVEL` | Choice | `INFO` | DEBUG, INFO, WARNING, ERROR, CRITICAL |
| `--log-format FORMAT` | Choice | `text` | text, json |

**Examples:**

```bash
# Debug logging
autotrader-scan --config config.yaml --log-level DEBUG

# JSON structured logging (for production)
autotrader-scan --config config.yaml --log-format json
```

#### Metrics & Telemetry

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--emit-metrics TYPE` | Choice | `none` | none, stdout, statsd |
| `--statsd-host HOST` | String | `localhost` | StatsD server hostname |
| `--statsd-port PORT` | Integer | `8125` | StatsD server port |

**Metric Naming Convention:**

All metrics follow the pattern: `autotrader.<component>.<metric_name>`

Examples:
- `autotrader.scan.total_duration` - Total scan duration
- `autotrader.scan.tokens_scanned` - Number of tokens scanned
- `autotrader.backtest.precision_at_10` - Backtest precision metric
- `autotrader.api.etherscan.latency` - API latency
- `autotrader.error.api_timeout` - Error counter

**Examples:**

```bash
# Emit metrics as JSON lines to stdout
autotrader-scan --config config.yaml --emit-metrics stdout

# Send metrics to StatsD server
autotrader-scan --config config.yaml \
  --emit-metrics statsd \
  --statsd-host metrics.example.com \
  --statsd-port 8125
```

**Metric Output Format (stdout):**

```json
{"name": "autotrader.scan.total_duration", "value": 12.5, "type": "timer", "timestamp": 1696723200.0, "unit": "ms"}
{"name": "autotrader.scan.tokens_scanned", "value": 1.0, "type": "counter", "timestamp": 1696723205.0}
{"name": "autotrader.scan.gem_score", "value": 78.5, "type": "gauge", "timestamp": 1696723210.0, "tags": {"symbol": "VOID"}}
```

#### Runtime Limits

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--max-duration-seconds N` | Float | None | Maximum execution duration (watchdog) |
| `--lock-file PATH` | Path | None | File lock to prevent concurrent runs |

**⚠️ File Lock Cross-Platform Behavior:**

The file lock implementation uses OS-level file creation atomicity (`O_CREAT | O_EXCL`). This is portable across Windows and Unix-like systems. However, note:

- **Race Condition:** Small window between file existence check and creation on some filesystems
- **Stale Lock Detection:** Uses platform-specific process checks (Windows: OpenProcess, Unix: os.kill(pid, 0))
- **Network Filesystems:** Not recommended for NFS or other network filesystems due to potential race conditions
- **Recommended:** Use local filesystem paths only (e.g., `/var/run/`, `C:\ProgramData\`)

**Examples:**

```bash
# Enforce 1-hour timeout
autotrader-scan --config config.yaml --max-duration-seconds 3600

# Prevent concurrent runs (local filesystem only)
autotrader-scan --config config.yaml --lock-file /var/run/autotrader.lock

# Both combined (production use)
autotrader-scan \
  --config config.yaml \
  --max-duration-seconds 3600 \
  --lock-file /var/run/autotrader.lock
```

#### Output Validation

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--validate-schema` | Flag | False | Validate output against JSON schema |
| `--schema-path PATH` | Path | `configs/output_schema.json` | Path to JSON schema file |

**Example:**

```bash
# Validate output structure
autotrader-scan --config config.yaml --validate-schema
```

---

## Exit Codes

**Simplified to 8 canonical categories:**

| Code | Name | Description |
|------|------|-------------|
| **0** | `OK` | Success - operation completed successfully |
| **1** | `CONFIG` | Configuration error - invalid config file or settings |
| **2** | `INPUT` | Input error - invalid command-line arguments or data format |
| **10** | `RUNTIME` | Runtime error - execution failure, API error, or strategy error |
| **20** | `TIMEOUT` | Timeout - operation exceeded time limit |
| **21** | `LOCKED` | Lock error - another instance is running or lock acquisition failed |
| **30** | `VALIDATION` | Validation error - output failed schema or format validation |
| **130** | `INTERRUPTED` | Interrupted - user cancelled operation (Ctrl+C) |

### Using Exit Codes in Scripts

**Bash/Zsh:**

```bash
autotrader-scan --config config.yaml
case $? in
    0) echo "✅ Success" ;;
    1) echo "❌ Configuration error" ;;
    2) echo "❌ Invalid input" ;;
    10) echo "❌ Runtime error" ;;
    20) echo "❌ Timeout" ;;
    21) echo "❌ Lock error (another instance running?)" ;;
    30) echo "❌ Validation error" ;;
    130) echo "⚠️ Interrupted by user" ;;
    *) echo "❌ Unknown error ($?)" ;;
esac
```

**PowerShell:**

```powershell
autotrader-scan --config config.yaml
switch ($LASTEXITCODE) {
    0   { Write-Host "✅ Success" -ForegroundColor Green }
    1   { Write-Host "❌ Configuration error" -ForegroundColor Red }
    2   { Write-Host "❌ Invalid input" -ForegroundColor Red }
    10  { Write-Host "❌ Runtime error" -ForegroundColor Red }
    20  { Write-Host "❌ Timeout" -ForegroundColor Red }
    21  { Write-Host "❌ Lock error" -ForegroundColor Red }
    30  { Write-Host "❌ Validation error" -ForegroundColor Red }
    130 { Write-Host "⚠️ Interrupted" -ForegroundColor Yellow }
}
```

**Python:**

```python
import subprocess

result = subprocess.run(["autotrader-scan", "--config", "config.yaml"])

EXIT_CODES = {
    0: "Success",
    1: "Configuration error",
    2: "Invalid input",
    10: "Runtime error",
    20: "Timeout",
    21: "Lock error",
    30: "Validation error",
    130: "Interrupted"
}

print(EXIT_CODES.get(result.returncode, f"Unknown error ({result.returncode})"))
```

### List Exit Codes

```bash
# Print all exit codes with descriptions
autotrader-scan --list-exit-codes
```

---

## Strategies & Plugins

### Built-in Strategies

- `default` - Default GemScore strategy
- `conservative` - Conservative risk profile
- `aggressive` - Aggressive risk profile

### List Available Strategies

```bash
autotrader-scan --list-strategies
```

### Using a Strategy

```bash
# Use built-in strategy
autotrader-scan --config config.yaml --strategy conservative

# Use custom strategy module
autotrader-scan --config config.yaml --strategy my_package.strategies.CustomStrategy
```

### Creating a Custom Plugin Strategy

Create a new Python file (e.g., `my_strategy.py`):

```python
"""Example custom strategy plugin."""

from typing import Dict, Any, List


class MyCustomStrategy:
    """Custom strategy implementation.
    
    Required interface:
    - __init__(config: Dict[str, Any]) -> None
    - analyze(token_data: Dict[str, Any]) -> Dict[str, Any]
    """
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize strategy with config.
        
        Args:
            config: Configuration dictionary from YAML
        """
        self.config = config
        self.liquidity_threshold = config.get("liquidity_threshold", 50000)
    
    def analyze(self, token_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze token and return results.
        
        Args:
            token_data: Token data dictionary with:
                - symbol: Token symbol (str)
                - price_data: Price information (dict)
                - social_metrics: Social media metrics (dict)
                - on_chain_data: On-chain data (dict)
        
        Returns:
            Analysis results with:
                - gem_score: Overall score (0-100)
                - signals: List of detected signals
                - risk_score: Risk assessment (0-100)
                - recommendation: "BUY", "HOLD", "SELL", or "SKIP"
        """
        symbol = token_data.get("symbol", "UNKNOWN")
        
        # Your custom logic here
        gem_score = 50.0  # Calculate your score
        
        return {
            "gem_score": gem_score,
            "signals": ["example_signal"],
            "risk_score": 50.0,
            "recommendation": "HOLD",
            "metadata": {
                "strategy": "my_custom_strategy",
                "version": "1.0.0"
            }
        }
```

**Register as entry point in `pyproject.toml`:**

```toml
[project.entry-points."autotrader.strategies"]
my_custom = "my_package.strategies:MyCustomStrategy"
```

**Use your custom strategy:**

```bash
pip install -e .  # Reinstall to register entry point
autotrader-scan --config config.yaml --strategy my_custom
```

See [example_strategy_plugin.py](https://github.com/CrisisCore-Systems/Autotrader/blob/main/examples/example_strategy_plugin.py) for a complete example.

---

## Metrics & Observability

### Metric Types

- **Counter** - Monotonically increasing value (e.g., total scans)
- **Gauge** - Point-in-time value (e.g., current gem score)
- **Timer** - Duration measurement (e.g., API latency)
- **Histogram** - Distribution of values (e.g., score distribution)

### Metric Naming Convention

**Pattern:** `autotrader.<component>.<metric_name>`

**Components:**
- `scan` - Scanner operations
- `backtest` - Backtesting operations
- `api` - External API calls
- `strategy` - Strategy execution
- `error` - Error tracking

**Examples:**
- `autotrader.scan.total_duration`
- `autotrader.scan.tokens_scanned`
- `autotrader.backtest.precision_at_10`
- `autotrader.api.etherscan.latency`
- `autotrader.api.coingecko.rate_limit_errors`
- `autotrader.strategy.execution_time`
- `autotrader.error.api_timeout`
- `autotrader.error.validation_failed`

### StatsD Integration

```bash
# Send metrics to StatsD
autotrader-scan --config config.yaml \
  --emit-metrics statsd \
  --statsd-host localhost \
  --statsd-port 8125
```

**Grafana Dashboard:** See [OBSERVABILITY_QUICK_REF.md](../observability/OBSERVABILITY_QUICK_REF.md) for Grafana dashboard configuration.

---

## Best Practices

### Production Deployment

```bash
#!/bin/bash
# production_scan.sh

set -e  # Exit on error

# Set environment
export PYTHONHASHSEED=0
export AUTOTRADER_LOG_LEVEL=INFO
export AUTOTRADER_LOG_FORMAT=json
export AUTOTRADER_EMIT_METRICS=statsd
export AUTOTRADER_STATSD_HOST=metrics.example.com

# Run with all safeguards
autotrader-scan \
  --config /etc/autotrader/config.yaml \
  --deterministic \
  --seed 42 \
  --max-duration-seconds 3600 \
  --lock-file /var/run/autotrader.lock \
  --validate-schema \
  --output /var/lib/autotrader/scans

# Check exit code
exit_code=$?
if [ $exit_code -ne 0 ]; then
    echo "Scan failed with exit code $exit_code" >&2
    # Alert on failure (e.g., PagerDuty, Slack)
    exit $exit_code
fi

echo "Scan completed successfully"
```

### CI/CD Integration

```yaml
# .github/workflows/scan.yml
name: AutoTrader Scan

on:
  schedule:
    - cron: '0 */6 * * *'  # Every 6 hours
  workflow_dispatch:

jobs:
  scan:
    runs-on: ubuntu-latest
    timeout-minutes: 60
    
    steps:
      - uses: actions/checkout@v4
      
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          
      - name: Install dependencies
        run: |
          pip install -e .
          
      - name: Run scan
        env:
          PYTHONHASHSEED: 0
          AUTOTRADER_ETHERSCAN_API_KEY: ${{ secrets.ETHERSCAN_API_KEY }}
          AUTOTRADER_LOG_FORMAT: json
        run: |
          autotrader-scan \
            --config configs/production.yaml \
            --deterministic \
            --seed 42 \
            --max-duration-seconds 3600 \
            --validate-schema \
            --emit-metrics stdout
            
      - name: Upload results
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: scan-results
          path: reports/scans/
```

### Docker Deployment

```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN pip install -e .

# Create directories
RUN mkdir -p /var/lib/autotrader/scans /var/run

# Set environment
ENV PYTHONHASHSEED=0
ENV AUTOTRADER_LOG_FORMAT=json

ENTRYPOINT ["autotrader-scan"]
CMD ["--config", "/etc/autotrader/config.yaml", \
     "--deterministic", \
     "--max-duration-seconds", "3600", \
     "--lock-file", "/var/run/autotrader.lock"]
```

```bash
# Run container
docker run -v /path/to/config.yaml:/etc/autotrader/config.yaml \
           -v /path/to/output:/var/lib/autotrader/scans \
           autotrader:latest
```

### Kubernetes CronJob

```yaml
# k8s/cronjob.yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: autotrader-scan
spec:
  schedule: "0 */6 * * *"  # Every 6 hours
  successfulJobsHistoryLimit: 3
  failedJobsHistoryLimit: 3
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: scanner
            image: autotrader:latest
            env:
            - name: PYTHONHASHSEED
              value: "0"
            - name: AUTOTRADER_LOG_FORMAT
              value: "json"
            - name: AUTOTRADER_EMIT_METRICS
              value: "statsd"
            - name: AUTOTRADER_STATSD_HOST
              value: "statsd-service"
            - name: AUTOTRADER_ETHERSCAN_API_KEY
              valueFrom:
                secretKeyRef:
                  name: api-keys
                  key: etherscan
            volumeMounts:
            - name: config
              mountPath: /etc/autotrader
            - name: output
              mountPath: /var/lib/autotrader/scans
          restartPolicy: OnFailure
          volumes:
          - name: config
            configMap:
              name: autotrader-config
          - name: output
            persistentVolumeClaim:
              claimName: autotrader-scans
```

---

## Troubleshooting

### Common Issues

#### Lock File Errors (Exit Code 21)

```bash
# Error: Failed to acquire lock
# Another instance may be running or stale lock file exists

# Check for running processes
ps aux | grep autotrader-scan

# Remove stale lock (if no process running)
rm /var/run/autotrader.lock

# Retry
autotrader-scan --config config.yaml --lock-file /var/run/autotrader.lock
```

#### Configuration Errors (Exit Code 1)

```bash
# Error: Invalid configuration

# Validate config with dry run
autotrader-scan --config config.yaml --dry-run

# Check YAML syntax
python -c "import yaml; yaml.safe_load(open('config.yaml'))"

# Enable debug logging
autotrader-scan --config config.yaml --log-level DEBUG
```

#### Timeout Errors (Exit Code 20)

```bash
# Error: Operation timeout

# Increase timeout
autotrader-scan --config config.yaml --max-duration-seconds 7200

# Check for hanging API calls
autotrader-scan --config config.yaml --log-level DEBUG
```

#### Validation Errors (Exit Code 30)

```bash
# Error: Output validation failed

# Check schema
cat configs/output_schema.json

# Run without validation first
autotrader-scan --config config.yaml  # No --validate-schema

# Compare output to schema
python -c "
import json
import jsonschema
data = json.load(open('reports/scans/latest.json'))
schema = json.load(open('configs/output_schema.json'))
jsonschema.validate(data, schema)
"
```

### Debug Mode

```bash
# Full debug output
autotrader-scan --config config.yaml \
  --log-level DEBUG \
  --log-format text \
  --emit-metrics stdout \
  --dry-run
```

### Getting Help

```bash
# Show help
autotrader-scan --help

# List exit codes
autotrader-scan --list-exit-codes

# List strategies
autotrader-scan --list-strategies

# Show version
autotrader-scan --version
```

---

## Related Documentation

- **[OBSERVABILITY_QUICK_REF.md](../observability/OBSERVABILITY_QUICK_REF.md)** - Metrics, logging, and monitoring
- **[PROVENANCE_QUICK_REF.md](../provenance/PROVENANCE_QUICK_REF.md)** - Artifact tracking and lineage
- **[SETUP_GUIDE.md](../install/SETUP_GUIDE.md)** - Installation and setup
- **[Project README](https://github.com/CrisisCore-Systems/Autotrader/blob/main/README.md)** - Project overview

---

## Support

For issues or questions:

1. Check this reference documentation
2. Enable debug logging: `--log-level DEBUG`
3. Use dry run mode: `--dry-run`
4. Check [GitHub Issues](https://github.com/CrisisCore-Systems/AutoTrader/issues)

---

*Last updated: October 8, 2025*

# AutoTrader CLI Guide

Comprehensive guide for the enhanced AutoTrader CLI with production-ready features.

## Table of Contents

- [Quick Start](#quick-start)
- [Configuration Resolution](#configuration-resolution)
- [Command-Line Options](#command-line-options)
- [Environment Variables](#environment-variables)
- [Deterministic Mode](#deterministic-mode)
- [Metrics & Telemetry](#metrics--telemetry)
- [Runtime Limits](#runtime-limits)
- [Plugin Strategies](#plugin-strategies)
- [Output Validation](#output-validation)
- [Exit Codes](#exit-codes)
- [Best Practices](#best-practices)
- [Examples](#examples)

---

## Quick Start

### Installation

```bash
# Install in development mode
pip install -e .

# Verify installation
autotrader-scan --version
autotrader-scan --list-exit-codes
```

### Basic Usage

```bash
# Simple scan with config file
autotrader-scan --config configs/example.yaml

# Dry run to validate configuration
autotrader-scan --config configs/example.yaml --dry-run

# List available strategies
autotrader-scan --list-strategies
```

---

## Configuration Resolution

Configuration is resolved from multiple sources with the following priority (highest to lowest):

1. **CLI Arguments** - Explicit command-line flags
2. **Environment Variables** - `AUTOTRADER_*` prefixed variables
3. **YAML Configuration** - File specified via `--config`

### YAML Configuration

Example `config.yaml`:

```yaml
# Scanner settings
scanner:
  liquidity_threshold: 75000

# Etherscan API key
etherscan_api_key: "YOUR_KEY_HERE"

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

### Loading Configuration

```bash
# Load from YAML
autotrader-scan --config myconfig.yaml

# Override with CLI args
autotrader-scan --config myconfig.yaml --log-level DEBUG --output /tmp/results

# Override with environment variables
AUTOTRADER_LOG_LEVEL=DEBUG autotrader-scan --config myconfig.yaml
```

---

## Command-Line Options

### Core Options

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--config PATH` | Path | None | YAML configuration file |
| `--output PATH` | Path | `reports/scans` | Output directory for results |

### Strategy Options

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--strategy NAME` | String | `default` | Strategy name or module path |
| `--list-strategies` | Flag | - | List available strategies and exit |

### Deterministic Mode

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--deterministic` | Flag | False | Enable deterministic mode |
| `--seed N` | Integer | 42 | Random seed for reproducibility |

**Example:**

```bash
# Enable deterministic mode
PYTHONHASHSEED=0 autotrader-scan --config config.yaml --deterministic --seed 42
```

### Logging Options

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--log-level LEVEL` | Choice | `INFO` | DEBUG, INFO, WARNING, ERROR, CRITICAL |
| `--log-format FORMAT` | Choice | `text` | text, json |

**Example:**

```bash
# JSON structured logging
autotrader-scan --config config.yaml --log-format json --log-level DEBUG
```

### Metrics & Telemetry

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--emit-metrics TYPE` | Choice | None | none, stdout, statsd |
| `--statsd-host HOST` | String | localhost | StatsD server hostname |
| `--statsd-port PORT` | Integer | 8125 | StatsD server port |

**Examples:**

```bash
# Emit metrics as JSON lines to stdout
autotrader-scan --config config.yaml --emit-metrics stdout

# Send metrics to StatsD server
autotrader-scan --config config.yaml --emit-metrics statsd --statsd-host metrics.example.com
```

**Metric Output Format (stdout):**

```json
{"name": "scan_total_duration", "value": 12.5, "type": "timer", "timestamp": 1696723200.0, "unit": "ms"}
{"name": "tokens_scanned", "value": 1.0, "type": "counter", "timestamp": 1696723205.0}
{"name": "gem_score_VOID", "value": 78.5, "type": "gauge", "timestamp": 1696723210.0}
```

### Runtime Limits

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--max-duration-seconds N` | Float | None | Maximum execution duration (watchdog) |
| `--lock-file PATH` | Path | None | File lock to prevent concurrent runs |

**Examples:**

```bash
# Enforce 1-hour timeout
autotrader-scan --config config.yaml --max-duration-seconds 3600

# Prevent concurrent runs
autotrader-scan --config config.yaml --lock-file /tmp/autotrader.lock

# Both combined (production use)
autotrader-scan \
  --config config.yaml \
  --max-duration-seconds 3600 \
  --lock-file /var/run/autotrader.lock
```

### Output Validation

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--validate-output` | Flag | False | Validate output against JSON schema |
| `--schema-path PATH` | Path | `configs/output_schema.json` | JSON schema file |

**Example:**

```bash
# Validate output structure
autotrader-scan --config config.yaml --validate-output
```

### Utility Flags

| Flag | Description |
|------|-------------|
| `--dry-run` | Validate config and exit (no scan) |
| `--list-exit-codes` | Show all exit codes and exit |
| `--version` | Show version and exit |

---

## Environment Variables

All configuration can be overridden via environment variables with the `AUTOTRADER_` prefix.

### Supported Variables

| Variable | Type | Example | Description |
|----------|------|---------|-------------|
| `AUTOTRADER_LOG_LEVEL` | String | `DEBUG` | Logging level |
| `AUTOTRADER_OUTPUT_DIR` | Path | `/tmp/results` | Output directory |
| `AUTOTRADER_ETHERSCAN_API_KEY` | String | `abc123...` | API key |
| `AUTOTRADER_SCANNER_LIQUIDITY_THRESHOLD` | Number | `50000` | Liquidity threshold |

### Nested Configuration

Use underscores for nested keys:

```bash
# scanner.liquidity_threshold
export AUTOTRADER_SCANNER_LIQUIDITY_THRESHOLD=50000

# Equivalent to YAML:
# scanner:
#   liquidity_threshold: 50000
```

### Type Parsing

Environment variables are automatically parsed:

- **Boolean**: `true`, `false`, `yes`, `no`, `1`, `0`
- **Integer**: `42`, `1000`
- **Float**: `3.14`, `0.001`
- **JSON**: `[1,2,3]`, `{"key": "value"}`
- **String**: Everything else

### Examples

```bash
# Boolean
export AUTOTRADER_DETERMINISTIC=true

# Nested config
export AUTOTRADER_SCANNER_LIQUIDITY_THRESHOLD=100000

# Run with overrides
AUTOTRADER_LOG_LEVEL=DEBUG \
AUTOTRADER_DETERMINISTIC=true \
AUTOTRADER_SEED=123 \
  autotrader-scan --config config.yaml
```

---

## Deterministic Mode

Ensures reproducible results across runs by seeding all random sources.

### What Gets Seeded

1. **Python `random` module**
2. **NumPy random** (if installed)
3. **PyTorch** (if installed, including CUDA)

### Full Reproducibility Checklist

```bash
# 1. Set hash seed BEFORE starting Python
export PYTHONHASHSEED=0

# 2. Enable deterministic mode with fixed seed
autotrader-scan --config config.yaml --deterministic --seed 42

# 3. Ensure same versions
pip freeze > requirements-exact.txt
```

### Verification

```bash
# Run twice and compare outputs
autotrader-scan --config config.yaml --deterministic --seed 42 --output run1
autotrader-scan --config config.yaml --deterministic --seed 42 --output run2

# Results should be identical
diff run1/scan_results.json run2/scan_results.json
```

### Limitations

Deterministic mode does NOT guarantee reproducibility across:
- Different Python versions
- Different library versions (NumPy, PyTorch, etc.)
- Different hardware (CPU vs GPU)
- Network calls with timestamps or rate limits

---

## Metrics & Telemetry

### Metric Types

1. **Counter** - Incrementing values (e.g., `tokens_scanned`)
2. **Gauge** - Point-in-time values (e.g., `gem_score_VOID`)
3. **Timer** - Durations in milliseconds (e.g., `scan_total_duration`)

### Built-in Metrics

| Metric Name | Type | Description |
|-------------|------|-------------|
| `scan_total_duration` | Timer | Total scan duration |
| `scan_token_{SYMBOL}` | Timer | Per-token scan duration |
| `tokens_to_scan` | Gauge | Number of tokens to process |
| `tokens_scanned` | Counter | Tokens processed |
| `tokens_successful` | Counter | Successful scans |
| `tokens_failed` | Counter | Failed scans |
| `gem_score_{SYMBOL}` | Gauge | GemScore for token |

### StatsD Integration

```bash
# Start StatsD server (example with Docker)
docker run -d \
  -p 8125:8125/udp \
  -p 8126:8126 \
  --name statsd \
  graphiteapp/graphite-statsd

# Configure AutoTrader to send metrics
autotrader-scan \
  --config config.yaml \
  --emit-metrics statsd \
  --statsd-host localhost \
  --statsd-port 8125
```

### Parsing JSON Lines Output

```bash
# Emit to file
autotrader-scan --config config.yaml --emit-metrics stdout > metrics.jsonl

# Parse with jq
cat metrics.jsonl | jq -r 'select(.type=="timer") | "\(.name): \(.value)ms"'

# Calculate totals
cat metrics.jsonl | jq -s 'map(select(.type=="counter")) | group_by(.name) | map({name: .[0].name, total: map(.value) | add})'
```

---

## Runtime Limits

### Watchdog Timer

Prevents runaway jobs by enforcing a maximum duration.

```bash
# 30-minute timeout
autotrader-scan --config config.yaml --max-duration-seconds 1800

# On timeout: exits with code 24 (WATCHDOG_TIMEOUT)
```

**Exit Code:** 24

### Concurrency Lock

Prevents multiple instances from running simultaneously.

```bash
# Create lock file during execution
autotrader-scan --config config.yaml --lock-file /tmp/scan.lock

# Second instance will fail with exit code 22 (LOCK_ERROR)
```

**Lock File Contents:**
```
12345
```
(Process ID of lock holder)

**Stale Lock Handling:**
- If process with PID no longer exists, lock is automatically removed
- Timeout can be adjusted (default: fail immediately)

### CI/CD Integration

```yaml
# GitHub Actions example
- name: Run AutoTrader Scan
  run: |
    autotrader-scan \
      --config configs/production.yaml \
      --max-duration-seconds 3600 \
      --lock-file /tmp/autotrader-ci.lock \
      --log-format json
  timeout-minutes: 65  # Slightly longer than watchdog
```

---

## Plugin Strategies

Extend AutoTrader with custom strategies via Python entry points.

### Built-in Strategies

| Name | Module | Description |
|------|--------|-------------|
| `default` | `src.core.pipeline:HiddenGemScanner` | Default hidden gem scanner |

### Using Entry Points

**1. Define strategy in `pyproject.toml`:**

```toml
[project.entry-points."autotrader.strategies"]
my_strategy = "my_package.strategies:MyStrategy"
momentum = "my_package.strategies:MomentumStrategy"
```

**2. List available strategies:**

```bash
autotrader-scan --list-strategies
```

**3. Use strategy:**

```bash
autotrader-scan --config config.yaml --strategy my_strategy
```

### Strategy Interface

Required methods:
- `scan(token: TokenConfig) -> ScanResult`
- `scan_with_tree(token: TokenConfig) -> Tuple[ScanResult, TreeNode]`

**Example Strategy:**

```python
from src.core.pipeline import TokenConfig, ScanResult
from src.core.tree import TreeNode

class MyStrategy:
    def scan(self, token: TokenConfig) -> ScanResult:
        # Your implementation
        pass
    
    def scan_with_tree(self, token: TokenConfig) -> tuple[ScanResult, TreeNode]:
        # Your implementation
        pass
```

### Direct Module Path

```bash
# Load strategy from module path
autotrader-scan \
  --config config.yaml \
  --strategy my_package.strategies:CustomStrategy
```

---

## Output Validation

Prevent silent shape drift with JSON schema validation.

### Schema Location

Default: `configs/output_schema.json`

### Enabling Validation

```bash
# Validate against default schema
autotrader-scan --config config.yaml --validate-output

# Custom schema path
autotrader-scan \
  --config config.yaml \
  --validate-output \
  --schema-path my_schema.json
```

### On Validation Failure

- **Exit Code:** 13 (SCHEMA_VALIDATION_ERROR)
- **Log Message:** Details about schema violation

### Output Structure

Expected output format:

```json
{
  "tokens": [
    {
      "symbol": "VOID",
      "gem_score": 78.5,
      "status": "success",
      "artifacts": {
        "markdown_path": "reports/scans/void_report.md",
        "html_path": "reports/scans/void_report.html"
      }
    }
  ],
  "metadata": {
    "version": "0.1.0",
    "strategy": "default",
    "duration_seconds": 12.5,
    "tokens_processed": 1,
    "tokens_successful": 1,
    "tokens_failed": 0
  },
  "timestamp": "2025-10-08T12:00:00Z",
  "config": {
    "liquidity_threshold": 75000,
    "deterministic": true,
    "seed": 42
  }
}
```

---

## Exit Codes

AutoTrader uses standard Unix exit codes for automation.

### Exit Code Categories

| Code | Name | Description |
|------|------|-------------|
| **Success** |||
| 0 | `SUCCESS` | Operation completed successfully |
| **General Errors** |||
| 1 | `GENERAL_ERROR` | Unspecified failure |
| 2 | `MISUSE` | Incorrect command-line usage |
| **Configuration Errors (10-19)** |||
| 10 | `CONFIG_ERROR` | General configuration problem |
| 11 | `CONFIG_NOT_FOUND` | Configuration file not found |
| 12 | `CONFIG_INVALID` | Configuration malformed |
| 13 | `SCHEMA_VALIDATION_ERROR` | Output schema validation failed |
| **Runtime Errors (20-29)** |||
| 20 | `RUNTIME_ERROR` | General execution failure |
| 21 | `TIMEOUT` | Operation timeout |
| 22 | `LOCK_ERROR` | Lock acquisition failed |
| 24 | `WATCHDOG_TIMEOUT` | Process exceeded max duration |
| **Data Errors (30-39)** |||
| 30 | `DATA_ERROR` | General data problem |
| 31 | `DATA_NOT_FOUND` | Required data not found |
| 32 | `DATA_INVALID` | Data format invalid |
| 33 | `API_ERROR` | External API call failed |
| **Strategy Errors (40-49)** |||
| 40 | `STRATEGY_ERROR` | General strategy problem |
| 41 | `STRATEGY_NOT_FOUND` | Strategy cannot be loaded |
| 42 | `STRATEGY_INVALID` | Strategy implementation invalid |
| **Output Errors (50-59)** |||
| 50 | `OUTPUT_ERROR` | Failed to write results |
| 51 | `OUTPUT_VALIDATION_ERROR` | Output validation failed |
| **Signal-Related** |||
| 130 | `SIGINT` | Interrupted by user (Ctrl+C) |
| 143 | `SIGTERM` | Terminated by signal |

### Listing Exit Codes

```bash
autotrader-scan --list-exit-codes
```

### Using Exit Codes in Scripts

**Bash:**

```bash
autotrader-scan --config config.yaml
EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo "✅ Success"
elif [ $EXIT_CODE -eq 10 ]; then
    echo "❌ Configuration error"
elif [ $EXIT_CODE -eq 24 ]; then
    echo "⏱️  Watchdog timeout"
else
    echo "❌ Failed with code $EXIT_CODE"
fi
```

**PowerShell:**

```powershell
autotrader-scan --config config.yaml
$exitCode = $LASTEXITCODE

switch ($exitCode) {
    0  { Write-Host "✅ Success" }
    10 { Write-Host "❌ Configuration error" }
    24 { Write-Host "⏱️  Watchdog timeout" }
    default { Write-Host "❌ Failed with code $exitCode" }
}
```

**Python:**

```python
import subprocess

result = subprocess.run(["autotrader-scan", "--config", "config.yaml"])

if result.returncode == 0:
    print("✅ Success")
elif result.returncode == 10:
    print("❌ Configuration error")
elif result.returncode == 24:
    print("⏱️  Watchdog timeout")
else:
    print(f"❌ Failed with code {result.returncode}")
```

---

## Best Practices

### 1. Configuration Management

```bash
# Store configs in version control
git add configs/*.yaml

# Use environment-specific configs
autotrader-scan --config configs/production.yaml
autotrader-scan --config configs/staging.yaml
autotrader-scan --config configs/development.yaml

# Never commit secrets
echo "*.secret.yaml" >> .gitignore
```

### 2. CI/CD Integration

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
    steps:
      - uses: actions/checkout@v3
      
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -e .
      
      - name: Run scan
        env:
          AUTOTRADER_ETHERSCAN_API_KEY: ${{ secrets.ETHERSCAN_API_KEY }}
          PYTHONHASHSEED: 0
        run: |
          autotrader-scan \
            --config configs/production.yaml \
            --deterministic \
            --seed 42 \
            --max-duration-seconds 3600 \
            --lock-file /tmp/scan.lock \
            --validate-output \
            --emit-metrics stdout \
            --log-format json
      
      - name: Upload results
        uses: actions/upload-artifact@v3
        if: always()
        with:
          name: scan-results
          path: reports/scans/
```

### 3. Error Handling

```bash
#!/bin/bash
set -euo pipefail

# Capture exit code
autotrader-scan --config config.yaml || EXIT_CODE=$?

# Handle errors
case ${EXIT_CODE:-0} in
  0)
    echo "✅ Scan completed successfully"
    ;;
  10|11|12)
    echo "❌ Configuration error - check config.yaml"
    exit 1
    ;;
  22)
    echo "⚠️  Another instance running - skipping"
    exit 0
    ;;
  24)
    echo "⏱️  Timeout exceeded - scan took too long"
    # Alert operations team
    curl -X POST https://alerts.example.com/notify \
      -d '{"message": "AutoTrader scan timeout"}'
    exit 1
    ;;
  130)
    echo "⚠️  Interrupted by user"
    exit 0
    ;;
  *)
    echo "❌ Scan failed with code $EXIT_CODE"
    exit 1
    ;;
esac
```

### 4. Monitoring & Observability

```bash
# Send metrics to monitoring system
autotrader-scan \
  --config config.yaml \
  --emit-metrics statsd \
  --statsd-host metrics.internal.com \
  --log-format json 2>&1 | \
  tee /var/log/autotrader/scan.log | \
  grep -v "^{" | \
  jq -r 'select(.level == "ERROR")'
```

### 5. Resource Management

```bash
# Limit memory usage (Linux)
ulimit -v 4194304  # 4GB

# Run with watchdog
autotrader-scan \
  --config config.yaml \
  --max-duration-seconds 1800 \
  --lock-file /var/run/autotrader.lock

# Clean up old artifacts
find reports/scans -type f -mtime +7 -delete
```

---

## Examples

### Example 1: Development

```bash
# Quick development scan
autotrader-scan \
  --config configs/development.yaml \
  --log-level DEBUG \
  --output /tmp/dev-scan
```

### Example 2: Staging/Testing

```bash
# Staging with validation
export PYTHONHASHSEED=0

autotrader-scan \
  --config configs/staging.yaml \
  --deterministic \
  --seed 42 \
  --validate-output \
  --log-format json
```

### Example 3: Production

```bash
# Full production setup
export AUTOTRADER_ETHERSCAN_API_KEY="${ETHERSCAN_KEY}"
export PYTHONHASHSEED=0

autotrader-scan \
  --config configs/production.yaml \
  --deterministic \
  --seed 42 \
  --max-duration-seconds 3600 \
  --lock-file /var/run/autotrader.lock \
  --emit-metrics statsd \
  --statsd-host metrics.prod.example.com \
  --validate-output \
  --log-format json \
  --log-level INFO
```

### Example 4: Scheduled Batch

```bash
#!/bin/bash
# cron: 0 */6 * * * /opt/autotrader/run-scan.sh

cd /opt/autotrader

# Load environment
source .env

# Run scan
autotrader-scan \
  --config configs/production.yaml \
  --max-duration-seconds 3600 \
  --lock-file /tmp/autotrader-cron.lock \
  --emit-metrics stdout > metrics-$(date +%Y%m%d-%H%M%S).jsonl \
  2>&1 | tee logs/scan-$(date +%Y%m%d-%H%M%S).log

# Archive old results
tar -czf archives/scan-$(date +%Y%m%d).tar.gz reports/scans/
```

### Example 5: Custom Strategy

```bash
# Create custom strategy module
cat > my_strategies.py <<'EOF'
class ConservativeStrategy:
    def scan(self, token):
        # Conservative scoring
        pass
    
    def scan_with_tree(self, token):
        # With tree-of-thought
        pass
EOF

# Register in pyproject.toml
cat >> pyproject.toml <<'EOF'
[project.entry-points."autotrader.strategies"]
conservative = "my_strategies:ConservativeStrategy"
EOF

# Reinstall
pip install -e .

# Use custom strategy
autotrader-scan \
  --config config.yaml \
  --strategy conservative
```

---

## Troubleshooting

### Issue: "Configuration file not found"

**Solution:**
```bash
# Check path
ls -la configs/example.yaml

# Use absolute path
autotrader-scan --config $(pwd)/configs/example.yaml
```

### Issue: "Lock acquisition failed"

**Solution:**
```bash
# Check if lock file exists
ls -la /tmp/autotrader.lock

# Remove stale lock (if safe)
rm /tmp/autotrader.lock

# Or use different lock file
autotrader-scan --config config.yaml --lock-file /tmp/scan-$(date +%s).lock
```

### Issue: "Strategy not found"

**Solution:**
```bash
# List available strategies
autotrader-scan --list-strategies

# Reinstall package
pip install -e .

# Use direct module path
autotrader-scan --config config.yaml --strategy src.core.pipeline:HiddenGemScanner
```

### Issue: Deterministic results differ

**Solution:**
```bash
# Ensure PYTHONHASHSEED is set
export PYTHONHASHSEED=0

# Check library versions
pip freeze

# Use same Python version
python --version
```

---

## Additional Resources

- [Exit Codes Reference](https://github.com/CrisisCore-Systems/Autotrader/blob/main/src/cli/exit_codes.py) - Complete exit code documentation
- [Output Schema](https://github.com/CrisisCore-Systems/Autotrader/blob/main/configs/output_schema.json) - JSON schema for validation
- [Example Configs](https://github.com/CrisisCore-Systems/Autotrader/tree/main/configs) - Sample configuration files
- [GitHub Issues](https://github.com/CrisisCore-Systems/AutoTrader/issues) - Report bugs

---

**Version:** 0.1.0  
**Last Updated:** October 8, 2025  
**Maintainer:** AutoTrader Team

# AutoTrader Scanner CLI - Quick Reference

Quick reference guide for the enhanced AutoTrader scanner CLI features.

## Installation

```bash
pip install -e .
autotrader-scan --version
```

## Basic Commands

```bash
# Simple scan
autotrader-scan --config configs/example.yaml

# Dry run (validate only)
autotrader-scan --config config.yaml --dry-run

# List strategies
autotrader-scan --list-strategies

# List exit codes
autotrader-scan --list-exit-codes
```

## Configuration Priority

1. **CLI args** (highest)
2. **Environment variables** (`AUTOTRADER_*`)
3. **YAML config** (lowest)

```bash
# Example: Override log level
AUTOTRADER_LOG_LEVEL=DEBUG autotrader-scan --config config.yaml
```

## Key Features

### 1. Config Resolution

```bash
# YAML config
autotrader-scan --config myconfig.yaml

# Env var override
AUTOTRADER_SCANNER_LIQUIDITY_THRESHOLD=100000 autotrader-scan --config config.yaml
```

### 2. Environment Variables

```bash
export AUTOTRADER_LOG_LEVEL=DEBUG
export AUTOTRADER_ETHERSCAN_API_KEY=abc123
export AUTOTRADER_SCANNER_LIQUIDITY_THRESHOLD=50000
```

### 3. JSON Schema Validation

```bash
autotrader-scan --config config.yaml --validate-output
```

### 4. Metrics Emission

```bash
# JSON lines to stdout
autotrader-scan --config config.yaml --emit-metrics stdout

# StatsD
autotrader-scan --config config.yaml --emit-metrics statsd --statsd-host metrics.local
```

### 5. Runtime Limits

```bash
# Watchdog (1 hour timeout)
autotrader-scan --config config.yaml --max-duration-seconds 3600

# Concurrency lock
autotrader-scan --config config.yaml --lock-file /tmp/scan.lock

# Both
autotrader-scan --config config.yaml --max-duration-seconds 3600 --lock-file /tmp/scan.lock
```

### 6. Plugin Strategies

```toml
# pyproject.toml
[project.entry-points."autotrader.strategies"]
my_strategy = "my_package:MyStrategy"
```

```bash
autotrader-scan --config config.yaml --strategy my_strategy
```

### 7. Deterministic Mode

```bash
export PYTHONHASHSEED=0
autotrader-scan --config config.yaml --deterministic --seed 42
```

### 8. Structured Logging

```bash
# JSON logging
autotrader-scan --config config.yaml --log-format json --log-level DEBUG
```

### 9. Dry Run

```bash
autotrader-scan --config config.yaml --dry-run
```

## Exit Codes (Key Ones)

| Code | Name | When |
|------|------|------|
| 0 | SUCCESS | All good |
| 10 | CONFIG_ERROR | Config issue |
| 13 | SCHEMA_VALIDATION_ERROR | Output invalid |
| 22 | LOCK_ERROR | Another instance running |
| 24 | WATCHDOG_TIMEOUT | Took too long |
| 41 | STRATEGY_NOT_FOUND | Strategy missing |
| 130 | SIGINT | Ctrl+C |

Full list: `autotrader-scan --list-exit-codes`

## Production Example

```bash
#!/bin/bash
export AUTOTRADER_ETHERSCAN_API_KEY="${ETHERSCAN_KEY}"
export PYTHONHASHSEED=0

autotrader-scan \
  --config configs/production.yaml \
  --deterministic \
  --seed 42 \
  --max-duration-seconds 3600 \
  --lock-file /var/run/autotrader.lock \
  --emit-metrics statsd \
  --statsd-host metrics.prod.local \
  --validate-output \
  --log-format json \
  --log-level INFO

EXIT_CODE=$?
case $EXIT_CODE in
  0)  echo "✅ Success" ;;
  22) echo "⚠️  Lock held (another instance running)" ;;
  24) echo "⏱️  Timeout exceeded" ;;
  *)  echo "❌ Failed: $EXIT_CODE" ;;
esac
```

## CI/CD Integration

```yaml
# .github/workflows/scan.yml
- name: Run Scan
  env:
    AUTOTRADER_ETHERSCAN_API_KEY: ${{ secrets.ETHERSCAN_KEY }}
    PYTHONHASHSEED: 0
  run: |
    autotrader-scan \
      --config configs/ci.yaml \
      --deterministic \
      --max-duration-seconds 1800 \
      --validate-output \
      --emit-metrics stdout \
      --log-format json
```

## Metric Output (stdout)

```json
{"name": "scan_total_duration", "value": 12500, "type": "timer", "timestamp": 1696723200.0, "unit": "ms"}
{"name": "tokens_scanned", "value": 1, "type": "counter", "timestamp": 1696723205.0}
{"name": "gem_score_VOID", "value": 78.5, "type": "gauge", "timestamp": 1696723210.0}
```

Parse with:
```bash
cat metrics.jsonl | jq -r 'select(.type=="timer") | "\(.name): \(.value)ms"'
```

## Environment Variable Examples

```bash
# Simple
export AUTOTRADER_LOG_LEVEL=DEBUG

# Nested (scanner.liquidity_threshold)
export AUTOTRADER_SCANNER_LIQUIDITY_THRESHOLD=100000

# Boolean
export AUTOTRADER_DETERMINISTIC=true

# JSON
export AUTOTRADER_TAGS='["prod","crypto","scanner"]'
```

## Troubleshooting

### Config not found
```bash
autotrader-scan --config $(pwd)/configs/example.yaml
```

### Lock held
```bash
rm /tmp/autotrader.lock  # If safe
# or
autotrader-scan --lock-file /tmp/scan-$$.lock
```

### Strategy not found
```bash
autotrader-scan --list-strategies
pip install -e .  # Reinstall
```

### Non-deterministic results
```bash
export PYTHONHASHSEED=0
pip freeze > requirements-exact.txt
```

## More Info

- **Full Guide:** [CLI_GUIDE.md](./CLI_GUIDE.md)
- **Exit Codes:** Run `autotrader-scan --list-exit-codes`
- **Strategies:** Run `autotrader-scan --list-strategies`
- **Schema:** [output_schema.json](https://github.com/CrisisCore-Systems/Autotrader/blob/main/configs/output_schema.json)

---

**Quick Help:** `autotrader-scan --help`

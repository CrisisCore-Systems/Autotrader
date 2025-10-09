# CLI Examples

Practical examples of using the AutoTrader CLI.

## Basic Usage

**Basic scan with default configuration**

```bash
autotrader-scan
```

**Scan with specific config file**

```bash
autotrader-scan --config /path/to/config.yaml
```

**Scan with custom lock timeout**

```bash
autotrader-scan --lock-ttl 3600
```

**Print effective configuration**

```bash
autotrader-scan --print-effective-config
```

**Generate reproducibility stamp**

```bash
autotrader-scan --enable-repro-stamp
```

**Verbose logging**

```bash
autotrader-scan --log-level DEBUG
```


## Advanced Examples

### Reproducible Scan with Stamp

```bash
autotrader-scan \
    --enable-repro-stamp \
    --deterministic \
    --random-seed 42 \
    --output results.json
```

The output will include a `repro_stamp` field:

```json
{
  "repro_stamp": {
    "timestamp": "2025-10-08T12:00:00Z",
    "git_commit": "abc123...",
    "git_branch": "main",
    "config_hash": "def456...",
    "input_hashes": {"data.csv": "789abc..."},
    "random_seed": 42
  }
}
```

### Validate Configuration Before Scan

```bash
# Check effective configuration
autotrader-scan --print-effective-config

# Then run actual scan
autotrader-scan
```

### Production Scan with Monitoring

```bash
autotrader-scan \
    --config /etc/autotrader/production.yaml \
    --lock-ttl 1800 \
    --log-file /var/log/autotrader.log \
    --metrics-port 9090 \
    --enable-tracing \
    --output /var/lib/autotrader/results.json
```

### Custom Strategy with Parameters

```bash
autotrader-scan \
    --strategy my_strategy \
    --strategy-params '{"threshold": 0.8, "lookback": 30}' \
    --output custom-results.json
```

### Debugging Configuration Issues

```bash
# See all deprecation warnings
autotrader-scan --print-deprecation-warnings

# See effective configuration with origins
autotrader-scan --print-effective-config --man-format md > config-debug.md

# Validate schema
autotrader-scan --validate-schema --schema-version 1.0.0
```

## Scripting Patterns

### Retry on Lock Failure

```bash
#!/bin/bash
MAX_RETRIES=3
RETRY_DELAY=60

for i in $(seq 1 $MAX_RETRIES); do
    autotrader-scan
    EXIT_CODE=$?
    
    if [ $EXIT_CODE -eq 0 ]; then
        echo "Scan completed successfully"
        exit 0
    elif [ $EXIT_CODE -eq 21 ]; then
        echo "Lock held, retrying in ${RETRY_DELAY}s (attempt $i/$MAX_RETRIES)"
        sleep $RETRY_DELAY
    else
        echo "Scan failed with exit code $EXIT_CODE"
        exit $EXIT_CODE
    fi
done

echo "Failed after $MAX_RETRIES attempts"
exit 21
```

### Parallel Scans with Different Configs

```bash
#!/bin/bash
# Run multiple scans in parallel with different strategies

autotrader-scan --strategy momentum --output momentum.json --no-lock &
autotrader-scan --strategy mean_reversion --output mean_reversion.json --no-lock &
autotrader-scan --strategy breakout --output breakout.json --no-lock &

wait  # Wait for all scans to complete
echo "All scans completed"
```

!!! warning "Lock Disabled"
    The `--no-lock` flag disables concurrency control. Only use this when
    you're certain the scans won't interfere with each other.
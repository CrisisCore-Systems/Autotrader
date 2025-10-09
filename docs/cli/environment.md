# Environment Variables

AutoTrader CLI can be configured using environment variables.
These variables are prefixed with `AUTOTRADER_`.

## Configuration Precedence

Settings are applied in the following order (later values override earlier):

1. **Defaults** - Built-in default values
2. **Config file** - Values from `config.yaml`
3. **Environment variables** - `AUTOTRADER_*` variables
4. **Command-line flags** - Explicit CLI arguments

Use `--print-effective-config` to see the final merged configuration.

## Available Variables

### `AUTOTRADER_CONFIG`

Path to configuration file (overrides default locations)

### `AUTOTRADER_LOG_LEVEL`

Logging level (DEBUG, INFO, WARNING, ERROR)

### `AUTOTRADER_METRICS_PORT`

Port for Prometheus metrics endpoint

### `AUTOTRADER_DATA_DIR`

Directory for data files and cache

### `AUTOTRADER_LOCK_TTL`

Default lock timeout in seconds

### `AUTOTRADER_API_KEY`

API key for data providers

### `AUTOTRADER_DETERMINISTIC`

Enable deterministic mode (1/true/yes)


## Nested Configuration

For nested configuration keys, use double underscores (`__`):

```bash
# Set nested value: data.provider = "yahoo"
export AUTOTRADER_DATA__PROVIDER=yahoo

# Set nested value: metrics.port = 9091
export AUTOTRADER_METRICS__PORT=9091
```

## Boolean Values

Boolean environment variables accept:

- **True**: `1`, `true`, `yes`, `on` (case-insensitive)
- **False**: `0`, `false`, `no`, `off` (case-insensitive)

```bash
export AUTOTRADER_DETERMINISTIC=true
export AUTOTRADER_DETERMINISTIC=1
export AUTOTRADER_DETERMINISTIC=yes
```

## Examples

### Development Configuration

```bash
export AUTOTRADER_LOG_LEVEL=DEBUG
export AUTOTRADER_METRICS_PORT=9091
export AUTOTRADER_DATA_DIR=./cache
autotrader-scan
```

### Production Configuration

```bash
export AUTOTRADER_CONFIG=/etc/autotrader/production.yaml
export AUTOTRADER_LOG_LEVEL=WARNING
export AUTOTRADER_LOG_FILE=/var/log/autotrader.log
export AUTOTRADER_LOCK_TTL=1800
autotrader-scan
```

### CI/CD Configuration

```bash
export AUTOTRADER_DETERMINISTIC=true
export AUTOTRADER_RANDOM_SEED=42
export AUTOTRADER_ENABLE_REPRO_STAMP=true
export AUTOTRADER_NO_LOCK=true  # Allow parallel CI builds
autotrader-scan --output results.json
```
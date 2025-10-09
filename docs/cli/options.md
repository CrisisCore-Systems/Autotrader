# Command-Line Options

Complete reference for all `autotrader-scan` command-line options.

!!! tip "Auto-Generated"
    This page is automatically generated from the CLI parser definition.
    Last updated: October 2025

### `--config` `PATH`

Path to configuration file (YAML format)

### `--print-effective-config`

Print effective merged configuration with origins and exit
  
**Default**: `False`

### `--log-level` `LOG_LEVEL`

Set logging verbosity level
  
**Default**: `INFO`

### `--log-file` `PATH`

Write logs to file instead of console

### `--lock-ttl` `SECONDS`

Lock timeout in seconds (auto-cleanup stale locks)

### `--no-lock`

Disable file locking (use with caution)
  
**Default**: `False`

### `--enable-repro-stamp`

Generate reproducibility stamp (git commit, input hashes, env)
  
**Default**: `False`

### `--deterministic`

Enable deterministic mode (fixed random seed, sorted outputs)
  
**Default**: `False`

### `--random-seed` `SEED`

Random seed for reproducibility

### `--metrics-port` `PORT`

Port for Prometheus metrics endpoint
  
**Default**: `9090`

### `--enable-tracing`

Enable distributed tracing
  
**Default**: `False`

### `--data-provider` `DATA_PROVIDER`

Data provider to use
  
**Default**: `yahoo`

### `--api-key` `KEY`

API key for data provider (or use AUTOTRADER_API_KEY env var)

### `--data-dir` `PATH`

Directory for data cache

### `--strategy` `NAME`

Strategy plugin to use

### `--strategy-params` `JSON`

Strategy parameters as JSON string

### `--output` `PATH`

Output file path (default: stdout)

### `--output-format` `OUTPUT_FORMAT`

Output format
  
**Default**: `json`

### `--pretty`

Pretty-print output (human-readable formatting)
  
**Default**: `False`

### `--validate-schema`

Validate output against schema before writing
  
**Default**: `False`

### `--schema-version` `VERSION`

Require specific schema version

### `--print-deprecation-warnings`

Print deprecation warnings and migration guide
  
**Default**: `False`

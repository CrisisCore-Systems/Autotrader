# Unified Logging Configuration Guide

## Overview

AutoTrader uses **structured JSON logging** via `src/core/logging_config.py` for consistent, machine-parseable logs across all components (CLI, backtest harness, services, notebooks).

## Architecture

```
┌─────────────────────────────────────────────┐
│     src/core/logging_config.py              │
│  (Centralized Configuration)                │
│  - Structured JSON logs                     │
│  - Context binding (correlation IDs)        │
│  - Environment injection                    │
└─────────────────────────────────────────────┘
              ▼           ▼           ▼
    ┌──────────────┐ ┌──────────┐ ┌──────────┐
    │  CLI Tools   │ │ Services │ │ Backtest │
    │ cli_backtest │ │   API    │ │ Harness  │
    └──────────────┘ └──────────┘ └──────────┘
              ▼           ▼           ▼
         JSON Logs → Aggregator → Observability Stack
```

## Quick Start

### 1. Basic Setup (CLI/Scripts)

```python
from src.core.logging_config import init_logging, get_logger

# Initialize once at application startup
logger = init_logging(
    service_name="autotrader-cli",
    level="INFO"  # DEBUG, INFO, WARNING, ERROR, CRITICAL
)

# Use throughout application
logger = get_logger(__name__)
logger.info("Application started", version="1.0.0")
```

### 2. CLI Backtest Integration

**File**: `pipeline/cli_backtest.py`

```python
from src.core.logging_config import setup_structured_logging, get_logger

def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint with structured logging."""
    
    # Initialize structured logging
    logger = setup_structured_logging(
        service_name="backtest-cli",
        level=args.log_level,  # From argparse
        enable_json=True,
        enable_console=True
    )
    
    # Bind context for this run
    logger = logger.bind(
        backtest_id=generate_id(),
        engine=args.engine,
        start_date=str(args.start),
        end_date=str(args.end)
    )
    
    logger.info("Starting backtest", k=args.k, walk_days=args.walk)
    
    try:
        results = run_backtest(config)
        logger.info("Backtest completed", 
                   output_path=str(results),
                   windows=len(results.windows))
        return 0
    except Exception as e:
        logger.error("Backtest failed", 
                    error=str(e), 
                    error_type=type(e).__name__)
        return 1
```

### 3. Service Integration (FastAPI)

**File**: `src/services/exporter.py`

```python
from fastapi import FastAPI, Request
from src.core.logging_config import setup_structured_logging, LogContext
import uuid

app = FastAPI()

# Initialize once at startup
@app.on_event("startup")
async def startup_event():
    global logger
    logger = setup_structured_logging(
        service_name="autotrader-api",
        environment="production",
        version="1.0.0",
        level="INFO"
    )
    logger.info("API server starting")

# Middleware for request correlation
@app.middleware("http")
async def add_correlation_id(request: Request, call_next):
    correlation_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
    
    # Bind correlation ID to all logs in this request
    with LogContext(logger, correlation_id=correlation_id) as req_logger:
        req_logger.info("Request received",
                       method=request.method,
                       path=request.url.path,
                       client=request.client.host)
        
        response = await call_next(request)
        
        req_logger.info("Request completed",
                       status_code=response.status_code)
        
        response.headers["X-Correlation-ID"] = correlation_id
        return response

@app.get("/scan/{token}")
async def scan_token(token: str):
    logger = get_logger(__name__)
    logger.info("Scanning token", token=token)
    # ... rest of handler
```

### 4. Backtest Harness Integration

**File**: `backtest/harness.py`

```python
from src.core.logging_config import get_logger

def evaluate_backtest(
    features_df: pd.DataFrame,
    k: int = 5,
    extended_metrics: bool = False
) -> dict:
    """Run backtest evaluation with structured logging."""
    
    logger = get_logger(__name__).bind(
        component="harness",
        k=k,
        extended_metrics=extended_metrics
    )
    
    logger.info("Starting harness evaluation", 
               num_samples=len(features_df))
    
    try:
        # Compute metrics
        precision = calculate_precision_at_k(features_df, k)
        logger.info("Metrics computed", precision_at_k=precision)
        
        if extended_metrics:
            logger.debug("Computing extended metrics")
            ic = compute_information_coefficient(features_df)
            logger.info("Extended metrics computed", ic=ic)
        
        return {"precision_at_k": precision}
        
    except Exception as e:
        logger.error("Harness evaluation failed",
                    error=str(e),
                    error_type=type(e).__name__,
                    exc_info=True)
        raise
```

### 5. Worker/Background Tasks

**File**: `src/core/worker.py`

```python
from src.core.logging_config import init_logging, get_logger
import time

def main():
    """Worker process with structured logging."""
    
    logger = init_logging(
        service_name="autotrader-worker",
        level="INFO"
    )
    
    logger = logger.bind(
        worker_id=os.getpid(),
        hostname=socket.gethostname()
    )
    
    logger.info("Worker started")
    
    while True:
        try:
            task = queue.get(timeout=5)
            
            task_logger = logger.bind(
                task_id=task.id,
                task_type=task.type
            )
            
            task_logger.info("Processing task")
            
            start_time = time.time()
            result = process_task(task)
            duration = time.time() - start_time
            
            task_logger.info("Task completed",
                           duration_ms=duration * 1000,
                           result_size=len(result))
            
        except queue.Empty:
            continue
        except Exception as e:
            task_logger.error("Task failed",
                            error=str(e),
                            exc_info=True)
```

## Configuration Options

### Environment Variables

```bash
# Control logging behavior via environment
export ENVIRONMENT=production        # dev, staging, production
export APP_VERSION=1.0.0            # Application version
export LOG_LEVEL=INFO               # DEBUG, INFO, WARNING, ERROR, CRITICAL
export LOG_FORMAT=json              # json or console
```

### setup_structured_logging() Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `service_name` | `str` | `"autotrader"` | Service identifier |
| `environment` | `str` | `$ENVIRONMENT` or `"development"` | Deployment env |
| `version` | `str` | `$APP_VERSION` or `"0.1.0"` | App version |
| `level` | `str` | `"INFO"` | Log level |
| `enable_console` | `bool` | `True` | Console output |
| `enable_json` | `bool` | `True` | JSON formatting |

## Log Levels

| Level | When to Use | Example |
|-------|-------------|---------|
| `DEBUG` | Development, verbose tracing | `logger.debug("Feature vector", shape=X.shape)` |
| `INFO` | Normal operations, milestones | `logger.info("Backtest completed", duration=10.5)` |
| `WARNING` | Recoverable issues | `logger.warning("Rate limit hit, retrying")` |
| `ERROR` | Errors requiring attention | `logger.error("API request failed", status=500)` |
| `CRITICAL` | System-level failures | `logger.critical("Database connection lost")` |

## Structured Fields

### Standard Fields (Automatic)

```json
{
  "timestamp": "2025-10-09T14:23:45.123456Z",
  "level": "INFO",
  "logger": "backtest.harness",
  "service": "autotrader-cli",
  "environment": "production",
  "version": "1.0.0",
  "event": "Backtest completed"
}
```

### Context Binding

```python
# Bind persistent context
logger = logger.bind(
    user_id="user123",
    request_id="req-abc",
    token="PEPE"
)

# All subsequent logs include these fields
logger.info("Scanning token")  # Includes user_id, request_id, token
logger.info("Score computed")  # Same context
```

### Ad-hoc Fields

```python
# Add fields to single log entry
logger.info("Metrics computed",
           precision=0.85,
           recall=0.72,
           f1_score=0.78)
```

## Integration Examples

### CLI Argument Parsing

```python
# pipeline/cli_backtest.py
def build_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO",
        help="Logging level"
    )
    return parser

def main():
    args = parser.parse_args()
    
    # Use CLI argument for log level
    logger = init_logging(level=args.log_level)
    
    if args.log_level == "DEBUG":
        logger.debug("Debug mode enabled")
```

### Docker Compose Logging

```yaml
# infra/docker-compose.yml
services:
  api:
    environment:
      - LOG_LEVEL=INFO
      - LOG_FORMAT=json
      - ENVIRONMENT=production
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "3"
```

### Log Aggregation (Filebeat/Fluentd)

```yaml
# Example Filebeat config
filebeat.inputs:
  - type: container
    paths:
      - '/var/lib/docker/containers/*/*.log'
    
processors:
  - decode_json_fields:
      fields: ["message"]
      target: ""
      overwrite_keys: true

output.elasticsearch:
  hosts: ["elasticsearch:9200"]
  index: "autotrader-logs-%{+yyyy.MM.dd}"
```

### Querying Logs (Elasticsearch/Kibana)

```
# Find all backtest errors
level:ERROR AND service:autotrader-cli

# Find slow operations
duration_ms:>5000 AND event:"Backtest completed"

# Trace specific request
correlation_id:"abc-123-xyz"
```

## Best Practices

### ✅ DO

```python
# Use structured fields, not string interpolation
logger.info("User logged in", user_id=user_id, ip=ip_address)

# Bind context for related operations
logger = logger.bind(request_id=req_id)

# Log exceptions with traceback
try:
    risky_operation()
except Exception as e:
    logger.exception("Operation failed", operation="risky_op")

# Use appropriate log levels
logger.debug("Cache miss", key=key)        # Development
logger.info("Request processed", status=200)  # Production
logger.error("Database timeout", timeout=30)  # Requires attention
```

### ❌ DON'T

```python
# Don't use string formatting
logger.info(f"User {user_id} logged in from {ip}")  # BAD

# Don't log sensitive data
logger.info("Auth attempt", password=password)  # NEVER

# Don't use print statements
print("Processing...")  # Use logger.info()

# Don't log in hot loops without sampling
for i in range(1_000_000):
    logger.debug(f"Processing item {i}")  # Too verbose!
```

## Testing

### Unit Tests

```python
# tests/test_logging.py
from src.core.logging_config import setup_structured_logging
import logging
from io import StringIO

def test_structured_logging(caplog):
    """Test structured logging output."""
    logger = setup_structured_logging(
        service_name="test",
        level="INFO"
    )
    
    logger.info("Test event", key="value")
    
    assert "test" in caplog.text
    assert "Test event" in caplog.text

def test_log_level_filtering():
    """Test log level filtering."""
    logger = setup_structured_logging(level="WARNING")
    
    with caplog.at_level(logging.WARNING):
        logger.debug("Debug message")  # Should not appear
        logger.warning("Warning message")  # Should appear
        
    assert "Debug message" not in caplog.text
    assert "Warning message" in caplog.text
```

### Integration Tests

```python
def test_cli_logging_integration():
    """Test CLI uses structured logging."""
    result = subprocess.run(
        ["python", "pipeline/cli_backtest.py", 
         "--start", "2024-01-01",
         "--end", "2024-01-31",
         "--log-level", "DEBUG"],
        capture_output=True,
        text=True
    )
    
    # Check for structured log fields
    assert '"level":"DEBUG"' in result.stderr
    assert '"service":"backtest-cli"' in result.stderr
```

## Performance Considerations

### Sampling for High-Volume Logs

```python
import random

def should_log_debug() -> bool:
    """Sample debug logs at 1% rate."""
    return random.random() < 0.01

for item in large_dataset:
    if should_log_debug():
        logger.debug("Processing item", item_id=item.id)
```

### Lazy Evaluation

```python
# Avoid expensive operations if debug not enabled
if logger.isEnabledFor(logging.DEBUG):
    logger.debug("Complex state", state=compute_expensive_state())
```

## Troubleshooting

### Logs Not Appearing

1. Check log level: `LOG_LEVEL=DEBUG`
2. Verify logger initialization: `init_logging()` called?
3. Check handlers: `logging.getLogger().handlers`

### JSON Parsing Errors

```python
# Ensure all fields are JSON-serializable
logger.info("Event", 
           timestamp=datetime.now().isoformat(),  # Not datetime object
           data={"key": "value"})  # Not custom object
```

### Performance Issues

```python
# Use lazy string formatting
logger.debug("Value: %s", expensive_func())  # Only called if DEBUG enabled
```

## Migration from print() Statements

```python
# BEFORE
print("Starting process...")
print(f"Processed {count} items in {duration}s")
print(f"ERROR: {error}")

# AFTER
logger = get_logger(__name__)
logger.info("Starting process")
logger.info("Processing complete", count=count, duration=duration)
logger.error("Processing failed", error=str(error), exc_info=True)
```

## Related Documentation

- `src/core/logging_config.py` - Core implementation
- `docs/OBSERVABILITY_GUIDE.md` - Full observability stack
- `docs/CLI_BACKTEST_GUIDE.md` - CLI usage examples
- `status-reports/quick-reference/OBSERVABILITY_QUICK_REF.md` - Metrics and tracing

## Quick Reference Card

| Use Case | Code Snippet |
|----------|--------------|
| **Initialize** | `logger = init_logging(service_name="myapp", level="INFO")` |
| **Get Logger** | `logger = get_logger(__name__)` |
| **Basic Log** | `logger.info("Event happened", key=value)` |
| **Bind Context** | `logger = logger.bind(request_id=req_id)` |
| **Log Exception** | `logger.exception("Error", exc_info=True)` |
| **Scoped Context** | `with LogContext(logger, task_id=id) as l: l.info(...)` |
| **CLI Log Level** | `--log-level DEBUG` |
| **Environment** | `export LOG_LEVEL=DEBUG` |

---

**Last Updated**: 2025-10-09  
**Status**: ✅ Production Ready  
**Maintainer**: Engineering Team

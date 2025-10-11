# 📊 Logging & Metrics Quick Reference

**AutoTrader Observability Stack**  
Complete guide to structured logging and Prometheus metrics instrumentation

---

## 🚀 Quick Start

### 1. Initialize Logging

```python
from src.core.logging_config import init_logging, get_logger

# At application startup
logger = init_logging(service_name="my-service", level="INFO")

# In any module
logger = get_logger(__name__)

logger.info(
    "event_name",
    key1="value1",
    key2=123,
    custom_field="data"
)
```

**Output (JSON):**
```json
{
  "timestamp": "2025-10-08T12:34:56.789Z",
  "level": "INFO",
  "logger": "my_module",
  "event": "event_name",
  "key1": "value1",
  "key2": 123,
  "custom_field": "data",
  "service": "my-service",
  "environment": "production",
  "version": "0.1.0"
}
```

### 2. Record Metrics

```python
from src.core.metrics import (
    record_scan_request,
    record_scan_duration,
    record_gem_score,
    record_scan_error,
)

# Record scan operations
record_scan_request("BTC", "success")
record_scan_duration("BTC", 2.34, "success")
record_gem_score("BTC", 85.5)

# Record errors
record_scan_error("BTC", "timeout")
```

### 3. Add Distributed Tracing

```python
from src.core.tracing import trace_operation, add_span_attributes

with trace_operation("my_operation", attributes={"token": "BTC"}):
    # Your code here
    result = process_token()
    add_span_attributes(score=result.score)
```

---

## 📝 Structured Logging Patterns

### Basic Logging

```python
logger = get_logger(__name__)

# Info level
logger.info("user_logged_in", user_id=123, ip="1.2.3.4")

# Warning level
logger.warning("rate_limit_approaching", current=95, limit=100)

# Error level
logger.error("api_call_failed", endpoint="/api/token", error="timeout")

# With exception
try:
    risky_operation()
except Exception as e:
    logger.exception("operation_failed", operation="risky_operation")
```

### Context Binding

```python
from src.core.logging_config import LogContext

# Bind context for a scope
with LogContext(logger, request_id="abc-123", user_id=456) as scoped_logger:
    scoped_logger.info("processing_request")
    scoped_logger.info("request_completed")
    # All logs include request_id and user_id

# Or bind permanently
request_logger = logger.bind(request_id="abc-123", user_id=456)
request_logger.info("event1")  # Includes context
request_logger.info("event2")  # Includes context
```

### Structured Event Names

**Best Practices:**
- Use `snake_case` for event names
- Use descriptive, action-oriented names
- Include entity type in name

```python
# ✅ Good
logger.info("scan_started", token="BTC")
logger.info("scan_completed", token="BTC", duration=2.3)
logger.info("token_flagged", token="SCAM", reason="honeypot")

# ❌ Avoid
logger.info("Started scanning BTC")  # Not structured
logger.info("done")  # Too vague
```

---

## 📊 Prometheus Metrics Guide

### Available Metric Types

1. **Counter** - Monotonically increasing value
2. **Histogram** - Distribution of values (latency, sizes)
3. **Gauge** - Value that can go up or down

### Scanner Metrics

```python
from src.core.metrics import (
    record_scan_request,
    record_scan_duration,
    record_scan_error,
    record_gem_score,
    record_confidence_score,
    record_flagged_token,
)

# Scan lifecycle
record_scan_request("BTC", status="success")  # Counter
record_scan_duration("BTC", 2.3, status="success")  # Histogram
record_scan_error("BTC", error_type="timeout")  # Counter

# Score distributions
record_gem_score("BTC", 85.5)  # Histogram (0-100)
record_confidence_score("BTC", 0.92)  # Histogram (0-1)

# Flagging
record_flagged_token("BTC", flag_reason="high_risk")  # Counter
```

**Exposed Metrics:**
- `scan_requests_total{token_symbol, status}`
- `scan_duration_seconds{token_symbol, status}`
- `scan_errors_total{token_symbol, error_type}`
- `gem_score_distribution{token_symbol}`
- `confidence_score_distribution{token_symbol}`
- `flagged_tokens_total{token_symbol, flag_reason}`

### Data Source Metrics

```python
from src.core.metrics import (
    record_data_source_request,
    record_data_source_latency,
    record_data_source_error,
    record_cache_hit,
    record_cache_miss,
)

# External API calls
record_data_source_request("coingecko", "/coins/markets", "success")
record_data_source_latency("coingecko", "/coins/markets", 0.234)

# Errors
record_data_source_error("coingecko", "/coins/markets", "rate_limit")

# Cache metrics
record_cache_hit("coingecko", "/coins/markets")
record_cache_miss("coingecko", "/coins/markets")
```

### API Metrics

```python
from src.core.metrics import (
    record_api_request,
    record_api_duration,
    record_api_error,
    ActiveRequestTracker,
)

# HTTP endpoints
record_api_request("GET", "/api/tokens", 200)
record_api_duration("GET", "/api/tokens", 0.123)
record_api_error("GET", "/api/tokens", "validation_error")

# Track active requests
with ActiveRequestTracker("GET", "/api/tokens"):
    # Process request
    pass
```

### LLM Metrics

```python
from src.core.metrics import (
    record_llm_request,
    record_llm_latency,
    record_llm_tokens,
    record_llm_cost,
)

# LLM usage
record_llm_request("groq", "llama3-70b", "success")
record_llm_latency("groq", "llama3-70b", 1.23)
record_llm_tokens("groq", "llama3-70b", "input", 150)
record_llm_tokens("groq", "llama3-70b", "output", 200)
record_llm_cost("groq", "llama3-70b", 0.0015)
```

---

## 🔍 Distributed Tracing

### Basic Tracing

```python
from src.core.tracing import trace_operation, add_span_attributes

with trace_operation("fetch_token_data", attributes={"token": "BTC"}):
    data = fetch_from_api()
    add_span_attributes(records_fetched=len(data))
```

### Function Decorators

```python
from src.core.tracing import trace_function

@trace_function("calculate_score")
def calculate_gem_score(token):
    # Function is automatically traced
    return score

# Async functions
@trace_async_function("async_operation")
async def fetch_data():
    return await api_call()
```

### Trace Context

```python
from src.core.tracing import get_trace_id, add_span_event

# Get current trace ID for correlation
trace_id = get_trace_id()
logger.info("processing", trace_id=trace_id)

# Add events to current span
add_span_event("cache_miss", {"key": "BTC"})
add_span_event("retry_attempt", {"attempt": 2})
```

---

## 🎯 Complete Example: Monitored Operation

```python
import time
from src.core.logging_config import get_logger, LogContext
from src.core.metrics import (
    record_scan_request,
    record_scan_duration,
    record_scan_error,
    record_gem_score,
)
from src.core.tracing import trace_operation, add_span_attributes, get_trace_id

logger = get_logger(__name__)

def scan_token(token: str):
    """Fully instrumented token scan with logging, metrics, and tracing."""
    
    start_time = time.time()
    
    # Bind context for all logs in this function
    with LogContext(logger, token=token, trace_id=get_trace_id()) as log:
        log.info("scan_started")
        
        try:
            # Distributed tracing
            with trace_operation("token_scan", attributes={"token": token}):
                
                # Simulate scan operations
                log.info("fetching_market_data")
                market_data = fetch_market_data(token)
                add_span_attributes(data_sources=len(market_data))
                
                log.info("calculating_score")
                score = calculate_score(market_data)
                add_span_attributes(gem_score=score)
                
                # Calculate duration
                duration = time.time() - start_time
                
                # Record metrics
                record_scan_request(token, "success")
                record_scan_duration(token, duration, "success")
                record_gem_score(token, score)
                
                # Log completion
                log.info(
                    "scan_completed",
                    gem_score=score,
                    duration_seconds=duration,
                )
                
                return {"token": token, "score": score, "status": "success"}
                
        except Exception as e:
            duration = time.time() - start_time
            
            # Record error metrics
            record_scan_request(token, "failure")
            record_scan_duration(token, duration, "failure")
            record_scan_error(token, type(e).__name__)
            
            # Log error
            log.error(
                "scan_failed",
                error_type=type(e).__name__,
                error_message=str(e),
                duration_seconds=duration,
            )
            
            raise
```

---

## 🖥️ Viewing Metrics

### Start Metrics Server

```bash
# Start on default port 9090
python -m src.services.metrics_server

# Custom port
python -m src.services.metrics_server --port 9091

# With specific log level
python -m src.services.metrics_server --port 9090 --log-level DEBUG
```

### Query Metrics Endpoint

```bash
# View all metrics
curl http://localhost:9090/metrics

# Filter specific metrics
curl http://localhost:9090/metrics | grep scan_requests

# With PowerShell
curl http://localhost:9090/metrics | Select-String -Pattern "scan_requests"
```

### PromQL Queries

```promql
# Scan success rate (last 5 minutes)
rate(scan_requests_total{status="success"}[5m])

# Average scan duration
rate(scan_duration_seconds_sum[5m]) / rate(scan_duration_seconds_count[5m])

# P95 latency
histogram_quantile(0.95, rate(scan_duration_seconds_bucket[5m]))

# Error rate percentage
100 * (
  rate(scan_errors_total[5m]) / 
  rate(scan_requests_total[5m])
)

# Cache hit ratio
rate(data_source_cache_hits_total[5m]) / 
(rate(data_source_cache_hits_total[5m]) + rate(data_source_cache_misses_total[5m]))
```

---

## 📋 Production Checklist

### ✅ Logging

- [ ] JSON logging enabled
- [ ] All critical operations logged
- [ ] Errors include full context
- [ ] Sensitive data filtered
- [ ] Log aggregation configured (ELK, Datadog, etc.)

### ✅ Metrics

- [ ] Prometheus server running
- [ ] Metrics endpoint exposed
- [ ] Grafana dashboards created
- [ ] Alert rules configured
- [ ] Metrics retention policy set

### ✅ Tracing

- [ ] OpenTelemetry configured
- [ ] Trace sampling rate set
- [ ] Jaeger/Zipkin backend configured
- [ ] Service mesh integration (if applicable)
- [ ] Trace ID propagation tested

---

## 🐛 Troubleshooting

### Metrics Not Showing

```python
from src.core.metrics import is_prometheus_available

if not is_prometheus_available():
    print("Install: pip install prometheus-client")
```

### Logs Not in JSON Format

```python
from src.core.logging_config import init_logging

# Ensure JSON format is enabled
logger = init_logging(service_name="my-app", level="INFO")
```

### Trace IDs Missing

```python
from src.core.tracing import is_tracing_available, get_trace_id

if not is_tracing_available():
    print("Install: pip install opentelemetry-api opentelemetry-sdk")
else:
    print(f"Current trace: {get_trace_id()}")
```

---

## 📚 Resources

- **Full Guide**: [docs/OBSERVABILITY_GUIDE.md](docs/OBSERVABILITY_GUIDE.md)
- **Metrics Reference**: [src/core/metrics.py](src/core/metrics.py)
- **Logging Config**: [src/core/logging_config.py](src/core/logging_config.py)
- **Tracing**: [src/core/tracing.py](src/core/tracing.py)

---

## 🎯 Common Patterns

### Pattern 1: Monitored API Endpoint

```python
from fastapi import FastAPI
from src.core.metrics import record_api_request, record_api_duration
from src.core.logging_config import get_logger
from src.core.tracing import trace_operation
import time

app = FastAPI()
logger = get_logger(__name__)

@app.get("/api/scan/{token}")
async def scan_endpoint(token: str):
    start = time.time()
    
    with trace_operation("api_scan", attributes={"token": token}):
        try:
            result = scan_token(token)
            duration = time.time() - start
            
            record_api_request("GET", "/api/scan", 200)
            record_api_duration("GET", "/api/scan", duration)
            
            logger.info("api_request_completed", token=token, duration=duration)
            
            return result
            
        except Exception as e:
            duration = time.time() - start
            
            record_api_request("GET", "/api/scan", 500)
            record_api_duration("GET", "/api/scan", duration)
            
            logger.error("api_request_failed", token=token, error=str(e))
            
            raise
```

### Pattern 2: Batch Processing

```python
def process_batch(tokens: list):
    logger.info("batch_started", batch_size=len(tokens))
    
    results = []
    for token in tokens:
        try:
            with trace_operation("batch_item", attributes={"token": token}):
                result = process_token(token)
                results.append(result)
        except Exception as e:
            logger.error("batch_item_failed", token=token, error=str(e))
    
    logger.info("batch_completed", success_count=len(results), total=len(tokens))
    return results
```

### Pattern 3: Retry with Metrics

```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, max=10))
def fetch_with_retry(source: str, endpoint: str):
    logger.info("fetch_attempt", source=source, endpoint=endpoint)
    
    try:
        data = api_call(source, endpoint)
        record_data_source_request(source, endpoint, "success")
        return data
    except Exception as e:
        record_data_source_error(source, endpoint, type(e).__name__)
        logger.warning("fetch_failed", source=source, endpoint=endpoint, error=str(e))
        raise
```

---

**📊 Happy Monitoring! 🚀**

# Observability Guide: Structured Logging + Prometheus Metrics

This guide covers the comprehensive observability infrastructure introduced to the AutoTrader system, including structured logging, Prometheus metrics, and OpenTelemetry distributed tracing.

## 📋 Table of Contents

- [Overview](#overview)
- [Quick Start](#quick-start)
- [Structured Logging](#structured-logging)
- [Prometheus Metrics](#prometheus-metrics)
- [Distributed Tracing](#distributed-tracing)
- [Configuration](#configuration)
- [Integration Examples](#integration-examples)
- [Monitoring & Alerting](#monitoring--alerting)
- [Troubleshooting](#troubleshooting)

---

## Overview

### Architecture

The observability stack consists of three pillars:

1. **Structured Logging**: JSON-formatted logs with context for aggregation
2. **Metrics**: Prometheus-compatible metrics for system health monitoring
3. **Tracing**: OpenTelemetry distributed tracing for request flow analysis

### Benefits

- **Production-Ready**: All logs in JSON format for easy parsing by log aggregators
- **Real-time Monitoring**: Prometheus metrics for dashboards and alerting
- **Distributed Tracing**: Track requests across services and identify bottlenecks
- **Retrofittable**: Designed to be added incrementally without breaking changes

---

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

Key packages installed:
- `structlog==24.1.0` - Structured logging
- `python-json-logger==2.0.7` - JSON log formatting
- `prometheus-client==0.20.0` - Metrics export
- `opentelemetry-api==1.23.0` - Tracing API
- `opentelemetry-sdk==1.23.0` - Tracing SDK

### 2. Start the Metrics Server

```bash
# Start Prometheus metrics endpoint on port 9090
python -m src.services.metrics_server --port 9090
```

Or with custom configuration:

```bash
python -m src.services.metrics_server --port 9090 --address 0.0.0.0 --log-level INFO
```

### 3. Verify Metrics Endpoint

```bash
# Check metrics are being exposed
curl http://localhost:9090/metrics
```

### 4. Configure Prometheus

Add to your `prometheus.yml`:

```yaml
scrape_configs:
  - job_name: 'autotrader'
    static_configs:
      - targets: ['localhost:9090']
    scrape_interval: 15s
```

---

## Structured Logging

### Basic Usage

```python
from src.core.logging_config import get_logger

logger = get_logger(__name__)

# Log with structured context
logger.info(
    "scan_started",
    token_symbol="BTC",
    contract_address="0x...",
    user_id="user123"
)
```

### Output Format

All logs are emitted in JSON format:

```json
{
  "timestamp": "2025-10-08T10:30:45.123Z",
  "level": "INFO",
  "logger": "src.core.pipeline",
  "event": "scan_completed",
  "token_symbol": "BTC",
  "gem_score": 85.5,
  "confidence": 0.92,
  "duration_seconds": 2.3,
  "service": "autotrader",
  "environment": "production",
  "version": "0.1.0"
}
```

### Context Binding

Bind context that persists across multiple log statements:

```python
from src.core.logging_config import get_logger

logger = get_logger(__name__)

# Bind context
request_logger = logger.bind(
    request_id="req-123",
    user_id="user-456"
)

# All subsequent logs will include bound context
request_logger.info("processing_started")
request_logger.info("validation_passed")
request_logger.error("unexpected_error", error_code=500)
```

### Log Levels

```python
logger.debug("debug_info", detail="...")      # Debug-level details
logger.info("operation_success", ...)         # Normal operations
logger.warning("degraded_performance", ...)   # Warnings
logger.error("operation_failed", ...)         # Errors
logger.critical("system_failure", ...)        # Critical failures
logger.exception("unhandled_exception", ...)  # Exceptions with traceback
```

### Initialization

```python
from src.core.logging_config import init_logging

# Initialize at application startup
logger = init_logging(
    service_name="autotrader",
    level="INFO"  # or "DEBUG" for verbose logging
)
```

---

## Prometheus Metrics

### Available Metrics

#### Scanner Metrics

```python
from src.core.metrics import (
    record_scan_request,
    record_scan_duration,
    record_scan_error,
    record_gem_score,
    record_confidence_score,
    record_flagged_token,
)

# Record scan operation
record_scan_request("BTC", "success")
record_scan_duration("BTC", 2.5, "success")
record_gem_score("BTC", 85.5)
record_confidence_score("BTC", 0.92)
record_flagged_token("BTC", "high_risk")
```

**Exposed metrics:**
- `scan_requests_total{token_symbol, status}` - Total scan requests
- `scan_duration_seconds{token_symbol, status}` - Scan duration histogram
- `scan_errors_total{token_symbol, error_type}` - Total scan errors
- `gem_score_distribution{token_symbol}` - GemScore distribution
- `confidence_score_distribution{token_symbol}` - Confidence distribution
- `flagged_tokens_total{token_symbol, flag_reason}` - Flagged tokens

#### Data Source Metrics

```python
from src.core.metrics import (
    record_data_source_request,
    record_data_source_latency,
    record_data_source_error,
    record_cache_hit,
    record_cache_miss,
)

# Track external API calls
record_data_source_request("coingecko", "/coins/markets", "success")
record_data_source_latency("coingecko", "/coins/markets", 0.234)
record_cache_hit("coingecko", "/coins/markets")
```

**Exposed metrics:**
- `data_source_requests_total{source, endpoint, status}`
- `data_source_latency_seconds{source, endpoint}`
- `data_source_errors_total{source, endpoint, error_type}`
- `data_source_cache_hits_total{source, endpoint}`
- `data_source_cache_misses_total{source, endpoint}`

#### Circuit Breaker Metrics

```python
from src.core.metrics import (
    set_circuit_breaker_state,
    record_circuit_breaker_trip,
    record_circuit_breaker_recovery,
)

# Track circuit breaker state
set_circuit_breaker_state("binance", "/orderbook", "open")
record_circuit_breaker_trip("binance", "/orderbook")
record_circuit_breaker_recovery("binance", "/orderbook")
```

**Exposed metrics:**
- `circuit_breaker_state{source, endpoint}` - 0=closed, 1=open, 2=half_open
- `circuit_breaker_trips_total{source, endpoint}`
- `circuit_breaker_recoveries_total{source, endpoint}`

#### API Metrics

```python
from src.core.metrics import (
    record_api_request,
    record_api_duration,
    record_api_error,
    ActiveRequestTracker,
)

# Track API requests (done automatically via middleware)
record_api_request("GET", "/api/tokens", 200)
record_api_duration("GET", "/api/tokens", 0.123)

# Track active requests
with ActiveRequestTracker("GET", "/api/tokens"):
    # Process request
    pass
```

**Exposed metrics:**
- `api_requests_total{method, endpoint, status_code}`
- `api_request_duration_seconds{method, endpoint}`
- `api_errors_total{method, endpoint, error_type}`
- `active_api_requests{method, endpoint}`

#### LLM Metrics

```python
from src.core.metrics import (
    record_llm_request,
    record_llm_latency,
    record_llm_tokens,
    record_llm_cost,
)

# Track LLM usage
record_llm_request("groq", "llama3-70b", "success")
record_llm_latency("groq", "llama3-70b", 1.23)
record_llm_tokens("groq", "llama3-70b", "input", 150)
record_llm_tokens("groq", "llama3-70b", "output", 200)
record_llm_cost("groq", "llama3-70b", 0.0015)
```

**Exposed metrics:**
- `llm_requests_total{provider, model, status}`
- `llm_latency_seconds{provider, model}`
- `llm_tokens_used_total{provider, model, token_type}`
- `llm_cost_usd_total{provider, model}`

### Querying Metrics

#### PromQL Examples

```promql
# Scan success rate (last 5 minutes)
rate(scan_requests_total{status="success"}[5m])

# Average scan duration
rate(scan_duration_seconds_sum[5m]) / rate(scan_duration_seconds_count[5m])

# API p95 latency
histogram_quantile(0.95, rate(api_request_duration_seconds_bucket[5m]))

# Error rate percentage
100 * (
  rate(scan_errors_total[5m]) / 
  rate(scan_requests_total[5m])
)

# Cache hit ratio
rate(data_source_cache_hits_total[5m]) / 
(rate(data_source_cache_hits_total[5m]) + rate(data_source_cache_misses_total[5m]))

# LLM cost per hour
rate(llm_cost_usd_total[1h]) * 3600
```

---

## Distributed Tracing

### Basic Usage

```python
from src.core.tracing import trace_operation, add_span_attributes

# Trace an operation
with trace_operation(
    "data_fetch",
    attributes={"source": "coingecko", "token": "BTC"}
) as span:
    # Do work
    data = fetch_data()
    
    # Add attributes to span
    add_span_attributes(
        records_fetched=len(data),
        cache_hit=True
    )
```

### Function Decorator

```python
from src.core.tracing import trace_function

@trace_function("process_token_data")
def process_token(token_symbol: str):
    # Function is automatically traced
    return result
```

### Async Function Decorator

```python
from src.core.tracing import trace_async_function

@trace_async_function("fetch_api_data")
async def fetch_data(url: str):
    # Async function is automatically traced
    return await httpx.get(url)
```

### Trace Context

```python
from src.core.tracing import get_trace_id, get_span_id

# Get current trace ID for correlation
trace_id = get_trace_id()
span_id = get_span_id()

logger.info("processing", trace_id=trace_id, span_id=span_id)
```

---

## Configuration

### Observability Config (`configs/observability.yaml`)

```yaml
observability:
  service_name: "autotrader"
  environment: "production"
  
  logging:
    level: "INFO"
    format: "json"
    
  metrics:
    enabled: true
    port: 9090
    
  tracing:
    enabled: true
    sampling:
      strategy: "probability"
      probability: 0.1  # Sample 10% in production
```

### Environment Variables

```bash
# Logging
export LOG_LEVEL=INFO
export ENVIRONMENT=production
export APP_VERSION=0.1.0

# Metrics
export METRICS_PORT=9090

# Tracing
export JAEGER_ENDPOINT=http://localhost:14268/api/traces
export OTLP_ENDPOINT=http://localhost:4317
```

---

## Integration Examples

### Adding Observability to a New Module

```python
from src.core.logging_config import get_logger
from src.core.metrics import Counter, Histogram
from src.core.tracing import trace_operation

# Initialize logger
logger = get_logger(__name__)

# Define module-specific metrics
MODULE_OPERATIONS = Counter(
    'module_operations_total',
    'Total module operations',
    ['operation_type', 'status']
)

MODULE_DURATION = Histogram(
    'module_duration_seconds',
    'Module operation duration',
    ['operation_type']
)

def process_data(data):
    """Process data with full observability."""
    operation_type = "data_processing"
    
    # Start trace
    with trace_operation(
        f"module.{operation_type}",
        attributes={"data_size": len(data)}
    ):
        start_time = time.time()
        
        logger.info(
            "processing_started",
            operation=operation_type,
            data_size=len(data)
        )
        
        try:
            # Do work
            result = _do_processing(data)
            
            # Record success
            duration = time.time() - start_time
            MODULE_OPERATIONS.labels(
                operation_type=operation_type,
                status="success"
            ).inc()
            MODULE_DURATION.labels(
                operation_type=operation_type
            ).observe(duration)
            
            logger.info(
                "processing_completed",
                operation=operation_type,
                duration_seconds=duration,
                result_size=len(result)
            )
            
            return result
            
        except Exception as e:
            # Record failure
            duration = time.time() - start_time
            MODULE_OPERATIONS.labels(
                operation_type=operation_type,
                status="failure"
            ).inc()
            
            logger.error(
                "processing_failed",
                operation=operation_type,
                error_type=type(e).__name__,
                error_message=str(e),
                duration_seconds=duration,
                exc_info=True
            )
            
            raise
```

---

## Monitoring & Alerting

### Grafana Dashboard

Create a Grafana dashboard with these panels:

1. **Scan Success Rate**
   ```promql
   rate(scan_requests_total{status="success"}[5m])
   ```

2. **API Latency p95**
   ```promql
   histogram_quantile(0.95, rate(api_request_duration_seconds_bucket[5m]))
   ```

3. **Error Rate**
   ```promql
   rate(scan_errors_total[5m])
   ```

4. **Active Requests**
   ```promql
   active_api_requests
   ```

### Prometheus Alerts

Add to `prometheus_rules.yml`:

```yaml
groups:
  - name: autotrader_alerts
    interval: 30s
    rules:
      - alert: HighScanErrorRate
        expr: rate(scan_errors_total[5m]) > 0.05
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High scan error rate detected"
          description: "Error rate is {{ $value }} errors/sec"
      
      - alert: HighAPILatency
        expr: histogram_quantile(0.95, rate(api_request_duration_seconds_bucket[5m])) > 2.0
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High API latency detected"
          description: "P95 latency is {{ $value }}s"
      
      - alert: CircuitBreakerOpen
        expr: circuit_breaker_state > 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Circuit breaker is open"
          description: "{{ $labels.source }}/{{ $labels.endpoint }} circuit is open"
```

---

## Troubleshooting

### Logs Not Appearing

**Check log level:**
```python
from src.core.logging_config import init_logging

# Ensure DEBUG level if needed
logger = init_logging(level="DEBUG")
```

**Check JSON formatting:**
```bash
# Logs should be valid JSON
python your_script.py 2>&1 | jq .
```

### Metrics Not Exposed

**Check server is running:**
```bash
curl http://localhost:9090/metrics
```

**Verify prometheus_client installed:**
```bash
pip list | grep prometheus
```

### High Memory Usage

**Reduce histogram buckets:**
```python
# In configs/observability.yaml
metrics:
  histograms:
    scan_duration_buckets: [1.0, 5.0, 10.0]  # Fewer buckets
```

**Increase export intervals:**
```python
performance:
  span_export_delay_seconds: 30  # Export less frequently
```

---

## Best Practices

1. **Always log structured data** - Use key-value pairs, not string interpolation
2. **Include correlation IDs** - Add request_id or trace_id to all logs
3. **Use appropriate log levels** - Reserve ERROR for actual errors
4. **Add context early** - Bind context at the start of request handling
5. **Monitor metric cardinality** - Don't use high-cardinality values as labels
6. **Sample traces in production** - 100% sampling is expensive
7. **Set up alerts** - Don't wait for issues to be reported

---

## Next Steps

1. **Set up log aggregation** - Ship logs to ELK, Loki, or Datadog
2. **Configure Grafana** - Create dashboards for key metrics
3. **Set up alerting** - Configure PagerDuty or Slack notifications
4. **Enable distributed tracing** - Set up Jaeger or Tempo
5. **Create runbooks** - Document how to respond to alerts

---

## Additional Resources

- [Structured Logging Best Practices](https://www.structlog.org/)
- [Prometheus Documentation](https://prometheus.io/docs/)
- [OpenTelemetry Documentation](https://opentelemetry.io/docs/)
- [Grafana Dashboard Examples](https://grafana.com/grafana/dashboards/)

---

**Need help?** Check the [troubleshooting section](#troubleshooting) or open an issue on GitHub.

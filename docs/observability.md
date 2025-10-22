# Observability Guide

This guide explains how to use the structured logging, metrics, and distributed tracing features in the Autotrader system.

## Table of Contents

- [Overview](#overview)
- [Structured Logging](#structured-logging)
- [Prometheus Metrics](#prometheus-metrics)
- [Distributed Tracing](#distributed-tracing)
- [API Instrumentation](#api-instrumentation)
- [Configuration](#configuration)
- [Monitoring Setup](#monitoring-setup)

## Overview

Autotrader implements comprehensive observability using industry-standard tools:

- **Structured Logging**: JSON-formatted logs with context using [structlog](https://www.structlog.org/)
- **Metrics**: Prometheus-compatible metrics using [prometheus_client](https://github.com/prometheus/client_python)
- **Distributed Tracing**: Request tracing using [OpenTelemetry](https://opentelemetry.io/)

All observability components are designed to:
- Work gracefully when dependencies are not installed (mock implementations)
- Add minimal performance overhead
- Provide correlation between logs, metrics, and traces

## Structured Logging

### Setup

Structured logging is automatically initialized in the application:

```python
from src.core.logging_config import setup_structured_logging, get_logger

# Initialize logging (typically done once at application startup)
logger = setup_structured_logging(
    service_name="autotrader-api",
    environment="production",
    version="1.0.0",
    level="INFO",
    enable_json=True,
)

# Get a logger for your module
logger = get_logger(__name__)
```

### Usage

```python
# Simple logging
logger.info("user_login", user_id="123", ip_address="192.168.1.1")

# Bind context that persists across multiple log calls
request_logger = logger.bind(request_id="abc-123", user_id="456")
request_logger.info("processing_request")
request_logger.info("request_completed", duration_ms=150)

# Using context manager
from src.core.logging_config import LogContext

with LogContext(logger, request_id="xyz-789") as scoped_logger:
    scoped_logger.info("operation_started")
    # ... do work ...
    scoped_logger.info("operation_completed")

# Log exceptions
try:
    risky_operation()
except Exception as e:
    logger.exception("operation_failed", error_type=type(e).__name__)
```

### Log Output Format

Logs are output in JSON format for easy parsing by log aggregation systems:

```json
{
  "timestamp": "2025-10-22T10:30:45.123456Z",
  "level": "info",
  "logger": "src.core.pipeline",
  "event": "scan_completed",
  "service": "autotrader-api",
  "environment": "production",
  "version": "1.0.0",
  "token_symbol": "ETH",
  "gem_score": 85.5,
  "duration_seconds": 2.34
}
```

## Prometheus Metrics

### Available Metrics

The system exposes the following metric types:

#### Scanner & Pipeline Metrics

- `scan_requests_total`: Total scan requests (labels: token_symbol, status)
- `scan_duration_seconds`: Scan operation duration histogram
- `scan_errors_total`: Total scan errors (labels: token_symbol, error_type)
- `gem_score_distribution`: Distribution of GemScore values
- `confidence_score_distribution`: Distribution of confidence scores
- `flagged_tokens_total`: Total flagged tokens (labels: token_symbol, flag_reason)

#### Data Source Metrics

- `data_source_requests_total`: Total data source requests (labels: source, endpoint, status)
- `data_source_latency_seconds`: Data source request latency histogram
- `data_source_errors_total`: Data source errors (labels: source, endpoint, error_type)
- `data_source_cache_hits_total`: Cache hits
- `data_source_cache_misses_total`: Cache misses

#### API Metrics

- `api_requests_total`: Total API requests (labels: method, endpoint, status_code)
- `api_request_duration_seconds`: API request duration histogram
- `api_errors_total`: API errors (labels: method, endpoint, error_type)
- `active_api_requests`: Currently active API requests

#### Feature Metrics

- `feature_validation_failures_total`: Feature validation failures
- `feature_validation_warnings_total`: Feature validation warnings
- `feature_value_distribution`: Distribution of feature values

### Recording Metrics

Metrics are automatically recorded by instrumented code, but you can also record them manually:

```python
from src.core.metrics import (
    record_scan_request,
    record_gem_score,
    record_data_source_request,
)

# Record a scan request
record_scan_request("ETH", "success")

# Record a gem score
record_gem_score("ETH", 85.5)

# Record a data source request
record_data_source_request("coingecko", "/api/v3/coins", "success")
```

### Metrics Server

Start the Prometheus metrics server to expose metrics for scraping:

```bash
# Start metrics server on port 9090
python -m src.services.metrics_server --port 9090

# Or with custom configuration
python -m src.services.metrics_server --port 9090 --address 0.0.0.0 --log-level INFO
```

The metrics endpoint will be available at: `http://localhost:9090/metrics`

### Prometheus Configuration

Add this job to your `prometheus.yml`:

```yaml
scrape_configs:
  - job_name: 'autotrader'
    scrape_interval: 15s
    static_configs:
      - targets: ['localhost:9090']
        labels:
          service: 'autotrader'
          environment: 'production'
```

## Distributed Tracing

### Setup

Tracing is automatically initialized in the application:

```python
from src.core.tracing import setup_tracing

# Initialize tracing (typically done once at application startup)
tracer = setup_tracing(
    service_name="autotrader-api",
    environment="production",
    enable_console_export=True,  # Set to False in production
)
```

### Usage

```python
from src.core.tracing import trace_operation, add_span_attributes

# Trace an operation
with trace_operation("fetch_market_data") as span:
    data = fetch_data()
    
    # Add custom attributes to the span
    add_span_attributes(
        token_symbol="ETH",
        data_points=len(data),
        cache_hit=False,
    )
```

### Trace Correlation

Traces are automatically correlated with logs using trace IDs:

1. Each traced operation generates a trace_id
2. The trace_id is added to log context automatically
3. API responses include the trace_id in the `X-Trace-Id` header

This allows you to:
- Find all logs related to a specific trace
- Track requests across service boundaries
- Debug issues by following the execution path

## API Instrumentation

The FastAPI application is automatically instrumented with:

1. **Request/Response Logging**: All requests are logged with:
   - Method, path, query parameters
   - Response status code
   - Duration
   - Client IP address
   - Trace ID

2. **Metrics Collection**: Automatic recording of:
   - Request counts by endpoint
   - Request duration histograms
   - Error counts by type
   - Active request gauges

3. **Distributed Tracing**: All API requests are traced with:
   - Automatic span creation
   - Context propagation
   - Trace ID in response headers

## Configuration

### Environment Variables

Control observability behavior with environment variables:

```bash
# Logging
export LOG_LEVEL=INFO                    # DEBUG, INFO, WARNING, ERROR, CRITICAL
export ENVIRONMENT=production            # development, staging, production
export APP_VERSION=1.0.0

# Metrics
export METRICS_PORT=9090
export METRICS_ADDRESS=0.0.0.0

# Tracing
export OTEL_SERVICE_NAME=autotrader-api
export OTEL_TRACES_EXPORTER=console      # console, jaeger, otlp
```

### Production Recommendations

For production deployments:

1. **Logging**:
   - Use `LOG_LEVEL=INFO` (or `WARNING` for high-traffic services)
   - Enable JSON output: `enable_json=True`
   - Ship logs to a centralized system (e.g., ELK, Loki)

2. **Metrics**:
   - Run metrics server on dedicated port
   - Configure Prometheus to scrape at 15-30 second intervals
   - Set up alerts for high error rates, latency spikes

3. **Tracing**:
   - Disable console export: `enable_console_export=False`
   - Use sampling to reduce overhead (trace ~1-10% of requests)
   - Export traces to Jaeger, Zipkin, or similar

## Monitoring Setup

### Example: Local Development with Docker

```yaml
# docker-compose.yml
version: '3'
services:
  autotrader:
    build: .
    ports:
      - "8000:8000"  # API
      - "9090:9090"  # Metrics
    environment:
      - LOG_LEVEL=DEBUG
      - ENVIRONMENT=development

  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9091:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'

  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
```

### Example Prometheus Queries

```promql
# Request rate by endpoint
rate(api_requests_total[5m])

# 95th percentile latency
histogram_quantile(0.95, rate(api_request_duration_seconds_bucket[5m]))

# Error rate
rate(api_errors_total[5m]) / rate(api_requests_total[5m])

# Scan success rate
rate(scan_requests_total{status="success"}[5m]) / rate(scan_requests_total[5m])

# Average gem score over time
avg_over_time(gem_score_distribution[5m])
```

### Grafana Dashboard

Import the following metrics into Grafana for monitoring:

1. **API Performance**:
   - Request rate
   - Error rate
   - Latency (p50, p95, p99)
   - Active requests

2. **Scanner Performance**:
   - Scan rate
   - Scan duration
   - Gem score distribution
   - Flagged token rate

3. **Data Sources**:
   - Request rate by source
   - Error rate by source
   - Latency by source
   - Cache hit rate

4. **System Health**:
   - Memory usage
   - CPU usage
   - Error rates
   - Circuit breaker states

## Best Practices

1. **Use structured logging**: Always use key-value pairs instead of string interpolation
   ```python
   # Good
   logger.info("user_action", user_id=user.id, action="login")
   
   # Bad
   logger.info(f"User {user.id} performed login")
   ```

2. **Add context to logs**: Use `bind()` to add persistent context
   ```python
   request_logger = logger.bind(request_id=request_id)
   # Now all logs will include request_id
   ```

3. **Record metrics at key points**: Record metrics where they matter
   ```python
   start = time.time()
   result = expensive_operation()
   record_operation_duration("expensive_op", time.time() - start)
   ```

4. **Use tracing for debugging**: Wrap complex operations in trace contexts
   ```python
   with trace_operation("complex_pipeline"):
       step1()
       step2()
       step3()
   ```

5. **Monitor SLAs**: Set up alerts based on your SLA requirements
   - API latency < 500ms (p95)
   - API error rate < 1%
   - Scan completion rate > 99%

## Troubleshooting

### No metrics appearing

- Check that the metrics server is running: `curl http://localhost:9090/metrics`
- Verify Prometheus configuration
- Check that instrumented code is being executed

### Logs not in JSON format

- Ensure `enable_json=True` in `setup_structured_logging()`
- Check that `pythonjsonlogger` is installed

### Traces not appearing

- Check that OpenTelemetry packages are installed
- Verify trace exporter configuration
- Ensure tracing is enabled: `enable_console_export=True` for debugging

### Performance impact

- Reduce log level in production (INFO or WARNING)
- Use sampling for traces (trace 1-10% of requests)
- Ensure metrics are collected efficiently (use histograms, not individual timings)

## References

- [structlog Documentation](https://www.structlog.org/)
- [Prometheus Documentation](https://prometheus.io/docs/)
- [OpenTelemetry Python Documentation](https://opentelemetry.io/docs/instrumentation/python/)
- [FastAPI Observability](https://fastapi.tiangolo.com/advanced/middleware/)

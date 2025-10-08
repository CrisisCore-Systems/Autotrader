# Observability Quick Reference

Quick reference for using structured logging, metrics, and tracing in AutoTrader.

---

## 📝 Structured Logging

### Import
```python
from src.core.logging_config import get_logger
logger = get_logger(__name__)
```

### Basic Usage
```python
# Info
logger.info("operation_completed", result_count=42, duration_ms=123)

# Warning
logger.warning("degraded_performance", latency_ms=5000)

# Error with exception
logger.error("operation_failed", error_code="ERR001", exc_info=True)
```

### Context Binding
```python
# Bind context to logger
request_logger = logger.bind(request_id="req-123", user_id="user-456")
request_logger.info("processing_started")
request_logger.info("validation_passed")
```

---

## 📊 Metrics

### Scanner Metrics
```python
from src.core.metrics import (
    record_scan_request,
    record_scan_duration,
    record_gem_score,
)

record_scan_request("BTC", "success")
record_scan_duration("BTC", 2.3, "success")
record_gem_score("BTC", 85.5)
```

### Data Source Metrics
```python
from src.core.metrics import (
    record_data_source_request,
    record_data_source_latency,
    record_cache_hit,
)

record_data_source_request("coingecko", "/coins/markets", "success")
record_data_source_latency("coingecko", "/coins/markets", 0.234)
record_cache_hit("coingecko", "/coins/markets")
```

### API Metrics (Auto via Middleware)
```python
# Metrics recorded automatically by dashboard_api.py middleware
# No manual action needed for FastAPI endpoints
```

### Custom Metrics
```python
from prometheus_client import Counter, Histogram

MY_COUNTER = Counter('my_operations_total', 'Total operations', ['type'])
MY_HISTOGRAM = Histogram('my_duration_seconds', 'Duration', ['operation'])

MY_COUNTER.labels(type="process").inc()
MY_HISTOGRAM.labels(operation="compute").observe(1.23)
```

---

## 🔍 Distributed Tracing

### Basic Tracing
```python
from src.core.tracing import trace_operation

with trace_operation("data_processing", attributes={"source": "api"}):
    result = process_data()
    # Automatically traced
```

### Function Decorator
```python
from src.core.tracing import trace_function

@trace_function("compute_score")
def compute_score(data):
    return score
```

### Async Function Decorator
```python
from src.core.tracing import trace_async_function

@trace_async_function("fetch_data")
async def fetch_data(url):
    return await httpx.get(url)
```

### Add Span Attributes
```python
from src.core.tracing import add_span_attributes

with trace_operation("operation"):
    result = do_work()
    add_span_attributes(
        records_processed=len(result),
        cache_hit=True
    )
```

---

## 🎯 Common Patterns

### Function with Full Observability
```python
from src.core.logging_config import get_logger
from src.core.metrics import Counter, Histogram
from src.core.tracing import trace_operation
import time

logger = get_logger(__name__)

OPERATIONS = Counter('operations_total', 'Operations', ['type', 'status'])
DURATION = Histogram('duration_seconds', 'Duration', ['type'])

def process_item(item):
    start = time.time()
    
    with trace_operation("process_item", attributes={"item_id": item.id}):
        logger.info("processing_started", item_id=item.id)
        
        try:
            result = _do_process(item)
            
            duration = time.time() - start
            OPERATIONS.labels(type="item", status="success").inc()
            DURATION.labels(type="item").observe(duration)
            
            logger.info("processing_completed", item_id=item.id, duration_seconds=duration)
            return result
            
        except Exception as e:
            duration = time.time() - start
            OPERATIONS.labels(type="item", status="failure").inc()
            
            logger.error("processing_failed", item_id=item.id, error=str(e), exc_info=True)
            raise
```

### API Endpoint (FastAPI)
```python
from fastapi import APIRouter
from src.core.logging_config import get_logger
from src.core.tracing import trace_operation

logger = get_logger(__name__)
router = APIRouter()

@router.get("/items/{item_id}")
async def get_item(item_id: str):
    # Logging and metrics handled by middleware
    # Just add business logic tracing
    
    with trace_operation("fetch_item", attributes={"item_id": item_id}):
        logger.info("fetching_item", item_id=item_id)
        item = await fetch_from_db(item_id)
        return item
```

---

## 🚀 Start Metrics Server

```bash
# Development
python -m src.services.metrics_server --port 9090 --log-level DEBUG

# Production
python -m src.services.metrics_server --port 9090 --address 0.0.0.0
```

Access metrics: `http://localhost:9090/metrics`

---

## 🔧 Configuration

### Environment Variables
```bash
# Logging
export LOG_LEVEL=INFO
export ENVIRONMENT=production

# Metrics
export METRICS_PORT=9090

# Tracing
export JAEGER_ENDPOINT=http://localhost:14268/api/traces
```

### Config File
Edit `configs/observability.yaml` for centralized settings.

---

## 📊 View Metrics

### Curl
```bash
curl http://localhost:9090/metrics
```

### Prometheus Queries
```promql
# Scan success rate
rate(scan_requests_total{status="success"}[5m])

# API latency p95
histogram_quantile(0.95, rate(api_request_duration_seconds_bucket[5m]))

# Error count
sum(rate(scan_errors_total[5m]))
```

---

## 🐛 Debugging

### Enable Debug Logging
```python
from src.core.logging_config import init_logging
logger = init_logging(level="DEBUG")
```

### Check Trace ID
```python
from src.core.tracing import get_trace_id
trace_id = get_trace_id()
logger.info("operation", trace_id=trace_id)
```

### Verify Metrics Available
```python
from src.core.metrics import is_prometheus_available
if is_prometheus_available():
    # Record metrics
    pass
```

---

## 📚 Documentation

- **Full Guide**: `docs/OBSERVABILITY_GUIDE.md`
- **Implementation**: `OBSERVABILITY_IMPLEMENTATION_COMPLETE.md`
- **Config**: `configs/observability.yaml`

---

**Need Help?** See the full guide or open an issue!

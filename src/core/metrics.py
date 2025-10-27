"""Metrics tracking for the Autotrader system.

Provides Prometheus-compatible metrics for:
- Feature validation failures and warnings
- Feature value distributions
- System performance
"""

from typing import Optional

try:
    from prometheus_client import Counter, Histogram, Gauge
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    # Provide mock implementations
    class Counter:
        """Mock Counter for when prometheus is not available."""
        def __init__(self, *args, **kwargs):
            pass
        
        def labels(self, **kwargs):
            return self
        
        def inc(self, amount=1):
            pass
    
    class Histogram:
        """Mock Histogram for when prometheus is not available."""
        def __init__(self, *args, **kwargs):
            pass
        
        def labels(self, **kwargs):
            return self
        
        def observe(self, value):
            pass
    
    class Gauge:
        """Mock Gauge for when prometheus is not available."""
        def __init__(self, *args, **kwargs):
            pass
        
        def labels(self, **kwargs):
            return self
        
        def set(self, value):
            pass
        
        def inc(self, amount=1):
            pass
        
        def dec(self, amount=1):
            pass


# =============================================================================
# Feature Validation Metrics
# =============================================================================

FEATURE_VALIDATION_FAILURES = Counter(
    'feature_validation_failures_total',
    'Total number of feature validation failures',
    ['feature_name', 'validation_type', 'severity']
)

FEATURE_VALIDATION_WARNINGS = Counter(
    'feature_validation_warnings_total',
    'Total number of feature validation warnings',
    ['feature_name', 'validation_type']
)

FEATURE_VALIDATION_SUCCESS = Counter(
    'feature_validation_success_total',
    'Total number of successful feature validations',
    ['feature_name']
)

FEATURE_VALUE_DISTRIBUTION = Histogram(
    'feature_value_distribution',
    'Distribution of feature values',
    ['feature_name', 'category'],
    buckets=[0, 10, 25, 50, 75, 90, 100]
)

FEATURE_FRESHNESS_SECONDS = Histogram(
    'feature_freshness_seconds',
    'Age of feature data in seconds',
    ['feature_name'],
    buckets=[1, 5, 10, 30, 60, 300, 600, 1800, 3600]
)

FEATURE_WRITE_DURATION = Histogram(
    'feature_write_duration_seconds',
    'Duration of feature write operations',
    ['feature_name'],
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0]
)

# =============================================================================
# Feature Store Metrics
# =============================================================================

FEATURE_STORE_SIZE = Gauge(
    'feature_store_size_total',
    'Total number of feature values in store',
    ['category']
)

FEATURE_STORE_OPERATIONS = Counter(
    'feature_store_operations_total',
    'Total number of feature store operations',
    ['operation', 'status']
)

# =============================================================================
# Ingestion Worker Metrics
# =============================================================================

INGESTION_CYCLE_DURATION_SECONDS = Histogram(
    'ingestion_cycle_duration_seconds',
    'Duration of ingestion worker cycles in seconds',
    ['worker', 'outcome'],
    buckets=[0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0]
)

INGESTION_ITEMS_TOTAL = Counter(
    'ingestion_items_total',
    'Total number of items collected by the ingestion worker',
    ['worker', 'source']
)

INGESTION_CYCLE_ERRORS_TOTAL = Counter(
    'ingestion_cycle_errors_total',
    'Total number of ingestion worker cycle errors',
    ['worker', 'stage']
)

INGESTION_LAST_SUCCESS_TIMESTAMP = Gauge(
    'ingestion_last_success_timestamp',
    'Unix timestamp of the last successful ingestion cycle',
    ['worker']
)

# =============================================================================
# Scanner & Pipeline Metrics
# =============================================================================

SCAN_REQUESTS_TOTAL = Counter(
    'scan_requests_total',
    'Total number of scan requests',
    ['token_symbol', 'status']
)

SCAN_DURATION_SECONDS = Histogram(
    'scan_duration_seconds',
    'Duration of scan operations',
    ['token_symbol', 'status'],
    buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0]
)

SCAN_ERRORS_TOTAL = Counter(
    'scan_errors_total',
    'Total number of scan errors',
    ['token_symbol', 'error_type']
)

GEM_SCORE_DISTRIBUTION = Histogram(
    'gem_score_distribution',
    'Distribution of GemScore values',
    ['token_symbol'],
    buckets=[0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
)

CONFIDENCE_SCORE_DISTRIBUTION = Histogram(
    'confidence_score_distribution',
    'Distribution of confidence scores',
    ['token_symbol'],
    buckets=[0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
)

FLAGGED_TOKENS_TOTAL = Counter(
    'flagged_tokens_total',
    'Total number of tokens flagged as suspicious',
    ['token_symbol', 'flag_reason']
)

# =============================================================================
# Data Source Metrics
# =============================================================================

DATA_SOURCE_REQUESTS_TOTAL = Counter(
    'data_source_requests_total',
    'Total number of data source requests',
    ['source', 'endpoint', 'status']
)

DATA_SOURCE_LATENCY_SECONDS = Histogram(
    'data_source_latency_seconds',
    'Latency of data source requests',
    ['source', 'endpoint'],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
)

DATA_SOURCE_ERRORS_TOTAL = Counter(
    'data_source_errors_total',
    'Total number of data source errors',
    ['source', 'endpoint', 'error_type']
)

DATA_SOURCE_CACHE_HITS = Counter(
    'data_source_cache_hits_total',
    'Total number of cache hits',
    ['source', 'endpoint']
)

DATA_SOURCE_CACHE_MISSES = Counter(
    'data_source_cache_misses_total',
    'Total number of cache misses',
    ['source', 'endpoint']
)

# =============================================================================
# Circuit Breaker Metrics
# =============================================================================

CIRCUIT_BREAKER_STATE = Gauge(
    'circuit_breaker_state',
    'Circuit breaker state (0=closed, 1=open, 2=half_open)',
    ['source', 'endpoint']
)

CIRCUIT_BREAKER_TRIPS_TOTAL = Counter(
    'circuit_breaker_trips_total',
    'Total number of circuit breaker trips',
    ['source', 'endpoint']
)

CIRCUIT_BREAKER_RECOVERIES_TOTAL = Counter(
    'circuit_breaker_recoveries_total',
    'Total number of circuit breaker recoveries',
    ['source', 'endpoint']
)

# =============================================================================
# API Metrics
# =============================================================================

API_REQUESTS_TOTAL = Counter(
    'api_requests_total',
    'Total number of API requests',
    ['method', 'endpoint', 'status_code']
)

API_REQUEST_DURATION_SECONDS = Histogram(
    'api_request_duration_seconds',
    'API request duration',
    ['method', 'endpoint'],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0]
)

API_ERRORS_TOTAL = Counter(
    'api_errors_total',
    'Total number of API errors',
    ['method', 'endpoint', 'error_type']
)

ACTIVE_API_REQUESTS = Gauge(
    'active_api_requests',
    'Number of currently active API requests',
    ['method', 'endpoint']
)

# =============================================================================
# LLM Metrics
# =============================================================================

LLM_REQUESTS_TOTAL = Counter(
    'llm_requests_total',
    'Total number of LLM requests',
    ['provider', 'model', 'status']
)

LLM_LATENCY_SECONDS = Histogram(
    'llm_latency_seconds',
    'LLM request latency',
    ['provider', 'model'],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0]
)

LLM_TOKENS_USED = Counter(
    'llm_tokens_used_total',
    'Total number of tokens used',
    ['provider', 'model', 'token_type']
)

LLM_COST_USD = Counter(
    'llm_cost_usd_total',
    'Total LLM cost in USD',
    ['provider', 'model']
)

# =============================================================================
# Helper Functions
# =============================================================================

def record_validation_failure(
    feature_name: str,
    validation_type: str,
    severity: str = "error"
) -> None:
    """Record a validation failure.
    
    Args:
        feature_name: Name of the feature that failed validation
        validation_type: Type of validation (range, monotonic, freshness, etc.)
        severity: Severity level (error or warning)
    """
    FEATURE_VALIDATION_FAILURES.labels(
        feature_name=feature_name,
        validation_type=validation_type,
        severity=severity
    ).inc()


def record_validation_warning(
    feature_name: str,
    validation_type: str
) -> None:
    """Record a validation warning.
    
    Args:
        feature_name: Name of the feature
        validation_type: Type of validation
    """
    FEATURE_VALIDATION_WARNINGS.labels(
        feature_name=feature_name,
        validation_type=validation_type
    ).inc()


def record_validation_success(feature_name: str) -> None:
    """Record a successful validation.
    
    Args:
        feature_name: Name of the feature
    """
    FEATURE_VALIDATION_SUCCESS.labels(feature_name=feature_name).inc()


def record_feature_value(
    feature_name: str,
    value: float,
    category: str = "unknown"
) -> None:
    """Record a feature value for distribution tracking.
    
    Args:
        feature_name: Name of the feature
        value: Value of the feature
        category: Category of the feature
    """
    try:
        numeric_value = float(value)
        FEATURE_VALUE_DISTRIBUTION.labels(
            feature_name=feature_name,
            category=category
        ).observe(numeric_value)
    except (TypeError, ValueError):
        # Skip non-numeric values
        pass


def record_feature_freshness(
    feature_name: str,
    age_seconds: float
) -> None:
    """Record feature data freshness.
    
    Args:
        feature_name: Name of the feature
        age_seconds: Age of the data in seconds
    """
    FEATURE_FRESHNESS_SECONDS.labels(feature_name=feature_name).observe(age_seconds)


def record_feature_write(
    feature_name: str,
    duration_seconds: float
) -> None:
    """Record feature write operation duration.
    
    Args:
        feature_name: Name of the feature
        duration_seconds: Duration of the write operation
    """
    FEATURE_WRITE_DURATION.labels(feature_name=feature_name).observe(duration_seconds)


def update_feature_store_size(category: str, size: int) -> None:
    """Update feature store size metric.
    
    Args:
        category: Feature category
        size: Number of features in this category
    """
    FEATURE_STORE_SIZE.labels(category=category).set(size)


def record_feature_store_operation(
    operation: str,
    status: str = "success"
) -> None:
    """Record a feature store operation.
    
    Args:
        operation: Type of operation (read, write, delete, etc.)
        status: Status of the operation (success, failure)
    """
    FEATURE_STORE_OPERATIONS.labels(
        operation=operation,
        status=status
    ).inc()


def is_prometheus_available() -> bool:
    """Check if Prometheus client is available.
    
    Returns:
        True if prometheus_client is installed
    """
    return PROMETHEUS_AVAILABLE


# =============================================================================
# Scanner & Pipeline Metric Helpers
# =============================================================================

def record_scan_request(
    token_symbol: str,
    status: str = "success"
) -> None:
    """Record a scan request.
    
    Args:
        token_symbol: Token symbol being scanned
        status: Status of the scan (success, failure, timeout)
    """
    SCAN_REQUESTS_TOTAL.labels(
        token_symbol=token_symbol,
        status=status
    ).inc()


def record_scan_duration(
    token_symbol: str,
    duration_seconds: float,
    status: str = "success"
) -> None:
    """Record scan operation duration.
    
    Args:
        token_symbol: Token symbol
        duration_seconds: Duration in seconds
        status: Status of the scan
    """
    SCAN_DURATION_SECONDS.labels(
        token_symbol=token_symbol,
        status=status
    ).observe(duration_seconds)


def record_scan_error(
    token_symbol: str,
    error_type: str
) -> None:
    """Record a scan error.
    
    Args:
        token_symbol: Token symbol
        error_type: Type of error (timeout, api_error, validation_error, etc.)
    """
    SCAN_ERRORS_TOTAL.labels(
        token_symbol=token_symbol,
        error_type=error_type
    ).inc()


def record_gem_score(
    token_symbol: str,
    score: float
) -> None:
    """Record a GemScore value.
    
    Args:
        token_symbol: Token symbol
        score: GemScore value (0-100)
    """
    GEM_SCORE_DISTRIBUTION.labels(token_symbol=token_symbol).observe(score)


def record_confidence_score(
    token_symbol: str,
    confidence: float
) -> None:
    """Record a confidence score.
    
    Args:
        token_symbol: Token symbol
        confidence: Confidence value (0-1)
    """
    CONFIDENCE_SCORE_DISTRIBUTION.labels(token_symbol=token_symbol).observe(confidence)


def record_flagged_token(
    token_symbol: str,
    flag_reason: str
) -> None:
    """Record a flagged token.
    
    Args:
        token_symbol: Token symbol
        flag_reason: Reason for flagging
    """
    FLAGGED_TOKENS_TOTAL.labels(
        token_symbol=token_symbol,
        flag_reason=flag_reason
    ).inc()


# =============================================================================
# Data Source Metric Helpers
# =============================================================================

def record_data_source_request(
    source: str,
    endpoint: str,
    status: str = "success"
) -> None:
    """Record a data source request.
    
    Args:
        source: Data source name (binance, coingecko, etc.)
        endpoint: Endpoint being called
        status: Status of the request
    """
    DATA_SOURCE_REQUESTS_TOTAL.labels(
        source=source,
        endpoint=endpoint,
        status=status
    ).inc()


def record_data_source_latency(
    source: str,
    endpoint: str,
    latency_seconds: float
) -> None:
    """Record data source latency.
    
    Args:
        source: Data source name
        endpoint: Endpoint being called
        latency_seconds: Latency in seconds
    """
    DATA_SOURCE_LATENCY_SECONDS.labels(
        source=source,
        endpoint=endpoint
    ).observe(latency_seconds)


def record_data_source_error(
    source: str,
    endpoint: str,
    error_type: str
) -> None:
    """Record a data source error.
    
    Args:
        source: Data source name
        endpoint: Endpoint being called
        error_type: Type of error
    """
    DATA_SOURCE_ERRORS_TOTAL.labels(
        source=source,
        endpoint=endpoint,
        error_type=error_type
    ).inc()


def record_cache_hit(source: str, endpoint: str) -> None:
    """Record a cache hit.
    
    Args:
        source: Data source name
        endpoint: Endpoint being called
    """
    DATA_SOURCE_CACHE_HITS.labels(
        source=source,
        endpoint=endpoint
    ).inc()


def record_cache_miss(source: str, endpoint: str) -> None:
    """Record a cache miss.
    
    Args:
        source: Data source name
        endpoint: Endpoint being called
    """
    DATA_SOURCE_CACHE_MISSES.labels(
        source=source,
        endpoint=endpoint
    ).inc()


# =============================================================================
# Circuit Breaker Metric Helpers
# =============================================================================

def set_circuit_breaker_state(
    source: str,
    endpoint: str,
    state: str
) -> None:
    """Set circuit breaker state.
    
    Args:
        source: Data source name
        endpoint: Endpoint
        state: State (closed, open, half_open)
    """
    state_value = {"closed": 0, "open": 1, "half_open": 2}.get(state.lower(), 0)
    CIRCUIT_BREAKER_STATE.labels(
        source=source,
        endpoint=endpoint
    ).set(state_value)


def record_circuit_breaker_trip(source: str, endpoint: str) -> None:
    """Record a circuit breaker trip.
    
    Args:
        source: Data source name
        endpoint: Endpoint
    """
    CIRCUIT_BREAKER_TRIPS_TOTAL.labels(
        source=source,
        endpoint=endpoint
    ).inc()


def record_circuit_breaker_recovery(source: str, endpoint: str) -> None:
    """Record a circuit breaker recovery.
    
    Args:
        source: Data source name
        endpoint: Endpoint
    """
    CIRCUIT_BREAKER_RECOVERIES_TOTAL.labels(
        source=source,
        endpoint=endpoint
    ).inc()


# =============================================================================
# API Metric Helpers
# =============================================================================

def record_api_request(
    method: str,
    endpoint: str,
    status_code: int
) -> None:
    """Record an API request.
    
    Args:
        method: HTTP method
        endpoint: API endpoint
        status_code: HTTP status code
    """
    API_REQUESTS_TOTAL.labels(
        method=method,
        endpoint=endpoint,
        status_code=str(status_code)
    ).inc()


def record_api_duration(
    method: str,
    endpoint: str,
    duration_seconds: float
) -> None:
    """Record API request duration.
    
    Args:
        method: HTTP method
        endpoint: API endpoint
        duration_seconds: Duration in seconds
    """
    API_REQUEST_DURATION_SECONDS.labels(
        method=method,
        endpoint=endpoint
    ).observe(duration_seconds)


def record_api_error(
    method: str,
    endpoint: str,
    error_type: str
) -> None:
    """Record an API error.
    
    Args:
        method: HTTP method
        endpoint: API endpoint
        error_type: Type of error
    """
    API_ERRORS_TOTAL.labels(
        method=method,
        endpoint=endpoint,
        error_type=error_type
    ).inc()


class ActiveRequestTracker:
    """Context manager for tracking active API requests."""
    
    def __init__(self, method: str, endpoint: str):
        """Initialize tracker.
        
        Args:
            method: HTTP method
            endpoint: API endpoint
        """
        self.method = method
        self.endpoint = endpoint
    
    def __enter__(self):
        """Increment active request counter."""
        ACTIVE_API_REQUESTS.labels(
            method=self.method,
            endpoint=self.endpoint
        ).inc()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Decrement active request counter."""
        ACTIVE_API_REQUESTS.labels(
            method=self.method,
            endpoint=self.endpoint
        ).dec()


# =============================================================================
# LLM Metric Helpers
# =============================================================================

def record_llm_request(
    provider: str,
    model: str,
    status: str = "success"
) -> None:
    """Record an LLM request.
    
    Args:
        provider: LLM provider (groq, openai, etc.)
        model: Model name
        status: Status of the request
    """
    LLM_REQUESTS_TOTAL.labels(
        provider=provider,
        model=model,
        status=status
    ).inc()


def record_llm_latency(
    provider: str,
    model: str,
    latency_seconds: float
) -> None:
    """Record LLM request latency.
    
    Args:
        provider: LLM provider
        model: Model name
        latency_seconds: Latency in seconds
    """
    LLM_LATENCY_SECONDS.labels(
        provider=provider,
        model=model
    ).observe(latency_seconds)


def record_llm_tokens(
    provider: str,
    model: str,
    token_type: str,
    count: int
) -> None:
    """Record LLM token usage.
    
    Args:
        provider: LLM provider
        model: Model name
        token_type: Type of tokens (input, output, total)
        count: Number of tokens
    """
    LLM_TOKENS_USED.labels(
        provider=provider,
        model=model,
        token_type=token_type
    ).inc(count)


def record_llm_cost(
    provider: str,
    model: str,
    cost_usd: float
) -> None:
    """Record LLM cost in USD.
    
    Args:
        provider: LLM provider
        model: Model name
        cost_usd: Cost in USD
    """
    LLM_COST_USD.labels(
        provider=provider,
        model=model
    ).inc(cost_usd)


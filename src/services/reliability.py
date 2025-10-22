"""Integration module to apply reliability patterns to existing data sources."""

from __future__ import annotations

from typing import Any, Callable, Optional, TypeVar

from src.services.cache_policy import EnhancedCache, CachePolicyConfig, cached
from src.services.circuit_breaker import (
    CircuitBreakerConfig,
    CircuitBreakerRegistry,
    CircuitState,
    with_circuit_breaker,
)
from src.services.sla_monitor import SLAThresholds, SLARegistry, monitored
from src.services.backoff import BackoffConfig, with_backoff
from src.services.circuit_breaker_alerts import get_alert_manager


# ============================================================================
# Data Source SLA Thresholds
# ============================================================================

# CEX order books: fast, high-frequency updates
CEX_ORDERBOOK_THRESHOLDS = SLAThresholds()
CEX_ORDERBOOK_THRESHOLDS.max_latency_p95 = 1000.0  # 1s in milliseconds
CEX_ORDERBOOK_THRESHOLDS.max_latency_p99 = 2000.0  # 2s in milliseconds
CEX_ORDERBOOK_THRESHOLDS.min_success_rate = 0.95
CEX_ORDERBOOK_THRESHOLDS.max_consecutive_failures = 3

# DEX aggregator: slower, less critical
DEX_THRESHOLDS = SLAThresholds()
DEX_THRESHOLDS.max_latency_p95 = 3000.0  # 3s in milliseconds
DEX_THRESHOLDS.max_latency_p99 = 5000.0  # 5s in milliseconds
DEX_THRESHOLDS.min_success_rate = 0.90
DEX_THRESHOLDS.max_consecutive_failures = 5

# Twitter API: rate-limited, variable latency
TWITTER_THRESHOLDS = SLAThresholds()
TWITTER_THRESHOLDS.max_latency_p95 = 5000.0  # 5s in milliseconds
TWITTER_THRESHOLDS.max_latency_p99 = 10000.0  # 10s in milliseconds
TWITTER_THRESHOLDS.min_success_rate = 0.85
TWITTER_THRESHOLDS.max_consecutive_failures = 3


# ============================================================================
# Circuit Breaker Configurations
# ============================================================================

# Get alert manager for circuit breaker hooks
_alert_manager = get_alert_manager()

# CEX APIs: fail fast
CEX_CIRCUIT_CONFIG = CircuitBreakerConfig(
    failure_threshold=5,
    timeout_seconds=30.0,
    success_threshold=2,
    on_open=_alert_manager.create_open_hook(),
    on_half_open=_alert_manager.create_half_open_hook(),
    on_close=_alert_manager.create_close_hook(),
)

# DEX APIs: more tolerant
DEX_CIRCUIT_CONFIG = CircuitBreakerConfig(
    failure_threshold=10,
    timeout_seconds=60.0,
    success_threshold=3,
    on_open=_alert_manager.create_open_hook(),
    on_half_open=_alert_manager.create_half_open_hook(),
    on_close=_alert_manager.create_close_hook(),
)

# Twitter API: very tolerant (rate limits)
TWITTER_CIRCUIT_CONFIG = CircuitBreakerConfig(
    failure_threshold=3,
    timeout_seconds=120.0,
    success_threshold=1,
    on_open=_alert_manager.create_open_hook(),
    on_half_open=_alert_manager.create_half_open_hook(),
    on_close=_alert_manager.create_close_hook(),
)


# ============================================================================
# Cache Configurations
# ============================================================================

# Order book cache: very short TTL
ORDERBOOK_CACHE_CONFIG = CachePolicyConfig(
    default_ttl_seconds=5.0,
    min_ttl_seconds=2.0,
    max_ttl_seconds=15.0,
    enable_adaptive_ttl=True,
    max_entries=500,
)

# DEX liquidity cache: moderate TTL
DEX_CACHE_CONFIG = CachePolicyConfig(
    default_ttl_seconds=30.0,
    min_ttl_seconds=10.0,
    max_ttl_seconds=120.0,
    enable_adaptive_ttl=True,
    max_entries=200,
)

# Twitter cache: longer TTL
TWITTER_CACHE_CONFIG = CachePolicyConfig(
    default_ttl_seconds=300.0,
    min_ttl_seconds=60.0,
    max_ttl_seconds=900.0,
    enable_adaptive_ttl=True,
    max_entries=1000,
)


# ============================================================================
# Registry Initialization
# ============================================================================

def initialize_monitoring() -> tuple[SLARegistry, CircuitBreakerRegistry]:
    """Initialize monitoring registries for all data sources.

    Returns:
        Tuple of (SLARegistry, CircuitBreakerRegistry)
    """
    # SLA monitors
    sla_registry = SLARegistry()

    # CEX monitors
    sla_registry.register("binance_orderbook", CEX_ORDERBOOK_THRESHOLDS)
    sla_registry.register("binance_futures", CEX_ORDERBOOK_THRESHOLDS)
    sla_registry.register("bybit_derivatives", CEX_ORDERBOOK_THRESHOLDS)

    # DEX monitors
    sla_registry.register("dexscreener", DEX_THRESHOLDS)

    # Twitter monitors
    sla_registry.register("twitter_search", TWITTER_THRESHOLDS)
    sla_registry.register("twitter_lookup", TWITTER_THRESHOLDS)

    # Circuit breakers
    breaker_registry = CircuitBreakerRegistry()

    # CEX breakers
    breaker_registry.get_or_create("binance_api", CEX_CIRCUIT_CONFIG)
    breaker_registry.get_or_create("bybit_api", CEX_CIRCUIT_CONFIG)

    # DEX breakers
    breaker_registry.get_or_create("dexscreener_api", DEX_CIRCUIT_CONFIG)

    # Twitter breakers
    breaker_registry.get_or_create("twitter_api", TWITTER_CIRCUIT_CONFIG)

    return sla_registry, breaker_registry


# Global registries
SLA_REGISTRY, CIRCUIT_REGISTRY = initialize_monitoring()


# ============================================================================
# Cache Instances
# ============================================================================

ORDERBOOK_CACHE = EnhancedCache(ORDERBOOK_CACHE_CONFIG)
DEX_CACHE = EnhancedCache(DEX_CACHE_CONFIG)
TWITTER_CACHE = EnhancedCache(TWITTER_CACHE_CONFIG)


# ============================================================================
# Backoff Configurations
# ============================================================================

# CEX backoff: aggressive retries
CEX_BACKOFF_CONFIG = BackoffConfig(
    initial_delay=0.5,
    max_delay=10.0,
    multiplier=2.0,
    max_attempts=3,
    jitter=True,
)

# DEX backoff: more patient retries
DEX_BACKOFF_CONFIG = BackoffConfig(
    initial_delay=1.0,
    max_delay=30.0,
    multiplier=2.0,
    max_attempts=4,
    jitter=True,
)

# Twitter backoff: very patient (rate limits)
TWITTER_BACKOFF_CONFIG = BackoffConfig(
    initial_delay=2.0,
    max_delay=60.0,
    multiplier=2.0,
    max_attempts=3,
    jitter=True,
)


# ============================================================================
# Composite Decorators
# ============================================================================

T = TypeVar("T")


def reliable_cex_call(
    cache_ttl: Optional[float] = None,
    cache_key_func: Optional[Callable[..., str]] = None,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Composite decorator for CEX API calls with monitoring, circuit breaker, and caching.

    Args:
        cache_ttl: Cache TTL in seconds
        cache_key_func: Function to generate cache key

    Returns:
        Decorated function

    Example:
        @reliable_cex_call(cache_ttl=5.0, cache_key_func=lambda symbol: f"binance:{symbol}")
        def fetch_binance_orderbook(symbol: str):
            return client.get_order_book_depth(symbol, limit=100)
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        # Extract breaker name from original function name before wrapping
        breaker_name = func.__name__.split("_")[0] + "_api"  # e.g., "binance_api"

        # Apply monitoring
        func = monitored(func.__name__, SLA_REGISTRY)(func)

        # Apply circuit breaker with unique name
        func = with_circuit_breaker(breaker_name, CEX_CIRCUIT_CONFIG, CIRCUIT_REGISTRY)(func)

        # Apply caching
        func = cached(
            ttl_seconds=cache_ttl or ORDERBOOK_CACHE_CONFIG.default_ttl_seconds,
            key_func=cache_key_func,
            cache_instance=ORDERBOOK_CACHE,
            allow_stale_on_error=True,
        )(func)

        return func

    return decorator


def reliable_dex_call(
    cache_ttl: Optional[float] = None,
    cache_key_func: Optional[Callable[..., str]] = None,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Composite decorator for DEX API calls with monitoring, circuit breaker, and caching.

    Args:
        cache_ttl: Cache TTL in seconds
        cache_key_func: Function to generate cache key

    Returns:
        Decorated function
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        func = monitored("dexscreener", SLA_REGISTRY)(func)
        func = with_circuit_breaker("dexscreener_api", DEX_CIRCUIT_CONFIG, CIRCUIT_REGISTRY)(func)
        func = cached(
            ttl_seconds=cache_ttl or DEX_CACHE_CONFIG.default_ttl_seconds,
            key_func=cache_key_func,
            cache_instance=DEX_CACHE,
            allow_stale_on_error=True,
        )(func)
        return func

    return decorator


def reliable_twitter_call(
    cache_ttl: Optional[float] = None,
    cache_key_func: Optional[Callable[..., str]] = None,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Composite decorator for Twitter API calls with monitoring, circuit breaker, and caching.

    Args:
        cache_ttl: Cache TTL in seconds
        cache_key_func: Function to generate cache key

    Returns:
        Decorated function
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        func = monitored("twitter_search", SLA_REGISTRY)(func)
        func = with_circuit_breaker("twitter_api", TWITTER_CIRCUIT_CONFIG, CIRCUIT_REGISTRY)(func)
        func = cached(
            ttl_seconds=cache_ttl or TWITTER_CACHE_CONFIG.default_ttl_seconds,
            key_func=cache_key_func,
            cache_instance=TWITTER_CACHE,
            allow_stale_on_error=True,
        )(func)
        return func

    return decorator


# ============================================================================
# Health Check Utilities
# ============================================================================

def get_system_health() -> dict[str, Any]:
    """Get overall system health status.

    Returns:
        Dictionary with health status for all monitored sources
    """
    health_status = {
        "overall_status": "HEALTHY",
        "healthy_sources": [],
        "degraded_sources": [],
        "failed_sources": [],
        "circuit_breakers": {},
        "cache_stats": {},
        "per_exchange_degradation": {},
    }

    # Check SLAs and categorize sources
    unhealthy = SLA_REGISTRY.get_unhealthy_sources()
    for source_name, monitor in SLA_REGISTRY.get_all().items():
        metrics = monitor.get_metrics()
        status = metrics.status.value
        
        source_info = {
            "name": source_name,
            "status": status,
            "latency_p95": metrics.latency_p95,
            "success_rate": metrics.success_rate,
        }
        
        if status == "HEALTHY":
            health_status["healthy_sources"].append(source_info)
        elif status == "DEGRADED":
            health_status["degraded_sources"].append(source_info)
        elif status == "FAILED":
            health_status["failed_sources"].append(source_info)

    if unhealthy:
        health_status["overall_status"] = "DEGRADED"

    # Check circuit breakers
    for breaker_name, breaker in CIRCUIT_REGISTRY.get_all().items():
        state = breaker.state
        health_status["circuit_breakers"][breaker_name] = {
            "state": state.value,
            "failure_count": breaker._failure_count,
        }

        if state == CircuitState.OPEN:
            health_status["overall_status"] = "DEGRADED"

    # Cache stats
    health_status["cache_stats"]["orderbook"] = ORDERBOOK_CACHE.get_stats()
    health_status["cache_stats"]["dex"] = DEX_CACHE.get_stats()
    health_status["cache_stats"]["twitter"] = TWITTER_CACHE.get_stats()

    # Per-exchange degradation tracking
    health_status["per_exchange_degradation"] = get_exchange_degradation()

    return health_status


def get_exchange_degradation() -> dict[str, Any]:
    """Get per-exchange degradation status and metrics.

    Returns:
        Dictionary mapping exchange names to their degradation metrics
    """
    exchange_status = {}

    # Group sources by exchange
    exchange_sources = {
        "binance": ["binance_orderbook", "binance_futures"],
        "bybit": ["bybit_derivatives"],
        "dexscreener": ["dexscreener"],
        "twitter": ["twitter_search", "twitter_lookup"],
    }

    for exchange_name, source_names in exchange_sources.items():
        exchange_metrics = {
            "exchange": exchange_name,
            "overall_status": "HEALTHY",
            "sources": [],
            "avg_latency_p95": 0.0,
            "avg_success_rate": 0.0,
            "circuit_breaker_state": "CLOSED",
            "degradation_score": 0.0,  # 0 = healthy, 1 = completely degraded
        }

        source_count = 0
        total_latency = 0.0
        total_success_rate = 0.0
        degraded_sources = 0
        failed_sources = 0

        for source_name in source_names:
            monitor = SLA_REGISTRY.get_monitor(source_name)
            if monitor:
                metrics = monitor.get_metrics()
                status = metrics.status.value

                exchange_metrics["sources"].append({
                    "name": source_name,
                    "status": status,
                    "latency_p95": metrics.latency_p95,
                    "success_rate": metrics.success_rate,
                })

                total_latency += metrics.latency_p95 or 0.0
                total_success_rate += metrics.success_rate or 0.0
                source_count += 1

                if status == "DEGRADED":
                    degraded_sources += 1
                elif status == "FAILED":
                    failed_sources += 1

        # Calculate averages
        if source_count > 0:
            exchange_metrics["avg_latency_p95"] = total_latency / source_count
            exchange_metrics["avg_success_rate"] = total_success_rate / source_count

        # Determine overall exchange status
        if failed_sources > 0:
            exchange_metrics["overall_status"] = "FAILED"
        elif degraded_sources > 0:
            exchange_metrics["overall_status"] = "DEGRADED"

        # Check circuit breaker for this exchange
        breaker_name = f"{exchange_name}_api"
        breaker = CIRCUIT_REGISTRY.get(breaker_name)
        if breaker:
            exchange_metrics["circuit_breaker_state"] = breaker.state.value
            if breaker.state != CircuitState.CLOSED:
                exchange_metrics["overall_status"] = "DEGRADED"

        # Calculate degradation score (0-1)
        # Factors: failed sources, degraded sources, circuit breaker state, success rate
        degradation_score = 0.0
        if source_count > 0:
            degradation_score += (failed_sources / source_count) * 0.5
            degradation_score += (degraded_sources / source_count) * 0.3
            if breaker and breaker.state == CircuitState.OPEN:
                degradation_score += 0.2
            elif breaker and breaker.state == CircuitState.HALF_OPEN:
                degradation_score += 0.1
            # Factor in success rate
            if exchange_metrics["avg_success_rate"] < 0.95:
                degradation_score += (1 - exchange_metrics["avg_success_rate"]) * 0.1

        exchange_metrics["degradation_score"] = min(degradation_score, 1.0)

        exchange_status[exchange_name] = exchange_metrics

    return exchange_status


def reset_all_monitors() -> None:
    """Reset all SLA monitors and circuit breakers (for testing)."""
    for monitor in SLA_REGISTRY.get_all().values():
        monitor.reset()

    for breaker in CIRCUIT_REGISTRY.get_all().values():
        breaker.reset()

    ORDERBOOK_CACHE.clear()
    DEX_CACHE.clear()
    TWITTER_CACHE.clear()

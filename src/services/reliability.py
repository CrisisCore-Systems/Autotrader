"""Integration module to apply reliability patterns to existing data sources."""

from __future__ import annotations

from typing import Any, Callable, Optional, TypeVar

from src.services.cache_policy import EnhancedCache, CachePolicyConfig, cached
from src.services.circuit_breaker import (
    CircuitBreakerConfig,
    CircuitBreakerRegistry,
    with_circuit_breaker,
)
from src.services.sla_monitor import SLAThresholds, SLARegistry, monitored


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

# CEX APIs: fail fast
CEX_CIRCUIT_CONFIG = CircuitBreakerConfig(
    failure_threshold=5,
    timeout_seconds=30.0,
    success_threshold=2,
)

# DEX APIs: more tolerant
DEX_CIRCUIT_CONFIG = CircuitBreakerConfig(
    failure_threshold=10,
    timeout_seconds=60.0,
    success_threshold=3,
)

# Twitter API: very tolerant (rate limits)
TWITTER_CIRCUIT_CONFIG = CircuitBreakerConfig(
    failure_threshold=3,
    timeout_seconds=120.0,
    success_threshold=1,
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
        # Apply monitoring
        func = monitored(func.__name__, SLA_REGISTRY)(func)

        # Apply circuit breaker
        breaker_name = func.__name__.split("_")[0] + "_api"  # e.g., "binance_api"
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
        "data_sources": {},
        "circuit_breakers": {},
        "cache_stats": {},
    }

    # Check SLAs
    unhealthy = SLA_REGISTRY.get_unhealthy_sources()
    for source_name, monitor in SLA_REGISTRY.get_all().items():
        metrics = monitor.get_current_metrics()
        health_status["data_sources"][source_name] = {
            "status": monitor.get_status().value,
            "latency_p95": metrics.latency_p95_seconds if metrics else None,
            "success_rate": metrics.success_rate if metrics else None,
        }

    if unhealthy:
        health_status["overall_status"] = "DEGRADED"

    # Check circuit breakers
    for breaker_name, breaker in CIRCUIT_REGISTRY.get_all().items():
        state = breaker.get_state()
        health_status["circuit_breakers"][breaker_name] = {
            "state": state.value,
            "failure_count": breaker._failure_count,
        }

        if state.value == "OPEN":
            health_status["overall_status"] = "DEGRADED"

    # Cache stats
    health_status["cache_stats"]["orderbook"] = ORDERBOOK_CACHE.get_stats()
    health_status["cache_stats"]["dex"] = DEX_CACHE.get_stats()
    health_status["cache_stats"]["twitter"] = TWITTER_CACHE.get_stats()

    return health_status


def reset_all_monitors() -> None:
    """Reset all SLA monitors and circuit breakers (for testing)."""
    for monitor in SLA_REGISTRY.get_all().values():
        monitor._latencies.clear()
        monitor._successes.clear()
        monitor._failures.clear()

    for breaker in CIRCUIT_REGISTRY.get_all().values():
        breaker._state = breaker._state.__class__.CLOSED
        breaker._failure_count = 0
        breaker._failure_times.clear()

    ORDERBOOK_CACHE.clear()
    DEX_CACHE.clear()
    TWITTER_CACHE.clear()

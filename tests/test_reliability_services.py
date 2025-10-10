"""Unit tests for reliability services and supporting infrastructure."""

from __future__ import annotations

import pytest

from src.services.cache_policy import (
    CachePolicyConfig,
    EnhancedCache,
    cache_aside,
    cached,
)
from src.services.circuit_breaker import CircuitBreakerError
from src.services.reliability import (
    CEX_CIRCUIT_CONFIG,
    CIRCUIT_REGISTRY,
    ORDERBOOK_CACHE,
    SLA_REGISTRY,
    get_system_health,
    initialize_monitoring,
    reliable_cex_call,
    reset_all_monitors,
)
from src.services.sla_monitor import SLAStatus


@pytest.fixture(autouse=True)
def clean_state() -> None:
    """Reset global registries and caches around each test."""
    reset_all_monitors()
    yield
    reset_all_monitors()


def test_initialize_monitoring_registers_expected_resources() -> None:
    """Monitoring bootstrap should register all default data sources."""
    sla_registry, breaker_registry = initialize_monitoring()

    expected_slas = {
        "binance_orderbook",
        "binance_futures",
        "bybit_derivatives",
        "dexscreener",
        "twitter_search",
        "twitter_lookup",
    }
    assert expected_slas.issubset(set(sla_registry.get_all().keys()))

    expected_breakers = {"binance_api", "bybit_api", "dexscreener_api", "twitter_api"}
    assert expected_breakers.issubset(set(breaker_registry.get_all().keys()))


def test_enhanced_cache_ttl_and_stats() -> None:
    """Cache entries should respect TTL and update hit/miss statistics."""
    cache = EnhancedCache(CachePolicyConfig(default_ttl_seconds=10, enable_adaptive_ttl=False))
    cache.set("token", {"price": 1.0}, current_time=0)

    assert cache.get("token", current_time=5) == {"price": 1.0}
    assert cache.get("token", current_time=15) is None

    stats = cache.get_stats()
    assert stats["hits"] == 1
    assert stats["misses"] == 1
    assert stats["total_requests"] == 2


def test_enhanced_cache_eviction_and_adaptive_ttl() -> None:
    """Accessing entries should extend TTL and trigger eviction when full."""
    config = CachePolicyConfig(
        default_ttl_seconds=5,
        max_ttl_seconds=20,
        enable_adaptive_ttl=True,
        max_entries=2,
        eviction_ratio=0.5,
    )
    cache = EnhancedCache(config)

    cache.set("a", "A", current_time=0)
    cache.set("b", "B", current_time=0)
    assert cache.get("a", current_time=1) == "A"
    assert cache._cache["a"].ttl_seconds > config.default_ttl_seconds

    cache.set("c", "C", current_time=2)
    assert cache.get("b", current_time=3) is None

    stats = cache.get_stats()
    assert stats["evictions"] == 1
    assert stats["size"] == 2


def test_cache_aside_decorator_caches_results() -> None:
    """cache_aside decorator should fetch data once per key."""
    cache = EnhancedCache(CachePolicyConfig(default_ttl_seconds=30, enable_adaptive_ttl=False))
    calls = {"count": 0}

    @cache_aside(cache)
    def load_value(key: str) -> str:
        calls["count"] += 1
        return f"value:{key}"

    assert load_value("alpha") == "value:alpha"
    assert load_value("alpha") == "value:alpha"
    assert calls["count"] == 1


def test_cached_decorator_uses_custom_key_and_reuses_results() -> None:
    """cached decorator should reuse results and track hits/misses."""
    cache = EnhancedCache(CachePolicyConfig(default_ttl_seconds=60, enable_adaptive_ttl=False))
    calls = {"count": 0}

    @cached(cache_instance=cache, key_func=lambda symbol: f"price:{symbol}")
    def fetch_price(symbol: str) -> dict[str, float | str]:
        calls["count"] += 1
        return {"symbol": symbol, "price": 1.0}

    assert fetch_price("ETH") == {"symbol": "ETH", "price": 1.0}
    assert fetch_price("ETH") == {"symbol": "ETH", "price": 1.0}
    assert fetch_price("BTC") == {"symbol": "BTC", "price": 1.0}
    assert calls["count"] == 2

    stats = cache.get_stats()
    assert stats["hits"] == 1
    assert stats["misses"] == 2


def test_reliable_cex_call_records_metrics_and_uses_cache() -> None:
    """Composite decorator should record SLA metrics and leverage caching."""
    calls = {"count": 0}

    @reliable_cex_call(cache_ttl=60.0, cache_key_func=lambda symbol: f"binance:{symbol}")
    def binance_depth(symbol: str) -> dict[str, str | int]:
        calls["count"] += 1
        return {"symbol": symbol, "depth": 42}

    assert binance_depth("ETH") == {"symbol": "ETH", "depth": 42}
    assert binance_depth("ETH") == {"symbol": "ETH", "depth": 42}
    assert calls["count"] == 1

    monitor = SLA_REGISTRY.get_monitor("binance_depth")
    assert monitor is not None
    metrics = monitor.get_metrics()
    assert metrics.total_requests == 1
    assert metrics.failed_requests == 0
    assert metrics.status == SLAStatus.HEALTHY

    stats = ORDERBOOK_CACHE.get_stats()
    assert stats["hits"] == 1
    assert stats["misses"] == 1

    breaker = CIRCUIT_REGISTRY.get("binance_api")
    assert breaker is not None
    assert breaker.is_closed


def test_reliable_cex_call_opens_circuit_on_repeated_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    """Repeated failures should open the circuit breaker and report degraded status."""
    monkeypatch.setattr(CEX_CIRCUIT_CONFIG, "failure_threshold", 2)
    monkeypatch.setattr(CEX_CIRCUIT_CONFIG, "timeout_seconds", 60.0)
    calls = {"count": 0}

    @reliable_cex_call(cache_ttl=0.0, cache_key_func=lambda symbol: f"fail:{symbol}")
    def binance_fail(symbol: str) -> None:  # pragma: no cover - exception path
        calls["count"] += 1
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        binance_fail("BTC")
    with pytest.raises(RuntimeError):
        binance_fail("BTC")
    with pytest.raises(CircuitBreakerError):
        binance_fail("BTC")

    assert calls["count"] == 2

    monitor = SLA_REGISTRY.get_monitor("binance_fail")
    assert monitor is not None
    metrics = monitor.get_metrics()
    assert metrics.failed_requests == 2
    assert metrics.status in {SLAStatus.DEGRADED, SLAStatus.FAILED}


def test_get_system_health_reports_expected_sections() -> None:
    """System health response should include SLA, breaker, and cache data."""

    @reliable_cex_call(cache_ttl=10.0, cache_key_func=lambda symbol: symbol)
    def binance_quote(symbol: str) -> dict[str, str]:
        return {"symbol": symbol}

    assert binance_quote("SOL") == {"symbol": "SOL"}

    health = get_system_health()
    assert set(health.keys()) == {"overall_status", "data_sources", "circuit_breakers", "cache_stats"}
    assert "binance_quote" in health["data_sources"]
    assert "orderbook" in health["cache_stats"]
    assert "binance_api" in health["circuit_breakers"]
    assert health["data_sources"]["binance_quote"]["status"] == "healthy"


def test_reset_all_monitors_clears_metrics_and_caches() -> None:
    """Reset helper should clear monitor metrics and cache statistics."""

    @reliable_cex_call(cache_ttl=10.0, cache_key_func=lambda symbol: symbol)
    def tracked_call(symbol: str) -> dict[str, str]:
        return {"symbol": symbol}

    assert tracked_call("ADA") == {"symbol": "ADA"}

    monitor = SLA_REGISTRY.get_monitor("tracked_call")
    assert monitor is not None
    assert monitor.get_metrics().total_requests == 1
    assert ORDERBOOK_CACHE.get_stats()["total_requests"] == 1

    reset_all_monitors()

    assert monitor.get_metrics().total_requests == 0
    assert ORDERBOOK_CACHE.get_stats()["total_requests"] == 0
    breaker = CIRCUIT_REGISTRY.get("binance_api")
    assert breaker is not None
    assert breaker.is_closed

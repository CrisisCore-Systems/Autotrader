"""Example demonstrating enhanced reliability features.

This script shows how to use:
1. Exponential backoff for resilient retries
2. Circuit breaker alerts for monitoring
3. Per-exchange degradation tracking
4. Health endpoint integration
"""

from __future__ import annotations

import time
from typing import Dict, Any

from src.services.backoff import with_backoff, BackoffConfig, BackoffExhausted
from src.services.circuit_breaker_alerts import (
    get_alert_manager,
    log_alert_handler,
    CircuitBreakerAlert,
)
from src.services.reliability import (
    get_system_health,
    get_exchange_degradation,
    reset_all_monitors,
    reliable_cex_call,
)


def print_section(title: str) -> None:
    """Print a section header."""
    print(f"\n{'=' * 70}")
    print(f"  {title}")
    print('=' * 70)


def example_1_exponential_backoff() -> None:
    """Example 1: Using exponential backoff for resilient API calls."""
    print_section("Example 1: Exponential Backoff")

    # Track attempts
    attempts = {"count": 0}

    @with_backoff(
        BackoffConfig(
            initial_delay=0.1,
            max_delay=2.0,
            max_attempts=4,
            jitter=False,  # Disable for predictable demo
            on_retry=lambda exc, attempt, delay: print(
                f"  Retry {attempt}: waiting {delay:.2f}s after {type(exc).__name__}"
            ),
        )
    )
    def flaky_api_call() -> Dict[str, Any]:
        """Simulates a flaky API that fails 2 times then succeeds."""
        attempts["count"] += 1
        print(f"  Attempt {attempts['count']}: Calling API...")

        if attempts["count"] < 3:
            raise ConnectionError("API temporarily unavailable")

        return {"status": "success", "data": [1, 2, 3]}

    # Make the call - will retry automatically
    print("\nCalling flaky API with automatic retries:")
    result = flaky_api_call()
    print(f"\n✅ Success after {attempts['count']} attempts!")
    print(f"Result: {result}")


def example_2_backoff_exhausted() -> None:
    """Example 2: Handling exhausted retries with fallback."""
    print_section("Example 2: Backoff Exhausted with Fallback")

    @with_backoff(
        BackoffConfig(
            initial_delay=0.05,
            max_attempts=3,
            jitter=False,
        )
    )
    def always_fails() -> Dict[str, Any]:
        """API that always fails."""
        print("  Attempting primary source...")
        raise TimeoutError("Primary source timeout")

    print("\nTrying primary source with automatic retries:")
    try:
        result = always_fails()
    except BackoffExhausted as e:
        print(f"\n⚠️  Retries exhausted after {e.attempts} attempts")
        print(f"Last error: {e.last_exception}")
        print("\n✅ Using fallback source instead")
        result = {"status": "success", "source": "fallback", "data": []}

    print(f"Final result: {result}")


def example_3_circuit_breaker_alerts() -> None:
    """Example 3: Circuit breaker alerts and monitoring."""
    print_section("Example 3: Circuit Breaker Alerts")

    # Get alert manager
    alert_manager = get_alert_manager()

    # Clear previous alerts
    alert_manager.clear_history()

    # Register log handler to see alerts in console
    print("\nRegistering alert handler...")
    alert_manager.register_handler(log_alert_handler)

    # Register custom handler
    alert_log = []

    def custom_handler(alert: CircuitBreakerAlert) -> None:
        """Custom handler that stores alerts."""
        alert_log.append(alert)

    alert_manager.register_handler(custom_handler)
    print("✅ Alert handlers registered")

    # Simulate failures to trigger circuit breaker
    print("\nSimulating API failures to trigger circuit breaker...")

    @reliable_cex_call(cache_ttl=0.01, cache_key_func=lambda: "test")
    def failing_call() -> None:
        raise RuntimeError("Service unavailable")

    # Try multiple times to trigger circuit breaker
    for i in range(6):
        try:
            failing_call()
        except Exception:
            print(f"  Call {i + 1}: Failed ❌")
            time.sleep(0.01)

    # Check alert history
    print(f"\n📋 Alerts generated: {len(alert_log)}")
    for alert in alert_log:
        print(
            f"  - {alert.severity.value.upper()}: {alert.breaker_name} "
            f"{alert.old_state} → {alert.new_state}"
        )


def example_4_exchange_degradation() -> None:
    """Example 4: Per-exchange degradation tracking."""
    print_section("Example 4: Per-Exchange Degradation Tracking")

    # Make some calls to populate metrics
    print("\nMaking test calls to populate metrics...")

    @reliable_cex_call(cache_ttl=1.0, cache_key_func=lambda symbol: f"test:{symbol}")
    def test_call(symbol: str) -> Dict[str, Any]:
        return {"symbol": symbol, "price": 100.0}

    # Successful calls
    for symbol in ["BTC", "ETH", "SOL"]:
        test_call(symbol)
        print(f"  ✅ Called for {symbol}")

    # Get per-exchange degradation
    print("\nPer-Exchange Degradation Status:")
    exchanges = get_exchange_degradation()

    for name, data in exchanges.items():
        status_icon = "✅" if data["overall_status"] == "HEALTHY" else "⚠️"
        print(f"\n{status_icon} {name.upper()}")
        print(f"  Status: {data['overall_status']}")
        print(f"  Degradation Score: {data['degradation_score']:.2f}")
        print(f"  Circuit Breaker: {data['circuit_breaker_state']}")
        print(f"  Avg P95 Latency: {data['avg_latency_p95']:.3f}s")
        print(f"  Avg Success Rate: {data['avg_success_rate']:.1%}")
        print(f"  Sources: {len(data['sources'])}")


def example_5_health_monitoring() -> None:
    """Example 5: Comprehensive health monitoring."""
    print_section("Example 5: Comprehensive Health Monitoring")

    # Get system health
    health = get_system_health()

    print(f"\nOverall System Status: {health['overall_status']}")

    # Show healthy sources
    if health["healthy_sources"]:
        print(f"\n✅ Healthy Sources ({len(health['healthy_sources'])}):")
        for source in health["healthy_sources"][:3]:  # Show first 3
            print(f"  - {source['name']}: {source['success_rate']:.1%} success rate")

    # Show degraded sources
    if health["degraded_sources"]:
        print(f"\n⚠️  Degraded Sources ({len(health['degraded_sources'])}):")
        for source in health["degraded_sources"]:
            print(
                f"  - {source['name']}: {source['success_rate']:.1%} success rate, "
                f"{source['latency_p95']:.2f}s P95"
            )

    # Show failed sources
    if health["failed_sources"]:
        print(f"\n❌ Failed Sources ({len(health['failed_sources'])}):")
        for source in health["failed_sources"]:
            print(f"  - {source['name']}")

    # Show circuit breaker states
    print(f"\n🔌 Circuit Breakers:")
    for name, breaker in health["circuit_breakers"].items():
        state_icon = "✅" if breaker["state"] == "CLOSED" else "❌"
        print(f"  {state_icon} {name}: {breaker['state']}")

    # Show cache performance
    print(f"\n💾 Cache Performance:")
    for cache_name, stats in health["cache_stats"].items():
        hit_rate = (
            stats["hits"] / stats["total_requests"]
            if stats["total_requests"] > 0
            else 0
        )
        print(f"  - {cache_name}: {hit_rate:.1%} hit rate, {stats['size']} entries")


def example_6_adaptive_behavior() -> None:
    """Example 6: Adaptive behavior based on exchange health."""
    print_section("Example 6: Adaptive Behavior Based on Health")

    exchanges = get_exchange_degradation()

    print("\nAdaptive Request Strategy:")
    for name, data in exchanges.items():
        score = data["degradation_score"]

        if score < 0.2:
            strategy = "Normal rate (50 req/sec)"
            icon = "✅"
        elif score < 0.5:
            strategy = "Reduced rate (25 req/sec)"
            icon = "⚠️"
        else:
            strategy = "Minimal rate (5 req/sec)"
            icon = "❌"

        print(f"{icon} {name}: {strategy} (score: {score:.2f})")


def main() -> None:
    """Run all examples."""
    print("\n" + "=" * 70)
    print("  Enhanced Reliability Features Demo")
    print("=" * 70)

    # Reset state before examples
    reset_all_monitors()

    try:
        example_1_exponential_backoff()
        time.sleep(0.1)

        example_2_backoff_exhausted()
        time.sleep(0.1)

        # Reset before circuit breaker example
        reset_all_monitors()
        example_3_circuit_breaker_alerts()
        time.sleep(0.1)

        # Reset before health examples
        reset_all_monitors()
        example_4_exchange_degradation()
        time.sleep(0.1)

        example_5_health_monitoring()
        time.sleep(0.1)

        example_6_adaptive_behavior()

    finally:
        # Cleanup
        reset_all_monitors()

    print("\n" + "=" * 70)
    print("  Demo Complete!")
    print("=" * 70)
    print("\nKey Takeaways:")
    print("  1. Exponential backoff handles transient failures automatically")
    print("  2. Circuit breaker alerts provide real-time failure notifications")
    print("  3. Per-exchange tracking enables granular monitoring")
    print("  4. Health endpoints aggregate all reliability data")
    print("  5. Systems can adapt behavior based on health metrics")
    print("\nSee docs/RELIABILITY_ENHANCEMENTS.md for full documentation.")


if __name__ == "__main__":
    main()

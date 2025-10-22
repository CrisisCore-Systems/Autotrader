"""Tests for enhanced health endpoints without FastAPI dependencies."""

from __future__ import annotations

from src.services.reliability import (
    get_exchange_degradation,
    get_system_health,
    reset_all_monitors,
)
from src.services.circuit_breaker_alerts import get_alert_manager


def test_get_exchange_degradation_returns_dict():
    """Test that get_exchange_degradation returns expected structure."""
    reset_all_monitors()

    result = get_exchange_degradation()

    # Should return dict
    assert isinstance(result, dict)

    # Should have exchange entries
    assert "binance" in result
    assert "bybit" in result
    assert "dexscreener" in result
    assert "twitter" in result


def test_get_exchange_degradation_structure():
    """Test that each exchange has required fields."""
    reset_all_monitors()

    result = get_exchange_degradation()

    for exchange_name, exchange_data in result.items():
        assert "exchange" in exchange_data
        assert "overall_status" in exchange_data
        assert "sources" in exchange_data
        assert "avg_latency_p95" in exchange_data
        assert "avg_success_rate" in exchange_data
        assert "circuit_breaker_state" in exchange_data
        assert "degradation_score" in exchange_data

        # Check types
        assert isinstance(exchange_data["exchange"], str)
        assert isinstance(exchange_data["sources"], list)
        assert isinstance(exchange_data["degradation_score"], float)
        assert 0 <= exchange_data["degradation_score"] <= 1


def test_get_system_health_includes_exchange_degradation():
    """Test that system health includes per-exchange degradation."""
    reset_all_monitors()

    health = get_system_health()

    # Should have all expected keys
    assert "overall_status" in health
    assert "healthy_sources" in health
    assert "degraded_sources" in health
    assert "failed_sources" in health
    assert "circuit_breakers" in health
    assert "cache_stats" in health
    assert "per_exchange_degradation" in health

    # per_exchange_degradation should match get_exchange_degradation
    exchanges = health["per_exchange_degradation"]
    assert isinstance(exchanges, dict)
    assert "binance" in exchanges
    assert "bybit" in exchanges
    assert "dexscreener" in exchanges
    assert "twitter" in exchanges


def test_alert_manager_tracks_circuit_breaker_events():
    """Test that alert manager can track circuit breaker events."""
    alert_manager = get_alert_manager()
    alert_manager.clear_history()

    # Create hooks
    on_open = alert_manager.create_open_hook()
    on_half_open = alert_manager.create_half_open_hook()
    on_close = alert_manager.create_close_hook()

    # Simulate state transitions
    on_open("test_breaker")
    on_half_open("test_breaker")
    on_close("test_breaker")

    # Check history
    history = alert_manager.get_alert_history()
    assert len(history) == 3

    # Check alert types
    assert history[0].new_state == "OPEN"
    assert history[1].new_state == "HALF_OPEN"
    assert history[2].new_state == "CLOSED"


def test_exchange_degradation_json_serializable():
    """Test that exchange degradation data is JSON-serializable."""
    import json

    reset_all_monitors()

    result = get_exchange_degradation()

    # Should be JSON-serializable
    json_str = json.dumps(result)
    assert json_str is not None

    # Should be able to parse back
    parsed = json.loads(json_str)
    assert parsed == result


def test_system_health_json_serializable():
    """Test that system health data is JSON-serializable."""
    import json

    reset_all_monitors()

    health = get_system_health()

    # Should be JSON-serializable
    json_str = json.dumps(health)
    assert json_str is not None

    # Should be able to parse back
    parsed = json.loads(json_str)
    assert "overall_status" in parsed
    assert "per_exchange_degradation" in parsed


def test_alert_history_json_serializable():
    """Test that alert history is JSON-serializable."""
    import json

    alert_manager = get_alert_manager()
    alert_manager.clear_history()

    # Generate some alerts
    on_open = alert_manager.create_open_hook()
    on_open("test_breaker")

    history = alert_manager.get_alert_history()

    # Convert to dicts
    alert_dicts = [alert.to_dict() for alert in history]

    # Should be JSON-serializable
    json_str = json.dumps(alert_dicts)
    assert json_str is not None

    # Should be able to parse back
    parsed = json.loads(json_str)
    assert len(parsed) == 1
    assert parsed[0]["breaker_name"] == "test_breaker"


def test_exchange_degradation_with_no_metrics():
    """Test that exchange degradation works with no metrics."""
    reset_all_monitors()

    # Get degradation immediately after reset (no metrics)
    result = get_exchange_degradation()

    # Should still return valid data
    assert isinstance(result, dict)

    for exchange_data in result.values():
        # Degradation score should be 0 for fresh state
        assert exchange_data["degradation_score"] == 0.0
        assert exchange_data["overall_status"] == "HEALTHY"

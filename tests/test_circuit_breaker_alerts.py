"""Tests for circuit breaker alert system."""

from __future__ import annotations

import pytest
from datetime import datetime

from src.services.circuit_breaker_alerts import (
    AlertSeverity,
    CircuitBreakerAlert,
    CircuitBreakerAlertManager,
    get_alert_manager,
    log_alert_handler,
)


def test_circuit_breaker_alert_creation():
    """Test creating a circuit breaker alert."""
    alert = CircuitBreakerAlert(
        breaker_name="test_breaker",
        old_state="CLOSED",
        new_state="OPEN",
        severity=AlertSeverity.CRITICAL,
        timestamp=datetime.utcnow(),
        failure_count=5,
        message="Circuit opened due to failures",
    )

    assert alert.breaker_name == "test_breaker"
    assert alert.old_state == "CLOSED"
    assert alert.new_state == "OPEN"
    assert alert.severity == AlertSeverity.CRITICAL
    assert alert.failure_count == 5


def test_circuit_breaker_alert_to_dict():
    """Test converting alert to dictionary."""
    timestamp = datetime.utcnow()
    alert = CircuitBreakerAlert(
        breaker_name="test_breaker",
        old_state="CLOSED",
        new_state="OPEN",
        severity=AlertSeverity.WARNING,
        timestamp=timestamp,
        message="Test message",
    )

    alert_dict = alert.to_dict()

    assert alert_dict["breaker_name"] == "test_breaker"
    assert alert_dict["old_state"] == "CLOSED"
    assert alert_dict["new_state"] == "OPEN"
    assert alert_dict["severity"] == "warning"
    assert alert_dict["timestamp"] == timestamp.isoformat()
    assert alert_dict["message"] == "Test message"


def test_alert_manager_register_handler():
    """Test registering alert handlers."""
    manager = CircuitBreakerAlertManager()
    handler_called = {"count": 0}

    def test_handler(alert: CircuitBreakerAlert):
        handler_called["count"] += 1

    manager.register_handler(test_handler)

    alert = CircuitBreakerAlert(
        breaker_name="test",
        old_state="CLOSED",
        new_state="OPEN",
        severity=AlertSeverity.CRITICAL,
        timestamp=datetime.utcnow(),
    )

    manager.send_alert(alert)

    assert handler_called["count"] == 1


def test_alert_manager_unregister_handler():
    """Test unregistering alert handlers."""
    manager = CircuitBreakerAlertManager()
    handler_called = {"count": 0}

    def test_handler(alert: CircuitBreakerAlert):
        handler_called["count"] += 1

    manager.register_handler(test_handler)
    manager.unregister_handler(test_handler)

    alert = CircuitBreakerAlert(
        breaker_name="test",
        old_state="CLOSED",
        new_state="OPEN",
        severity=AlertSeverity.CRITICAL,
        timestamp=datetime.utcnow(),
    )

    manager.send_alert(alert)

    assert handler_called["count"] == 0


def test_alert_manager_multiple_handlers():
    """Test multiple handlers receiving alerts."""
    manager = CircuitBreakerAlertManager()
    handler1_calls = []
    handler2_calls = []

    def handler1(alert: CircuitBreakerAlert):
        handler1_calls.append(alert)

    def handler2(alert: CircuitBreakerAlert):
        handler2_calls.append(alert)

    manager.register_handler(handler1)
    manager.register_handler(handler2)

    alert = CircuitBreakerAlert(
        breaker_name="test",
        old_state="CLOSED",
        new_state="OPEN",
        severity=AlertSeverity.CRITICAL,
        timestamp=datetime.utcnow(),
    )

    manager.send_alert(alert)

    assert len(handler1_calls) == 1
    assert len(handler2_calls) == 1
    assert handler1_calls[0] == alert
    assert handler2_calls[0] == alert


def test_alert_manager_alert_history():
    """Test alert history tracking."""
    manager = CircuitBreakerAlertManager()

    for i in range(5):
        alert = CircuitBreakerAlert(
            breaker_name=f"breaker_{i}",
            old_state="CLOSED",
            new_state="OPEN",
            severity=AlertSeverity.CRITICAL,
            timestamp=datetime.utcnow(),
        )
        manager.send_alert(alert)

    history = manager.get_alert_history()
    assert len(history) == 5

    # Test limit
    limited_history = manager.get_alert_history(limit=3)
    assert len(limited_history) == 3
    assert limited_history[0].breaker_name == "breaker_2"


def test_alert_manager_clear_history():
    """Test clearing alert history."""
    manager = CircuitBreakerAlertManager()

    alert = CircuitBreakerAlert(
        breaker_name="test",
        old_state="CLOSED",
        new_state="OPEN",
        severity=AlertSeverity.CRITICAL,
        timestamp=datetime.utcnow(),
    )
    manager.send_alert(alert)

    assert len(manager.get_alert_history()) == 1

    manager.clear_history()
    assert len(manager.get_alert_history()) == 0


def test_alert_manager_max_history_size():
    """Test that history respects max size."""
    manager = CircuitBreakerAlertManager()
    manager._max_history_size = 10

    for i in range(15):
        alert = CircuitBreakerAlert(
            breaker_name=f"breaker_{i}",
            old_state="CLOSED",
            new_state="OPEN",
            severity=AlertSeverity.CRITICAL,
            timestamp=datetime.utcnow(),
        )
        manager.send_alert(alert)

    history = manager.get_alert_history()
    assert len(history) == 10
    # Should keep the most recent 10
    assert history[0].breaker_name == "breaker_5"
    assert history[-1].breaker_name == "breaker_14"


def test_alert_manager_create_open_hook():
    """Test creating open hook that generates alerts."""
    manager = CircuitBreakerAlertManager()
    on_open = manager.create_open_hook()

    on_open("test_breaker")

    history = manager.get_alert_history()
    assert len(history) == 1
    alert = history[0]
    assert alert.breaker_name == "test_breaker"
    assert alert.new_state == "OPEN"
    assert alert.severity == AlertSeverity.CRITICAL


def test_alert_manager_create_half_open_hook():
    """Test creating half-open hook that generates alerts."""
    manager = CircuitBreakerAlertManager()
    on_half_open = manager.create_half_open_hook()

    on_half_open("test_breaker")

    history = manager.get_alert_history()
    assert len(history) == 1
    alert = history[0]
    assert alert.breaker_name == "test_breaker"
    assert alert.new_state == "HALF_OPEN"
    assert alert.severity == AlertSeverity.WARNING


def test_alert_manager_create_close_hook():
    """Test creating close hook that generates alerts."""
    manager = CircuitBreakerAlertManager()
    on_close = manager.create_close_hook()

    on_close("test_breaker")

    history = manager.get_alert_history()
    assert len(history) == 1
    alert = history[0]
    assert alert.breaker_name == "test_breaker"
    assert alert.new_state == "CLOSED"
    assert alert.severity == AlertSeverity.INFO


def test_alert_manager_handler_exception_handling():
    """Test that exceptions in handlers don't break alert sending."""
    manager = CircuitBreakerAlertManager()
    good_handler_called = {"count": 0}

    def bad_handler(alert: CircuitBreakerAlert):
        raise ValueError("Handler error")

    def good_handler(alert: CircuitBreakerAlert):
        good_handler_called["count"] += 1

    manager.register_handler(bad_handler)
    manager.register_handler(good_handler)

    alert = CircuitBreakerAlert(
        breaker_name="test",
        old_state="CLOSED",
        new_state="OPEN",
        severity=AlertSeverity.CRITICAL,
        timestamp=datetime.utcnow(),
    )

    # Should not raise exception
    manager.send_alert(alert)

    # Good handler should still be called
    assert good_handler_called["count"] == 1
    # Alert should still be in history
    assert len(manager.get_alert_history()) == 1


def test_get_alert_manager_returns_global_instance():
    """Test that get_alert_manager returns consistent instance."""
    manager1 = get_alert_manager()
    manager2 = get_alert_manager()

    assert manager1 is manager2


def test_log_alert_handler(capsys):
    """Test log alert handler outputs correctly."""
    alert = CircuitBreakerAlert(
        breaker_name="test_breaker",
        old_state="CLOSED",
        new_state="OPEN",
        severity=AlertSeverity.CRITICAL,
        timestamp=datetime.utcnow(),
        message="Test alert message",
    )

    log_alert_handler(alert)

    captured = capsys.readouterr()
    assert "CRITICAL" in captured.out
    assert "test_breaker" in captured.out
    assert "CLOSED -> OPEN" in captured.out
    assert "Test alert message" in captured.out

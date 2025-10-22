"""Tests for exponential backoff strategy."""

from __future__ import annotations

import time
import pytest

from src.services.backoff import (
    BackoffConfig,
    BackoffExhausted,
    ExponentialBackoff,
    with_backoff,
    calculate_backoff_delay,
)


def test_exponential_backoff_calculates_increasing_delays():
    """Backoff should calculate exponentially increasing delays."""
    backoff = ExponentialBackoff(
        BackoffConfig(
            initial_delay=1.0,
            multiplier=2.0,
            max_delay=100.0,
            jitter=False,
        )
    )

    delays = [backoff.next_delay() for _ in range(5)]

    # Should be: 1.0, 2.0, 4.0, 8.0, 16.0
    assert delays[0] == 1.0
    assert delays[1] == 2.0
    assert delays[2] == 4.0
    assert delays[3] == 8.0
    assert delays[4] == 16.0


def test_exponential_backoff_respects_max_delay():
    """Backoff should cap delays at max_delay."""
    backoff = ExponentialBackoff(
        BackoffConfig(
            initial_delay=10.0,
            multiplier=2.0,
            max_delay=20.0,
            jitter=False,
        )
    )

    delays = [backoff.next_delay() for _ in range(3)]

    assert delays[0] == 10.0
    assert delays[1] == 20.0  # Would be 20, capped
    assert delays[2] == 20.0  # Would be 40, capped at 20


def test_exponential_backoff_with_jitter_adds_randomness():
    """Backoff with jitter should add randomness to delays."""
    backoff = ExponentialBackoff(
        BackoffConfig(
            initial_delay=10.0,
            multiplier=2.0,
            max_delay=100.0,
            jitter=True,
        )
    )

    delays = [backoff.next_delay() for _ in range(10)]

    # All delays should be between 0 and their expected value
    for i, delay in enumerate(delays):
        expected_max = min(10.0 * (2.0 ** i), 100.0)
        assert 0 <= delay <= expected_max


def test_exponential_backoff_reset():
    """Reset should clear attempt counter."""
    backoff = ExponentialBackoff(BackoffConfig(jitter=False))

    backoff.next_delay()
    backoff.next_delay()
    assert backoff.attempts == 2

    backoff.reset()
    assert backoff.attempts == 0

    # Next delay should be initial_delay again
    assert backoff.next_delay() == 1.0


def test_with_backoff_decorator_retries_on_failure():
    """Decorator should retry failed calls with exponential backoff."""
    calls = {"count": 0}

    @with_backoff(
        BackoffConfig(
            initial_delay=0.01,
            max_attempts=3,
            jitter=False,
        )
    )
    def flaky_function():
        calls["count"] += 1
        if calls["count"] < 3:
            raise ValueError("Not yet")
        return "success"

    start = time.time()
    result = flaky_function()
    elapsed = time.time() - start

    assert result == "success"
    assert calls["count"] == 3
    # Should have waited: 0.01 + 0.02 = 0.03 seconds
    assert elapsed >= 0.03


def test_with_backoff_decorator_raises_backoff_exhausted():
    """Decorator should raise BackoffExhausted when max_attempts reached."""
    calls = {"count": 0}

    @with_backoff(
        BackoffConfig(
            initial_delay=0.01,
            max_attempts=3,
            jitter=False,
        )
    )
    def always_fails():
        calls["count"] += 1
        raise ValueError("Always fails")

    with pytest.raises(BackoffExhausted) as exc_info:
        always_fails()

    assert calls["count"] == 3
    assert isinstance(exc_info.value.last_exception, ValueError)
    assert exc_info.value.attempts == 3


def test_with_backoff_decorator_success_on_first_try():
    """Decorator should not retry on immediate success."""
    calls = {"count": 0}

    @with_backoff(BackoffConfig(max_attempts=3))
    def immediate_success():
        calls["count"] += 1
        return "success"

    result = immediate_success()

    assert result == "success"
    assert calls["count"] == 1


def test_with_backoff_custom_retryable_exceptions():
    """Decorator should only retry specific exceptions."""
    calls = {"count": 0}

    @with_backoff(
        BackoffConfig(
            initial_delay=0.01,
            max_attempts=3,
            retryable_exceptions=(ValueError,),
        )
    )
    def raises_different_exceptions():
        calls["count"] += 1
        if calls["count"] == 1:
            raise ValueError("Retryable")
        raise TypeError("Not retryable")

    with pytest.raises(TypeError):
        raises_different_exceptions()

    assert calls["count"] == 2  # First ValueError retried, then TypeError raised


def test_with_backoff_on_retry_callback():
    """Decorator should call on_retry callback."""
    retry_info = []

    def on_retry_callback(exc, attempt, delay):
        retry_info.append({"attempt": attempt, "delay": delay, "error": str(exc)})

    calls = {"count": 0}

    @with_backoff(
        BackoffConfig(
            initial_delay=0.01,
            max_attempts=3,
            jitter=False,
            on_retry=on_retry_callback,
        )
    )
    def flaky_function():
        calls["count"] += 1
        if calls["count"] < 3:
            raise ValueError(f"Attempt {calls['count']}")
        return "success"

    result = flaky_function()

    assert result == "success"
    assert len(retry_info) == 2
    assert retry_info[0]["attempt"] == 1
    assert retry_info[0]["delay"] == 0.01
    assert retry_info[1]["attempt"] == 2
    assert retry_info[1]["delay"] == 0.02


def test_calculate_backoff_delay_function():
    """Calculate_backoff_delay should work as a standalone function."""
    # Test without jitter
    delay_0 = calculate_backoff_delay(0, initial_delay=1.0, multiplier=2.0, jitter=False)
    delay_1 = calculate_backoff_delay(1, initial_delay=1.0, multiplier=2.0, jitter=False)
    delay_2 = calculate_backoff_delay(2, initial_delay=1.0, multiplier=2.0, jitter=False)

    assert delay_0 == 1.0
    assert delay_1 == 2.0
    assert delay_2 == 4.0

    # Test max_delay
    delay_10 = calculate_backoff_delay(
        10, initial_delay=1.0, max_delay=10.0, multiplier=2.0, jitter=False
    )
    assert delay_10 == 10.0


def test_calculate_backoff_delay_with_jitter():
    """Calculate_backoff_delay with jitter should add randomness."""
    delays = [
        calculate_backoff_delay(2, initial_delay=1.0, multiplier=2.0, jitter=True)
        for _ in range(20)
    ]

    # All should be between 0 and 4.0
    for delay in delays:
        assert 0 <= delay <= 4.0

    # Should have some variety (very unlikely all are the same)
    assert len(set(delays)) > 1

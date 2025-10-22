"""Circuit breaker pattern for resilient external service calls."""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Optional, TypeVar, List

from functools import wraps


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failures exceeded, requests blocked
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker behavior."""

    # Failure threshold to open circuit
    failure_threshold: int = 5

    # Success threshold to close circuit from half-open
    success_threshold: int = 2

    # Time window for counting failures (seconds)
    failure_window_seconds: float = 60.0

    # Timeout before attempting recovery (seconds)
    timeout_seconds: float = 30.0

    # Expected exceptions to count as failures
    expected_exceptions: tuple = (Exception,)

    # Alert hooks for state transitions
    on_open: Optional[Callable[[str], None]] = None
    on_half_open: Optional[Callable[[str], None]] = None
    on_close: Optional[Callable[[str], None]] = None


class CircuitBreakerError(Exception):
    """Raised when circuit breaker is open."""
    pass


class CircuitBreaker:
    """Circuit breaker for protecting against cascading failures."""

    def __init__(
        self,
        name: str,
        config: Optional[CircuitBreakerConfig] = None,
    ) -> None:
        """Initialize circuit breaker.

        Args:
            name: Name identifier for this circuit breaker
            config: Configuration parameters
        """
        self.name = name
        self.config = config or CircuitBreakerConfig()

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: Optional[float] = None
        self._opened_at: Optional[float] = None
        self._failure_times: list[float] = []

    @property
    def state(self) -> CircuitState:
        """Get current circuit state."""
        return self._state

    @property
    def is_closed(self) -> bool:
        """Check if circuit is closed (normal operation)."""
        return self._state == CircuitState.CLOSED

    @property
    def is_open(self) -> bool:
        """Check if circuit is open (blocking requests)."""
        return self._state == CircuitState.OPEN

    @property
    def is_half_open(self) -> bool:
        """Check if circuit is half-open (testing recovery)."""
        return self._state == CircuitState.HALF_OPEN

    def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function through circuit breaker.

        Args:
            func: Function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments

        Returns:
            Function result

        Raises:
            CircuitBreakerError: If circuit is open
        """
        # Check if circuit should transition to half-open
        if self.is_open and self._should_attempt_reset():
            self._transition_to_half_open()

        # Block requests if circuit is open
        if self.is_open:
            raise CircuitBreakerError(
                f"Circuit breaker '{self.name}' is OPEN. "
                f"Service unavailable since {self._opened_at}"
            )

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result

        except self.config.expected_exceptions as exc:
            self._on_failure()
            raise exc

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset."""
        if not self._opened_at:
            return False

        elapsed = time.time() - self._opened_at
        return elapsed >= self.config.timeout_seconds

    def _transition_to_half_open(self) -> None:
        """Transition from OPEN to HALF_OPEN state."""
        self._state = CircuitState.HALF_OPEN
        self._success_count = 0
        print(f"Circuit breaker '{self.name}' transitioned to HALF_OPEN")
        
        # Call alert hook if configured
        if self.config.on_half_open:
            try:
                self.config.on_half_open(self.name)
            except Exception as e:
                print(f"Error calling on_half_open hook for '{self.name}': {e}")

    def _on_success(self) -> None:
        """Handle successful call."""
        current_time = time.time()

        if self.is_half_open:
            self._success_count += 1

            if self._success_count >= self.config.success_threshold:
                self._transition_to_closed()
        elif self.is_closed:
            # Remove old failures outside window
            self._clean_old_failures(current_time)

    def _on_failure(self) -> None:
        """Handle failed call."""
        current_time = time.time()
        self._last_failure_time = current_time
        self._failure_times.append(current_time)

        # Clean old failures
        self._clean_old_failures(current_time)

        if self.is_half_open:
            # Failure during recovery -> back to OPEN
            self._transition_to_open(current_time)
        elif self.is_closed:
            # Count recent failures
            self._failure_count = len(self._failure_times)

            if self._failure_count >= self.config.failure_threshold:
                self._transition_to_open(current_time)

    def _clean_old_failures(self, current_time: float) -> None:
        """Remove failures outside the time window."""
        cutoff = current_time - self.config.failure_window_seconds
        self._failure_times = [t for t in self._failure_times if t > cutoff]
        self._failure_count = len(self._failure_times)

    def _transition_to_open(self, current_time: float) -> None:
        """Transition to OPEN state."""
        self._state = CircuitState.OPEN
        self._opened_at = current_time
        print(
            f"Circuit breaker '{self.name}' OPENED after {self._failure_count} failures"
        )
        
        # Call alert hook if configured
        if self.config.on_open:
            try:
                self.config.on_open(self.name)
            except Exception as e:
                print(f"Error calling on_open hook for '{self.name}': {e}")

    def _transition_to_closed(self) -> None:
        """Transition to CLOSED state."""
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._failure_times.clear()
        self._opened_at = None
        print(f"Circuit breaker '{self.name}' CLOSED - service recovered")
        
        # Call alert hook if configured
        if self.config.on_close:
            try:
                self.config.on_close(self.name)
            except Exception as e:
                print(f"Error calling on_close hook for '{self.name}': {e}")

    def reset(self) -> None:
        """Manually reset circuit breaker to CLOSED state."""
        self._transition_to_closed()

    def get_stats(self) -> dict[str, Any]:
        """Get circuit breaker statistics.

        Returns:
            Dictionary with current stats
        """
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self._failure_count,
            "success_count": self._success_count,
            "last_failure_time": (
                datetime.fromtimestamp(self._last_failure_time).isoformat()
                if self._last_failure_time
                else None
            ),
            "opened_at": (
                datetime.fromtimestamp(self._opened_at).isoformat()
                if self._opened_at
                else None
            ),
        }


class CircuitBreakerRegistry:
    """Registry for managing multiple circuit breakers."""

    def __init__(self) -> None:
        """Initialize circuit breaker registry."""
        self._breakers: dict[str, CircuitBreaker] = {}

    def get_or_create(
        self,
        name: str,
        config: Optional[CircuitBreakerConfig] = None,
    ) -> CircuitBreaker:
        """Get existing circuit breaker or create new one.

        Args:
            name: Circuit breaker name
            config: Configuration (only used when creating)

        Returns:
            Circuit breaker instance
        """
        if name not in self._breakers:
            self._breakers[name] = CircuitBreaker(name, config)
        return self._breakers[name]

    def get(self, name: str) -> Optional[CircuitBreaker]:
        """Get circuit breaker by name.

        Args:
            name: Circuit breaker name

        Returns:
            Circuit breaker or None if not found
        """
        return self._breakers.get(name)

    def get_all(self) -> dict[str, CircuitBreaker]:
        """Return mapping of registered circuit breakers."""

        return self._breakers

    def get_all_stats(self) -> list[dict[str, Any]]:
        """Get stats for all circuit breakers.

        Returns:
            List of stats dictionaries
        """
        return [breaker.get_stats() for breaker in self._breakers.values()]

    def reset_all(self) -> None:
        """Reset all circuit breakers."""
        for breaker in self._breakers.values():
            breaker.reset()


# Global registry
_global_breaker_registry = CircuitBreakerRegistry()


def get_circuit_breaker_registry() -> CircuitBreakerRegistry:
    """Get global circuit breaker registry.

    Returns:
        Global registry instance
    """
    return _global_breaker_registry


T = TypeVar("T")


def with_circuit_breaker(
    name: str,
    config: Optional[CircuitBreakerConfig] = None,
    registry: Optional[CircuitBreakerRegistry] = None,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator to protect function with circuit breaker.

    Args:
        name: Circuit breaker name
        config: Configuration parameters
        registry: Registry to use (global if not provided)

    Returns:
        Decorated function

    Example:
        @with_circuit_breaker("api_calls", CircuitBreakerConfig(failure_threshold=3))
        def fetch_data():
            return requests.get("https://api.example.com/data")
    """
    reg = registry or get_circuit_breaker_registry()
    breaker = reg.get_or_create(name, config)

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            return breaker.call(func, *args, **kwargs)

        return wrapper

    return decorator


def graceful_degradation(
    fallback_value: Any = None,
    fallback_func: Optional[Callable] = None,
    log_errors: bool = True,
) -> Callable:
    """Decorator for graceful degradation on failures.

    Args:
        fallback_value: Value to return on failure
        fallback_func: Function to call on failure (takes exception as arg)
        log_errors: Whether to log errors

    Returns:
        Decorated function

    Example:
        @graceful_degradation(fallback_value=[])
        def fetch_items():
            return api.get_items()  # Returns [] if fails
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            try:
                return func(*args, **kwargs)
            except Exception as exc:
                if log_errors:
                    print(f"Error in {func.__name__}: {exc}. Using fallback.")

                if fallback_func:
                    return fallback_func(exc)

                return fallback_value

        return wrapper

    return decorator

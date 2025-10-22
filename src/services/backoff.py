"""Unified exponential backoff strategy for resilient retries."""

from __future__ import annotations

import random
import time
from dataclasses import dataclass
from functools import wraps
from typing import Any, Callable, Optional, TypeVar

T = TypeVar("T")


@dataclass
class BackoffConfig:
    """Configuration for exponential backoff behavior."""

    # Initial delay in seconds
    initial_delay: float = 1.0

    # Maximum delay in seconds
    max_delay: float = 60.0

    # Multiplier for each retry (exponential factor)
    multiplier: float = 2.0

    # Maximum number of retry attempts
    max_attempts: int = 5

    # Whether to add jitter to prevent thundering herd
    jitter: bool = True

    # Exceptions to retry on (default: all exceptions)
    retryable_exceptions: tuple[type[Exception], ...] = (Exception,)

    # Optional callback on retry
    on_retry: Optional[Callable[[Exception, int, float], None]] = None


class BackoffExhausted(Exception):
    """Raised when all retry attempts have been exhausted."""

    def __init__(self, last_exception: Exception, attempts: int) -> None:
        """Initialize with the last exception and number of attempts."""
        self.last_exception = last_exception
        self.attempts = attempts
        super().__init__(
            f"Backoff exhausted after {attempts} attempts. "
            f"Last error: {last_exception}"
        )


class ExponentialBackoff:
    """Exponential backoff strategy with jitter."""

    def __init__(self, config: Optional[BackoffConfig] = None) -> None:
        """Initialize exponential backoff.

        Args:
            config: Configuration parameters
        """
        self.config = config or BackoffConfig()
        self._attempt = 0

    def next_delay(self) -> float:
        """Calculate next delay duration.

        Returns:
            Delay in seconds before next retry
        """
        # Calculate exponential delay
        delay = min(
            self.config.initial_delay * (self.config.multiplier ** self._attempt),
            self.config.max_delay,
        )

        # Add jitter if enabled (uniform random between 0 and delay)
        if self.config.jitter:
            delay = random.uniform(0, delay)

        self._attempt += 1
        return delay

    def reset(self) -> None:
        """Reset attempt counter."""
        self._attempt = 0

    @property
    def attempts(self) -> int:
        """Get current attempt count."""
        return self._attempt

    def should_retry(self, exception: Exception) -> bool:
        """Check if exception is retryable.

        Args:
            exception: Exception to check

        Returns:
            True if should retry, False otherwise
        """
        return isinstance(exception, self.config.retryable_exceptions)


def with_backoff(
    config: Optional[BackoffConfig] = None,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator to retry function with exponential backoff.

    Args:
        config: Backoff configuration

    Returns:
        Decorated function

    Example:
        @with_backoff(BackoffConfig(max_attempts=3, initial_delay=0.5))
        def fetch_data():
            return requests.get("https://api.example.com/data")
    """
    cfg = config or BackoffConfig()

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            backoff = ExponentialBackoff(cfg)
            last_exception: Optional[Exception] = None

            for attempt in range(cfg.max_attempts):
                try:
                    result = func(*args, **kwargs)
                    # Reset on success for next call
                    backoff.reset()
                    return result

                except cfg.retryable_exceptions as exc:
                    last_exception = exc

                    # Check if we should retry
                    if not backoff.should_retry(exc):
                        raise

                    # Last attempt - don't wait
                    if attempt == cfg.max_attempts - 1:
                        break

                    # Calculate delay and wait
                    delay = backoff.next_delay()

                    # Call retry callback if provided
                    if cfg.on_retry:
                        cfg.on_retry(exc, attempt + 1, delay)

                    time.sleep(delay)

            # All retries exhausted
            raise BackoffExhausted(last_exception, cfg.max_attempts)  # type: ignore

        return wrapper

    return decorator


async def async_with_backoff(
    config: Optional[BackoffConfig] = None,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator to retry async function with exponential backoff.

    Args:
        config: Backoff configuration

    Returns:
        Decorated async function

    Example:
        @async_with_backoff(BackoffConfig(max_attempts=3))
        async def fetch_data():
            return await aiohttp.get("https://api.example.com/data")
    """
    cfg = config or BackoffConfig()

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            import asyncio

            backoff = ExponentialBackoff(cfg)
            last_exception: Optional[Exception] = None

            for attempt in range(cfg.max_attempts):
                try:
                    result = await func(*args, **kwargs)
                    backoff.reset()
                    return result

                except cfg.retryable_exceptions as exc:
                    last_exception = exc

                    if not backoff.should_retry(exc):
                        raise

                    if attempt == cfg.max_attempts - 1:
                        break

                    delay = backoff.next_delay()

                    if cfg.on_retry:
                        cfg.on_retry(exc, attempt + 1, delay)

                    await asyncio.sleep(delay)

            raise BackoffExhausted(last_exception, cfg.max_attempts)  # type: ignore

        return wrapper

    return decorator


def calculate_backoff_delay(
    attempt: int,
    initial_delay: float = 1.0,
    max_delay: float = 60.0,
    multiplier: float = 2.0,
    jitter: bool = True,
) -> float:
    """Calculate backoff delay for a given attempt.

    Args:
        attempt: Attempt number (0-indexed)
        initial_delay: Initial delay in seconds
        max_delay: Maximum delay in seconds
        multiplier: Exponential multiplier
        jitter: Whether to add random jitter

    Returns:
        Delay in seconds
    """
    delay = min(initial_delay * (multiplier ** attempt), max_delay)

    if jitter:
        delay = random.uniform(0, delay)

    return delay


__all__ = [
    "BackoffConfig",
    "BackoffExhausted",
    "ExponentialBackoff",
    "with_backoff",
    "async_with_backoff",
    "calculate_backoff_delay",
]

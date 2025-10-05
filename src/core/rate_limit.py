"""Rate limiting primitives shared by ingestion clients."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from threading import Lock
from time import monotonic
from typing import Deque


@dataclass(frozen=True)
class RateLimit:
    """Simple token bucket style limit."""

    max_requests: int
    window_seconds: float

    def __post_init__(self) -> None:
        if self.max_requests <= 0:
            raise ValueError("max_requests must be positive")
        if self.window_seconds <= 0:
            raise ValueError("window_seconds must be positive")


class RateLimiter:
    """Thread-safe sliding window rate limiter."""

    def __init__(self, limit: RateLimit) -> None:
        self._limit = limit
        self._lock = Lock()
        self._timestamps: Deque[float] = deque()

    def acquire(self) -> float:
        """Reserve a slot and return required sleep duration in seconds."""

        with self._lock:
            now = monotonic()
            self._prune(now)
            if len(self._timestamps) < self._limit.max_requests:
                self._timestamps.append(now)
                return 0.0

            earliest = self._timestamps[0]
            wait_until = earliest + self._limit.window_seconds
            wait = max(wait_until - now, 0.0)
            scheduled = wait_until if wait_until > now else now
            self._timestamps.append(scheduled)
            self._timestamps.popleft()
            return wait

    def _prune(self, current: float) -> None:
        window_start = current - self._limit.window_seconds
        while self._timestamps and self._timestamps[0] <= window_start:
            self._timestamps.popleft()


__all__ = ["RateLimit", "RateLimiter"]

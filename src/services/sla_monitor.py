"""SLA monitoring and metrics collection for data ingestion pipelines."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from collections import deque


class SLAStatus(Enum):
    """SLA compliance status."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILED = "failed"
    UNKNOWN = "unknown"


@dataclass
class SLAMetrics:
    """SLA metrics for a data source."""

    source_name: str
    timestamp: datetime

    # Latency metrics (milliseconds)
    latency_p50: float = 0.0
    latency_p95: float = 0.0
    latency_p99: float = 0.0
    avg_latency: float = 0.0

    # Success rate
    success_rate: float = 1.0
    total_requests: int = 0
    failed_requests: int = 0

    # Availability
    uptime_percentage: float = 100.0
    consecutive_failures: int = 0

    # Data quality
    data_completeness: float = 1.0
    data_freshness_seconds: float = 0.0

    # Status
    status: SLAStatus = SLAStatus.HEALTHY
    status_message: str = ""


@dataclass
class SLAThresholds:
    """SLA thresholds for alerting."""

    # Latency thresholds (milliseconds)
    max_latency_p95: float = 2000.0
    max_latency_p99: float = 5000.0

    # Success rate threshold
    min_success_rate: float = 0.95

    # Availability threshold
    min_uptime_percentage: float = 99.0
    max_consecutive_failures: int = 3

    # Data quality thresholds
    min_data_completeness: float = 0.8
    max_data_freshness_seconds: float = 300.0


class SLAMonitor:
    """Monitors SLA compliance for data sources."""

    def __init__(
        self,
        source_name: str,
        thresholds: Optional[SLAThresholds] = None,
        window_size: int = 100,
    ) -> None:
        """Initialize SLA monitor.

        Args:
            source_name: Name of the data source
            thresholds: SLA thresholds for alerting
            window_size: Number of recent requests to track
        """
        self.source_name = source_name
        self.thresholds = thresholds or SLAThresholds()
        self.window_size = window_size

        # Rolling window of latencies (milliseconds)
        self._latencies: deque[float] = deque(maxlen=window_size)

        # Rolling window of success/failure
        self._successes: deque[bool] = deque(maxlen=window_size)

        # Failure tracking
        self._consecutive_failures = 0
        self._last_success_time: Optional[datetime] = None
        self._last_failure_time: Optional[datetime] = None

        # Total counters
        self._total_requests = 0
        self._total_failures = 0
        self._total_uptime_seconds = 0.0
        self._total_downtime_seconds = 0.0
        self._start_time = datetime.utcnow()

    def record_request(
        self,
        latency_ms: float,
        success: bool,
        data_completeness: float = 1.0,
    ) -> None:
        """Record a request and update metrics.

        Args:
            latency_ms: Request latency in milliseconds
            success: Whether the request succeeded
            data_completeness: Data completeness score (0-1)
        """
        now = datetime.utcnow()

        self._latencies.append(latency_ms)
        self._successes.append(success)
        self._total_requests += 1

        if success:
            self._consecutive_failures = 0
            self._last_success_time = now

            # Update uptime
            if self._last_failure_time:
                downtime = (now - self._last_failure_time).total_seconds()
                self._total_downtime_seconds += downtime
                self._last_failure_time = None
        else:
            self._consecutive_failures += 1
            self._total_failures += 1
            self._last_failure_time = now

    def get_metrics(self) -> SLAMetrics:
        """Get current SLA metrics.

        Returns:
            SLAMetrics with current state
        """
        now = datetime.utcnow()

        # Calculate latency percentiles
        latencies_sorted = sorted(self._latencies)
        n = len(latencies_sorted)

        if n > 0:
            p50_idx = int(n * 0.50)
            p95_idx = int(n * 0.95)
            p99_idx = int(n * 0.99)

            latency_p50 = latencies_sorted[p50_idx] if p50_idx < n else 0.0
            latency_p95 = latencies_sorted[p95_idx] if p95_idx < n else 0.0
            latency_p99 = latencies_sorted[p99_idx] if p99_idx < n else 0.0
            avg_latency = sum(latencies_sorted) / n
        else:
            latency_p50 = latency_p95 = latency_p99 = avg_latency = 0.0

        # Calculate success rate
        if self._total_requests > 0:
            success_rate = 1.0 - (self._total_failures / self._total_requests)
        else:
            success_rate = 1.0

        # Calculate uptime
        total_time = (now - self._start_time).total_seconds()
        if total_time > 0:
            uptime_percentage = (
                (total_time - self._total_downtime_seconds) / total_time * 100
            )
        else:
            uptime_percentage = 100.0

        # Calculate data freshness
        if self._last_success_time:
            freshness_seconds = (now - self._last_success_time).total_seconds()
        else:
            freshness_seconds = total_time

        # Determine status
        status, message = self._determine_status(
            latency_p95,
            latency_p99,
            success_rate,
            uptime_percentage,
            self._consecutive_failures,
            freshness_seconds,
        )

        return SLAMetrics(
            source_name=self.source_name,
            timestamp=now,
            latency_p50=latency_p50,
            latency_p95=latency_p95,
            latency_p99=latency_p99,
            avg_latency=avg_latency,
            success_rate=success_rate,
            total_requests=self._total_requests,
            failed_requests=self._total_failures,
            uptime_percentage=uptime_percentage,
            consecutive_failures=self._consecutive_failures,
            data_freshness_seconds=freshness_seconds,
            status=status,
            status_message=message,
        )

    def _determine_status(
        self,
        latency_p95: float,
        latency_p99: float,
        success_rate: float,
        uptime_percentage: float,
        consecutive_failures: int,
        freshness_seconds: float,
    ) -> tuple[SLAStatus, str]:
        """Determine SLA status based on metrics.

        Returns:
            Tuple of (status, message)
        """
        issues: List[str] = []

        # Check latency
        if latency_p99 > self.thresholds.max_latency_p99:
            issues.append(f"P99 latency {latency_p99:.0f}ms exceeds {self.thresholds.max_latency_p99:.0f}ms")
        elif latency_p95 > self.thresholds.max_latency_p95:
            issues.append(f"P95 latency {latency_p95:.0f}ms exceeds {self.thresholds.max_latency_p95:.0f}ms")

        # Check success rate
        if success_rate < self.thresholds.min_success_rate:
            issues.append(f"Success rate {success_rate:.2%} below {self.thresholds.min_success_rate:.2%}")

        # Check consecutive failures
        if consecutive_failures >= self.thresholds.max_consecutive_failures:
            issues.append(f"{consecutive_failures} consecutive failures")

        # Check uptime
        if uptime_percentage < self.thresholds.min_uptime_percentage:
            issues.append(f"Uptime {uptime_percentage:.2f}% below {self.thresholds.min_uptime_percentage:.2f}%")

        # Check freshness
        if freshness_seconds > self.thresholds.max_data_freshness_seconds:
            issues.append(f"Data stale for {freshness_seconds:.0f}s")

        # Determine overall status
        if not issues:
            return SLAStatus.HEALTHY, "All metrics within SLA"

        if consecutive_failures >= self.thresholds.max_consecutive_failures:
            return SLAStatus.FAILED, "; ".join(issues)

        if success_rate < self.thresholds.min_success_rate:
            return SLAStatus.DEGRADED, "; ".join(issues)

        return SLAStatus.DEGRADED, "; ".join(issues)

    def reset(self) -> None:
        """Reset all metrics."""
        self._latencies.clear()
        self._successes.clear()
        self._consecutive_failures = 0
        self._last_success_time = None
        self._last_failure_time = None
        self._total_requests = 0
        self._total_failures = 0
        self._total_uptime_seconds = 0.0
        self._total_downtime_seconds = 0.0
        self._start_time = datetime.utcnow()


class SLARegistry:
    """Registry for managing multiple SLA monitors."""

    def __init__(self) -> None:
        """Initialize SLA registry."""
        self._monitors: Dict[str, SLAMonitor] = {}

    def register(
        self,
        source_name: str,
        thresholds: Optional[SLAThresholds] = None,
        window_size: int = 100,
    ) -> SLAMonitor:
        """Register a new SLA monitor.

        Args:
            source_name: Name of the data source
            thresholds: SLA thresholds
            window_size: Rolling window size

        Returns:
            Created SLA monitor
        """
        monitor = SLAMonitor(source_name, thresholds, window_size)
        self._monitors[source_name] = monitor
        return monitor

    def get_monitor(self, source_name: str) -> Optional[SLAMonitor]:
        """Get monitor by source name.

        Args:
            source_name: Name of the data source

        Returns:
            SLA monitor or None if not found
        """
        return self._monitors.get(source_name)

    def get_all_metrics(self) -> List[SLAMetrics]:
        """Get metrics for all registered monitors.

        Returns:
            List of SLA metrics
        """
        return [monitor.get_metrics() for monitor in self._monitors.values()]

    def get_unhealthy_sources(self) -> List[SLAMetrics]:
        """Get metrics for sources not in healthy state.

        Returns:
            List of metrics for degraded/failed sources
        """
        metrics = self.get_all_metrics()
        return [m for m in metrics if m.status != SLAStatus.HEALTHY]


# Global registry instance
_global_registry = SLARegistry()


def get_sla_registry() -> SLARegistry:
    """Get the global SLA registry.

    Returns:
        Global SLA registry instance
    """
    return _global_registry


def monitored(
    source_name: str,
    registry: Optional[SLARegistry] = None,
) -> Callable:
    """Decorator to monitor function execution with SLA tracking.

    Args:
        source_name: Name of the data source
        registry: Optional SLA registry (uses global if not provided)

    Returns:
        Decorated function
    """
    reg = registry or get_sla_registry()

    def decorator(func: Callable) -> Callable:
        def wrapper(*args, **kwargs) -> Any:
            monitor = reg.get_monitor(source_name)
            if not monitor:
                monitor = reg.register(source_name)

            start_time = time.perf_counter()
            success = False
            result = None

            try:
                result = func(*args, **kwargs)
                success = True
                return result
            finally:
                end_time = time.perf_counter()
                latency_ms = (end_time - start_time) * 1000

                # Estimate data completeness (1.0 if successful, 0.0 if failed)
                completeness = 1.0 if success else 0.0

                monitor.record_request(latency_ms, success, completeness)

        return wrapper

    return decorator

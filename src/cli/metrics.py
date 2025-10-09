"""Metrics and telemetry emission for CLI operations.

Supports:
- Stdout JSON lines (--emit-metrics stdout)
- StatsD protocol (--emit-metrics statsd)
- Custom handlers via registry
"""

from __future__ import annotations

import json
import logging
import socket
import sys
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Iterator

logger = logging.getLogger(__name__)


class MetricType(Enum):
    """Type of metric being emitted."""
    COUNTER = "counter"
    GAUGE = "gauge"
    TIMER = "timer"
    HISTOGRAM = "histogram"


@dataclass
class Metric:
    """Represents a single metric observation."""
    name: str
    value: float
    type: MetricType
    timestamp: float
    tags: dict[str, str] | None = None
    unit: str | None = None

    def to_json(self) -> str:
        """Serialize metric to JSON line format."""
        data = {
            "name": self.name,
            "value": self.value,
            "type": self.type.value,
            "timestamp": self.timestamp,
        }
        if self.tags:
            data["tags"] = self.tags
        if self.unit:
            data["unit"] = self.unit
        return json.dumps(data)

    def to_statsd(self, prefix: str = "autotrader") -> str:
        """Format metric for StatsD protocol.
        
        Format: prefix.name:value|type[|@sample_rate][#tag1:val1,tag2:val2]
        """
        full_name = f"{prefix}.{self.name}"
        
        # Map metric types to StatsD types
        type_map = {
            MetricType.COUNTER: "c",
            MetricType.GAUGE: "g",
            MetricType.TIMER: "ms",
            MetricType.HISTOGRAM: "h",
        }
        statsd_type = type_map.get(self.type, "g")
        
        metric_str = f"{full_name}:{self.value}|{statsd_type}"
        
        # Add tags (DogStatsD format)
        if self.tags:
            tag_str = ",".join(f"{k}:{v}" for k, v in self.tags.items())
            metric_str += f"|#{tag_str}"
        
        return metric_str


class MetricsEmitter:
    """Base class for metrics emission."""
    
    def emit(self, metric: Metric) -> None:
        """Emit a single metric."""
        raise NotImplementedError
    
    def close(self) -> None:
        """Clean up resources."""
        pass


class StdoutEmitter(MetricsEmitter):
    """Emit metrics as JSON lines to stdout."""
    
    def emit(self, metric: Metric) -> None:
        """Write metric as JSON line to stdout."""
        try:
            print(metric.to_json(), file=sys.stdout, flush=True)
        except Exception as e:
            logger.warning(f"Failed to emit metric to stdout: {e}")


class StatsDEmitter(MetricsEmitter):
    """Emit metrics via StatsD UDP protocol."""
    
    def __init__(
        self,
        host: str = "localhost",
        port: int = 8125,
        prefix: str = "autotrader",
    ):
        """Initialize StatsD emitter.
        
        Args:
            host: StatsD server hostname
            port: StatsD server port
            prefix: Metric name prefix
        """
        self.host = host
        self.port = port
        self.prefix = prefix
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        logger.info(f"✅ StatsD emitter initialized: {host}:{port}")
    
    def emit(self, metric: Metric) -> None:
        """Send metric via UDP to StatsD server."""
        try:
            message = metric.to_statsd(self.prefix)
            self.socket.sendto(message.encode('utf-8'), (self.host, self.port))
        except Exception as e:
            logger.warning(f"Failed to emit metric to StatsD: {e}")
    
    def close(self) -> None:
        """Close UDP socket."""
        try:
            self.socket.close()
        except Exception as e:
            logger.warning(f"Failed to close StatsD socket: {e}")


class NullEmitter(MetricsEmitter):
    """No-op emitter when metrics are disabled."""
    
    def emit(self, metric: Metric) -> None:
        """Do nothing."""
        pass


class MetricsCollector:
    """Central metrics collection and emission coordinator."""
    
    def __init__(self, emitter: MetricsEmitter | None = None):
        """Initialize metrics collector.
        
        Args:
            emitter: Metrics emitter (defaults to NullEmitter)
        """
        self.emitter = emitter or NullEmitter()
        self._counters: dict[str, float] = {}
        self._gauges: dict[str, float] = {}
    
    def counter(
        self,
        name: str,
        value: float = 1.0,
        tags: dict[str, str] | None = None,
    ) -> None:
        """Increment a counter metric.
        
        Args:
            name: Metric name
            value: Amount to increment (default: 1.0)
            tags: Optional tags/labels
        """
        self._counters[name] = self._counters.get(name, 0) + value
        
        metric = Metric(
            name=name,
            value=value,
            type=MetricType.COUNTER,
            timestamp=time.time(),
            tags=tags,
        )
        self.emitter.emit(metric)
    
    def gauge(
        self,
        name: str,
        value: float,
        tags: dict[str, str] | None = None,
        unit: str | None = None,
    ) -> None:
        """Set a gauge metric.
        
        Args:
            name: Metric name
            value: Gauge value
            tags: Optional tags/labels
            unit: Optional unit (e.g., 'seconds', 'bytes')
        """
        self._gauges[name] = value
        
        metric = Metric(
            name=name,
            value=value,
            type=MetricType.GAUGE,
            timestamp=time.time(),
            tags=tags,
            unit=unit,
        )
        self.emitter.emit(metric)
    
    def timer(
        self,
        name: str,
        value: float,
        tags: dict[str, str] | None = None,
    ) -> None:
        """Record a timer metric (duration in seconds).
        
        Args:
            name: Metric name
            value: Duration in seconds
            tags: Optional tags/labels
        """
        metric = Metric(
            name=name,
            value=value * 1000,  # Convert to milliseconds
            type=MetricType.TIMER,
            timestamp=time.time(),
            tags=tags,
            unit="ms",
        )
        self.emitter.emit(metric)
    
    @contextmanager
    def timed(
        self,
        name: str,
        tags: dict[str, str] | None = None,
    ) -> Iterator[None]:
        """Context manager for timing operations.
        
        Args:
            name: Metric name
            tags: Optional tags/labels
            
        Example:
            with collector.timed("scan_duration"):
                run_scan()
        """
        start = time.time()
        try:
            yield
        finally:
            duration = time.time() - start
            self.timer(name, duration, tags)
    
    def histogram(
        self,
        name: str,
        value: float,
        tags: dict[str, str] | None = None,
        unit: str | None = None,
    ) -> None:
        """Record a histogram metric.
        
        Args:
            name: Metric name
            value: Observed value
            tags: Optional tags/labels
            unit: Optional unit
        """
        metric = Metric(
            name=name,
            value=value,
            type=MetricType.HISTOGRAM,
            timestamp=time.time(),
            tags=tags,
            unit=unit,
        )
        self.emitter.emit(metric)
    
    def get_summary(self) -> dict[str, Any]:
        """Get summary of collected metrics.
        
        Returns:
            Dictionary with counters and gauges
        """
        return {
            "counters": self._counters.copy(),
            "gauges": self._gauges.copy(),
        }
    
    def close(self) -> None:
        """Clean up emitter resources."""
        self.emitter.close()


def create_emitter(
    emit_type: str | None,
    statsd_host: str = "localhost",
    statsd_port: int = 8125,
    statsd_prefix: str = "autotrader",
) -> MetricsEmitter:
    """Factory function to create appropriate emitter.
    
    Args:
        emit_type: Type of emitter ('stdout', 'statsd', or None)
        statsd_host: StatsD server hostname
        statsd_port: StatsD server port
        statsd_prefix: Metric name prefix for StatsD
        
    Returns:
        Configured MetricsEmitter instance
        
    Raises:
        ValueError: If emit_type is invalid
    """
    if emit_type is None or emit_type.lower() == "none":
        return NullEmitter()
    
    if emit_type.lower() == "stdout":
        logger.info("✅ Metrics emitter: stdout (JSON lines)")
        return StdoutEmitter()
    
    if emit_type.lower() == "statsd":
        logger.info(f"✅ Metrics emitter: StatsD ({statsd_host}:{statsd_port})")
        return StatsDEmitter(host=statsd_host, port=statsd_port, prefix=statsd_prefix)
    
    raise ValueError(f"Unknown emit type: {emit_type}. Use 'stdout', 'statsd', or None")


# Global collector instance (lazy initialization)
_global_collector: MetricsCollector | None = None


def get_collector() -> MetricsCollector:
    """Get or create global metrics collector.
    
    Returns:
        Global MetricsCollector instance
    """
    global _global_collector
    if _global_collector is None:
        _global_collector = MetricsCollector()
    return _global_collector


def initialize_metrics(
    emit_type: str | None,
    **kwargs: Any,
) -> MetricsCollector:
    """Initialize global metrics collector.
    
    Args:
        emit_type: Type of emitter ('stdout', 'statsd', or None)
        **kwargs: Additional arguments for emitter
        
    Returns:
        Configured MetricsCollector instance
    """
    global _global_collector
    
    emitter = create_emitter(emit_type, **kwargs)
    _global_collector = MetricsCollector(emitter)
    
    logger.info("✅ Metrics collector initialized")
    return _global_collector


def shutdown_metrics() -> None:
    """Shutdown global metrics collector and clean up resources."""
    global _global_collector
    
    if _global_collector:
        _global_collector.close()
        _global_collector = None
        logger.info("✅ Metrics collector shutdown complete")

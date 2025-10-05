"""Alerting utilities for Autotrader monitoring workflows."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Callable, Dict, Iterable, List, Mapping, MutableSequence, Sequence


AlertSeverity = str


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class Alert:
    """Concrete alert emitted by :class:`AlertManager`."""

    rule: str
    event: str
    severity: AlertSeverity
    message: str
    triggered_at: datetime
    metrics: Mapping[str, float] = field(default_factory=dict)
    tags: Sequence[str] = field(default_factory=tuple)


class NotificationChannel:
    """Base class for alert notification transports."""

    def __init__(self, name: str) -> None:
        self.name = name

    def notify(self, alert: Alert) -> None:  # pragma: no cover - interface hook
        raise NotImplementedError


class MemoryChannel(NotificationChannel):
    """In-memory channel used for tests and local development."""

    def __init__(self, name: str = "memory") -> None:
        super().__init__(name)
        self.alerts: MutableSequence[Alert] = []

    def notify(self, alert: Alert) -> None:
        self.alerts.append(alert)


class AlertRule:
    """Simple predicate-based alert rule."""

    def __init__(
        self,
        name: str,
        *,
        condition: Callable[[Mapping[str, float]], bool],
        severity: AlertSeverity = "warning",
        message: str | None = None,
        description: str = "",
        tags: Sequence[str] | None = None,
    ) -> None:
        self.name = name
        self.condition = condition
        self.severity = severity
        self.message = message or f"Alert rule '{name}' triggered"
        self.description = description
        self.tags = tuple(tags or ())

    def evaluate(self, event: str, metrics: Mapping[str, float], *, now: datetime | None = None) -> Alert | None:
        if not self.condition(metrics):
            return None
        return Alert(
            rule=self.name,
            event=event,
            severity=self.severity,
            message=self.message,
            triggered_at=now or _utcnow(),
            metrics=dict(metrics),
            tags=self.tags,
        )


class AlertManager:
    """Evaluates metrics against alert rules and emits notifications."""

    def __init__(
        self,
        *,
        rules: Iterable[AlertRule] | None = None,
        channels: Iterable[NotificationChannel] | None = None,
        dedup_ttl: timedelta = timedelta(minutes=5),
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._rules: List[AlertRule] = list(rules or [])
        self._channels: List[NotificationChannel] = list(channels or [])
        self._dedup_ttl = dedup_ttl
        self._clock = clock or _utcnow
        self._history: List[Alert] = []
        self._last_triggered: Dict[tuple[str, str], datetime] = {}

    def add_rule(self, rule: AlertRule) -> None:
        self._rules.append(rule)

    def add_channel(self, channel: NotificationChannel) -> None:
        self._channels.append(channel)

    def history(self, *, limit: int | None = None) -> List[Alert]:
        if limit is None:
            return list(self._history)
        return list(self._history[-limit:])

    def process_event(self, event: str, metrics: Mapping[str, float]) -> List[Alert]:
        now = self._clock()
        emitted: List[Alert] = []
        for rule in self._rules:
            alert = rule.evaluate(event, metrics, now=now)
            if alert is None:
                continue
            dedup_key = (rule.name, alert.severity)
            last = self._last_triggered.get(dedup_key)
            if last and now - last < self._dedup_ttl:
                continue
            self._last_triggered[dedup_key] = now
            self._history.append(alert)
            emitted.append(alert)
            for channel in self._channels:
                try:
                    channel.notify(alert)
                except Exception:
                    continue
        return emitted

    # ------------------------------------------------------------------
    # Domain-specific helpers
    # ------------------------------------------------------------------
    def ingest_scan(self, result: "ScanResult", *, extra_metrics: Mapping[str, float] | None = None) -> List[Alert]:
        """Build a metrics payload from a :class:`ScanResult` and evaluate rules."""

        metrics: Dict[str, float] = {
            "final_score": float(result.final_score),
            "gem_score": float(result.gem_score.score),
            "confidence": float(result.gem_score.confidence),
            "flagged": 1.0 if result.flag else 0.0,
            "liquidity": float(result.market_snapshot.liquidity_usd),
        }
        metrics.update(result.debug)
        if extra_metrics:
            metrics.update({k: float(v) for k, v in extra_metrics.items()})
        return self.process_event(f"scan.{result.token}", metrics)


if TYPE_CHECKING:  # pragma: no cover
    from src.core.pipeline import ScanResult


__all__ = [
    "Alert",
    "AlertManager",
    "AlertRule",
    "MemoryChannel",
    "NotificationChannel",
]

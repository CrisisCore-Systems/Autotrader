"""Alert outbox persistence primitives.

The alerting workflow uses an *outbox pattern* so the synchronous rule engine
only has to persist intent while a background dispatcher is responsible for
delivery with retries.  This module provides a small protocol that can be
implemented by relational databases, Redis, or any other durable store.  The
in-memory implementation is primarily used in unit tests, but it mirrors the
behaviour required in production: unique idempotency keys, audit fields, and a
simple dead-letter queue for exhausted retries.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Dict, Iterable, Protocol


@dataclass(slots=True)
class AlertOutboxEntry:
    """Represents a queued alert awaiting delivery."""

    key: str
    payload: Dict[str, object]
    status: str = "queued"
    attempts: int = 0
    last_error: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    next_attempt_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    delivered_at: datetime | None = None
    failed_at: datetime | None = None


class AlertOutboxRepo(Protocol):
    """Persistence contract for the alert outbox pattern."""

    def seen_recently(self, key: str, *, within: timedelta) -> bool:
        """Return ``True`` when the alert key has been processed recently."""

    def enqueue(self, *, key: str, payload: Dict[str, object]) -> AlertOutboxEntry:
        """Persist an alert payload for asynchronous delivery."""

    def mark_attempt(
        self,
        key: str,
        *,
        status: str,
        error: str | None = None,
        next_attempt_at: datetime | None = None,
    ) -> None:
        """Update audit trail fields after a delivery attempt or retry."""

    def list_pending(
        self,
        *,
        now: datetime | None = None,
    ) -> Iterable[AlertOutboxEntry]:  # pragma: no cover - optional hook
        """Return all alerts that are ready for delivery."""

    def list_dead_letters(self) -> Iterable[AlertOutboxEntry]:  # pragma: no cover - optional hook
        """Return alerts that exceeded the retry budget."""


class InMemoryAlertOutbox(AlertOutboxRepo):
    """Simple in-memory repository used for unit tests."""

    def __init__(self) -> None:
        self._entries: Dict[str, AlertOutboxEntry] = {}

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def seen_recently(self, key: str, *, within: timedelta) -> bool:
        entry = self._entries.get(key)
        if not entry:
            return False
        return self._now() - entry.updated_at < within

    def enqueue(self, *, key: str, payload: Dict[str, object]) -> AlertOutboxEntry:
        now = self._now()
        entry = self._entries.get(key)
        if entry:
            entry.payload = dict(payload)
            entry.status = "queued"
            entry.last_error = None
            entry.updated_at = now
            entry.next_attempt_at = now
            entry.failed_at = None
            entry.delivered_at = None
            entry.attempts = 0
            return entry

        entry = AlertOutboxEntry(
            key=key,
            payload=dict(payload),
            created_at=now,
            updated_at=now,
            next_attempt_at=now,
        )
        self._entries[key] = entry
        return entry

    def mark_attempt(
        self,
        key: str,
        *,
        status: str,
        error: str | None = None,
        next_attempt_at: datetime | None = None,
    ) -> None:
        entry = self._entries.setdefault(key, AlertOutboxEntry(key=key, payload={}))
        now = self._now()
        entry.status = status
        entry.last_error = error
        entry.updated_at = now
        entry.attempts += 1

        if status == "queued":
            entry.next_attempt_at = next_attempt_at or now
        elif status == "sent":
            entry.delivered_at = now
            entry.next_attempt_at = now
        elif status == "failed":
            entry.failed_at = now
            entry.next_attempt_at = now

    def list_pending(self, *, now: datetime | None = None) -> Iterable[AlertOutboxEntry]:
        cutoff = now or self._now()
        return [
            entry
            for entry in self._entries.values()
            if entry.status == "queued" and entry.next_attempt_at <= cutoff
        ]

    def list_dead_letters(self) -> Iterable[AlertOutboxEntry]:
        return [entry for entry in self._entries.values() if entry.status == "failed"]


__all__ = ["AlertOutboxEntry", "AlertOutboxRepo", "InMemoryAlertOutbox"]

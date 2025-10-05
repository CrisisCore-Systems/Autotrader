"""Async dispatcher that drains the alert outbox with retries and DLQ support."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Awaitable, Callable, Dict, Iterable, Mapping, MutableMapping

from .repo import AlertOutboxEntry, AlertOutboxRepo

NotifierCallable = Callable[[Mapping[str, object]], Awaitable[None]]


@dataclass(slots=True)
class DispatchResult:
    """Outcome of a delivery attempt for observability and tests."""

    sent: int
    retried: int
    failed: int


class AlertDispatcher:
    """Drain pending alerts with exponential backoff and channel fan-out."""

    def __init__(
        self,
        *,
        repo: AlertOutboxRepo,
        notifiers: Mapping[str, NotifierCallable],
        max_attempts: int = 5,
        base_backoff: timedelta = timedelta(seconds=10),
    ) -> None:
        self._repo = repo
        self._notifiers = dict(notifiers)
        self._max_attempts = max_attempts
        self._base_backoff = base_backoff

    async def deliver_pending(self, *, now: datetime | None = None) -> DispatchResult:
        """Deliver queued alerts that are due for processing."""

        now = now or datetime.now(timezone.utc)
        sent = retried = failed = 0

        for entry in list(self._repo.list_pending(now=now)):
            errors = await self._dispatch_entry(entry)
            if not errors:
                self._repo.mark_attempt(entry.key, status="sent")
                sent += 1
                continue

            attempts = entry.attempts + 1
            error_message = "; ".join(errors)
            if attempts >= self._max_attempts:
                self._repo.mark_attempt(entry.key, status="failed", error=error_message)
                failed += 1
                continue

            backoff_seconds = self._base_backoff.total_seconds() * (2 ** (attempts - 1))
            next_attempt = now + timedelta(seconds=backoff_seconds)
            self._repo.mark_attempt(
                entry.key,
                status="queued",
                error=error_message,
                next_attempt_at=next_attempt,
            )
            retried += 1

        return DispatchResult(sent=sent, retried=retried, failed=failed)

    async def _dispatch_entry(self, entry: AlertOutboxEntry) -> Iterable[str]:
        payload: MutableMapping[str, object] = dict(entry.payload)
        channels = tuple(payload.pop("channels", ()))
        errors = []

        if not channels:
            return ["no channels configured"]

        for channel in channels:
            notifier = self._notifiers.get(channel)
            if not notifier:
                errors.append(f"missing notifier: {channel}")
                continue
            try:
                await self._send_with_channel(notifier, payload, channel)
            except Exception as exc:  # pragma: no cover - deterministic via tests
                errors.append(f"{channel}: {exc}")

        return errors

    async def _send_with_channel(
        self,
        notifier: NotifierCallable,
        payload: Mapping[str, object],
        channel: str,
    ) -> None:
        message_payload: Dict[str, object] = dict(payload)
        message_payload.setdefault("channel", channel)
        await notifier(message_payload)


__all__ = ["AlertDispatcher", "DispatchResult"]

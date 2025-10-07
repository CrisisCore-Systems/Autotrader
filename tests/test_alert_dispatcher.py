import asyncio
from datetime import timedelta
from typing import Mapping

from src.alerts.dispatcher import AlertDispatcher
from src.alerts.repo import InMemoryAlertOutbox


def _collecting_notifier(bucket: list):
    async def _inner(payload: Mapping[str, object]) -> None:
        bucket.append(dict(payload))

    return _inner


def test_dispatcher_marks_sent_on_success() -> None:
    repo = InMemoryAlertOutbox()
    entry = repo.enqueue(
        key="TOKEN:window:rule:v1",
        payload={
            "symbol": "TOKEN",
            "rule": "rule",
            "channels": ["telegram", "slack"],
        },
    )

    telegram_bucket: list = []
    slack_bucket: list = []
    dispatcher = AlertDispatcher(
        repo=repo,
        notifiers={
            "telegram": _collecting_notifier(telegram_bucket),
            "slack": _collecting_notifier(slack_bucket),
        },
    )

    now = repo._entries[entry.key].next_attempt_at  # type: ignore[attr-defined]
    result = asyncio.run(dispatcher.deliver_pending(now=now))

    assert result.sent == 1
    assert list(repo.list_pending(now=now)) == []
    assert telegram_bucket and slack_bucket
    assert list(repo.list_dead_letters()) == []
    stored_entry = repo._entries[entry.key]  # type: ignore[attr-defined]
    assert stored_entry.status == "sent"


def test_dispatcher_retries_and_enters_dlq() -> None:
    repo = InMemoryAlertOutbox()
    entry = repo.enqueue(
        key="FAIL:window:rule:v1",
        payload={"symbol": "FAIL", "rule": "rule", "channels": ["telegram"]},
    )

    async def failing_notifier(payload: Mapping[str, object]) -> None:  # pragma: no cover - deterministic in tests
        raise RuntimeError("boom")

    dispatcher = AlertDispatcher(
        repo=repo,
        notifiers={"telegram": failing_notifier},
        max_attempts=2,
        base_backoff=timedelta(seconds=1),
    )

    now = repo._entries[entry.key].next_attempt_at  # type: ignore[attr-defined]

    first = asyncio.run(dispatcher.deliver_pending(now=now))
    assert first.retried == 1
    stored_entry = repo._entries[entry.key]  # type: ignore[attr-defined]
    assert stored_entry.status == "queued"
    assert stored_entry.next_attempt_at > now

    # Run again after the backoff window expires.
    second = asyncio.run(dispatcher.deliver_pending(now=now + timedelta(seconds=2)))
    assert second.failed == 1
    dlq = list(repo.list_dead_letters())
    assert len(dlq) == 1
    assert dlq[0].last_error is not None and "boom" in dlq[0].last_error

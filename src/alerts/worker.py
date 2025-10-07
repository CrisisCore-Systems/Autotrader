"""Command line helpers for running the alert dispatcher loop.

This module is intentionally lightweight so the runbooks can reference a
single, documented entrypoint for draining the alert outbox.  It wires the
``AlertDispatcher`` with a repository implementation and a collection of
notification transports that can be toggled with command line flags or
environment variables.

Example usage:

.. code-block:: bash

    # Run a one-off drain against the in-memory repository populated with
    # demo data and emit notifications to stdout.
    python -m src.alerts.worker dispatch --once --repo src.alerts.worker:build_demo_repo

Operational environments can provide their own repository factory and
additional notifiers by using the dotted-path import helpers exposed by this
module (``module.submodule:callable``).
"""

from __future__ import annotations

import argparse
import asyncio
import importlib
import inspect
import json
import logging
import os
from datetime import timedelta
from typing import Awaitable, Callable, Dict, Mapping

from .dispatcher import AlertDispatcher, DispatchResult
from .repo import AlertOutboxRepo, InMemoryAlertOutbox
from .notifiers import render_markdown, send_email, send_slack, send_telegram

NotifierCallable = Callable[[Mapping[str, object]], Awaitable[None]]

LOGGER = logging.getLogger(__name__)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Alert dispatcher utilities")
    subparsers = parser.add_subparsers(dest="command", required=True)

    dispatch = subparsers.add_parser("dispatch", help="Drain pending alerts")
    dispatch.add_argument(
        "--repo",
        default=os.environ.get("ALERTS_REPOSITORY", "src.alerts.repo:InMemoryAlertOutbox"),
        help="Repository factory specified as module:callable (defaults to the in-memory repo)",
    )
    dispatch.add_argument(
        "--channels",
        nargs="+",
        default=_default_channels(),
        help=(
            "Notifier channels to enable. Built-ins include 'stdout', 'telegram', "
            "'slack', and 'email'. Custom callables can be referenced via module:callable"
        ),
    )
    dispatch.add_argument(
        "--interval",
        type=float,
        default=float(os.environ.get("ALERTS_DISPATCH_INTERVAL", "30")),
        help="Seconds to sleep between drain cycles when running continuously",
    )
    dispatch.add_argument(
        "--once",
        action="store_true",
        help="Run a single delivery cycle instead of looping forever",
    )
    dispatch.add_argument(
        "--max-attempts",
        type=int,
        default=int(os.environ.get("ALERTS_MAX_ATTEMPTS", "5")),
        help="Maximum delivery attempts before moving an alert to the DLQ",
    )
    dispatch.add_argument(
        "--base-backoff",
        type=float,
        default=float(os.environ.get("ALERTS_BASE_BACKOFF", "10")),
        help="Initial backoff in seconds used for exponential retries",
    )
    dispatch.add_argument(
        "--log-level",
        default=os.environ.get("LOG_LEVEL", "INFO"),
        help="Logging level (e.g. INFO, DEBUG)",
    )

    return parser.parse_args(argv)


def _default_channels() -> list[str]:
    env_value = os.environ.get("ALERTS_CHANNELS")
    if not env_value:
        return ["stdout"]
    return [entry for entry in (item.strip() for item in env_value.split(",")) if entry]


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO))

    if args.command == "dispatch":
        asyncio.run(_run_dispatch(args))
        return 0

    raise RuntimeError(f"Unhandled command: {args.command}")


async def _run_dispatch(args: argparse.Namespace) -> None:
    repo = _load_repo(args.repo)
    notifiers = _load_notifiers(args.channels)
    dispatcher = AlertDispatcher(
        repo=repo,
        notifiers=notifiers,
        max_attempts=args.max_attempts,
        base_backoff=timedelta(seconds=args.base_backoff),
    )

    if args.once:
        result = await dispatcher.deliver_pending()
        _log_result(result)
        return

    interval = max(0, args.interval)
    while True:
        result = await dispatcher.deliver_pending()
        _log_result(result)
        await asyncio.sleep(interval)


def _log_result(result: DispatchResult) -> None:
    LOGGER.info(
        "dispatcher cycle complete", extra={"sent": result.sent, "retried": result.retried, "failed": result.failed}
    )


def _load_repo(spec: str) -> AlertOutboxRepo:
    factory = _import_from_spec(spec)
    repo = factory() if callable(factory) else factory
    for attribute in ("enqueue", "list_pending", "mark_attempt"):
        if not hasattr(repo, attribute):
            raise TypeError(f"Repository {spec!r} is missing required attribute: {attribute}")
    return repo  # type: ignore[return-value]


def _load_notifiers(channels: list[str]) -> Dict[str, NotifierCallable]:
    notifiers: Dict[str, NotifierCallable] = {}
    for channel in channels:
        notifiers[channel] = _resolve_notifier(channel)
    return notifiers


def _resolve_notifier(channel: str) -> NotifierCallable:
    builder = _BUILTIN_NOTIFIERS.get(channel)
    if builder is not None:
        return builder()

    imported = _import_from_spec(channel)
    if callable(imported):
        return _coerce_async(imported)

    raise ValueError(f"Notifier specification {channel!r} is not callable")


def _import_from_spec(spec: str):  # type: ignore[no-untyped-def]
    module_name, _, attribute = spec.partition(":")
    if not module_name:
        raise ValueError(f"Invalid specification: {spec!r}")
    module = importlib.import_module(module_name)
    return getattr(module, attribute) if attribute else module


def _coerce_async(func: Callable[[Mapping[str, object]], object]) -> NotifierCallable:
    if inspect.iscoroutinefunction(func):
        return func  # type: ignore[return-value]

    async def _wrapper(payload: Mapping[str, object]) -> None:
        result = func(payload)
        if inspect.isawaitable(result):
            await result  # pragma: no cover - defensive branch

    return _wrapper


def _build_stdout_notifier() -> NotifierCallable:
    async def notify(payload: Mapping[str, object]) -> None:
        print(json.dumps(dict(payload), sort_keys=True))

    return notify


def _build_telegram_notifier() -> NotifierCallable:
    async def notify(payload: Mapping[str, object]) -> None:
        message = render_markdown(payload)
        await send_telegram(message)

    return notify


def _build_slack_notifier() -> NotifierCallable:
    async def notify(payload: Mapping[str, object]) -> None:
        message = render_markdown(payload)
        await send_slack(message)

    return notify


def _build_email_notifier() -> NotifierCallable:
    async def notify(payload: Mapping[str, object]) -> None:
        message = render_markdown(payload)
        await send_email(
            subject=payload.get("subject", "Alert"),
            body=message,
            to=str(payload.get("to") or os.environ.get("ALERT_EMAIL_TO", "alerts@example.com")),
        )

    return notify


_BUILTIN_NOTIFIERS: Dict[str, Callable[[], NotifierCallable]] = {
    "stdout": _build_stdout_notifier,
    "telegram": _build_telegram_notifier,
    "slack": _build_slack_notifier,
    "email": _build_email_notifier,
}


def build_demo_repo() -> AlertOutboxRepo:
    """Return an in-memory repository populated with a sample alert.

    The helper is primarily used in documentation examples to illustrate how the
    dispatcher drains a pending alert without requiring access to production
    infrastructure.
    """

    repo = InMemoryAlertOutbox()
    repo.enqueue(
        key="demo:BTC-USD:rule:1",
        payload={
            "channels": ("stdout",),
            "rule": "Demo breakout",
            "symbol": "BTC-USD",
            "price": "50000",
        },
    )
    return repo


if __name__ == "__main__":  # pragma: no cover - manual invocation
    raise SystemExit(main())


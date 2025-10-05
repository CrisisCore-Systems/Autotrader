"""Alerting primitives for GemScore notifications."""

from .dispatcher import AlertDispatcher, DispatchResult
from .engine import evaluate_and_enqueue
from .rules import AlertRule, load_rules
from .repo import AlertOutboxEntry, AlertOutboxRepo

__all__ = [
    "AlertDispatcher",
    "AlertRule",
    "AlertOutboxEntry",
    "AlertOutboxRepo",
    "DispatchResult",
    "evaluate_and_enqueue",
    "load_rules",
]

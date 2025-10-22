"""Alerting primitives for GemScore notifications."""

from .dispatcher import AlertDispatcher, DispatchResult
from .engine import AlertCandidate, evaluate_and_enqueue
from .rules import AlertRule, CompoundCondition, SimpleCondition, load_rules
from .repo import AlertOutboxEntry, AlertOutboxRepo
from .backtest import AlertBacktester, BacktestResult, BacktestAlert, compare_rule_versions

__all__ = [
    "AlertDispatcher",
    "AlertRule",
    "AlertCandidate",
    "AlertOutboxEntry",
    "AlertOutboxRepo",
    "CompoundCondition",
    "SimpleCondition",
    "DispatchResult",
    "evaluate_and_enqueue",
    "load_rules",
    "AlertBacktester",
    "BacktestResult",
    "BacktestAlert",
    "compare_rule_versions",
]

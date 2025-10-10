"""Historical validator that backtests on curated pump events."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

from ..metrics.performance import ClassificationReport, classification_report


@dataclass
class BacktestResult:
    report: ClassificationReport
    alerts_triggered: int


def run_backtest(*, predictions: Sequence[int], labels: Sequence[int]) -> BacktestResult:
    report = classification_report(predictions=predictions, labels=labels)
    alerts_triggered = int(sum(predictions))
    return BacktestResult(report=report, alerts_triggered=alerts_triggered)

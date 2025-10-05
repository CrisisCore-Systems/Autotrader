"""Feedback loop utilities for precision@K tracking and weight optimisation."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from statistics import mean
from typing import TYPE_CHECKING, Dict, Iterable, List, Mapping, Sequence


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class RecommendationOutcome:
    """Represents the outcome for a single recommendation."""

    token: str
    rank: int
    score: float
    flagged: bool
    executed: bool
    realized_return: float | None = None


@dataclass
class RunLog:
    """Log entry for a single inference cycle."""

    run_id: str
    timestamp: datetime
    outcomes: List[RecommendationOutcome]


class PrecisionTracker:
    """Maintains rolling precision@K metrics for inference cycles."""

    def __init__(self, *, window: int = 50) -> None:
        self._window = max(1, int(window))
        self._runs: deque[RunLog] = deque(maxlen=self._window)

    # ------------------------------------------------------------------
    # Logging helpers
    # ------------------------------------------------------------------
    def log_run(
        self,
        run_id: str,
        outcomes: Iterable[RecommendationOutcome],
        *,
        timestamp: datetime | None = None,
    ) -> None:
        record = RunLog(run_id=run_id, timestamp=timestamp or _utcnow(), outcomes=list(outcomes))
        self._runs.append(record)

    def log_scan(
        self,
        run_id: str,
        result: "ScanResult",
        *,
        executed: bool = False,
        realized_return: float | None = None,
        timestamp: datetime | None = None,
    ) -> None:
        outcome = RecommendationOutcome(
            token=result.token,
            rank=1,
            score=float(result.final_score),
            flagged=bool(result.flag),
            executed=executed,
            realized_return=realized_return,
        )
        self.log_run(run_id, [outcome], timestamp=timestamp)

    def update_outcomes(
        self,
        run_id: str,
        updates: Mapping[str, Mapping[str, float | bool | int | None]],
    ) -> None:
        for record in self._runs:
            if record.run_id != run_id:
                continue
            for outcome in record.outcomes:
                payload = updates.get(outcome.token)
                if not payload:
                    continue
                if "executed" in payload:
                    outcome.executed = bool(payload["executed"])
                if "realized_return" in payload:
                    value = payload["realized_return"]
                    outcome.realized_return = float(value) if value is not None else None
            break

    # ------------------------------------------------------------------
    # Metric computation
    # ------------------------------------------------------------------
    def precision_at_k(self, k: int = 5, *, runs: int | None = None) -> float:
        k = max(1, int(k))
        considered = list(self._iter_recent_runs(runs))
        if not considered:
            return 0.0
        hits = 0
        total = 0
        for record in considered:
            top = sorted(record.outcomes, key=lambda item: item.rank)[:k]
            total += len(top)
            for outcome in top:
                if outcome.executed and (outcome.realized_return or 0.0) > 0:
                    hits += 1
        if total == 0:
            return 0.0
        return hits / total

    def average_return_at_k(self, k: int = 5, *, runs: int | None = None) -> float:
        k = max(1, int(k))
        considered = list(self._iter_recent_runs(runs))
        returns: List[float] = []
        for record in considered:
            top = sorted(record.outcomes, key=lambda item: item.rank)[:k]
            for outcome in top:
                if outcome.realized_return is not None:
                    returns.append(float(outcome.realized_return))
        if not returns:
            return 0.0
        return float(mean(returns))

    def flagged_assets(self, *, runs: int | None = None) -> List[str]:
        names: List[str] = []
        for record in self._iter_recent_runs(runs):
            for outcome in record.outcomes:
                if outcome.flagged:
                    names.append(outcome.token)
        return names

    def recent_runs(self, *, limit: int | None = None) -> List[RunLog]:
        records = list(self._runs)
        if limit is None:
            return records
        return records[-limit:]

    def _iter_recent_runs(self, runs: int | None) -> Iterable[RunLog]:
        if runs is None:
            yield from self._runs
        else:
            for record in list(self._runs)[-runs:]:
                yield record


class WeightOptimizer:
    """Utility for computing simple strategy weights based on returns."""

    def optimise(self, metrics: Mapping[str, Sequence[float]], *, floor: float = 0.0) -> Dict[str, float]:
        scores: Dict[str, float] = {}
        for name, values in metrics.items():
            data = [float(value) for value in values if value is not None]
            if not data:
                scores[name] = float(floor)
                continue
            avg = mean(data)
            scores[name] = float(max(floor, avg))
        total = sum(scores.values())
        if total <= 0:
            n = len(scores) or 1
            return {name: 1.0 / n for name in scores}
        return {name: value / total for name, value in scores.items()}


if TYPE_CHECKING:  # pragma: no cover
    from src.core.pipeline import ScanResult


__all__ = [
    "PrecisionTracker",
    "RecommendationOutcome",
    "RunLog",
    "WeightOptimizer",
]

"""Lightweight scheduling and backtesting orchestration utilities."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from typing import Callable, Dict, List, Sequence, Tuple

from backtest.harness import BacktestResult, evaluate_period, load_snapshots


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Schedule:
    """Abstract schedule definition."""

    def next_run(self, previous: datetime) -> datetime:  # pragma: no cover - interface hook
        raise NotImplementedError


@dataclass
class IntervalSchedule(Schedule):
    """Run a job at fixed time intervals."""

    interval: timedelta

    def __post_init__(self) -> None:
        if self.interval.total_seconds() <= 0:
            raise ValueError("interval must be positive")

    def next_run(self, previous: datetime) -> datetime:
        return previous + self.interval


@dataclass
class DailySchedule(Schedule):
    """Run a job once per day at the configured UTC time."""

    at: time

    def next_run(self, previous: datetime) -> datetime:
        candidate = datetime.combine(previous.date(), self.at, tzinfo=timezone.utc)
        if candidate <= previous:
            candidate += timedelta(days=1)
        return candidate


@dataclass
class ScheduledJob:
    """Internal representation of a scheduled task."""

    name: str
    func: Callable[..., object]
    schedule: Schedule
    args: Sequence[object] = field(default_factory=tuple)
    kwargs: Dict[str, object] = field(default_factory=dict)
    tags: Tuple[str, ...] = field(default_factory=tuple)
    next_run: datetime | None = None
    last_run: datetime | None = None


@dataclass
class JobResult:
    """Result metadata for a job execution."""

    name: str
    run_at: datetime
    duration: timedelta
    outcome: object | None
    error: Exception | None = None

    @property
    def success(self) -> bool:
        return self.error is None


@dataclass(frozen=True)
class BacktestConfig:
    """Configuration for automated backtest jobs."""

    name: str
    data: Path
    top_k: int = 10


@dataclass
class BacktestSummary:
    """Serializable summary of a backtest run."""

    precision_at_k: float
    average_return_at_k: float
    flagged_assets: Sequence[str]


class Scheduler:
    """Minimal scheduler for orchestrating inference and backtests."""

    def __init__(self, *, clock: Callable[[], datetime] | None = None) -> None:
        self._clock = clock or _utcnow
        self._jobs: Dict[str, ScheduledJob] = {}
        self._history: List[JobResult] = []

    def add_job(
        self,
        func: Callable[..., object],
        schedule: Schedule,
        *,
        name: str | None = None,
        args: Sequence[object] | None = None,
        kwargs: Dict[str, object] | None = None,
        tags: Sequence[str] | None = None,
    ) -> str:
        job_name = name or getattr(func, "__name__", "job")
        if job_name in self._jobs:
            raise ValueError(f"Job '{job_name}' already exists")
        job = ScheduledJob(
            name=job_name,
            func=func,
            schedule=schedule,
            args=tuple(args or ()),
            kwargs=dict(kwargs or {}),
            tags=tuple(tags or ()),
        )
        now = self._clock()
        job.next_run = schedule.next_run(now)
        self._jobs[job_name] = job
        return job_name

    def remove_job(self, name: str) -> None:
        self._jobs.pop(name, None)

    def run_pending(self) -> List[JobResult]:
        now = self._clock()
        results: List[JobResult] = []
        for job in sorted(self._jobs.values(), key=lambda j: j.next_run or now):
            if job.next_run and job.next_run > now:
                continue
            results.append(self._run_job(job, now))
        return results

    def trigger(self, name: str) -> JobResult:
        job = self._jobs[name]
        return self._run_job(job, self._clock())

    def history(self, *, limit: int | None = None) -> List[JobResult]:
        if limit is None:
            return list(self._history)
        return list(self._history[-limit:])

    def schedule_backtest(self, config: BacktestConfig, schedule: Schedule) -> str:
        return self.add_job(
            lambda: self.run_backtest(config),
            schedule,
            name=f"backtest:{config.name}",
            tags=("backtest",),
        )

    def run_backtest(self, config: BacktestConfig) -> BacktestSummary:
        snapshots = list(load_snapshots(config.data))
        result: BacktestResult = evaluate_period(snapshots, top_k=config.top_k)
        return BacktestSummary(
            precision_at_k=result.precision_at_k,
            average_return_at_k=result.average_return_at_k,
            flagged_assets=list(result.flagged_assets),
        )

    def _run_job(self, job: ScheduledJob, now: datetime) -> JobResult:
        start = now
        outcome: object | None = None
        error: Exception | None = None
        try:
            outcome = job.func(*job.args, **job.kwargs)
        except Exception as exc:  # pragma: no cover
            error = exc
        finally:
            job.last_run = start
            job.next_run = job.schedule.next_run(start)
        result = JobResult(
            name=job.name,
            run_at=start,
            duration=self._clock() - start,
            outcome=outcome,
            error=error,
        )
        self._history.append(result)
        return result


__all__ = [
    "BacktestConfig",
    "BacktestSummary",
    "DailySchedule",
    "IntervalSchedule",
    "JobResult",
    "Schedule",
    "Scheduler",
]

from datetime import datetime, timedelta, timezone

import pandas as pd

from src.services.scheduler import (
    BacktestConfig,
    IntervalSchedule,
    Scheduler,
)


def test_scheduler_runs_jobs_and_records_history() -> None:
    clock = [datetime(2024, 1, 1, tzinfo=timezone.utc)]

    def _clock() -> datetime:
        return clock[0]

    scheduler = Scheduler(clock=_clock)
    calls: list[datetime] = []

    def _job() -> str:
        calls.append(_clock())
        return "ran"

    scheduler.add_job(_job, IntervalSchedule(timedelta(minutes=5)), name="heartbeat")

    clock[0] = clock[0] + timedelta(minutes=6)
    results = scheduler.run_pending()
    assert len(results) == 1
    assert results[0].success
    assert results[0].outcome == "ran"
    assert scheduler.history(limit=1)[0].name == "heartbeat"

    clock[0] = clock[0] + timedelta(minutes=5)
    scheduler.trigger("heartbeat")
    assert len(calls) == 2


def test_scheduler_backtest_summary(tmp_path) -> None:
    data = pd.DataFrame(
        [
            {
                "token": "AAA",
                "date": "2024-01-01",
                "f_SentimentScore": 0.8,
                "f_AccumulationScore": 0.7,
                "f_OnchainActivity": 0.6,
                "f_LiquidityDepth": 0.6,
                "f_TokenomicsRisk": 0.9,
                "f_ContractSafety": 0.8,
                "f_NarrativeMomentum": 0.75,
                "f_CommunityGrowth": 0.7,
                "future_return_7d": 0.15,
            },
            {
                "token": "BBB",
                "date": "2024-01-01",
                "f_SentimentScore": 0.6,
                "f_AccumulationScore": 0.4,
                "f_OnchainActivity": 0.3,
                "f_LiquidityDepth": 0.5,
                "f_TokenomicsRisk": 0.8,
                "f_ContractSafety": 0.7,
                "f_NarrativeMomentum": 0.65,
                "f_CommunityGrowth": 0.6,
                "future_return_7d": -0.05,
            },
        ]
    )
    csv_path = tmp_path / "backtest.csv"
    data.to_csv(csv_path, index=False)

    scheduler = Scheduler()
    summary = scheduler.run_backtest(BacktestConfig(name="demo", data=csv_path, top_k=1))

    assert 0.0 <= summary.precision_at_k <= 1.0
    assert isinstance(summary.flagged_assets, list)
    job_id = scheduler.schedule_backtest(BacktestConfig(name="demo2", data=csv_path), IntervalSchedule(timedelta(days=1)))
    assert job_id.startswith("backtest:")

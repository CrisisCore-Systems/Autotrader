from datetime import datetime, timedelta, timezone

from src.core.features import MarketSnapshot
from src.core.narrative import NarrativeInsight
from src.core.pipeline import ScanResult
from src.core.safety import SafetyReport
from src.core.scoring import GemScoreResult
from src.services.alerting import AlertManager, AlertRule, MemoryChannel


def _build_scan_result() -> ScanResult:
    snapshot = MarketSnapshot(
        symbol="TEST",
        timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
        price=1.0,
        volume_24h=100_000.0,
        liquidity_usd=75_000.0,
        holders=1_200,
        onchain_metrics={"active_wallets": 1_200},
        narratives=["Testing narrative"],
    )
    narrative = NarrativeInsight(
        sentiment_score=0.6,
        momentum=0.7,
        themes=["growth"],
        volatility=0.2,
        meme_momentum=0.4,
    )
    gem_score = GemScoreResult(score=45.0, confidence=80.0, contributions={})
    safety = SafetyReport(score=0.8, severity="low", findings=[], flags={})
    return ScanResult(
        token="TEST",
        market_snapshot=snapshot,
        narrative=narrative,
        raw_features={},
        adjusted_features={},
        gem_score=gem_score,
        safety_report=safety,
        flag=False,
        debug={"drawdown": 0.12},
        artifact_payload={},
        artifact_markdown="",
        artifact_html="",
        final_score=45.0,
    )


def test_alert_manager_deduplicates_and_notifies_channels() -> None:
    now = datetime(2024, 1, 1, tzinfo=timezone.utc)
    clock = [now]

    def _clock() -> datetime:
        return clock[0]

    channel = MemoryChannel()
    manager = AlertManager(
        rules=[
            AlertRule(
                "low-score",
                condition=lambda metrics: metrics.get("final_score", 100) < 50,
                severity="critical",
                message="Score dropped below threshold",
            )
        ],
        channels=[channel],
        dedup_ttl=timedelta(minutes=5),
        clock=_clock,
    )

    alerts = manager.process_event("scan.TEST", {"final_score": 42.0})
    assert len(alerts) == 1
    assert channel.alerts[-1].message == "Score dropped below threshold"

    clock[0] = now + timedelta(minutes=1)
    assert manager.process_event("scan.TEST", {"final_score": 41.0}) == []

    clock[0] = now + timedelta(minutes=6)
    alerts = manager.process_event("scan.TEST", {"final_score": 40.0})
    assert len(alerts) == 1
    assert manager.history(limit=2)[-1].severity == "critical"


def test_ingest_scan_builds_metrics_payload() -> None:
    channel = MemoryChannel()
    manager = AlertManager(
        rules=[
            AlertRule(
                "drawdown",
                condition=lambda metrics: metrics.get("drawdown", 0.0) > 0.1,
                severity="warning",
                message="Drawdown exceeded 10%",
            )
        ],
        channels=[channel],
        dedup_ttl=timedelta(seconds=0),
    )

    result = _build_scan_result()
    alerts = manager.ingest_scan(result)
    assert len(alerts) == 1
    assert alerts[0].metrics["drawdown"] == 0.12
    assert channel.alerts[-1].event == "scan.TEST"

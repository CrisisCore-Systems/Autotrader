from datetime import datetime, timedelta

from src.alerts.engine import AlertCandidate, evaluate_and_enqueue
from src.alerts.repo import InMemoryAlertOutbox
from src.alerts.rules import AlertRule, load_rules


def test_evaluate_and_enqueue_deduplicates() -> None:
    outbox = InMemoryAlertOutbox()
    now = datetime(2024, 1, 1, 12, 0, 0)
    rule = AlertRule(
        id="gate",
        score_min=70,
        confidence_min=0.5,
        safety_ok=True,
        cool_off_minutes=60,
    )
    candidate = AlertCandidate(
        symbol="TEST",
        window_start="2024-01-01T12:00:00Z",
        gem_score=72,
        confidence=0.6,
        safety_ok=True,
    )

    entries = evaluate_and_enqueue([candidate], now=now, outbox=outbox, rules=[rule])
    assert len(entries) == 1

    # Second evaluation within the cooldown should be dropped.
    entries = evaluate_and_enqueue([candidate], now=now + timedelta(minutes=1), outbox=outbox, rules=[rule])
    assert entries == []


def test_load_rules_from_yaml(tmp_path) -> None:
    path = tmp_path / "rules.yaml"
    path.write_text(
        """
        rules:
          - id: custom
            description: Example
            where:
              gem_score_min: 80
              confidence_min: 0.9
              safety_ok: true
            channels: [telegram]
            cool_off_minutes: 120
            version: v2
        """
    )

    rules = load_rules(path)
    assert len(rules) == 1
    rule = rules[0]
    assert rule.id == "custom"
    assert rule.cool_off_minutes == 120
    assert rule.version == "v2"


def test_candidate_payload_includes_metadata() -> None:
    outbox = InMemoryAlertOutbox()
    now = datetime(2024, 1, 1, 0, 0, 0)
    rule = AlertRule(
        id="meta",
        score_min=10,
        confidence_min=0.1,
        safety_ok=True,
        cool_off_minutes=1,
    )
    candidate = AlertCandidate(
        symbol="META",
        window_start="2024-01-01T00:00:00Z",
        gem_score=15,
        confidence=0.9,
        safety_ok=True,
        metadata={"trend": "bullish"},
    )

    entries = evaluate_and_enqueue([candidate], now=now, outbox=outbox, rules=[rule])
    assert entries[0].payload["trend"] == "bullish"

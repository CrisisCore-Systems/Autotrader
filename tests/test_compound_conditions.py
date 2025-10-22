"""Tests for compound condition evaluation in alert rules."""

from datetime import datetime

import pytest

from src.alerts.engine import AlertCandidate, evaluate_and_enqueue
from src.alerts.repo import InMemoryAlertOutbox
from src.alerts.rules import AlertRule, CompoundCondition, SimpleCondition


def test_simple_condition_evaluation():
    """Test simple condition evaluation."""
    condition = SimpleCondition(metric="gem_score", operator="gt", threshold=70)
    
    context_pass = {"gem_score": 75}
    assert condition.evaluate(context_pass) is True
    
    context_fail = {"gem_score": 65}
    assert condition.evaluate(context_fail) is False


def test_compound_and_condition():
    """Test AND compound condition."""
    condition = CompoundCondition(
        operator="AND",
        conditions=(
            SimpleCondition(metric="gem_score", operator="gt", threshold=70),
            SimpleCondition(metric="liquidity_usd", operator="gt", threshold=10000),
        )
    )
    
    # Both conditions true
    context_pass = {"gem_score": 75, "liquidity_usd": 15000}
    assert condition.evaluate(context_pass) is True
    
    # One condition false
    context_fail = {"gem_score": 75, "liquidity_usd": 5000}
    assert condition.evaluate(context_fail) is False


def test_compound_or_condition():
    """Test OR compound condition."""
    condition = CompoundCondition(
        operator="OR",
        conditions=(
            SimpleCondition(metric="gem_score", operator="lt", threshold=30),
            SimpleCondition(metric="honeypot_detected", operator="eq", threshold=True),
        )
    )
    
    # First condition true
    context1 = {"gem_score": 25, "honeypot_detected": False}
    assert condition.evaluate(context1) is True
    
    # Second condition true
    context2 = {"gem_score": 50, "honeypot_detected": True}
    assert condition.evaluate(context2) is True
    
    # Both false
    context_fail = {"gem_score": 50, "honeypot_detected": False}
    assert condition.evaluate(context_fail) is False


def test_nested_compound_conditions():
    """Test nested compound conditions: (A AND (B OR C))."""
    condition = CompoundCondition(
        operator="AND",
        conditions=(
            SimpleCondition(metric="gem_score", operator="gte", threshold=70),
            CompoundCondition(
                operator="OR",
                conditions=(
                    SimpleCondition(metric="liquidity_usd", operator="lt", threshold=10000),
                    SimpleCondition(metric="safety_score", operator="lt", threshold=0.5),
                )
            )
        )
    )
    
    # High score + low liquidity
    context1 = {"gem_score": 75, "liquidity_usd": 5000, "safety_score": 0.8}
    assert condition.evaluate(context1) is True
    
    # High score + low safety
    context2 = {"gem_score": 80, "liquidity_usd": 50000, "safety_score": 0.3}
    assert condition.evaluate(context2) is True
    
    # High score + all good (should fail)
    context_fail = {"gem_score": 75, "liquidity_usd": 50000, "safety_score": 0.8}
    assert condition.evaluate(context_fail) is False


def test_alert_rule_v2_with_compound_condition():
    """Test AlertRule evaluation with compound conditions."""
    outbox = InMemoryAlertOutbox()
    now = datetime(2024, 1, 1, 12, 0, 0)
    
    # Create v2 rule with compound condition
    rule = AlertRule(
        id="critical_risk",
        score_min=0,  # Not used in v2
        confidence_min=0,
        safety_ok=True,
        cool_off_minutes=60,
        version="v2",
        condition=CompoundCondition(
            operator="AND",
            conditions=(
                SimpleCondition(metric="gem_score", operator="lt", threshold=30),
                SimpleCondition(metric="honeypot_detected", operator="eq", threshold=True),
            )
        ),
        severity="critical",
        message_template="Critical: score={gem_score}, honeypot={honeypot_detected}",
    )
    
    # Create candidate that matches
    candidate = AlertCandidate(
        symbol="BAD",
        window_start="2024-01-01T12:00:00Z",
        gem_score=25,
        confidence=0.8,
        safety_ok=True,
        metadata={"honeypot_detected": True},
    )
    
    entries = evaluate_and_enqueue([candidate], now=now, outbox=outbox, rules=[rule])
    assert len(entries) == 1
    assert entries[0].payload["severity"] == "critical"
    assert "Critical: score=25" in entries[0].payload["message"]


def test_v2_rule_with_template_formatting():
    """Test message template formatting with context."""
    outbox = InMemoryAlertOutbox()
    now = datetime(2024, 1, 1, 12, 0, 0)
    
    rule = AlertRule(
        id="liquidity_alert",
        score_min=0,
        confidence_min=0,
        safety_ok=True,
        cool_off_minutes=30,
        version="v2",
        condition=SimpleCondition(metric="liquidity_usd", operator="lt", threshold=10000),
        message_template="Low liquidity detected: ${liquidity_usd} for {symbol}",
        severity="warning",
    )
    
    candidate = AlertCandidate(
        symbol="TOKEN",
        window_start="2024-01-01T12:00:00Z",
        gem_score=60,
        confidence=0.7,
        safety_ok=True,
        metadata={"liquidity_usd": 5000},
    )
    
    entries = evaluate_and_enqueue([candidate], now=now, outbox=outbox, rules=[rule])
    assert len(entries) == 1
    assert "Low liquidity detected: $5000 for TOKEN" in entries[0].payload["message"]


def test_v2_rule_with_feature_diff():
    """Test including feature diff in alert payload."""
    outbox = InMemoryAlertOutbox()
    now = datetime(2024, 1, 1, 12, 0, 0)
    
    rule = AlertRule(
        id="feature_change",
        score_min=0,
        confidence_min=0,
        safety_ok=True,
        cool_off_minutes=30,
        version="v2",
        condition=SimpleCondition(metric="gem_score", operator="gt", threshold=60),
    )
    
    candidate = AlertCandidate(
        symbol="TOKEN",
        window_start="2024-01-01T12:00:00Z",
        gem_score=70,
        confidence=0.8,
        safety_ok=True,
        feature_diff={
            "liquidity_usd": {"before": 5000, "after": 15000, "change_pct": 200},
            "volume_24h": {"before": 10000, "after": 50000, "change_pct": 400},
        },
        prior_period={
            "gem_score": 50,
            "confidence": 0.6,
        }
    )
    
    entries = evaluate_and_enqueue([candidate], now=now, outbox=outbox, rules=[rule])
    assert len(entries) == 1
    assert "feature_diff" in entries[0].payload
    assert entries[0].payload["feature_diff"]["liquidity_usd"]["change_pct"] == 200
    assert "prior_period" in entries[0].payload
    assert entries[0].payload["prior_period"]["gem_score"] == 50


def test_v1_rule_still_works():
    """Test that v1 rules still work with backward compatibility."""
    outbox = InMemoryAlertOutbox()
    now = datetime(2024, 1, 1, 12, 0, 0)
    
    # V1 rule without compound conditions
    rule = AlertRule(
        id="legacy_rule",
        score_min=70,
        confidence_min=0.75,
        safety_ok=True,
        cool_off_minutes=60,
        version="v1",
    )
    
    candidate = AlertCandidate(
        symbol="TOKEN",
        window_start="2024-01-01T12:00:00Z",
        gem_score=75,
        confidence=0.8,
        safety_ok=True,
    )
    
    entries = evaluate_and_enqueue([candidate], now=now, outbox=outbox, rules=[rule])
    assert len(entries) == 1


def test_operator_aliases():
    """Test that operator aliases work correctly."""
    # Test all operator variants
    operators_gt = [">", "gt"]
    for op in operators_gt:
        condition = SimpleCondition(metric="value", operator=op, threshold=50)
        assert condition.evaluate({"value": 60}) is True
        assert condition.evaluate({"value": 40}) is False
    
    operators_gte = [">=", "gte", "ge"]
    for op in operators_gte:
        condition = SimpleCondition(metric="value", operator=op, threshold=50)
        assert condition.evaluate({"value": 50}) is True
        assert condition.evaluate({"value": 40}) is False
    
    operators_eq = ["==", "eq"]
    for op in operators_eq:
        condition = SimpleCondition(metric="value", operator=op, threshold=True)
        assert condition.evaluate({"value": True}) is True
        assert condition.evaluate({"value": False}) is False


def test_missing_metric_returns_false():
    """Test that missing metrics safely return False."""
    condition = SimpleCondition(metric="missing_metric", operator="gt", threshold=50)
    context = {"other_metric": 100}
    assert condition.evaluate(context) is False


def test_type_error_in_comparison_returns_false():
    """Test that type errors are handled gracefully."""
    condition = SimpleCondition(metric="value", operator="gt", threshold=50)
    # Try to compare incompatible types
    context = {"value": "string"}
    assert condition.evaluate(context) is False

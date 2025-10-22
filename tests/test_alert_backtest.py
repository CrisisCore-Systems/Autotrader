"""Tests for backtestable alert logic."""

from datetime import datetime, timedelta

import pytest

from src.alerts.backtest import AlertBacktester, BacktestResult, compare_rule_versions
from src.alerts.engine import AlertCandidate
from src.alerts.rules import AlertRule, SimpleCondition


def test_backtest_basic_run():
    """Test basic backtest run with simple rule."""
    rule = AlertRule(
        id="test_rule",
        score_min=0,
        confidence_min=0,
        safety_ok=True,
        cool_off_minutes=60,
        version="v2",
        condition=SimpleCondition(metric="gem_score", operator="gt", threshold=70),
        severity="info",
    )
    
    backtester = AlertBacktester([rule])
    
    # Create test candidates
    start_time = datetime(2024, 1, 1, 0, 0, 0)
    candidates = [
        AlertCandidate(
            symbol="TOKEN1",
            window_start="2024-01-01T00:00:00Z",
            gem_score=75,
            confidence=0.8,
            safety_ok=True,
        ),
        AlertCandidate(
            symbol="TOKEN2",
            window_start="2024-01-01T01:00:00Z",
            gem_score=60,  # Below threshold
            confidence=0.8,
            safety_ok=True,
        ),
        AlertCandidate(
            symbol="TOKEN3",
            window_start="2024-01-01T02:00:00Z",
            gem_score=80,
            confidence=0.8,
            safety_ok=True,
        ),
    ]
    
    end_time = datetime(2024, 1, 1, 12, 0, 0)
    result = backtester.run(candidates, start_time, end_time)
    
    assert result.total_candidates == 3
    assert result.alerts_fired == 2  # TOKEN1 and TOKEN3 match
    assert "test_rule" in result.alerts_by_rule
    assert result.alerts_by_rule["test_rule"] == 2


def test_backtest_with_suppression():
    """Test that suppression works for same window evaluated multiple times."""
    rule = AlertRule(
        id="test_rule",
        score_min=0,
        confidence_min=0,
        safety_ok=True,
        cool_off_minutes=60,  # 1 hour suppression
        version="v2",
        condition=SimpleCondition(metric="gem_score", operator="gt", threshold=70),
    )
    
    backtester = AlertBacktester([rule])
    
    # Create duplicate candidates for same token AND same window_start
    # This simulates re-evaluation of the same window
    start_time = datetime(2024, 1, 1, 0, 0, 0)
    candidates = [
        AlertCandidate(
            symbol="TOKEN",
            window_start="2024-01-01T00:00:00Z",
            gem_score=75,
            confidence=0.8,
            safety_ok=True,
        ),
        AlertCandidate(
            symbol="TOKEN",
            window_start="2024-01-01T00:00:00Z",  # Same window, should be suppressed
            gem_score=80,
            confidence=0.8,
            safety_ok=True,
        ),
        AlertCandidate(
            symbol="TOKEN",
            window_start="2024-01-01T02:00:00Z",  # Different window, not suppressed
            gem_score=85,
            confidence=0.8,
            safety_ok=True,
        ),
    ]
    
    end_time = datetime(2024, 1, 1, 12, 0, 0)
    result = backtester.run(candidates, start_time, end_time)
    
    # First occurrence of each window fires, duplicate is suppressed
    assert result.alerts_fired == 2


def test_backtest_summary():
    """Test backtest summary statistics."""
    rule1 = AlertRule(
        id="high_score",
        score_min=0,
        confidence_min=0,
        safety_ok=True,
        cool_off_minutes=30,
        version="v2",
        condition=SimpleCondition(metric="gem_score", operator="gt", threshold=70),
        severity="info",
    )
    
    rule2 = AlertRule(
        id="critical_risk",
        score_min=0,
        confidence_min=0,
        safety_ok=True,
        cool_off_minutes=30,
        version="v2",
        condition=SimpleCondition(metric="gem_score", operator="lt", threshold=30),
        severity="critical",
    )
    
    backtester = AlertBacktester([rule1, rule2])
    
    start_time = datetime(2024, 1, 1, 0, 0, 0)
    candidates = [
        AlertCandidate(
            symbol="GOOD",
            window_start="2024-01-01T00:00:00Z",
            gem_score=75,
            confidence=0.8,
            safety_ok=True,
        ),
        AlertCandidate(
            symbol="BAD",
            window_start="2024-01-01T01:00:00Z",
            gem_score=25,
            confidence=0.8,
            safety_ok=True,
        ),
    ]
    
    end_time = datetime(2024, 1, 1, 12, 0, 0)
    result = backtester.run(candidates, start_time, end_time)
    
    summary = result.summary()
    assert summary["candidates_evaluated"] == 2
    assert summary["alerts_fired"] == 2
    assert "by_rule" in summary
    assert summary["by_rule"]["high_score"] == 1
    assert summary["by_rule"]["critical_risk"] == 1
    assert "by_severity" in summary
    assert summary["by_severity"]["info"] == 1
    assert summary["by_severity"]["critical"] == 1


def test_backtest_filters_by_time_range():
    """Test that backtest only processes candidates within time range."""
    rule = AlertRule(
        id="test_rule",
        score_min=0,
        confidence_min=0,
        safety_ok=True,
        cool_off_minutes=30,
        version="v2",
        condition=SimpleCondition(metric="gem_score", operator="gt", threshold=70),
    )
    
    backtester = AlertBacktester([rule])
    
    # Candidates outside the time range
    candidates = [
        AlertCandidate(
            symbol="EARLY",
            window_start="2023-12-31T23:00:00Z",  # Before start
            gem_score=75,
            confidence=0.8,
            safety_ok=True,
        ),
        AlertCandidate(
            symbol="INRANGE",
            window_start="2024-01-01T06:00:00Z",  # In range
            gem_score=75,
            confidence=0.8,
            safety_ok=True,
        ),
        AlertCandidate(
            symbol="LATE",
            window_start="2024-01-02T00:00:00Z",  # After end
            gem_score=75,
            confidence=0.8,
            safety_ok=True,
        ),
    ]
    
    start_time = datetime(2024, 1, 1, 0, 0, 0)
    end_time = datetime(2024, 1, 1, 12, 0, 0)
    result = backtester.run(candidates, start_time, end_time)
    
    # Only the in-range candidate should fire
    assert result.alerts_fired == 1
    assert result.alert_details[0].symbol == "INRANGE"


def test_compare_rule_versions():
    """Test comparing different rule versions."""
    # V1: Simple threshold
    rules_v1 = [
        AlertRule(
            id="rule_v1",
            score_min=70,
            confidence_min=0.7,
            safety_ok=True,
            cool_off_minutes=60,
            version="v1",
        )
    ]
    
    # V2: Compound condition
    rules_v2 = [
        AlertRule(
            id="rule_v2",
            score_min=0,
            confidence_min=0,
            safety_ok=True,
            cool_off_minutes=60,
            version="v2",
            condition=SimpleCondition(metric="gem_score", operator="gt", threshold=65),
        )
    ]
    
    # Create test candidates
    candidates = [
        AlertCandidate(
            symbol="TOKEN1",
            window_start="2024-01-01T00:00:00Z",
            gem_score=75,
            confidence=0.8,
            safety_ok=True,
        ),
        AlertCandidate(
            symbol="TOKEN2",
            window_start="2024-01-01T01:00:00Z",
            gem_score=68,  # Matches v2 (>65) but not v1 (>70)
            confidence=0.8,
            safety_ok=True,
        ),
    ]
    
    start_time = datetime(2024, 1, 1, 0, 0, 0)
    end_time = datetime(2024, 1, 1, 12, 0, 0)
    
    results = compare_rule_versions(candidates, rules_v1, rules_v2, start_time, end_time)
    
    assert "v1" in results
    assert "v2" in results
    assert "comparison" in results
    
    # V2 should fire more alerts (lower threshold)
    assert results["v2"].alerts_fired > results["v1"].alerts_fired
    assert results["comparison"]["alert_diff"] > 0


def test_backtest_result_alert_details():
    """Test that alert details are properly captured."""
    rule = AlertRule(
        id="test_rule",
        score_min=0,
        confidence_min=0,
        safety_ok=True,
        cool_off_minutes=30,
        version="v2",
        condition=SimpleCondition(metric="gem_score", operator="gt", threshold=70),
        severity="warning",
        message_template="Alert for {symbol}: score={gem_score}",
    )
    
    backtester = AlertBacktester([rule])
    
    start_time = datetime(2024, 1, 1, 0, 0, 0)
    candidates = [
        AlertCandidate(
            symbol="TOKEN",
            window_start="2024-01-01T00:00:00Z",
            gem_score=75,
            confidence=0.8,
            safety_ok=True,
        ),
    ]
    
    end_time = datetime(2024, 1, 1, 12, 0, 0)
    result = backtester.run(candidates, start_time, end_time)
    
    assert len(result.alert_details) == 1
    alert = result.alert_details[0]
    assert alert.rule_id == "test_rule"
    assert alert.symbol == "TOKEN"
    assert alert.severity == "warning"
    assert alert.context["gem_score"] == 75


def test_backtest_empty_candidates():
    """Test backtest with no candidates."""
    rule = AlertRule(
        id="test_rule",
        score_min=0,
        confidence_min=0,
        safety_ok=True,
        cool_off_minutes=30,
        version="v2",
        condition=SimpleCondition(metric="gem_score", operator="gt", threshold=70),
    )
    
    backtester = AlertBacktester([rule])
    
    start_time = datetime(2024, 1, 1, 0, 0, 0)
    end_time = datetime(2024, 1, 1, 12, 0, 0)
    result = backtester.run([], start_time, end_time)
    
    assert result.total_candidates == 0
    assert result.alerts_fired == 0
    assert len(result.alert_details) == 0

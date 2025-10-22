"""
Demonstration of Expanded Alert Rule Engine Features

This example showcases:
1. Compound logic (AND, OR, NOT) in alert rules
2. Backtestable alert logic for historical analysis
3. Templated alert messages with context (feature diffs, prior period comparison)
4. Suppression/cool-off periods
5. Escalation policies
"""

from datetime import datetime, timedelta
from src.alerts import (
    AlertRule,
    AlertCandidate,
    CompoundCondition,
    SimpleCondition,
    AlertBacktester,
    evaluate_and_enqueue,
)
from src.alerts.repo import InMemoryAlertOutbox


def example_1_compound_conditions():
    """Example 1: Using compound conditions for complex alert logic."""
    print("\n" + "=" * 80)
    print("EXAMPLE 1: Compound Conditions")
    print("=" * 80)
    
    # Rule: Alert when (gem_score < 30) AND (honeypot_detected = true)
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
        message_template="🚨 CRITICAL: Low score ({gem_score}) AND honeypot detected for {symbol}!",
        description="Critical risk: low GemScore AND honeypot detected",
    )
    
    outbox = InMemoryAlertOutbox()
    now = datetime.now()
    
    # Test case 1: Both conditions match
    print("\n📊 Test Case 1: Both conditions match")
    candidate1 = AlertCandidate(
        symbol="SCAM_TOKEN",
        window_start=now.isoformat(),
        gem_score=25,
        confidence=0.8,
        safety_ok=True,
        metadata={"honeypot_detected": True, "liquidity_usd": 1000},
    )
    
    alerts1 = evaluate_and_enqueue([candidate1], now=now, outbox=outbox, rules=[rule])
    if alerts1:
        print(f"   ✅ Alert fired: {alerts1[0].payload['message']}")
    else:
        print("   ❌ No alert (unexpected)")
    
    # Test case 2: Only one condition matches
    print("\n📊 Test Case 2: Only one condition matches")
    candidate2 = AlertCandidate(
        symbol="SAFE_TOKEN",
        window_start=now.isoformat(),
        gem_score=25,  # Low score but...
        confidence=0.8,
        safety_ok=True,
        metadata={"honeypot_detected": False},  # ...not a honeypot
    )
    
    alerts2 = evaluate_and_enqueue([candidate2], now=now, outbox=outbox, rules=[rule])
    if alerts2:
        print("   ❌ Alert fired (unexpected)")
    else:
        print("   ✅ No alert (correctly suppressed)")


def example_2_nested_conditions():
    """Example 2: Nested compound conditions."""
    print("\n" + "=" * 80)
    print("EXAMPLE 2: Nested Compound Conditions")
    print("=" * 80)
    
    # Rule: Alert when (gem_score >= 70) AND ((liquidity < 10000) OR (safety_score < 0.5))
    rule = AlertRule(
        id="suspicious_high_score",
        score_min=0,
        confidence_min=0,
        safety_ok=True,
        cool_off_minutes=30,
        version="v2",
        condition=CompoundCondition(
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
        ),
        severity="warning",
        message_template="⚠️ High score ({gem_score}) but red flags: liquidity=${liquidity_usd}, safety={safety_score}",
        description="High score token with red flags",
    )
    
    outbox = InMemoryAlertOutbox()
    now = datetime.now()
    
    # Test case: High score + low liquidity
    print("\n📊 Test Case: High score + low liquidity")
    candidate = AlertCandidate(
        symbol="SUSPICIOUS",
        window_start=now.isoformat(),
        gem_score=75,
        confidence=0.8,
        safety_ok=True,
        metadata={"liquidity_usd": 5000, "safety_score": 0.8},
    )
    
    alerts = evaluate_and_enqueue([candidate], now=now, outbox=outbox, rules=[rule])
    if alerts:
        print(f"   ✅ Alert fired: {alerts[0].payload['message']}")
    else:
        print("   ❌ No alert (unexpected)")


def example_3_templated_messages():
    """Example 3: Templated messages with feature diffs and prior period comparison."""
    print("\n" + "=" * 80)
    print("EXAMPLE 3: Templated Messages with Context")
    print("=" * 80)
    
    rule = AlertRule(
        id="liquidity_surge",
        score_min=0,
        confidence_min=0,
        safety_ok=True,
        cool_off_minutes=30,
        version="v2",
        condition=SimpleCondition(metric="gem_score", operator="gte", threshold=70),
        severity="info",
        message_template=(
            "💎 GEM ALERT: {symbol} scored {gem_score} (confidence: {confidence})\n"
            "Liquidity: ${liquidity_usd} | Volume: ${volume_24h}"
        ),
        description="High quality gem detected",
    )
    
    outbox = InMemoryAlertOutbox()
    now = datetime.now()
    
    # Create candidate with feature diff and prior period data
    candidate = AlertCandidate(
        symbol="GEM_TOKEN",
        window_start=now.isoformat(),
        gem_score=85,
        confidence=0.9,
        safety_ok=True,
        metadata={
            "liquidity_usd": 50000,
            "volume_24h": 100000,
        },
        feature_diff={
            "liquidity_usd": {"before": 20000, "after": 50000, "change_pct": 150},
            "volume_24h": {"before": 30000, "after": 100000, "change_pct": 233},
        },
        prior_period={
            "gem_score": 65,
            "confidence": 0.7,
        }
    )
    
    alerts = evaluate_and_enqueue([candidate], now=now, outbox=outbox, rules=[rule])
    if alerts:
        alert = alerts[0]
        print(f"\n✅ Alert fired with rich context:")
        print(f"   Message: {alert.payload['message']}")
        print(f"\n   Feature Diff:")
        for feature, diff in alert.payload.get('feature_diff', {}).items():
            print(f"      {feature}: {diff['before']} → {diff['after']} ({diff['change_pct']:+.0f}%)")
        print(f"\n   Prior Period Comparison:")
        for metric, value in alert.payload.get('prior_period', {}).items():
            print(f"      Previous {metric}: {value}")


def example_4_backtest():
    """Example 4: Backtesting alert rules on historical data."""
    print("\n" + "=" * 80)
    print("EXAMPLE 4: Backtesting Alert Rules")
    print("=" * 80)
    
    # Create a simple rule
    rule = AlertRule(
        id="high_gem_score",
        score_min=0,
        confidence_min=0,
        safety_ok=True,
        cool_off_minutes=60,
        version="v2",
        condition=SimpleCondition(metric="gem_score", operator="gte", threshold=70),
        severity="info",
    )
    
    # Create historical candidates (simulating 24 hours of data)
    start_time = datetime(2024, 1, 1, 0, 0, 0)
    candidates = []
    
    for hour in range(24):
        timestamp = start_time + timedelta(hours=hour)
        # Simulate various gem scores throughout the day
        gem_score = 50 + (hour % 5) * 10  # Varies between 50-90
        
        candidates.append(AlertCandidate(
            symbol=f"TOKEN_{hour % 3}",  # 3 different tokens
            window_start=timestamp.isoformat() + "Z",
            gem_score=gem_score,
            confidence=0.8,
            safety_ok=True,
            metadata={"hour": hour},
        ))
    
    # Run backtest
    backtester = AlertBacktester([rule])
    end_time = start_time + timedelta(days=1)
    result = backtester.run(candidates, start_time, end_time)
    
    print(f"\n📊 Backtest Results:")
    print(f"   Period: {start_time.date()} (24 hours)")
    print(f"   Candidates evaluated: {result.total_candidates}")
    print(f"   Alerts fired: {result.alerts_fired}")
    print(f"   Alerts suppressed: {result.alerts_suppressed}")
    print(f"\n   Summary:")
    summary = result.summary()
    print(f"      Duration: {summary['period']['duration_hours']:.1f} hours")
    print(f"      Suppression rate: {summary['suppression_rate']:.1%}")
    print(f"      Alerts by rule: {summary['by_rule']}")
    print(f"      Alerts by severity: {summary['by_severity']}")
    
    # Show first few alerts
    print(f"\n   First 3 alerts:")
    for i, alert in enumerate(result.alert_details[:3], 1):
        print(f"      {i}. {alert.timestamp.strftime('%H:%M')} - {alert.symbol} (score: {alert.context['gem_score']})")


def example_5_rule_comparison():
    """Example 5: Comparing different rule versions."""
    print("\n" + "=" * 80)
    print("EXAMPLE 5: Comparing Rule Versions")
    print("=" * 80)
    
    # Version 1: Strict thresholds
    rules_v1 = [
        AlertRule(
            id="strict_rule",
            score_min=75,  # Higher threshold
            confidence_min=0.8,
            safety_ok=True,
            cool_off_minutes=60,
            version="v1",
        )
    ]
    
    # Version 2: More lenient thresholds
    rules_v2 = [
        AlertRule(
            id="lenient_rule",
            score_min=0,
            confidence_min=0,
            safety_ok=True,
            cool_off_minutes=60,
            version="v2",
            condition=SimpleCondition(metric="gem_score", operator="gte", threshold=65),  # Lower threshold
        )
    ]
    
    # Create test candidates
    start_time = datetime(2024, 1, 1, 0, 0, 0)
    candidates = [
        AlertCandidate(
            symbol=f"TOKEN_{i}",
            window_start=(start_time + timedelta(hours=i)).isoformat() + "Z",
            gem_score=65 + (i % 3) * 5,  # Scores: 65, 70, 75, 65, 70, ...
            confidence=0.85,
            safety_ok=True,
        )
        for i in range(10)
    ]
    
    # Compare versions
    from src.alerts.backtest import compare_rule_versions
    
    end_time = start_time + timedelta(hours=12)
    results = compare_rule_versions(candidates, rules_v1, rules_v2, start_time, end_time)
    
    print(f"\n📊 Version Comparison:")
    print(f"   V1 (strict): {results['v1'].alerts_fired} alerts")
    print(f"   V2 (lenient): {results['v2'].alerts_fired} alerts")
    print(f"   Difference: {results['comparison']['alert_diff']:+d} alerts")
    print(f"\n   V1 would have missed {results['comparison']['alert_diff']} opportunities!")


def example_6_escalation_policies():
    """Example 6: Alert escalation policies."""
    print("\n" + "=" * 80)
    print("EXAMPLE 6: Escalation Policies")
    print("=" * 80)
    
    rule = AlertRule(
        id="critical_with_escalation",
        score_min=0,
        confidence_min=0,
        safety_ok=True,
        cool_off_minutes=30,
        version="v2",
        condition=SimpleCondition(metric="gem_score", operator="lt", threshold=20),
        severity="critical",
        escalation_policy="immediate",  # References escalation policy from config
        message_template="🚨 CRITICAL: Very low score ({gem_score}) for {symbol}",
        tags=["risk", "urgent"],
    )
    
    outbox = InMemoryAlertOutbox()
    now = datetime.now()
    
    candidate = AlertCandidate(
        symbol="DANGER_TOKEN",
        window_start=now.isoformat(),
        gem_score=15,
        confidence=0.9,
        safety_ok=False,
        metadata={"honeypot_detected": True},
    )
    
    alerts = evaluate_and_enqueue([candidate], now=now, outbox=outbox, rules=[rule])
    if alerts:
        alert = alerts[0]
        print(f"\n✅ Critical alert with escalation:")
        print(f"   Message: {alert.payload['message']}")
        print(f"   Severity: {alert.payload['severity']}")
        print(f"   Escalation Policy: {alert.payload['escalation_policy']}")
        print(f"   Tags: {alert.payload['tags']}")
        print(f"   Channels: {alert.payload['channels']}")


def main():
    """Run all examples."""
    print("\n" + "=" * 80)
    print("EXPANDED ALERT RULE ENGINE DEMONSTRATION")
    print("=" * 80)
    
    example_1_compound_conditions()
    example_2_nested_conditions()
    example_3_templated_messages()
    example_4_backtest()
    example_5_rule_comparison()
    example_6_escalation_policies()
    
    print("\n" + "=" * 80)
    print("✅ All examples completed successfully!")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()

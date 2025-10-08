"""
Example: Alert Engine v2 Usage

Demonstrates compound conditions, suppression, and escalation policies.
"""

from src.services.alerting_v2 import (
    AlertCondition, CompoundCondition, AlertRule, AlertManager,
    SuppressionRule, EscalationPolicy
)
from datetime import timedelta
from src.core.logging_config import get_logger

logger = get_logger(__name__)


def example_simple_alert():
    """Example 1: Simple threshold alert."""
    print("\n" + "="*60)
    print("EXAMPLE 1: Simple Threshold Alert")
    print("="*60)
    
    manager = AlertManager()
    
    # Create rule: gem_score < 30
    condition = AlertCondition(
        metric="gem_score",
        operator="lt",
        threshold=30
    )
    
    rule = AlertRule(
        id="low_score",
        name="Low GemScore Warning",
        condition=condition,
        severity="warning",
        message="Token has low GemScore: {gem_score}"
    )
    
    manager.add_rule(rule)
    
    # Test data
    metrics = {"gem_score": 25}
    print(f"\nEvaluating metrics: {metrics}")
    
    alerts = manager.evaluate(metrics)
    
    if alerts:
        for alert in alerts:
            print(f"\n🚨 ALERT FIRED:")
            print(f"   Rule: {alert.rule_id}")
            print(f"   Severity: {alert.severity}")
            print(f"   Message: {alert.message}")
    else:
        print("✅ No alerts fired")


def example_compound_and():
    """Example 2: Compound AND condition."""
    print("\n" + "="*60)
    print("EXAMPLE 2: Compound AND Condition")
    print("="*60)
    
    manager = AlertManager()
    
    # Create rule: (gem_score < 30) AND (honeypot_detected == True)
    condition = CompoundCondition(
        operator="AND",
        conditions=[
            AlertCondition("gem_score", "lt", 30),
            AlertCondition("honeypot_detected", "eq", True)
        ]
    )
    
    rule = AlertRule(
        id="critical_risk",
        name="Critical Risk Detected",
        condition=condition,
        severity="critical",
        message="CRITICAL: Low score ({gem_score}) AND honeypot detected!"
    )
    
    manager.add_rule(rule)
    
    # Test case 1: Both conditions true
    metrics1 = {"gem_score": 25, "honeypot_detected": True}
    print(f"\nTest 1 - Both true: {metrics1}")
    alerts1 = manager.evaluate(metrics1)
    print(f"Result: {'🚨 ALERT' if alerts1 else '✅ No alert'}")
    
    # Test case 2: Only one condition true
    metrics2 = {"gem_score": 25, "honeypot_detected": False}
    print(f"\nTest 2 - One true: {metrics2}")
    alerts2 = manager.evaluate(metrics2)
    print(f"Result: {'🚨 ALERT' if alerts2 else '✅ No alert'}")


def example_nested_conditions():
    """Example 3: Complex nested conditions."""
    print("\n" + "="*60)
    print("EXAMPLE 3: Nested Compound Conditions")
    print("="*60)
    
    manager = AlertManager()
    
    # Create rule: (gem_score >= 70) AND ((liquidity < 10000) OR (safety < 0.5))
    condition = CompoundCondition(
        operator="AND",
        conditions=[
            AlertCondition("gem_score", "gte", 70),
            CompoundCondition(
                operator="OR",
                conditions=[
                    AlertCondition("liquidity_usd", "lt", 10000),
                    AlertCondition("safety_score", "lt", 0.5)
                ]
            )
        ]
    )
    
    rule = AlertRule(
        id="suspicious_high_score",
        name="Suspicious High Score",
        condition=condition,
        severity="warning",
        message="High score ({gem_score}) but red flags: liquidity=${liquidity_usd}, safety={safety_score}"
    )
    
    manager.add_rule(rule)
    
    # Test case 1: High score + low liquidity
    metrics1 = {"gem_score": 75, "liquidity_usd": 5000, "safety_score": 0.8}
    print(f"\nTest 1 - High score + low liquidity: {metrics1}")
    alerts1 = manager.evaluate(metrics1)
    if alerts1:
        print(f"🚨 ALERT: {alerts1[0].message}")
    else:
        print("✅ No alert")
    
    # Test case 2: High score + low safety
    metrics2 = {"gem_score": 80, "liquidity_usd": 50000, "safety_score": 0.3}
    print(f"\nTest 2 - High score + low safety: {metrics2}")
    alerts2 = manager.evaluate(metrics2)
    if alerts2:
        print(f"🚨 ALERT: {alerts2[0].message}")
    else:
        print("✅ No alert")
    
    # Test case 3: High score + all good
    metrics3 = {"gem_score": 75, "liquidity_usd": 50000, "safety_score": 0.8}
    print(f"\nTest 3 - High score + all good: {metrics3}")
    alerts3 = manager.evaluate(metrics3)
    print(f"Result: {'🚨 ALERT' if alerts3 else '✅ No alert (expected)'}")


def example_suppression():
    """Example 4: Alert suppression and deduplication."""
    print("\n" + "="*60)
    print("EXAMPLE 4: Alert Suppression")
    print("="*60)
    
    manager = AlertManager()
    
    # Add rule
    condition = AlertCondition("gem_score", "lt", 30)
    rule = AlertRule(
        id="low_score",
        name="Low Score",
        condition=condition,
        severity="warning"
    )
    manager.add_rule(rule)
    
    # Add suppression rule (pattern-based)
    suppression = SuppressionRule(
        pattern=r".*test.*",
        field="token_name",
        duration=timedelta(hours=1)
    )
    manager.add_suppression_rule(suppression)
    
    metrics = {"gem_score": 25}
    
    # First evaluation
    print("\n1️⃣ First evaluation (same metrics):")
    alerts1 = manager.evaluate(metrics)
    print(f"   Alerts fired: {len(alerts1)}")
    
    # Second evaluation (should be suppressed due to deduplication)
    print("\n2️⃣ Second evaluation (same metrics):")
    alerts2 = manager.evaluate(metrics)
    print(f"   Alerts fired: {len(alerts2)} (suppressed by deduplication)")
    
    # Third evaluation (different metrics)
    print("\n3️⃣ Third evaluation (different metrics):")
    different_metrics = {"gem_score": 20}  # Different value
    alerts3 = manager.evaluate(different_metrics)
    print(f"   Alerts fired: {len(alerts3)} (new fingerprint)")
    
    # Show stats
    from src.core.metrics import ALERTS_FIRED, ALERTS_SUPPRESSED
    print(f"\n📊 Stats:")
    print(f"   Total fired: {ALERTS_FIRED._value.get()}")
    print(f"   Total suppressed: {ALERTS_SUPPRESSED._value.get()}")


def example_escalation():
    """Example 5: Escalation policies."""
    print("\n" + "="*60)
    print("EXAMPLE 5: Escalation Policies")
    print("="*60)
    
    manager = AlertManager()
    
    # Create escalation policy
    escalation = EscalationPolicy(
        levels=[
            {"delay": timedelta(seconds=0), "channels": ["slack"]},
            {"delay": timedelta(minutes=5), "channels": ["telegram"]},
            {"delay": timedelta(minutes=15), "channels": ["pagerduty"]}
        ]
    )
    
    # Create rule with escalation
    condition = AlertCondition("gem_score", "lt", 20)
    rule = AlertRule(
        id="critical_with_escalation",
        name="Critical with Escalation",
        condition=condition,
        severity="critical",
        escalation_policy=escalation,
        message="Critical: GemScore is {gem_score}"
    )
    
    manager.add_rule(rule)
    
    # Trigger alert
    metrics = {"gem_score": 15}
    print(f"\nEvaluating: {metrics}")
    
    alerts = manager.evaluate(metrics)
    
    if alerts:
        alert = alerts[0]
        print(f"\n🚨 Alert fired with escalation:")
        print(f"   Rule: {alert.rule_id}")
        print(f"   Severity: {alert.severity}")
        
        print(f"\n📢 Escalation schedule:")
        for i, level in enumerate(alert.escalation_policy.levels, 1):
            print(f"   Level {i}: {level['channels']} (delay: {level['delay']})")


def example_production_workflow():
    """Example 6: Production workflow with multiple rules."""
    print("\n" + "="*60)
    print("EXAMPLE 6: Production Workflow")
    print("="*60)
    
    manager = AlertManager()
    
    # Add multiple rules
    rules = [
        AlertRule(
            id="critical_risk",
            name="Critical Risk",
            condition=CompoundCondition("AND", [
                AlertCondition("gem_score", "lt", 30),
                AlertCondition("honeypot_detected", "eq", True)
            ]),
            severity="critical",
            message="Critical risk: score={gem_score}, honeypot=true"
        ),
        AlertRule(
            id="low_liquidity",
            name="Low Liquidity",
            condition=AlertCondition("liquidity_usd", "lt", 10000),
            severity="warning",
            message="Low liquidity: ${liquidity_usd}"
        ),
        AlertRule(
            id="high_gem",
            name="High Quality Gem",
            condition=CompoundCondition("AND", [
                AlertCondition("gem_score", "gte", 85),
                AlertCondition("safety_score", "gte", 0.8)
            ]),
            severity="info",
            message="High quality opportunity: score={gem_score}"
        )
    ]
    
    for rule in rules:
        manager.add_rule(rule)
    
    print(f"\n✅ Loaded {len(rules)} alert rules")
    
    # Test with production-like data
    test_cases = [
        {
            "name": "Critical token",
            "metrics": {
                "gem_score": 25,
                "honeypot_detected": True,
                "liquidity_usd": 5000,
                "safety_score": 0.3
            }
        },
        {
            "name": "High quality gem",
            "metrics": {
                "gem_score": 90,
                "honeypot_detected": False,
                "liquidity_usd": 100000,
                "safety_score": 0.9
            }
        },
        {
            "name": "Medium token",
            "metrics": {
                "gem_score": 60,
                "honeypot_detected": False,
                "liquidity_usd": 50000,
                "safety_score": 0.7
            }
        }
    ]
    
    for test_case in test_cases:
        print(f"\n📊 Testing: {test_case['name']}")
        print(f"   Metrics: {test_case['metrics']}")
        
        alerts = manager.evaluate(test_case['metrics'])
        
        if alerts:
            print(f"   🚨 Alerts: {len(alerts)}")
            for alert in alerts:
                print(f"      - [{alert.severity}] {alert.message}")
        else:
            print("   ✅ No alerts")
    
    # Show summary
    print(f"\n📈 Summary:")
    print(f"   Rules configured: {len(manager.rules)}")
    print(f"   Active alerts: {len(manager.get_active_alerts())}")


if __name__ == "__main__":
    print("🚨 Alert Engine v2 Examples")
    print("="*60)
    
    # Run all examples
    example_simple_alert()
    example_compound_and()
    example_nested_conditions()
    example_suppression()
    example_escalation()
    example_production_workflow()
    
    print("\n" + "="*60)
    print("✅ All examples completed!")
    print("="*60)

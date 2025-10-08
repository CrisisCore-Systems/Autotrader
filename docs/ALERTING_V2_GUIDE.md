# Alert Engine v2 - Comprehensive Guide

## 🚨 Overview

Alert Engine v2 provides advanced alerting capabilities with:

- **Compound Conditions**: Complex alert logic using AND/OR/NOT operators
- **Alert Suppression**: Prevent alert fatigue with time-based suppression
- **Deduplication**: Fingerprint-based duplicate detection
- **Escalation Policies**: Multi-level notification with time delays
- **Alert Lifecycle**: Complete state management (firing, resolved, acknowledged, suppressed)

## 📚 Table of Contents

- [Quick Start](#quick-start)
- [Core Concepts](#core-concepts)
- [API Reference](#api-reference)
- [Configuration](#configuration)
- [Examples](#examples)
- [Best Practices](#best-practices)
- [Integration](#integration)

## 🚀 Quick Start

### Basic Alert Rule

```python
from src.services.alerting_v2 import AlertCondition, AlertRule, AlertManager

# Create alert manager
manager = AlertManager()

# Simple condition: gem_score < 30
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

# Evaluate
metrics = {"gem_score": 25}
alerts = manager.evaluate(metrics)
```

### Compound Condition

```python
from src.services.alerting_v2 import CompoundCondition

# Complex logic: (gem_score < 30) AND (honeypot_detected == true)
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
    severity="critical"
)
```

## 🧠 Core Concepts

### 1. Alert Conditions

Three types of conditions:

#### Simple Condition

Tests a single metric:

```python
AlertCondition(
    metric="liquidity_usd",
    operator="lt",
    threshold=10000
)
```

**Operators**: `eq`, `ne`, `gt`, `gte`, `lt`, `lte`, `in`, `not_in`, `contains`

#### Compound Condition (AND)

All conditions must be true:

```python
CompoundCondition(
    operator="AND",
    conditions=[
        AlertCondition("gem_score", "gte", 70),
        AlertCondition("safety_score", "gte", 0.7)
    ]
)
```

#### Compound Condition (OR)

At least one condition must be true:

```python
CompoundCondition(
    operator="OR",
    conditions=[
        AlertCondition("honeypot_detected", "eq", True),
        AlertCondition("rug_pull_risk", "gte", 0.8)
    ]
)
```

#### Compound Condition (NOT)

Inverts the result:

```python
CompoundCondition(
    operator="NOT",
    conditions=[
        AlertCondition("contract_verified", "eq", True)
    ]
)
```

### 2. Nested Conditions

Combine operators for complex logic:

```python
# High score BUT (low liquidity OR low safety)
CompoundCondition(
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
```

### 3. Alert Fingerprinting

Alerts are deduplicated using fingerprints:

```python
# Fingerprint = hash(rule_id + sorted_metrics)
alert.fingerprint  # "abc123..."

# Same metrics = same fingerprint = suppressed
```

### 4. Suppression Rules

Prevent alert spam:

```python
from src.services.alerting_v2 import SuppressionRule
from datetime import timedelta

# Suppress test tokens
suppression = SuppressionRule(
    pattern=r".*test.*",
    field="token_name",
    duration=timedelta(hours=1)
)

manager.add_suppression_rule(suppression)
```

### 5. Escalation Policies

Multi-level notifications:

```python
from src.services.alerting_v2 import EscalationPolicy

policy = EscalationPolicy(
    levels=[
        {"delay": timedelta(0), "channels": ["slack"]},
        {"delay": timedelta(minutes=5), "channels": ["telegram"]},
        {"delay": timedelta(minutes=15), "channels": ["pagerduty"]}
    ]
)

rule = AlertRule(
    id="critical",
    condition=condition,
    escalation_policy=policy
)
```

## 📖 API Reference

### AlertCondition

```python
AlertCondition(
    metric: str,          # Metric name
    operator: str,        # Comparison operator
    threshold: Any        # Comparison value
)
```

### CompoundCondition

```python
CompoundCondition(
    operator: str,                    # "AND", "OR", "NOT"
    conditions: List[Condition]       # Child conditions
)
```

### AlertRule

```python
AlertRule(
    id: str,                          # Unique identifier
    name: str,                        # Human-readable name
    condition: Condition,             # Alert condition
    severity: str = "info",          # Severity level
    message: str = "",               # Alert message (supports {metric} placeholders)
    tags: Optional[Dict] = None,     # Metadata
    suppression_duration: Optional[timedelta] = None,
    escalation_policy: Optional[EscalationPolicy] = None
)
```

### AlertManager

```python
manager = AlertManager()

# Add rules
manager.add_rule(rule)

# Add suppression
manager.add_suppression_rule(suppression)

# Evaluate metrics
alerts = manager.evaluate(metrics: Dict[str, Any]) -> List[Alert]

# Alert lifecycle
manager.resolve_alert(alert_id: str, resolution: str)
manager.acknowledge_alert(alert_id: str, acknowledged_by: str)

# Query
active_alerts = manager.get_active_alerts()
alert_history = manager.get_alert_history(hours=24)
```

## ⚙️ Configuration

### YAML Configuration

```yaml
rules:
  - id: critical_risk_token
    description: "Critical risk: low GemScore AND honeypot detected"
    condition:
      type: compound
      operator: AND
      conditions:
        - metric: gem_score
          operator: lt
          threshold: 30
        - metric: honeypot_detected
          operator: eq
          threshold: true
    severity: critical
    channels: [telegram, slack, pagerduty]
    escalation_policy: immediate
    suppression_duration: 3600
    version: v2

suppression:
  - pattern: ".*test.*token.*"
    field: token_name
    duration: 86400

escalation_policies:
  immediate:
    levels:
      - delay: 0
        channels: [telegram, slack, pagerduty]
```

### Loading Configuration

```python
import yaml
from pathlib import Path

# Load rules from YAML
config_path = Path("configs/alert_rules.yaml")
with open(config_path) as f:
    config = yaml.safe_load(f)

# Parse and add rules
for rule_config in config['rules']:
    if rule_config.get('version') == 'v2':
        rule = parse_rule_from_config(rule_config)
        manager.add_rule(rule)
```

## 💡 Examples

### Example 1: Market Manipulation Detection

```python
manipulation_condition = CompoundCondition(
    operator="AND",
    conditions=[
        # High holder concentration OR suspicious buy pressure
        CompoundCondition(
            operator="OR",
            conditions=[
                AlertCondition("holder_concentration_top10", "gt", 80),
                AlertCondition("buy_sell_ratio_1h", "gt", 5.0)
            ]
        ),
        # Rapid price increase + new contract
        CompoundCondition(
            operator="AND",
            conditions=[
                AlertCondition("price_change_1h", "gt", 50),
                AlertCondition("contract_age_hours", "lt", 24)
            ]
        )
    ]
)

rule = AlertRule(
    id="potential_manipulation",
    name="Potential Market Manipulation",
    condition=manipulation_condition,
    severity="critical",
    message="Manipulation pattern detected: concentration={holder_concentration_top10}%, price_change={price_change_1h}%"
)
```

### Example 2: Opportunity Alert

```python
gem_opportunity = CompoundCondition(
    operator="AND",
    conditions=[
        AlertCondition("gem_score", "gte", 85),
        AlertCondition("liquidity_usd", "gte", 50000),
        AlertCondition("contract_age_hours", "lt", 168),  # < 1 week
        AlertCondition("honeypot_detected", "eq", False),
        AlertCondition("safety_score", "gte", 0.8)
    ]
)

rule = AlertRule(
    id="exceptional_gem",
    name="Exceptional Gem Opportunity",
    condition=gem_opportunity,
    severity="info",
    message="🔥 High-quality opportunity found: score={gem_score}, liquidity=${liquidity_usd}"
)
```

### Example 3: Model Performance Degradation

```python
performance_condition = CompoundCondition(
    operator="AND",
    conditions=[
        AlertCondition("avg_confidence_1h", "lt", 0.6),
        AlertCondition("predictions_count_1h", "gte", 10)
    ]
)

rule = AlertRule(
    id="model_degradation",
    name="Model Performance Degradation",
    condition=performance_condition,
    severity="warning",
    message="Model confidence dropped to {avg_confidence_1h:.2f} over {predictions_count_1h} predictions",
    escalation_policy=progressive_policy
)
```

### Example 4: Progressive Suppression

```python
from datetime import datetime

# Custom suppression logic
def should_suppress(alert: Alert) -> bool:
    # Suppress if fired in last hour
    recent_alerts = [
        a for a in manager.alert_history
        if a.fingerprint == alert.fingerprint
        and (datetime.utcnow() - a.created_at).seconds < 3600
    ]
    return len(recent_alerts) > 0

# Apply during evaluation
if not should_suppress(alert):
    manager.fire_alert(alert)
```

## 🎯 Best Practices

### 1. Rule Design

✅ **DO**:
- Use descriptive rule IDs and names
- Include relevant metrics in messages
- Set appropriate severity levels
- Test conditions with sample data

❌ **DON'T**:
- Create overlapping rules
- Use overly complex nested conditions
- Ignore suppression duration
- Forget to validate thresholds

### 2. Suppression Strategy

```python
# Good: Tiered suppression based on severity
critical_suppression = timedelta(minutes=10)
warning_suppression = timedelta(hours=1)
info_suppression = timedelta(hours=6)

# Good: Pattern-based suppression
test_pattern = r".*(test|demo|example).*"
staging_pattern = r".*staging.*"
```

### 3. Escalation Design

```python
# Progressive escalation for non-critical
progressive = EscalationPolicy([
    {"delay": timedelta(0), "channels": ["slack"]},
    {"delay": timedelta(minutes=5), "channels": ["telegram"]},
    {"delay": timedelta(minutes=15), "channels": ["pagerduty"]}
])

# Immediate for critical
immediate = EscalationPolicy([
    {"delay": timedelta(0), "channels": ["telegram", "slack", "pagerduty"]}
])
```

### 4. Monitoring

```python
from src.core.metrics import ALERTS_FIRED, ALERTS_SUPPRESSED, ACTIVE_ALERTS

# Track alert metrics
print(f"Alerts fired: {ALERTS_FIRED._value.get()}")
print(f"Alerts suppressed: {ALERTS_SUPPRESSED._value.get()}")
print(f"Active alerts: {ACTIVE_ALERTS._value.get()}")
```

### 5. Testing

```python
def test_alert_rule():
    manager = AlertManager()
    manager.add_rule(rule)
    
    # Test positive case
    metrics_critical = {"gem_score": 25, "honeypot_detected": True}
    alerts = manager.evaluate(metrics_critical)
    assert len(alerts) == 1
    
    # Test negative case
    metrics_safe = {"gem_score": 75, "honeypot_detected": False}
    alerts = manager.evaluate(metrics_safe)
    assert len(alerts) == 0
```

## 🔗 Integration

### With Existing Observability

```python
from src.core.logging_config import get_logger
from src.core.metrics import ALERTS_FIRED

logger = get_logger(__name__)

# Log alert events
for alert in alerts:
    logger.warning(
        "alert_fired",
        alert_id=alert.id,
        rule_id=alert.rule_id,
        severity=alert.severity,
        fingerprint=alert.fingerprint
    )
    ALERTS_FIRED.labels(
        rule_id=alert.rule_id,
        severity=alert.severity
    ).inc()
```

### With Drift Monitor

```python
from src.monitoring.drift_monitor import DriftMonitor

# Create drift alert rule
drift_condition = CompoundCondition(
    operator="OR",
    conditions=[
        AlertCondition("drift_ks_statistic", "gt", 0.3),
        AlertCondition("drift_psi_score", "gt", 0.2)
    ]
)

drift_rule = AlertRule(
    id="feature_drift",
    condition=drift_condition,
    severity="high",
    message="Feature drift detected: KS={drift_ks_statistic:.3f}, PSI={drift_psi_score:.3f}"
)

# Monitor and alert
drift_report = drift_monitor.detect_drift(baseline, features, predictions)
drift_metrics = {
    "drift_ks_statistic": max(r.ks_statistic for r in drift_report.feature_drift.values()),
    "drift_psi_score": max(r.psi for r in drift_report.feature_drift.values())
}

alerts = manager.evaluate(drift_metrics)
```

### With Notification Services

```python
import requests

def send_telegram_alert(alert: Alert):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    message = f"🚨 {alert.severity.upper()}\n\n{alert.message}"
    requests.post(url, json={"chat_id": CHAT_ID, "text": message})

def send_slack_alert(alert: Alert):
    webhook_url = SLACK_WEBHOOK
    payload = {
        "text": alert.message,
        "attachments": [{
            "color": "danger" if alert.severity == "critical" else "warning",
            "fields": [
                {"title": "Rule", "value": alert.rule_id, "short": True},
                {"title": "Severity", "value": alert.severity, "short": True}
            ]
        }]
    }
    requests.post(webhook_url, json=payload)

# Send alerts
for alert in alerts:
    if "telegram" in alert.channels:
        send_telegram_alert(alert)
    if "slack" in alert.channels:
        send_slack_alert(alert)
```

## 📊 Metrics

Alert Engine v2 exposes Prometheus metrics:

```
# Total alerts fired
alerts_fired_total{rule_id="critical_risk", severity="critical"} 42

# Total alerts suppressed
alerts_suppressed_total{rule_id="critical_risk", reason="duplicate"} 15

# Current active alerts
active_alerts{severity="warning"} 3

# Alert evaluation time
alert_evaluation_seconds{rule_id="critical_risk"} 0.002
```

## 🐛 Troubleshooting

### Alerts Not Firing

```python
# Debug condition evaluation
condition = rule.condition
result = condition.evaluate(metrics)
print(f"Condition result: {result}")

# Check metric values
print(f"Metrics: {metrics}")
```

### Excessive Alert Volume

```python
# Check suppression
print(f"Suppressed: {ALERTS_SUPPRESSED._value.get()}")

# Review suppression rules
for suppression in manager.suppression_rules:
    print(f"Pattern: {suppression.pattern}")
    print(f"Duration: {suppression.duration}")
```

### Alert State Issues

```python
# Check alert history
history = manager.get_alert_history(hours=24)
for alert in history:
    print(f"{alert.id}: {alert.status} at {alert.created_at}")

# Verify state transitions
active = manager.get_active_alerts()
print(f"Active alerts: {len(active)}")
```

## 📚 Additional Resources

- [Alert Rules Configuration](../configs/alert_rules.yaml)
- [Observability Guide](OBSERVABILITY_GUIDE.md)
- [Drift Monitoring Guide](DRIFT_MONITORING_GUIDE.md)
- [Jupyter Notebook Demo](../notebooks/hidden_gem_scanner.ipynb)

## 🚀 What's Next?

- **Alert Templates**: Reusable condition templates
- **ML-Based Thresholds**: Dynamic threshold adjustment
- **Alert Aggregation**: Group related alerts
- **Custom Operators**: User-defined comparison logic
- **Alert Correlation**: Identify related incidents

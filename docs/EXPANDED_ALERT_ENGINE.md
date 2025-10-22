# Expanded Alert Rule Engine

The alert rule engine has been significantly enhanced to support advanced features for production alerting systems. This document describes the new capabilities and how to use them.

## Overview

The expanded alert engine now supports:
- **Compound Logic**: AND, OR, NOT operators for complex alert conditions
- **Nested Conditions**: Arbitrary nesting of compound conditions
- **Backtestable Alerts**: Historical analysis and optimization of alert rules
- **Templated Messages**: Context-aware alert messages with feature diffs and prior period comparisons
- **Enhanced Suppression**: Configurable suppression/cool-off periods
- **Escalation Policies**: Multi-level alert escalation

## Features

### 1. Compound Conditions

Define complex alert logic using compound conditions with AND, OR, and NOT operators.

#### Simple Condition
```python
from src.alerts import SimpleCondition

# Alert when gem_score > 70
condition = SimpleCondition(
    metric="gem_score",
    operator="gt",
    threshold=70
)
```

#### Compound AND Condition
```python
from src.alerts import CompoundCondition, SimpleCondition

# Alert when (gem_score < 30) AND (honeypot_detected = true)
condition = CompoundCondition(
    operator="AND",
    conditions=(
        SimpleCondition(metric="gem_score", operator="lt", threshold=30),
        SimpleCondition(metric="honeypot_detected", operator="eq", threshold=True),
    )
)
```

#### Nested Conditions
```python
# Alert when (gem_score >= 70) AND ((liquidity < 10000) OR (safety_score < 0.5))
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
```

#### Supported Operators

**Comparison Operators:**
- `gt`, `>`: Greater than
- `gte`, `>=`, `ge`: Greater than or equal
- `lt`, `<`: Less than
- `lte`, `<=`, `le`: Less than or equal
- `eq`, `==`: Equal
- `neq`, `!=`: Not equal

**Logical Operators:**
- `AND`: All conditions must be true
- `OR`: At least one condition must be true
- `NOT`: Negation of conditions

### 2. Alert Rules V2

Create enhanced alert rules with compound conditions:

```python
from src.alerts import AlertRule, CompoundCondition, SimpleCondition

rule = AlertRule(
    id="critical_risk",
    score_min=0,  # Not used in v2
    confidence_min=0,
    safety_ok=True,
    cool_off_minutes=60,
    version="v2",  # Important: specify v2
    condition=CompoundCondition(...),  # Your compound condition
    severity="critical",
    message_template="Alert: {symbol} score={gem_score}",
    escalation_policy="immediate",
    tags=["risk", "urgent"],
)
```

### 3. Templated Messages

Alert messages support template variables that are replaced with actual values:

```python
rule = AlertRule(
    id="liquidity_alert",
    # ... other fields ...
    message_template=(
        "💎 GEM: {symbol} scored {gem_score} (confidence: {confidence})\n"
        "Liquidity: ${liquidity_usd} | Volume: ${volume_24h}"
    ),
)
```

All metrics in the candidate context are available for template substitution.

### 4. Feature Diffs and Prior Period Comparison

Include feature changes and historical comparisons in alerts:

```python
from src.alerts import AlertCandidate

candidate = AlertCandidate(
    symbol="TOKEN",
    window_start="2024-01-01T00:00:00Z",
    gem_score=85,
    confidence=0.9,
    safety_ok=True,
    metadata={
        "liquidity_usd": 50000,
        "volume_24h": 100000,
    },
    # Feature differences from previous period
    feature_diff={
        "liquidity_usd": {
            "before": 20000,
            "after": 50000,
            "change_pct": 150
        },
        "volume_24h": {
            "before": 30000,
            "after": 100000,
            "change_pct": 233
        },
    },
    # Prior period metrics for comparison
    prior_period={
        "gem_score": 65,
        "confidence": 0.7,
    }
)
```

These are automatically included in the alert payload for reference.

### 5. Backtesting

Test alert rules on historical data to evaluate their effectiveness:

```python
from src.alerts import AlertBacktester
from datetime import datetime, timedelta

# Create backtester with your rules
backtester = AlertBacktester([rule1, rule2])

# Run on historical data
start_time = datetime(2024, 1, 1, 0, 0, 0)
end_time = datetime(2024, 1, 2, 0, 0, 0)
result = backtester.run(candidates, start_time, end_time)

# Analyze results
print(f"Alerts fired: {result.alerts_fired}")
print(f"Suppression rate: {result.summary()['suppression_rate']:.1%}")
print(f"By severity: {result.alerts_by_severity}")
```

#### Compare Rule Versions

Compare different rule configurations to find optimal thresholds:

```python
from src.alerts.backtest import compare_rule_versions

results = compare_rule_versions(
    candidates,
    rules_v1,  # Original rules
    rules_v2,  # Updated rules
    start_time,
    end_time
)

print(f"V1 alerts: {results['v1'].alerts_fired}")
print(f"V2 alerts: {results['v2'].alerts_fired}")
print(f"Difference: {results['comparison']['alert_diff']}")
```

### 6. Configuration via YAML

Define rules in YAML for easy configuration:

```yaml
rules:
  - id: critical_risk
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
    suppression_duration: 3600  # 1 hour
    version: v2

  - id: nested_example
    description: "High score but with red flags"
    condition:
      type: compound
      operator: AND
      conditions:
        - metric: gem_score
          operator: gte
          threshold: 70
        - type: compound
          operator: OR
          conditions:
            - metric: liquidity_usd
              operator: lt
              threshold: 10000
            - metric: safety_score
              operator: lt
              threshold: 0.5
    severity: warning
    channels: [slack]
    suppression_duration: 1800
    version: v2
```

Load rules from YAML:

```python
from src.alerts.rules import load_rules

rules = load_rules("configs/alert_rules.yaml")
```

## Migration Guide

### From V1 to V2

**V1 Rule (simple thresholds):**
```python
rule_v1 = AlertRule(
    id="my_rule",
    score_min=70,
    confidence_min=0.75,
    safety_ok=True,
    cool_off_minutes=240,
    version="v1",
)
```

**V2 Rule (compound conditions):**
```python
rule_v2 = AlertRule(
    id="my_rule",
    score_min=0,  # Not used
    confidence_min=0,
    safety_ok=True,
    cool_off_minutes=240,
    version="v2",
    condition=CompoundCondition(
        operator="AND",
        conditions=(
            SimpleCondition(metric="gem_score", operator="gte", threshold=70),
            SimpleCondition(metric="confidence", operator="gte", threshold=0.75),
            SimpleCondition(metric="safety_ok", operator="eq", threshold=True),
        )
    ),
)
```

**Backward Compatibility:**
V1 rules continue to work without modification. The engine automatically detects the version and uses the appropriate evaluation method.

## Examples

See `examples/expanded_alert_engine_demo.py` for comprehensive examples including:
1. Compound conditions (AND, OR)
2. Nested compound conditions
3. Templated messages with context
4. Backtesting on historical data
5. Comparing rule versions
6. Escalation policies

Run the demo:
```bash
python examples/expanded_alert_engine_demo.py
```

## API Reference

### Classes

#### `SimpleCondition`
Single metric comparison condition.

**Parameters:**
- `metric` (str): Metric name to evaluate
- `operator` (str): Comparison operator (gt, lt, gte, lte, eq, neq)
- `threshold` (Any): Threshold value

#### `CompoundCondition`
Compound condition with logical operators.

**Parameters:**
- `operator` (str): Logical operator (AND, OR, NOT)
- `conditions` (tuple): Tuple of SimpleCondition or CompoundCondition instances

#### `AlertRule`
Alert rule configuration with v2 enhancements.

**Key V2 Parameters:**
- `version` (str): "v2" for compound conditions
- `condition` (CompoundCondition | SimpleCondition): Rule condition
- `severity` (str): Alert severity (info, warning, high, critical)
- `message_template` (str): Template string for alert message
- `escalation_policy` (Optional[str]): Escalation policy name
- `suppression_duration` (int): Suppression period in seconds
- `tags` (Sequence[str]): Alert tags

#### `AlertCandidate`
Alert candidate with enhanced context.

**Enhanced Parameters:**
- `feature_diff` (Optional[Dict]): Feature changes from previous period
- `prior_period` (Optional[Dict]): Prior period metrics for comparison

#### `AlertBacktester`
Backtester for historical alert analysis.

**Methods:**
- `run(candidates, start_time, end_time)`: Run backtest
- `evaluate_thresholds(...)`: Evaluate different threshold values

#### `BacktestResult`
Results from backtesting.

**Attributes:**
- `total_candidates`: Number of candidates evaluated
- `alerts_fired`: Number of alerts fired
- `alerts_suppressed`: Number of suppressed alerts
- `alerts_by_rule`: Alerts grouped by rule
- `alerts_by_severity`: Alerts grouped by severity
- `alert_details`: List of BacktestAlert instances

**Methods:**
- `summary()`: Get summary statistics

## Testing

Run tests for the expanded alert engine:

```bash
# Test compound conditions
pytest tests/test_compound_conditions.py -v

# Test backtesting
pytest tests/test_alert_backtest.py -v

# Test backward compatibility
pytest tests/test_alerts_engine.py -v
```

## Performance Considerations

- **Nested Conditions**: Keep nesting depth reasonable (< 5 levels) for performance
- **Backtest Size**: For large datasets, consider chunking candidates
- **Suppression**: Use appropriate cool-off periods to avoid spam
- **Template Complexity**: Keep message templates simple for fast formatting

## Best Practices

1. **Start Simple**: Begin with simple conditions and add complexity as needed
2. **Test First**: Use backtesting to validate rules before production deployment
3. **Monitor Suppression**: Check suppression rates to ensure alerts aren't over-suppressed
4. **Use Severity Levels**: Properly categorize alerts by severity for escalation
5. **Template Variables**: Include key context in message templates for actionability
6. **Version Rules**: Use semantic versioning for rule IDs to track changes

## Troubleshooting

### Alert Not Firing

1. Check condition logic with simple test cases
2. Verify all required metrics are present in context
3. Check suppression hasn't blocked the alert
4. Ensure rule version is set correctly ("v2" for compound conditions)

### Too Many Alerts

1. Increase suppression_duration
2. Add more restrictive conditions
3. Use compound AND to narrow criteria
4. Review backtest results to tune thresholds

### Template Errors

1. Verify all template variables exist in context
2. Check for typos in variable names
3. Use try/except in custom formatters
4. Test templates with sample data

## Future Enhancements

Planned features:
- Time-based conditions (time-of-day, day-of-week)
- Statistical thresholds (standard deviations)
- Correlation-based conditions
- Machine learning-based anomaly detection
- Real-time threshold adaptation
- Multi-rule dependencies

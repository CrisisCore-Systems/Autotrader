# Alert Engine V2 - Quick Start Guide

## 5-Minute Getting Started

### 1. Simple Alert Rule (V2)

```python
from src.alerts import AlertRule, SimpleCondition, evaluate_and_enqueue
from src.alerts.repo import InMemoryAlertOutbox
from datetime import datetime

# Create a simple rule: alert when gem_score > 70
rule = AlertRule(
    id="high_score",
    version="v2",
    score_min=0,
    confidence_min=0,
    safety_ok=True,
    cool_off_minutes=60,
    condition=SimpleCondition(metric="gem_score", operator="gt", threshold=70),
    severity="info",
    message_template="💎 High score detected: {symbol} = {gem_score}",
)

# Evaluate candidates
from src.alerts import AlertCandidate

candidate = AlertCandidate(
    symbol="TOKEN",
    window_start="2024-01-01T00:00:00Z",
    gem_score=75,
    confidence=0.8,
    safety_ok=True,
)

outbox = InMemoryAlertOutbox()
alerts = evaluate_and_enqueue([candidate], now=datetime.now(), outbox=outbox, rules=[rule])

if alerts:
    print(f"🚨 Alert: {alerts[0].payload['message']}")
```

### 2. Compound Condition (AND)

```python
from src.alerts import CompoundCondition

# Alert when (gem_score < 30) AND (honeypot_detected = true)
rule = AlertRule(
    id="critical_risk",
    version="v2",
    score_min=0,
    confidence_min=0,
    safety_ok=True,
    cool_off_minutes=60,
    condition=CompoundCondition(
        operator="AND",
        conditions=(
            SimpleCondition(metric="gem_score", operator="lt", threshold=30),
            SimpleCondition(metric="honeypot_detected", operator="eq", threshold=True),
        )
    ),
    severity="critical",
    message_template="🚨 CRITICAL: {symbol} - score={gem_score}, honeypot detected!",
)
```

### 3. Nested Compound Conditions

```python
# Alert when (gem_score >= 70) AND ((liquidity < 10000) OR (safety < 0.5))
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

### 4. Backtesting

```python
from src.alerts import AlertBacktester
from datetime import datetime, timedelta

# Create backtester
backtester = AlertBacktester([rule])

# Run on historical data
start_time = datetime(2024, 1, 1, 0, 0, 0)
end_time = datetime(2024, 1, 2, 0, 0, 0)
result = backtester.run(candidates, start_time, end_time)

# View results
print(f"Alerts fired: {result.alerts_fired}")
print(f"Suppression rate: {result.summary()['suppression_rate']:.1%}")
print(f"By severity: {result.alerts_by_severity}")
```

### 5. Feature Diffs & Prior Period

```python
candidate = AlertCandidate(
    symbol="TOKEN",
    window_start="2024-01-01T00:00:00Z",
    gem_score=85,
    confidence=0.9,
    safety_ok=True,
    metadata={"liquidity_usd": 50000},
    # Feature changes
    feature_diff={
        "liquidity_usd": {
            "before": 20000,
            "after": 50000,
            "change_pct": 150
        }
    },
    # Prior period for comparison
    prior_period={
        "gem_score": 65,
        "confidence": 0.7,
    }
)
```

### 6. Load Rules from YAML

```python
from src.alerts.rules import load_rules

rules = load_rules("configs/alert_rules.yaml")
print(f"Loaded {len(rules)} rules")
```

## Quick Reference

### Operators

**Comparison:**
- `gt`, `>` - Greater than
- `gte`, `>=` - Greater than or equal
- `lt`, `<` - Less than
- `lte`, `<=` - Less than or equal
- `eq`, `==` - Equal
- `neq`, `!=` - Not equal

**Logical:**
- `AND` - All conditions must be true
- `OR` - At least one condition must be true
- `NOT` - Negation

### Alert Severities

- `info` - Informational
- `warning` - Warning
- `high` - High priority
- `critical` - Critical priority

### Rule Versions

- `v1` - Simple threshold rules (legacy)
- `v2` - Compound condition rules (new)

## Common Patterns

### Pattern 1: Critical Risk Detection
```python
CompoundCondition(operator="AND", conditions=(
    SimpleCondition(metric="gem_score", operator="lt", threshold=30),
    SimpleCondition(metric="honeypot_detected", operator="eq", threshold=True),
))
```

### Pattern 2: High Score with Red Flags
```python
CompoundCondition(operator="AND", conditions=(
    SimpleCondition(metric="gem_score", operator="gte", threshold=70),
    CompoundCondition(operator="OR", conditions=(
        SimpleCondition(metric="liquidity_usd", operator="lt", threshold=10000),
        SimpleCondition(metric="safety_score", operator="lt", threshold=0.5),
    ))
))
```

### Pattern 3: Multiple Warning Signs
```python
CompoundCondition(operator="OR", conditions=(
    SimpleCondition(metric="holder_concentration", operator="gt", threshold=80),
    SimpleCondition(metric="contract_unverified", operator="eq", threshold=True),
    SimpleCondition(metric="liquidity_locked", operator="eq", threshold=False),
))
```

## YAML Configuration

```yaml
rules:
  - id: my_rule
    description: "My custom rule"
    condition:
      type: compound
      operator: AND
      conditions:
        - metric: gem_score
          operator: gt
          threshold: 70
        - metric: safety_ok
          operator: eq
          threshold: true
    severity: warning
    channels: [slack, telegram]
    escalation_policy: progressive
    suppression_duration: 3600
    message_template: "Alert: {symbol} scored {gem_score}"
    version: v2
```

## Migration from V1 to V2

**Before (V1):**
```python
AlertRule(
    id="rule",
    score_min=70,
    confidence_min=0.75,
    safety_ok=True,
    cool_off_minutes=240,
)
```

**After (V2):**
```python
AlertRule(
    id="rule",
    version="v2",
    score_min=0,  # Not used in v2
    confidence_min=0,
    safety_ok=True,
    cool_off_minutes=240,
    condition=CompoundCondition(
        operator="AND",
        conditions=(
            SimpleCondition(metric="gem_score", operator="gte", threshold=70),
            SimpleCondition(metric="confidence", operator="gte", threshold=0.75),
            SimpleCondition(metric="safety_ok", operator="eq", threshold=True),
        )
    ),
    severity="info",
    message_template="Alert for {symbol}",
)
```

## Next Steps

1. **Run the Demo:** `python examples/expanded_alert_engine_demo.py`
2. **Read Full Docs:** `docs/EXPANDED_ALERT_ENGINE.md`
3. **Review Examples:** See `examples/expanded_alert_engine_demo.py`
4. **Run Tests:** `pytest tests/test_compound_conditions.py -v`

## Common Issues

### Issue: Alert not firing
✅ **Solution:** Check condition logic, verify metrics in context

### Issue: Too many alerts
✅ **Solution:** Increase suppression_duration, add stricter conditions

### Issue: Template error
✅ **Solution:** Verify all template variables exist in context

## Resources

- **Full Documentation:** `docs/EXPANDED_ALERT_ENGINE.md`
- **Examples:** `examples/expanded_alert_engine_demo.py`
- **Tests:** `tests/test_compound_conditions.py`
- **Summary:** `ALERT_ENGINE_EXPANSION_SUMMARY.md`

## Support

For issues or questions:
1. Check the troubleshooting section in `docs/EXPANDED_ALERT_ENGINE.md`
2. Review the test cases for usage examples
3. Run the demo to see features in action

# Alert Engine v2 & Drift Monitor - Quick Reference

## 🚨 Alert Engine v2

### Basic Usage

```python
from src.services.alerting_v2 import AlertManager, AlertCondition, AlertRule

manager = AlertManager()

# Simple threshold
rule = AlertRule(
    id="low_score",
    condition=AlertCondition("gem_score", "lt", 30),
    severity="warning"
)
manager.add_rule(rule)

# Evaluate
alerts = manager.evaluate({"gem_score": 25})
```

### Compound Conditions

```python
from src.services.alerting_v2 import CompoundCondition

# AND: Both must be true
and_condition = CompoundCondition(
    operator="AND",
    conditions=[
        AlertCondition("gem_score", "lt", 30),
        AlertCondition("honeypot_detected", "eq", True)
    ]
)

# OR: At least one true
or_condition = CompoundCondition(
    operator="OR",
    conditions=[
        AlertCondition("liquidity_usd", "lt", 10000),
        AlertCondition("safety_score", "lt", 0.5)
    ]
)

# Nested: (A AND (B OR C))
nested = CompoundCondition(
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

### Operators

```python
# Comparison
"eq"    # Equal (==)
"ne"    # Not equal (!=)
"gt"    # Greater than (>)
"gte"   # Greater than or equal (>=)
"lt"    # Less than (<)
"lte"   # Less than or equal (<=)

# Collection
"in"        # Value in list
"not_in"    # Value not in list
"contains"  # List contains value
```

### Suppression

```python
from src.services.alerting_v2 import SuppressionRule
from datetime import timedelta

# Pattern-based
suppression = SuppressionRule(
    pattern=r".*test.*",
    field="token_name",
    duration=timedelta(hours=1)
)
manager.add_suppression_rule(suppression)

# Deduplication is automatic (same fingerprint within window)
```

### Escalation

```python
from src.services.alerting_v2 import EscalationPolicy

escalation = EscalationPolicy(
    levels=[
        {"delay": timedelta(0), "channels": ["slack"]},
        {"delay": timedelta(minutes=5), "channels": ["telegram"]},
        {"delay": timedelta(minutes=15), "channels": ["pagerduty"]}
    ]
)

rule = AlertRule(
    id="critical",
    condition=condition,
    escalation_policy=escalation
)
```

### Alert Lifecycle

```python
# Acknowledge
manager.acknowledge_alert(alert_id, "investigating")

# Resolve
manager.resolve_alert(alert_id, "fixed")

# Query
active = manager.get_active_alerts()
history = manager.get_alert_history(hours=24)
```

---

## 📊 Drift Monitor MVP

### Basic Usage

```python
from src.monitoring.drift_monitor import DriftMonitor, Baseline
import numpy as np

monitor = DriftMonitor()

# Create baseline
baseline = Baseline(
    features={
        "gem_score": historical_gem_scores,
        "liquidity_usd": historical_liquidity
    },
    predictions=historical_predictions
)
baseline.save("baselines/baseline.json")

# Detect drift
current_features = {"gem_score": current_scores}
report = monitor.detect_feature_drift(baseline, current_features)

if report.drift_detected:
    print("⚠️ Drift detected!")
```

### Statistical Tests

```python
from src.monitoring.drift_monitor import DriftDetector

detector = DriftDetector()

# Kolmogorov-Smirnov (continuous)
ks_result = detector.kolmogorov_smirnov_test(baseline_data, current_data)
print(f"KS: {ks_result.ks_statistic:.3f}, p={ks_result.ks_p_value:.4f}")

# PSI (distribution shift)
psi_result = detector.population_stability_index(baseline_data, current_data)
print(f"PSI: {psi_result.psi:.3f}")

# Chi-square (categorical)
chi_result = detector.chi_square_test(baseline_cat, current_cat)
print(f"Chi2: {chi_result.chi_square:.3f}")
```

### Thresholds

```python
# Default thresholds
monitor = DriftMonitor(
    ks_threshold=0.05,   # KS test p-value
    psi_threshold=0.2    # PSI score
)

# Custom thresholds
sensitive = DriftMonitor(
    ks_threshold=0.01,   # Stricter
    psi_threshold=0.15
)
```

### PSI Interpretation

```
PSI < 0.1   : No significant change
PSI 0.1-0.2 : Moderate shift (monitor)
PSI > 0.2   : Significant shift (action!)
```

### Drift Types

```python
# Feature drift
feature_report = monitor.detect_feature_drift(baseline, current_features)

# Prediction drift
pred_report = monitor.detect_prediction_drift(baseline, current_predictions)

# Performance drift
perf_report = monitor.detect_performance_drift(
    baseline, 
    current_metrics,
    threshold=0.10  # 10% degradation
)

# Comprehensive (all types)
full_report = monitor.detect_drift(
    baseline=baseline,
    current_features=current_features,
    current_predictions=current_predictions,
    current_performance=current_metrics
)
```

### Baseline Management

```python
# Save
baseline.save("baselines/prod_baseline.json")

# Load
baseline = Baseline.load("baselines/prod_baseline.json")

# Metadata
baseline = Baseline(
    features=features,
    predictions=predictions,
    metadata={
        "created_at": datetime.utcnow().isoformat(),
        "model_version": "v1.2",
        "sample_size": 1000
    }
)
```

---

## 🔗 Integration

### Alert Engine + Drift Monitor

```python
# Detect drift
drift_report = monitor.detect_drift(baseline, features, predictions)

# Extract metrics for alerting
drift_metrics = {
    "drift_ks_statistic": max(r.ks_statistic for r in drift_report.feature_drift.values()),
    "drift_psi_score": max(r.psi for r in drift_report.feature_drift.values())
}

# Evaluate alert rules
alerts = alert_manager.evaluate(drift_metrics)
```

### Alert Rule for Drift

```python
drift_alert = AlertRule(
    id="feature_drift",
    condition=CompoundCondition("OR", [
        AlertCondition("drift_ks_statistic", "gt", 0.3),
        AlertCondition("drift_psi_score", "gt", 0.2)
    ]),
    severity="high",
    message="Drift: KS={drift_ks_statistic:.3f}, PSI={drift_psi_score:.3f}"
)
```

---

## 📊 Metrics

### Alert Engine

```promql
# Prometheus queries
alerts_fired_total{rule_id="critical_risk"}
alerts_suppressed_total{reason="duplicate"}
active_alerts{severity="warning"}
```

### Drift Monitor

```promql
drift_detections_total{model="gem_scorer"}
drift_score{feature="gem_score", metric="ks"}
prediction_distribution{percentile="p50"}
```

---

## 🎯 Common Patterns

### Pattern 1: Daily Drift Check

```python
# Load baseline
baseline = Baseline.load("baselines/baseline.json")

# Get today's data
today_features = get_production_features(days=1)
today_predictions = get_production_predictions(days=1)

# Check drift
report = monitor.detect_drift(baseline, today_features, today_predictions)

# Alert if drifted
if report.drift_detected:
    send_alert("Drift detected!")
```

### Pattern 2: Automated Retraining

```python
def should_retrain(report):
    drifted = sum(1 for r in report.feature_drift.values() if r.drift_detected)
    max_psi = max(r.psi for r in report.feature_drift.values())
    return drifted > len(report.feature_drift) / 2 or max_psi > 0.3

if should_retrain(drift_report):
    trigger_retraining_pipeline()
```

### Pattern 3: Compound Alert with Multiple Conditions

```python
manipulation = AlertRule(
    id="manipulation",
    condition=CompoundCondition("AND", [
        CompoundCondition("OR", [
            AlertCondition("holder_concentration", "gt", 80),
            AlertCondition("buy_sell_ratio", "gt", 5)
        ]),
        CompoundCondition("AND", [
            AlertCondition("price_change_1h", "gt", 50),
            AlertCondition("contract_age_hours", "lt", 24)
        ])
    ]),
    severity="critical"
)
```

---

## 📚 Resources

- **Full Guides**:
  - `docs/ALERTING_V2_GUIDE.md`
  - `docs/DRIFT_MONITORING_GUIDE.md`

- **Configuration**:
  - `configs/alert_rules.yaml`

- **Examples**:
  - `example_alerting_v2.py`
  - `example_drift_monitoring.py`

- **Notebook**:
  - `notebooks/hidden_gem_scanner.ipynb` (cells 30-38)

---

## 🐛 Troubleshooting

### Alerts not firing?
```python
# Debug condition
result = condition.evaluate(metrics)
print(f"Condition result: {result}")
print(f"Metrics: {metrics}")
```

### Too many false positives?
```python
# Adjust thresholds
monitor = DriftMonitor(
    ks_threshold=0.10,   # Less sensitive
    psi_threshold=0.25
)
```

### Baseline issues?
```python
# Validate baseline
assert len(baseline.predictions) >= 1000  # Sufficient samples
assert not np.any(np.isnan(baseline.features["gem_score"]))  # No NaN
```

---

**Pro Tip**: Start with default thresholds and adjust based on your false positive/negative rates!

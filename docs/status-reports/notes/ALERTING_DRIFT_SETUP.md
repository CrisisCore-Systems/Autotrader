# Alert Engine v2 & Drift Monitor MVP - Installation & Setup

## 📦 Installation

### 1. Install Dependencies

The drift monitor requires `scipy` for statistical tests. Install dependencies:

```powershell
# Standard installation (Python 3.11 and below)
pip install -r requirements.txt

# Python 3.13+ installation
pip install -r requirements-py313.txt
```

**New dependency added**: `scipy` (v1.11.4 for Python 3.11, v1.14.0+ for Python 3.13)

### 2. Verify Installation

```python
# Test imports
from src.services.alerting_v2 import AlertManager, AlertCondition
from src.monitoring.drift_monitor import DriftMonitor, Baseline
import numpy as np
from scipy import stats

print("✅ All imports successful!")
```

## 🚀 Quick Start

### Alert Engine v2

```powershell
# Run examples
python example_alerting_v2.py
```

Expected output:
- ✅ 6 examples demonstrating compound conditions, suppression, escalation
- 🚨 Sample alerts with various severity levels
- 📊 Suppression and deduplication statistics

### Drift Monitor MVP

```powershell
# Run examples
python example_drift_monitoring.py
```

Expected output:
- ✅ 8 examples demonstrating drift detection
- 📊 Statistical test results (KS, PSI, Chi-square)
- ⚠️ Drift detection with visualizations
- 💾 Baseline creation and persistence

### Jupyter Notebook

```powershell
# Start Jupyter
jupyter notebook notebooks/hidden_gem_scanner.ipynb
```

Navigate to cells 30-38 for interactive demonstrations.

## 📁 Directory Structure

After installation, ensure these directories exist:

```
artifacts/
└── baselines/          # Drift monitor baselines
    └── *.json          # Saved baseline files

configs/
└── alert_rules.yaml    # Alert engine configuration

docs/
├── ALERTING_V2_GUIDE.md
└── DRIFT_MONITORING_GUIDE.md
```

## ⚙️ Configuration

### Alert Rules

Edit `configs/alert_rules.yaml` to customize alert rules:

```yaml
rules:
  - id: your_rule
    condition:
      type: compound
      operator: AND
      conditions:
        - metric: gem_score
          operator: lt
          threshold: 30
    severity: critical
```

### Drift Monitor Thresholds

Customize thresholds in your code:

```python
from src.monitoring.drift_monitor import DriftMonitor

monitor = DriftMonitor(
    ks_threshold=0.05,   # KS test p-value (default: 0.05)
    psi_threshold=0.2    # PSI threshold (default: 0.2)
)
```

## 🧪 Testing

### Unit Tests

Create test files for your alert rules:

```python
# test_custom_alerts.py
from src.services.alerting_v2 import AlertManager, AlertCondition, AlertRule

def test_critical_risk_alert():
    manager = AlertManager()
    
    rule = AlertRule(
        id="test_critical",
        condition=AlertCondition("gem_score", "lt", 30),
        severity="critical"
    )
    manager.add_rule(rule)
    
    # Should fire
    alerts = manager.evaluate({"gem_score": 25})
    assert len(alerts) == 1
    
    # Should not fire
    alerts = manager.evaluate({"gem_score": 50})
    assert len(alerts) == 0
```

Run tests:

```powershell
pytest test_custom_alerts.py -v
```

### Integration Tests

Test drift monitor with real data:

```python
# test_drift_integration.py
import numpy as np
from src.monitoring.drift_monitor import DriftMonitor, Baseline

def test_drift_detection_workflow():
    # Create baseline
    baseline = Baseline(
        features={"gem_score": np.random.normal(60, 15, 1000)},
        predictions=np.random.normal(65, 20, 1000).tolist()
    )
    
    # Test drift
    monitor = DriftMonitor()
    drifted = {"gem_score": np.random.normal(40, 15, 200)}
    
    report = monitor.detect_feature_drift(baseline, drifted)
    assert report.drift_detected  # Should detect drift
```

## 🔗 Integration with Existing System

### 1. Add to Scanner Pipeline

```python
# In your scanner code
from src.services.alerting_v2 import AlertManager
from src.monitoring.drift_monitor import DriftMonitor, Baseline

# Initialize (once)
alert_manager = AlertManager()
drift_monitor = DriftMonitor()
baseline = Baseline.load("artifacts/baselines/production_baseline.json")

# In scan loop
def scan_token(token_address):
    # ... existing scan logic ...
    
    # Evaluate alerts
    alerts = alert_manager.evaluate({
        "gem_score": result.gem_score,
        "honeypot_detected": result.is_honeypot,
        "liquidity_usd": result.liquidity
    })
    
    # Handle alerts
    for alert in alerts:
        send_notification(alert)
    
    return result

# Daily drift check
def daily_drift_check():
    today_features = get_features_from_database(days=1)
    report = drift_monitor.detect_feature_drift(baseline, today_features)
    
    if report.drift_detected:
        send_drift_alert(report)
```

### 2. Add Prometheus Metrics Endpoint

Your existing metrics server (`src/services/metrics_server.py`) already exposes metrics on port 9090.

New metrics available:
```
alerts_fired_total
alerts_suppressed_total
active_alerts
drift_detections_total
drift_score
```

Query in Prometheus:
```promql
# Alert metrics
rate(alerts_fired_total[5m])
sum(active_alerts) by (severity)

# Drift metrics
drift_score{feature="gem_score", metric="ks"}
```

### 3. Add Structured Logging

Alerts and drift events are automatically logged via existing `src/core/logging_config.py`:

```json
{
  "event": "alert_fired",
  "alert_id": "abc123",
  "rule_id": "critical_risk",
  "severity": "critical",
  "timestamp": "2024-01-15T10:30:00Z"
}

{
  "event": "drift_detected",
  "model": "gem_scorer",
  "features_drifted": ["gem_score", "liquidity_usd"],
  "max_psi": 0.25,
  "timestamp": "2024-01-15T11:00:00Z"
}
```

## 📊 Monitoring Dashboard

### Grafana Queries

Create dashboards with these queries:

```promql
# Alert Rate
rate(alerts_fired_total[5m])

# Active Alerts by Severity
sum(active_alerts) by (severity)

# Alert Suppression Rate
rate(alerts_suppressed_total[5m]) / rate(alerts_fired_total[5m])

# Feature Drift Score
drift_score{feature="gem_score", metric="psi"}

# Drift Detection Events
increase(drift_detections_total[1h])
```

## 🐛 Troubleshooting

### Issue: scipy import error

```powershell
# Reinstall scipy
pip install --upgrade scipy

# Verify version
python -c "import scipy; print(scipy.__version__)"
```

### Issue: Baseline not found

```python
from pathlib import Path

baseline_path = Path("artifacts/baselines/baseline.json")
if not baseline_path.exists():
    baseline_path.parent.mkdir(parents=True, exist_ok=True)
    # Create new baseline
```

### Issue: Alerts not firing

Enable debug logging:

```python
from src.core.logging_config import get_logger
import logging

logger = get_logger(__name__)
logger.setLevel(logging.DEBUG)

# Check condition evaluation
condition = rule.condition
result = condition.evaluate(metrics)
logger.debug(f"Condition result: {result}", metrics=metrics)
```

### Issue: Too many false drift alerts

Adjust thresholds:

```python
# Less sensitive
monitor = DriftMonitor(
    ks_threshold=0.10,    # Was 0.05
    psi_threshold=0.25    # Was 0.2
)
```

## 📚 Next Steps

1. **Run Examples**:
   ```powershell
   python example_alerting_v2.py
   python example_drift_monitoring.py
   ```

2. **Customize Rules**:
   - Edit `configs/alert_rules.yaml`
   - Add your own compound conditions

3. **Create Baselines**:
   - Generate baseline from 30 days of production data
   - Save to `artifacts/baselines/`

4. **Set Up Monitoring**:
   - Configure Grafana dashboards
   - Set up daily drift checks
   - Integrate with notification services

5. **Read Documentation**:
   - `docs/ALERTING_V2_GUIDE.md` - Complete alert engine reference
   - `docs/DRIFT_MONITORING_GUIDE.md` - Complete drift monitor reference
   - `../quick-reference/ALERTING_DRIFT_QUICK_REF.md` - Quick reference card

## ✅ Verification Checklist

- [ ] Dependencies installed (`scipy`, `numpy`)
- [ ] Imports working (no errors)
- [ ] Example scripts run successfully
- [ ] Notebook cells execute without errors
- [ ] Alert rules loaded from YAML
- [ ] Baselines directory created
- [ ] Prometheus metrics exposed
- [ ] Logs captured in JSON format

## 🆘 Support

For issues or questions:
1. Check the troubleshooting section above
2. Review the comprehensive guides in `docs/`
3. Check example scripts for reference implementations
4. Review Jupyter notebook for interactive demos

---

**Installation Date**: Run `pip install -r requirements.txt` to begin!

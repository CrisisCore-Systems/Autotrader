# Compliance Monitoring Quick Reference

**Phase 12 Component** | **Status**: ✅ Production Ready

---

## Quick Start

```python
from datetime import datetime, timedelta, timezone
from autotrader.monitoring.compliance import ComplianceMonitor

# Initialize monitor
monitor = ComplianceMonitor()

# Analyze last 7 days
end_time = datetime.now(tz=timezone.utc)
start_time = end_time - timedelta(days=7)

# Run analysis
report = monitor.analyze_period(start_time, end_time)

# Check results
print(f"Issues found: {report.totals['total']}")
print(f"Critical: {report.totals['critical']}")
```

---

## Policy Configuration

```python
from autotrader.monitoring.compliance import CompliancePolicy

# Production policy
policy = CompliancePolicy(
    require_risk_check=True,       # Require risk evaluation
    require_llm_review=True,        # Require LLM oversight
    max_risk_score=0.75,           # Max acceptable risk (0-1)
    max_order_notional=100000.0,   # Max order size ($)
    forbidden_llm_decisions=(      # Blacklisted actions
        "override_limits",
        "proceed_despite_reject",
    )
)

monitor = ComplianceMonitor(policy=policy)
```

---

## Issue Codes

| Code | Severity | Description |
|------|----------|-------------|
| `missing_risk_check` | CRITICAL | Signal executed without risk check |
| `risk_override` | CRITICAL | Risk rejected but trade executed |
| `risk_check_failed` | CRITICAL | Failed risk checks but trade proceeded |
| `llm_forbidden_action` | CRITICAL | LLM made blacklisted decision |
| `risk_score_exceeded` | WARNING | Risk score > threshold |
| `order_notional_exceeded` | WARNING | Order size > limit |
| `llm_review_missing` | WARNING | Required LLM review not recorded |

---

## Alert Routing

```python
from autotrader.monitoring.compliance import ComplianceSeverity

def route_alert(issue):
    if issue.severity == ComplianceSeverity.CRITICAL:
        send_to_pagerduty(issue)
        send_to_slack(issue, "#alerts-critical")
    elif issue.severity == ComplianceSeverity.WARNING:
        send_to_slack(issue, "#alerts-warnings")
    else:
        send_email(issue, "compliance@example.com")

for issue in report.issues:
    route_alert(issue)
```

---

## Single Signal Check

```python
# Check specific signal
issues = monitor.check_signal("sig_20251025_123456")

if issues:
    for issue in issues:
        print(f"[{issue.severity}] {issue.issue_code}")
        print(f"  {issue.description}")
```

---

## Anomaly Integration

```python
from autotrader.monitoring.anomaly import AnomalyDetector
from autotrader.monitoring.realtime import RealtimeDashboardAggregator

# Get metrics from dashboard
aggregator = RealtimeDashboardAggregator()
snapshot = aggregator.build_snapshot()
metrics = snapshot.to_dict()

# Add anomaly detection
detector = AnomalyDetector()
monitor = ComplianceMonitor(anomaly_detector=detector)

# Analyze with metrics
report = monitor.analyze_period(start, end, metrics=metrics)

print(f"Compliance issues: {len(report.issues)}")
print(f"Anomalies detected: {len(report.anomalies)}")
```

---

## Report Export

```python
import json

# Get report
report = monitor.analyze_period(start, end)

# Export to JSON
report_dict = report.to_dict()

# Save to file
with open("compliance_report.json", "w") as f:
    json.dump(report_dict, f, indent=2)

# Send to API
requests.post("https://api.example.com/compliance", json=report_dict)
```

---

## Scheduled Checks

```python
from apscheduler.schedulers.blocking import BlockingScheduler

scheduler = BlockingScheduler()

@scheduler.scheduled_job('cron', hour=8)  # Daily at 8am
def daily_compliance():
    monitor = ComplianceMonitor(policy=production_policy)
    end = datetime.now(tz=timezone.utc)
    start = end - timedelta(days=1)
    
    report = monitor.analyze_period(start, end)
    
    for issue in report.issues:
        route_alert(issue)

scheduler.start()
```

---

## Demo Script

```bash
# Run all demonstrations
python scripts/demo_compliance_monitoring.py

# Output:
# ✅ Demo 1: Basic Compliance Monitoring
# ✅ Demo 2: Strict Compliance Policy
# ✅ Demo 3: Signal-Specific Compliance Check
# ✅ Demo 4: Compliance with Anomaly Detection
# ✅ Demo 5: Export Compliance Report
# ✅ Demo 6: Custom Issue Handling
```

---

## Troubleshooting

### No signals found
```python
from autotrader.audit import get_audit_trail, EventType

audit = get_audit_trail()
signals = audit.query_events(EventType.SIGNAL)
print(f"Found {len(signals)} signals")
```

### Empty report
```python
# Verify time range
events = audit.query_events(start_time=start, end_time=end)
print(f"Found {len(events)} events in range")
```

### High false positive rate
```python
# Loosen thresholds
policy.max_risk_score *= 1.1
policy.max_order_notional *= 1.2
```

---

## Performance

- **Period analysis**: ~200ms for 7-day window
- **Signal check**: ~10ms per signal
- **Memory**: ~50MB for 7-day analysis
- **Scalability**: Tested up to 10,000 signals/period

---

## Files

| File | Purpose |
|------|---------|
| `autotrader/monitoring/compliance/monitor.py` | Core engine |
| `autotrader/monitoring/compliance/__init__.py` | Package exports |
| `scripts/demo_compliance_monitoring.py` | 6 usage demos |
| `COMPLIANCE_MONITORING_COMPLETE.md` | Full documentation |
| `PHASE_12_IMPLEMENTATION_GUIDE.md` | Integration guide |

---

## Next Steps

1. Configure alert routing (PagerDuty, Slack)
2. Set up scheduled compliance checks
3. Create Grafana dashboards for metrics
4. Integrate with Phase 13 automation

---

**For complete documentation, see**: `COMPLIANCE_MONITORING_COMPLETE.md`

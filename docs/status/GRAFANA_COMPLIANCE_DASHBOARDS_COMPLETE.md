# 📊 Grafana Compliance Monitoring Dashboards

**Status**: ✅ **COMPLETE** - Ready for Production

Comprehensive Grafana dashboards for real-time compliance monitoring with Prometheus metrics integration.

---

## 🎯 What's Included

### 1. Compliance Monitoring Dashboard
**File**: `infrastructure/grafana/dashboards/compliance-monitoring.json`

**13 Visualization Panels**:
1. **Active Critical Violations** (Gauge) - Real-time critical issue count with thresholds
2. **Active Warning Violations** (Gauge) - Real-time warning issue count
3. **Issues by Severity** (Pie Chart) - Distribution of all issues by severity
4. **Alert Delivery Success Rate** (Gauge) - % of alerts successfully delivered
5. **Compliance Issues Over Time** (Time Series) - Stacked area chart by severity
6. **Issues by Type** (Bar Chart) - Count of each issue type (missing_risk_check, etc.)
7. **Risk Check Failures** (Time Series) - Failure rate by failure type
8. **Alert Delivery Status** (Time Series) - Success/failure/error rates
9. **Top 10 Issue Types** (Table) - Most common issues with severity
10. **Alert Delivery Summary** (Table) - Breakdown by channel and status
11. **Active Violations by Severity** (Bar Gauge) - Current violation counts
12. **Compliance Check Duration** (Time Series) - p50/p95 performance metrics
13. **Compliance Checks Rate** (Time Series) - Check execution rate by type

### 2. Prometheus Metrics
**Location**: `autotrader/monitoring/compliance/monitor.py`

**6 Core Metrics**:
```promql
# Total issues detected
compliance_issues_total{severity="critical|warning|info", issue_code="<code>"}

# Compliance checks performed
compliance_checks_total{check_type="period_analysis|signal_check", status="completed|failed"}

# Check execution duration
compliance_check_duration_seconds{check_type="<type>"}

# Risk check failures
risk_check_failures_total{failure_type="missing|failed"}

# Alert delivery metrics
alert_delivery_total{channel="telegram|email", severity="<severity>", status="success|failure|error"}

# Current active violations
active_violations{severity="critical|warning|info"}
```

### 3. Metrics Exporter
**File**: `scripts/monitoring/export_compliance_metrics.py`

Features:
- Prometheus HTTP server (default port 9090)
- Continuous metrics updates (configurable interval)
- Multiple policy support (default/strict/permissive)
- 24-hour rolling analysis window
- Graceful error handling

---

## 🚀 Quick Start

### Step 1: Install Dependencies

```bash
# Install Prometheus client (if not already installed)
pip install prometheus-client
```

### Step 2: Start Metrics Exporter

```bash
# Default configuration (port 9090, 5-minute updates)
python scripts/monitoring/export_compliance_metrics.py

# Custom configuration
python scripts/monitoring/export_compliance_metrics.py \
    --port 9091 \
    --update-interval 60 \
    --policy strict
```

**Expected Output**:
```
================================================================================
Compliance Monitoring - Prometheus Metrics Exporter
================================================================================

📊 Configuration:
   Port: 9090
   Update Interval: 300s
   Policy: default

✅ Prometheus metrics server started on port 9090
   Metrics endpoint: http://localhost:9090/metrics

📈 Available metrics:
   - compliance_issues_total{severity, issue_code}
   - compliance_checks_total{check_type, status}
   - compliance_check_duration_seconds{check_type}
   - risk_check_failures_total{failure_type}
   - alert_delivery_total{channel, severity, status}
   - active_violations{severity}

🔄 Updating metrics every 300 seconds...
   Press Ctrl+C to stop
```

### Step 3: Configure Prometheus

Add to `infrastructure/prometheus/prometheus.yml`:

```yaml
scrape_configs:
  - job_name: 'compliance_monitoring'
    static_configs:
      - targets: ['localhost:9090']
    scrape_interval: 15s
```

Restart Prometheus:
```bash
# If using Docker
docker-compose restart prometheus

# If running standalone
systemctl restart prometheus
```

### Step 4: Import Grafana Dashboard

**Option A: Grafana UI**
1. Open Grafana (http://localhost:3000)
2. Navigate to **Dashboards** → **Import**
3. Upload `infrastructure/grafana/dashboards/compliance-monitoring.json`
4. Select Prometheus data source
5. Click **Import**

**Option B: Auto-provisioning**
Add to `infrastructure/grafana/provisioning/dashboards.yml`:
```yaml
apiVersion: 1

providers:
  - name: 'Compliance Monitoring'
    folder: 'Governance'
    type: file
    options:
      path: /etc/grafana/dashboards/compliance-monitoring.json
```

### Step 5: Verify Metrics

Visit Prometheus query UI: http://localhost:9090/graph

Test queries:
```promql
# Total compliance issues
sum(compliance_issues_total)

# Critical violations
sum(active_violations{severity="critical"})

# Alert success rate
100 * sum(rate(alert_delivery_total{status="success"}[5m])) / sum(rate(alert_delivery_total[5m]))

# Risk check failure rate
rate(risk_check_failures_total[5m])
```

---

## 📊 Dashboard Usage

### Real-Time Monitoring

**Critical Violations Alert**: Top-left gauge shows active critical issues
- 🟢 Green (0-4): Normal operations
- 🟡 Yellow (5-9): Elevated violations, investigate
- 🔴 Red (10+): Critical state, immediate action required

**Alert Delivery**: Top-right gauge shows delivery success rate
- 🟢 Green (>90%): Healthy alert system
- 🟡 Yellow (90-95%): Degraded delivery
- 🔴 Red (<90%): Alert system issues

### Issue Analysis

**Issues Over Time** (Middle-left): Stacked time series
- Red area: Critical issues
- Orange area: Warnings
- Blue area: Info
- Look for spikes or trends

**Issues by Type** (Middle-right): Bar chart of issue codes
- `missing_risk_check`: Signals without risk checks (CRITICAL)
- `risk_score_exceeded`: Risk above threshold (WARNING)
- `risk_override`: Manual risk overrides (CRITICAL)
- `llm_review_missing`: Missing LLM reviews (WARNING)
- `excessive_notional`: Large orders (WARNING)

### Performance Monitoring

**Compliance Check Duration** (Bottom-left):
- p50: Median check time (typical performance)
- p95: 95th percentile (worst-case performance)
- Watch for increasing latency

**Compliance Checks Rate** (Bottom-right):
- Shows checks per minute by type
- Useful for capacity planning

---

## 🔧 Configuration

### Policy Modes

**Default Policy**:
```python
CompliancePolicy(
    require_risk_check=True,
    require_llm_review=False,
    max_risk_score=0.75,
    max_order_notional=500_000.0,
    forbidden_llm_decisions=['override_human', 'bypass_risk', 'emergency_order']
)
```

**Strict Policy** (`--policy strict`):
```python
CompliancePolicy(
    require_risk_check=True,
    require_llm_review=True,
    max_risk_score=0.5,
    max_order_notional=100_000.0,
    forbidden_llm_decisions=['override_human', 'bypass_risk']
)
```

**Permissive Policy** (`--policy permissive`):
```python
CompliancePolicy(
    require_risk_check=False,
    require_llm_review=False,
    max_risk_score=0.95,
    max_order_notional=1_000_000.0,
    forbidden_llm_decisions=[]
)
```

### Update Intervals

```bash
# Frequent updates (1 minute) - high overhead, real-time data
python scripts/monitoring/export_compliance_metrics.py --update-interval 60

# Balanced updates (5 minutes) - default, recommended
python scripts/monitoring/export_compliance_metrics.py --update-interval 300

# Infrequent updates (15 minutes) - low overhead, delayed data
python scripts/monitoring/export_compliance_metrics.py --update-interval 900
```

### Custom Port

```bash
# Avoid port conflicts
python scripts/monitoring/export_compliance_metrics.py --port 9091
```

---

## 🎨 Customization

### Add Custom Panel

1. Open dashboard in Grafana
2. Click **Add Panel** → **Add new panel**
3. Select visualization type
4. Write PromQL query
5. Configure display options
6. Click **Apply**
7. **Save dashboard**

### Example Custom Panels

**High-Risk Signals** (Stat Panel):
```promql
sum(compliance_issues_total{issue_code="risk_score_exceeded"})
```

**24-Hour Issue Trend** (Time Series):
```promql
increase(compliance_issues_total[24h])
```

**Alert Failure Breakdown** (Pie Chart):
```promql
sum by (status) (alert_delivery_total{status=~"failure|error"})
```

### Modify Thresholds

Edit dashboard JSON:
```json
{
  "thresholds": {
    "mode": "absolute",
    "steps": [
      {"color": "green", "value": null},
      {"color": "yellow", "value": 5},    // Change warning threshold
      {"color": "red", "value": 10}       // Change critical threshold
    ]
  }
}
```

---

## 🚨 Alerting

### Prometheus Alert Rules

Create `infrastructure/prometheus/alerts/compliance.yml`:

```yaml
groups:
  - name: compliance_alerts
    interval: 1m
    rules:
      - alert: HighCriticalViolations
        expr: sum(active_violations{severity="critical"}) > 5
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "High number of critical compliance violations"
          description: "{{ $value }} critical violations detected"
      
      - alert: AlertDeliveryFailure
        expr: |
          100 * sum(rate(alert_delivery_total{status="success"}[5m])) 
          / sum(rate(alert_delivery_total[5m])) < 90
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Alert delivery success rate below 90%"
          description: "Only {{ $value }}% of alerts delivered successfully"
      
      - alert: RiskCheckFailureSpike
        expr: rate(risk_check_failures_total[5m]) > 0.1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High rate of risk check failures"
          description: "{{ $value }} failures per second"
      
      - alert: ComplianceCheckSlow
        expr: |
          histogram_quantile(0.95, 
            rate(compliance_check_duration_seconds_bucket[5m])) > 10
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Compliance checks taking too long"
          description: "p95 duration: {{ $value }}s (threshold: 10s)"
```

Reload Prometheus:
```bash
curl -X POST http://localhost:9090/-/reload
```

### Grafana Alerts

1. Open panel in edit mode
2. Click **Alert** tab
3. Click **Create alert rule from this panel**
4. Configure conditions:
   - Query: Your PromQL expression
   - Condition: IS ABOVE / IS BELOW
   - Threshold: Your limit value
   - For: Duration before alerting
5. Add notification channel (Telegram, Email, Slack)
6. Save alert

---

## 📈 Metrics Reference

### compliance_issues_total

**Type**: Counter  
**Labels**: `severity`, `issue_code`  
**Description**: Total compliance issues detected since startup

**Example Queries**:
```promql
# Issues per minute by severity
sum by (severity) (rate(compliance_issues_total[5m]) * 60)

# Most common issue types
topk(5, sum by (issue_code) (compliance_issues_total))

# Critical issues only
compliance_issues_total{severity="critical"}
```

### active_violations

**Type**: Gauge  
**Labels**: `severity`  
**Description**: Current number of unresolved violations

**Example Queries**:
```promql
# Total active violations
sum(active_violations)

# Critical only
sum(active_violations{severity="critical"})

# Violations by severity
active_violations
```

### alert_delivery_total

**Type**: Counter  
**Labels**: `channel`, `severity`, `status`  
**Description**: Alert delivery attempts and outcomes

**Example Queries**:
```promql
# Success rate
100 * sum(rate(alert_delivery_total{status="success"}[5m])) 
    / sum(rate(alert_delivery_total[5m]))

# Failures per minute
sum by (status) (rate(alert_delivery_total{status=~"failure|error"}[5m]) * 60)

# Telegram delivery rate
rate(alert_delivery_total{channel="telegram"}[5m])
```

### compliance_check_duration_seconds

**Type**: Histogram  
**Labels**: `check_type`  
**Description**: Time spent running compliance checks

**Example Queries**:
```promql
# p95 latency
histogram_quantile(0.95, 
  rate(compliance_check_duration_seconds_bucket[5m]))

# p50 latency by check type
histogram_quantile(0.50, 
  sum by (check_type, le) (rate(compliance_check_duration_seconds_bucket[5m])))

# Average duration
rate(compliance_check_duration_seconds_sum[5m]) 
  / rate(compliance_check_duration_seconds_count[5m])
```

---

## 🐛 Troubleshooting

### Metrics Not Appearing

**Check metrics exporter**:
```bash
# Is it running?
curl http://localhost:9090/metrics

# Should see output like:
# compliance_issues_total{severity="critical",issue_code="missing_risk_check"} 4.0
```

**Check Prometheus scraping**:
```promql
# In Prometheus UI
up{job="compliance_monitoring"}

# Should return: 1 (up)
```

**Check Grafana data source**:
1. Settings → Data Sources → Prometheus
2. Click **Test** → Should see "Data source is working"

### Dashboard Shows "No Data"

**Possible causes**:
1. Metrics exporter not running → Start it
2. No trading activity → Generate test data with `run_compliance_test_trading.py`
3. Time range mismatch → Adjust dashboard time range (top-right)
4. Prometheus not scraping → Check `prometheus.yml` config

### High Memory Usage

Metrics exporter consuming too much memory:

**Solution 1**: Increase update interval
```bash
# From 5 minutes to 15 minutes
python scripts/monitoring/export_compliance_metrics.py --update-interval 900
```

**Solution 2**: Reduce analysis window

Edit `export_compliance_metrics.py`:
```python
# Change from 24 hours to 6 hours
start_time = end_time - timedelta(hours=6)  # Was: hours=24
```

### Alert Delivery Metrics Missing

If `alert_delivery_total` is 0:

1. Generate violations:
   ```bash
   python scripts/run_compliance_test_trading.py --cycles 10 --include-violations
   ```

2. Run compliance monitoring:
   ```bash
   python scripts/demo_compliance_monitoring.py
   ```

3. Verify Telegram alerts sent (check logs for "Alert sent to Telegram")

---

## 📚 Next Steps

✅ **Current Status**: Grafana dashboards ready!

**Recommended Actions**:

1. **Start Monitoring** (5 minutes)
   ```bash
   # Terminal 1: Start metrics exporter
   python scripts/monitoring/export_compliance_metrics.py
   
   # Terminal 2: Generate test violations
   python scripts/run_compliance_test_trading.py --cycles 20 --include-violations
   
   # Terminal 3: Run compliance analysis
   python scripts/demo_compliance_monitoring.py
   ```

2. **Import Dashboard** (2 minutes)
   - Open Grafana
   - Import `compliance-monitoring.json`
   - Watch real-time metrics!

3. **Set Up Alerts** (10 minutes)
   - Configure Prometheus alert rules
   - Add Grafana notification channels
   - Test with intentional violations

4. **Production Deployment** (30 minutes)
   - Run metrics exporter as service/daemon
   - Configure Prometheus for production
   - Set up retention policies
   - Document escalation procedures

---

## 🎯 Integration with Existing System

Your compliance monitoring now has **full observability**:

```
Trading System
    ↓
Audit Trail (data/audit/)
    ↓
Compliance Monitor (analyze_period)
    ↓
Prometheus Metrics (compliance_issues_total, etc.)
    ↓
Grafana Dashboard (13 panels, real-time)
    ↓
Alerts (Prometheus + Grafana)
    ↓
Telegram Notifications (via AlertRouter)
```

**All Components Working Together**:
- ✅ Compliance monitoring detects violations
- ✅ Prometheus records metrics
- ✅ Grafana visualizes trends
- ✅ Alerts trigger on thresholds
- ✅ Telegram delivers notifications
- ✅ Audit trail maintains full history

---

## 📞 Support

**Documentation**:
- Compliance Framework: `COMPLIANCE_MONITORING_COMPLETE.md`
- Telegram Alerts: `TELEGRAM_ALERTS_COMPLETE.md`
- This Guide: `GRAFANA_COMPLIANCE_DASHBOARDS_COMPLETE.md`

**Demo Scripts**:
- `scripts/demo_compliance_monitoring.py` - Full framework demo
- `scripts/run_compliance_test_trading.py` - Generate test data
- `scripts/monitoring/export_compliance_metrics.py` - Metrics exporter

**Quick Test**:
```bash
# 1. Start metrics exporter
python scripts/monitoring/export_compliance_metrics.py

# 2. In browser: http://localhost:9090/metrics
# Should see Prometheus metrics output

# 3. Generate violations and alerts
python scripts/run_compliance_test_trading.py --cycles 5 --include-violations
python scripts/demo_compliance_monitoring.py

# 4. Check Grafana dashboard for updates
```

---

**Status**: 🎉 **PRODUCTION READY**

Compliance monitoring now has enterprise-grade visualization and alerting!

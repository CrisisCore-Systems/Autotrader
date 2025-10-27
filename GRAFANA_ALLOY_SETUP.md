# Grafana Alloy Setup Guide for AutoTrader
# Complete setup instructions for sending metrics to Grafana Cloud

## 📋 Overview

This guide walks you through installing Grafana Alloy and configuring it to send your AutoTrader compliance metrics to Grafana Cloud.

**What is Alloy?**
- Grafana Alloy is an OpenTelemetry collector that scrapes Prometheus metrics
- It forwards metrics to Grafana Cloud for visualization
- Replaces the need for running your own Prometheus server

**Architecture:**
```
AutoTrader Metrics Exporter (port 9090)
    ↓
Grafana Alloy (scrapes every 15s)
    ↓
Grafana Cloud (stores & visualizes)
    ↓
Compliance Dashboard (13 panels)
```

---

## 🚀 Quick Setup (3 Steps)

### Step 1: Install Grafana Alloy

**Windows (PowerShell as Administrator):**
```powershell
# Download Alloy installer
$version = "v1.0.0"
$url = "https://github.com/grafana/alloy/releases/download/$version/alloy-installer-windows-amd64.exe"
Invoke-WebRequest -Uri $url -OutFile "$env:TEMP\alloy-installer.exe"

# Run installer
Start-Process -FilePath "$env:TEMP\alloy-installer.exe" -Wait

# Verify installation
alloy --version
```

**Alternative (Chocolatey):**
```powershell
choco install grafana-alloy
```

**Linux/Mac:**
```bash
# Linux
curl -O -L "https://github.com/grafana/alloy/releases/download/v1.0.0/alloy-linux-amd64"
sudo mv alloy-linux-amd64 /usr/local/bin/alloy
sudo chmod +x /usr/local/bin/alloy

# Mac (Homebrew)
brew install grafana/grafana/alloy
```

### Step 2: Configure Alloy

Your Alloy configuration is already created at:
```
configs/alloy-config.river
```

This config:
- ✅ Scrapes metrics from `localhost:9090` (your exporter)
- ✅ Sends to Grafana Cloud (ca-east-0 region)
- ✅ Uses your API token (scoped for data write)
- ✅ Adds labels: `cluster=autotrader-compliance`, `environment=production`

**Important:** The config contains your API token. Keep it secure!

### Step 3: Start Alloy

**Windows:**
```powershell
# Start Alloy with your config
alloy run configs\alloy-config.river

# Or run as background service
alloy run configs\alloy-config.river --server.http.listen-addr=127.0.0.1:12345
```

**Linux/Mac:**
```bash
# Start Alloy
alloy run configs/alloy-config.river

# Or as systemd service
sudo systemctl enable alloy
sudo systemctl start alloy
```

---

## 🔍 Verify Setup

### 1. Start Metrics Exporter
```powershell
# Terminal 1: Start exporter (provides metrics on port 9090)
python scripts\monitoring\export_compliance_metrics.py
```

**Expected Output:**
```
🎯 Prometheus Compliance Metrics Exporter
==========================================
📡 HTTP server started on port 9090
📊 Metrics endpoint: http://localhost:9090/metrics
🔄 Update interval: 300 seconds (5 minutes)
📋 Policy: default

✅ Metrics updated successfully
   Total issues: 6
   Critical violations: 4
   Warning violations: 2
   ...
```

### 2. Check Alloy is Scraping
```powershell
# Terminal 2: Start Alloy
alloy run configs\alloy-config.river

# Visit Alloy UI (if using --server.http.listen-addr)
# Open: http://localhost:12345
```

**Expected Logs:**
```
level=info msg="starting Alloy"
level=info component=prometheus.scrape.compliance_metrics msg="scraping target" target=localhost:9090
level=info component=prometheus.remote_write.grafana_cloud msg="remote write started" endpoint=https://prometheus-prod-ca-east-0.grafana.net
```

### 3. Verify Metrics in Grafana Cloud

1. **Login to Grafana Cloud:**
   - URL: `https://crisiscore-systems.grafana.net` (or your org URL)
   - Use your Grafana Cloud credentials

2. **Check Metrics Explorer:**
   - Navigate to: **Explore** → Select **Prometheus** data source
   - Run query: `compliance_issues_total`
   - Should see metrics with labels: `cluster="autotrader-compliance"`

3. **Import Dashboard:**
   - Go to: **Dashboards** → **Import**
   - Upload: `infrastructure/grafana/dashboards/compliance-monitoring.json`
   - Select data source: **Prometheus** (Grafana Cloud)
   - Click **Import**

4. **View Dashboard:**
   - Should see 13 panels with real-time data:
     - Active Critical Violations (gauge)
     - Compliance Issues Over Time (time series)
     - Alert Delivery Success Rate (gauge)
     - Risk Check Failures (time series)
     - And 9 more panels...

---

## 📊 Available Metrics

Your compliance monitoring exposes 6 key metrics:

### 1. **compliance_issues_total**
- Type: Counter
- Labels: `severity` (critical/warning/info), `issue_code`
- Query: `sum by (severity) (rate(compliance_issues_total[5m]) * 60)`

### 2. **active_violations**
- Type: Gauge
- Labels: `severity` (critical/warning/info)
- Query: `sum(active_violations{severity="critical"})`

### 3. **alert_delivery_total**
- Type: Counter
- Labels: `channel` (telegram/email), `severity`, `status` (success/failure/error)
- Query: `sum by (status) (rate(alert_delivery_total{channel="telegram"}[5m]) * 60)`

### 4. **risk_check_failures_total**
- Type: Counter
- Labels: `failure_type` (missing_check/insufficient_data/...)
- Query: `sum by (failure_type) (rate(risk_check_failures_total[5m]) * 60)`

### 5. **compliance_check_duration_seconds**
- Type: Histogram
- Labels: `check_type` (risk/limits/ml/...)
- Query: `histogram_quantile(0.95, sum by (check_type, le) (rate(compliance_check_duration_seconds_bucket[5m])))`

### 6. **compliance_checks_total**
- Type: Counter
- Labels: `check_type`, `status` (passed/failed)
- Query: `sum by (check_type, status) (rate(compliance_checks_total[5m]) * 60)`

---

## 🎯 Complete Workflow

### Full System Running

**Terminal 1: Generate Trading Data**
```powershell
python scripts\run_compliance_test_trading.py --cycles 20 --include-violations
```

**Terminal 2: Export Metrics**
```powershell
python scripts\monitoring\export_compliance_metrics.py
```

**Terminal 3: Run Alloy**
```powershell
alloy run configs\alloy-config.river
```

**Result:**
- Trading data generates compliance violations
- Violations trigger Telegram alerts (already working!)
- Metrics exporter exposes Prometheus metrics
- Alloy scrapes metrics and sends to Grafana Cloud
- Dashboard visualizes violations in real-time

### View in Grafana Cloud

1. Open dashboard: `https://your-org.grafana.net/d/compliance-monitoring`
2. See real-time updates every 10 seconds
3. Monitor:
   - **Panel 1:** Active critical violations (gauge with red/yellow/green thresholds)
   - **Panel 2:** Total issues detected (stat)
   - **Panel 3:** Alert delivery success rate (gauge)
   - **Panel 5:** Issues over time by severity (time series)
   - **Panel 8:** Alert delivery status (time series)
   - **Panel 12:** Compliance check latency p50/p95 (time series)

---

## 🔧 Configuration Options

### Change Scrape Interval

Edit `configs/alloy-config.river`:
```river
prometheus.scrape "compliance_metrics" {
  scrape_interval = "30s"  # Change from 15s to 30s
  scrape_timeout  = "10s"
}
```

### Add More Exporters

```river
prometheus.scrape "compliance_metrics" {
  targets = [
    {"__address__" = "localhost:9090"},
    {"__address__" = "localhost:9091"},  # Add second exporter
  ]
  forward_to = [prometheus.remote_write.grafana_cloud.receiver]
}
```

### Change Environment Label

```river
prometheus.remote_write "grafana_cloud" {
  external_labels = {
    cluster = "autotrader-compliance",
    environment = "development",  # Change from production
    source = "alloy",
  }
}
```

### Enable Debug Logging

```river
logging {
  level  = "debug"  # Change from info
  format = "logfmt"
}
```

---

## 🐛 Troubleshooting

### Issue 1: Alloy not scraping metrics

**Symptom:**
```
level=error component=prometheus.scrape msg="scrape failed" target=localhost:9090 error="connection refused"
```

**Solution:**
```powershell
# Check exporter is running
curl http://localhost:9090/metrics

# If not, start it:
python scripts\monitoring\export_compliance_metrics.py
```

### Issue 2: Metrics not appearing in Grafana Cloud

**Symptom:** Dashboard panels show "No Data"

**Checks:**
1. Verify Alloy logs show remote write success:
   ```
   level=info component=prometheus.remote_write msg="successfully sent samples"
   ```

2. Check Grafana Cloud Prometheus:
   - Go to **Explore** → Run: `up{job="compliance_metrics"}`
   - Should return `1` if scraping

3. Verify time range in dashboard:
   - Change from "Last 1 hour" to "Last 6 hours"
   - May need time for data to accumulate

### Issue 3: Authentication errors

**Symptom:**
```
level=error component=prometheus.remote_write msg="remote write failed" error="401 Unauthorized"
```

**Solution:**
1. Verify token in `configs/alloy-config.river`
2. Check token hasn't expired (yours has "No expiry")
3. Verify token has `alloy-data-write` scope

### Issue 4: Exporter import errors

**Symptom:** `ModuleNotFoundError: No module named 'autotrader'`

**Solution:**
```powershell
# Install AutoTrader in development mode
pip install -e .

# Or use virtual environment
.venv-1\Scripts\Activate.ps1
python scripts\monitoring\export_compliance_metrics.py
```

---

## 📚 Additional Resources

### Grafana Alloy Documentation
- Installation: https://grafana.com/docs/alloy/latest/get-started/install/
- Configuration: https://grafana.com/docs/alloy/latest/reference/config-blocks/
- River language: https://grafana.com/docs/alloy/latest/reference/river/

### Grafana Cloud
- Dashboards: https://grafana.com/docs/grafana-cloud/visualizations/dashboards/
- Prometheus: https://grafana.com/docs/grafana-cloud/metrics-prometheus/
- Alerting: https://grafana.com/docs/grafana-cloud/alerting-and-irm/

### AutoTrader Compliance Docs
- Compliance Monitoring: `COMPLIANCE_MONITORING_COMPLETE.md`
- Grafana Dashboards: `GRAFANA_COMPLIANCE_DASHBOARDS_COMPLETE.md`
- Telegram Alerts: `TELEGRAM_ALERTS_COMPLETE.md`

---

## 🎉 Success Checklist

- [ ] Grafana Alloy installed (`alloy --version` works)
- [ ] Config file created (`configs/alloy-config.river` exists)
- [ ] Metrics exporter running (port 9090 accessible)
- [ ] Alloy scraping metrics (logs show successful scrapes)
- [ ] Grafana Cloud receiving data (`up` query returns 1)
- [ ] Dashboard imported (13 panels visible)
- [ ] Panels showing real-time data (not "No Data")
- [ ] Telegram alerts still working (end-to-end validation)

**When all checked:** Your compliance monitoring is fully integrated with Grafana Cloud! 🚀

---

## 🔐 Security Notes

1. **Protect Your Token:**
   - File `configs/grafana_cloud.yaml` contains your API token
   - Add to `.gitignore` if committing to public repo
   - Rotate token if accidentally exposed

2. **Network Security:**
   - Alloy connects to `prometheus-prod-ca-east-0.grafana.net` (HTTPS)
   - Metrics exporter runs on `localhost:9090` (local only by default)
   - To expose externally, add `--host 0.0.0.0` to exporter

3. **Token Scopes:**
   - Your token has `alloy-data-write` scope (metrics only)
   - Cannot read data or modify dashboard settings
   - Safe for automated systems

---

**Next Steps:**
- Start with 3-step Quick Setup above
- Run verification checks
- Import dashboard to Grafana Cloud
- Enjoy real-time compliance monitoring! 📊✨

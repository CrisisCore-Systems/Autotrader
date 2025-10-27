# Grafana Alloy - Docker Quick Start
# Easiest way to run Alloy without installation!

## 🐳 Option 1: Docker Compose (Recommended)

### Prerequisites
```powershell
# Check Docker is running
docker --version
docker-compose --version
```

### Start Alloy + Metrics Exporter
```powershell
# Start both services
docker-compose -f docker-compose.alloy.yml up -d

# Check status
docker-compose -f docker-compose.alloy.yml ps

# View logs
docker-compose -f docker-compose.alloy.yml logs -f alloy
```

### Verify It's Working
```powershell
# Check Alloy UI
Start-Process http://localhost:12345

# Check metrics endpoint
curl http://localhost:9090/metrics

# Check Alloy is scraping
docker-compose -f docker-compose.alloy.yml logs alloy | Select-String "successfully"
```

### Stop Services
```powershell
docker-compose -f docker-compose.alloy.yml down
```

---

## 🚀 Option 2: Docker Run (Simple)

### Run Alloy Only
```powershell
docker run -d \
  --name autotrader-alloy \
  --network host \
  -v ${PWD}/configs/alloy-config.river:/etc/alloy/config.river:ro \
  grafana/alloy:latest \
  run /etc/alloy/config.river --server.http.listen-addr=0.0.0.0:12345
```

### Check Logs
```powershell
docker logs -f autotrader-alloy
```

### Stop Container
```powershell
docker stop autotrader-alloy
docker rm autotrader-alloy
```

---

## 🎯 Option 3: Run Metrics Exporter Locally, Alloy in Docker

### Terminal 1: Start Metrics Exporter
```powershell
# Activate virtual environment
.venv-1\Scripts\Activate.ps1

# Fix import issues (one-time)
pip install -e .

# Start exporter
python scripts\monitoring\export_compliance_metrics.py
```

### Terminal 2: Start Alloy in Docker
```powershell
docker run -d \
  --name autotrader-alloy \
  --network host \
  -v ${PWD}/configs/alloy-config.river:/etc/alloy/config.river:ro \
  grafana/alloy:latest \
  run /etc/alloy/config.river
```

### Terminal 3: Monitor Both
```powershell
# Watch Alloy logs
docker logs -f autotrader-alloy

# In another terminal:
curl http://localhost:9090/metrics
```

---

## ✅ Verification Checklist

After starting services, verify:

1. **Metrics Exporter Running**
```powershell
curl http://localhost:9090/metrics | Select-String "compliance_issues_total"
# Should see: compliance_issues_total{severity="critical",issue_code="..."} X
```

2. **Alloy Scraping Metrics**
```powershell
docker logs autotrader-alloy | Select-String "scraping"
# Should see: level=info component=prometheus.scrape msg="scraping target" target=localhost:9090
```

3. **Alloy Sending to Grafana Cloud**
```powershell
docker logs autotrader-alloy | Select-String "remote_write"
# Should see: level=info component=prometheus.remote_write msg="successfully sent samples"
```

4. **Alloy UI Accessible**
```powershell
Start-Process http://localhost:12345
# Should open Alloy web UI showing component graph
```

5. **Metrics in Grafana Cloud**
   - Login to: `https://crisiscore-systems.grafana.net`
   - Go to: **Explore** → **Prometheus**
   - Query: `up{job="compliance_metrics"}`
   - Should return: `1` (target is up)

---

## 🐛 Troubleshooting

### Issue: Docker not found
```powershell
# Install Docker Desktop for Windows
winget install Docker.DockerDesktop
# Or download from: https://www.docker.com/products/docker-desktop
```

### Issue: Metrics exporter fails with import errors
```powershell
# Solution: Install in development mode
pip install -e .

# Or use Docker for everything:
docker-compose -f docker-compose.alloy.yml up -d
```

### Issue: Alloy can't reach localhost:9090
```powershell
# Check exporter is running
curl http://localhost:9090/metrics

# If using Docker Compose, use --network host
# Already configured in docker-compose.alloy.yml
```

### Issue: No data in Grafana Cloud
```powershell
# Check Alloy logs for errors
docker logs autotrader-alloy | Select-String "error"

# Verify credentials are set via environment variables (recommended)
# In PowerShell (same session where you run Alloy):
#   $env:GRAFANA_CLOUD_METRICS_USERNAME = "<your instance id, e.g., 1417118>"
#   $env:GRAFANA_CLOUD_METRICS_TOKEN    = "glc_..."
# Then (prefer stdin approach):
#   .\scripts\run_alloy.ps1
```

---

## 📊 Next Steps After Alloy is Running

1. **Import Dashboard to Grafana Cloud**
   - Login: `https://crisiscore-systems.grafana.net`
   - Navigate: **Dashboards** → **Import**
   - Upload: `infrastructure/grafana/dashboards/compliance-monitoring.json`
   - Select data source: **Prometheus** (Grafana Cloud)
   - Click: **Import**

2. **Generate Test Data**
```powershell
python scripts\run_compliance_test_trading.py --cycles 20 --include-violations
```

3. **View Real-Time Dashboard**
   - Open imported dashboard
   - Should see 13 panels with live data:
     - Active Critical Violations
     - Compliance Issues Over Time
     - Alert Delivery Success Rate
     - Risk Check Failures
     - And 9 more panels...

4. **Set Up Alerts (Optional)**
   - In Grafana Cloud dashboard
   - Click panel → **Edit** → **Alert** tab
   - Create alert rule: "Notify when critical violations > 5"
   - Choose notification channel (email/Slack/PagerDuty)

---

## 🎉 Success!

When you see:
```
✅ Metrics exporter running (port 9090)
✅ Alloy scraping every 15 seconds
✅ Alloy sending to Grafana Cloud
✅ Dashboard showing real-time data
✅ Telegram alerts working (from earlier setup)
```

You have **full end-to-end compliance monitoring**! 🚀

---

## 🔄 Daily Usage

### Start Monitoring
```powershell
# Start Alloy + Exporter
docker-compose -f docker-compose.alloy.yml up -d

# Generate trading activity
python scripts\run_compliance_test_trading.py --cycles 10 --include-violations

# View dashboard in Grafana Cloud
```

### Stop Monitoring
```powershell
docker-compose -f docker-compose.alloy.yml down
```

### Update Configuration
```powershell
# Edit configs/alloy-config.river
# Restart Alloy
docker-compose -f docker-compose.alloy.yml restart alloy
```

---

**Recommendation:** Start with Docker Compose (Option 1) - it's the easiest and most reliable method!

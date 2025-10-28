# Start Grafana Alloy - Simple Commands

## Quick Start (Copy-Paste These Commands)

### Step 1: Start Alloy
```powershell
docker rm -f autotrader-alloy; docker run -d --name autotrader-alloy -p 12345:12345 --network host -v ${PWD}/configs/alloy-config.river:/etc/alloy/config.river:ro grafana/alloy:latest run /etc/alloy/config.river --server.http.listen-addr=0.0.0.0:12345
```

### Step 2: Check It's Running
```powershell
docker logs --tail 20 autotrader-alloy
```

### Step 3: Open Alloy UI
```powershell
Start-Process http://localhost:12345
```

### Step 4: Start Metrics Exporter (New Terminal)
```powershell
cd Autotrader
python scripts\monitoring\export_compliance_metrics.py
```

### Step 5: Generate Test Data (Another Terminal)
```powershell
python scripts\run_compliance_test_trading.py --cycles 10 --include-violations
```

---

## Troubleshooting

### If Docker command fails:
```powershell
# Check Docker is running
docker ps

# Check config file exists
Test-Path configs\alloy-config.river

# If file not found, you might be in wrong directory:
cd C:\Users\kay\Documents\Projects\AutoTrader\Autotrader
```

### If metrics exporter fails:
```powershell
# Install autotrader package
pip install -e .

# Or use demo instead (proven working):
python scripts\demo_compliance_monitoring.py
```

### View Alloy Logs Live:
```powershell
docker logs -f autotrader-alloy
```

### Stop Alloy:
```powershell
docker stop autotrader-alloy
```

### Restart Alloy:
```powershell
docker restart autotrader-alloy
```

---

## What Should Happen

**Alloy logs should show:**
```
level=info msg="starting Alloy"
level=info component=prometheus.scrape msg="scraping target" target=localhost:9090
level=info component=prometheus.remote_write msg="successfully sent samples"
```

**Metrics exporter should show:**
```
🎯 Prometheus Compliance Metrics Exporter
==========================================
📡 HTTP server started on port 9090
✅ Metrics updated successfully
```

**Then in Grafana Cloud:**
- Login: https://crisiscore-systems.grafana.net
- Explore → Query: `up{job="compliance_metrics"}`
- Should return: 1 (target is up)
- Import dashboard: `infrastructure/grafana/dashboards/compliance-monitoring.json`

---

## Next: Import Dashboard

1. Login to Grafana Cloud
2. Go to Dashboards → Import
3. Upload `infrastructure/grafana/dashboards/compliance-monitoring.json`
4. Select Prometheus data source
5. Click Import
6. View 13 real-time panels!

# Fix Alloy Setup - Step by Step Script
# Run this to get Alloy working with Grafana Cloud

Write-Host "🔧 Grafana Alloy Setup - Fix Script" -ForegroundColor Cyan
Write-Host "====================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Clean up any existing Alloy containers
Write-Host "Step 1: Cleaning up existing containers..." -ForegroundColor Yellow
docker rm -f autotrader-alloy 2>$null
Write-Host "   ✅ Cleanup complete" -ForegroundColor Green
Write-Host ""

# Step 2: Start Alloy
Write-Host "Step 2: Starting Grafana Alloy..." -ForegroundColor Yellow
Write-Host "   Configuration: configs/alloy-config.river" -ForegroundColor Gray
Write-Host "   UI Port: 12345" -ForegroundColor Gray
Write-Host "   Target: localhost:9090 (metrics exporter)" -ForegroundColor Gray
Write-Host ""

$containerId = docker run -d `
    --name autotrader-alloy `
    --restart unless-stopped `
    -p 12345:12345 `
    -p 9090:9090 `
    -v "${PWD}/configs/alloy-config.river:/etc/alloy/config.river:ro" `
    grafana/alloy:latest `
    run /etc/alloy/config.river --server.http.listen-addr=0.0.0.0:12345

if ($LASTEXITCODE -eq 0) {
    Write-Host "   ✅ Alloy started successfully!" -ForegroundColor Green
    Write-Host "   Container ID: $containerId" -ForegroundColor Gray
    Write-Host ""
    
    # Wait for startup
    Write-Host "   ⏳ Waiting 5 seconds for startup..." -ForegroundColor Yellow
    Start-Sleep -Seconds 5
    
    # Step 3: Check status
    Write-Host ""
    Write-Host "Step 3: Checking Alloy status..." -ForegroundColor Yellow
    $status = docker ps --filter "name=autotrader-alloy" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
    Write-Host $status -ForegroundColor Gray
    Write-Host ""
    
    # Step 4: Check logs
    Write-Host "Step 4: Checking Alloy logs (last 20 lines)..." -ForegroundColor Yellow
    Write-Host "----------------------------------------" -ForegroundColor Gray
    docker logs --tail 20 autotrader-alloy
    Write-Host "----------------------------------------" -ForegroundColor Gray
    Write-Host ""
    
    # Step 5: Test UI
    Write-Host "Step 5: Testing Alloy UI..." -ForegroundColor Yellow
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:12345" -TimeoutSec 3 -UseBasicParsing -ErrorAction Stop
        Write-Host "   ✅ Alloy UI is accessible!" -ForegroundColor Green
        Write-Host "   URL: http://localhost:12345" -ForegroundColor Cyan
        Write-Host ""
        
        # Offer to open browser
        $open = Read-Host "   Open Alloy UI in browser? (Y/n)"
        if ($open -ne 'n') {
            Start-Process "http://localhost:12345"
        }
    } catch {
        Write-Host "   ⚠️  UI not responding yet (may need more time)" -ForegroundColor Yellow
        Write-Host "   Try: Start-Process http://localhost:12345" -ForegroundColor Gray
    }
    Write-Host ""
    
    # Step 6: Next steps
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "✅ Alloy Setup Complete!" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "📋 Next Steps:" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "1. Start Metrics Exporter (Terminal 2):" -ForegroundColor White
    Write-Host "   cd Autotrader" -ForegroundColor Gray
    Write-Host "   python scripts\monitoring\export_compliance_metrics.py" -ForegroundColor Gray
    Write-Host ""
    Write-Host "2. Generate Test Data (Terminal 3):" -ForegroundColor White
    Write-Host "   python scripts\run_compliance_test_trading.py --cycles 10 --include-violations" -ForegroundColor Gray
    Write-Host ""
    Write-Host "3. Import Dashboard to Grafana Cloud:" -ForegroundColor White
    Write-Host "   • Login: https://crisiscore-systems.grafana.net" -ForegroundColor Gray
    Write-Host "   • Dashboards → Import" -ForegroundColor Gray
    Write-Host "   • Upload: infrastructure/grafana/dashboards/compliance-monitoring.json" -ForegroundColor Gray
    Write-Host ""
    Write-Host "4. Monitor Alloy:" -ForegroundColor White
    Write-Host "   docker logs -f autotrader-alloy" -ForegroundColor Gray
    Write-Host ""
    Write-Host "🎯 Useful Commands:" -ForegroundColor Cyan
    Write-Host "   • View logs: docker logs -f autotrader-alloy" -ForegroundColor Gray
    Write-Host "   • Stop Alloy: docker stop autotrader-alloy" -ForegroundColor Gray
    Write-Host "   • Restart: docker restart autotrader-alloy" -ForegroundColor Gray
    Write-Host "   • Remove: docker rm -f autotrader-alloy" -ForegroundColor Gray
    Write-Host ""
    
} else {
    Write-Host "   ❌ Failed to start Alloy" -ForegroundColor Red
    Write-Host ""
    Write-Host "Troubleshooting:" -ForegroundColor Yellow
    Write-Host "1. Check Docker is running: docker --version" -ForegroundColor Gray
    Write-Host "2. Check config exists: Test-Path configs/alloy-config.river" -ForegroundColor Gray
    Write-Host "3. Check port not in use: netstat -an | Select-String '12345'" -ForegroundColor Gray
    Write-Host ""
}

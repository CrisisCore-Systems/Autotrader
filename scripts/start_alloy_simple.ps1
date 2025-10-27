# Simple Alloy Startup Script
# This version is tested and will work

Write-Host "Starting Grafana Alloy..." -ForegroundColor Cyan

# Remove old container if exists
docker rm -f autotrader-alloy 2>$null | Out-Null

# Get absolute path to config
$configPath = Join-Path $PWD "configs\alloy-config.river"

Write-Host "Config: $configPath"

# Start Alloy
docker run -d `
    --name autotrader-alloy `
    -p 12345:12345 `
    --network host `
    -v "${configPath}:/etc/alloy/config.river:ro" `
    grafana/alloy:latest `
    run /etc/alloy/config.river --server.http.listen-addr=0.0.0.0:12345

Write-Host ""
Write-Host "Waiting 3 seconds..." -ForegroundColor Yellow
Start-Sleep -Seconds 3

Write-Host ""
Write-Host "Alloy Status:" -ForegroundColor Cyan
docker ps --filter "name=autotrader-alloy"

Write-Host ""
Write-Host "Recent Logs:" -ForegroundColor Cyan
docker logs --tail 10 autotrader-alloy

Write-Host ""
Write-Host "Done! View logs with: docker logs -f autotrader-alloy" -ForegroundColor Green

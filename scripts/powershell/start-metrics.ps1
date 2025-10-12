#!/usr/bin/env pwsh
# Start Prometheus metrics server for AutoTrader

param(
    [int]$Port = 9090,
    [string]$Address = "0.0.0.0",
    [string]$LogLevel = "INFO"
)

Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host "AutoTrader - Prometheus Metrics Server" -ForegroundColor White
Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host ""

# Check if Python is available
try {
    $pythonVersion = python --version 2>&1
    Write-Host "✓ Python found: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "✗ Python not found. Please install Python 3.13+" -ForegroundColor Red
    exit 1
}

# Check if dependencies are installed
Write-Host "Checking dependencies..." -NoNewline
try {
    python -c "import structlog, prometheus_client, opentelemetry" 2>$null
    Write-Host " ✓" -ForegroundColor Green
} catch {
    Write-Host " ✗" -ForegroundColor Red
    Write-Host ""
    Write-Host "Missing dependencies. Installing..." -ForegroundColor Yellow
    pip install structlog python-json-logger prometheus-client opentelemetry-api opentelemetry-sdk
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "✗ Failed to install dependencies" -ForegroundColor Red
        exit 1
    }
    
    Write-Host "✓ Dependencies installed" -ForegroundColor Green
}

Write-Host ""
Write-Host "Starting metrics server..." -ForegroundColor White
Write-Host "  Port:      $Port" -ForegroundColor Cyan
Write-Host "  Address:   $Address" -ForegroundColor Cyan
Write-Host "  Log Level: $LogLevel" -ForegroundColor Cyan
Write-Host ""
Write-Host "Metrics will be available at:" -ForegroundColor White
Write-Host "  http://localhost:$Port/metrics" -ForegroundColor Green
Write-Host ""
Write-Host "Press Ctrl+C to stop the server" -ForegroundColor Gray
Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host ""

# Start the metrics server
try {
    python -m src.services.metrics_server --port $Port --address $Address --log-level $LogLevel
} catch {
    Write-Host ""
    Write-Host "✗ Server stopped" -ForegroundColor Red
    exit 1
}

# VoidBloom Scanner - Startup Script
# This script starts both the backend API and frontend dashboard

Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host "VoidBloom Hidden Gem Scanner - Startup" -ForegroundColor Cyan
Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host ""

# Check if we're in the correct directory
if (!(Test-Path ".\src\core\pipeline.py")) {
    Write-Host "ERROR: Please run this script from the Autotrader root directory" -ForegroundColor Red
    Write-Host "Expected location: C:\Users\kay\Documents\Projects\AutoTrader\Autotrader" -ForegroundColor Red
    exit 1
}

# Set environment variables
$env:PYTHONPATH = (Get-Location).Path
Write-Host "[1/4] Environment configured" -ForegroundColor Green
Write-Host "       PYTHONPATH: $env:PYTHONPATH" -ForegroundColor Gray
Write-Host ""

# Start backend API in new window
Write-Host "[2/4] Starting Backend API..." -ForegroundColor Yellow
$backendArgs = @(
    "-NoExit",
    "-Command",
    "cd '$((Get-Location).Path)'; `$env:PYTHONPATH='$((Get-Location).Path)'; uvicorn simple_api:app --host 127.0.0.1 --port 8000"
)
Start-Process powershell -ArgumentList $backendArgs
Write-Host "       Backend starting on http://127.0.0.1:8000" -ForegroundColor Gray
Write-Host "       API Docs: http://127.0.0.1:8000/docs" -ForegroundColor Gray
Write-Host ""

Start-Sleep -Seconds 3

# Start frontend dashboard in new window  
Write-Host "[3/4] Starting Frontend Dashboard..." -ForegroundColor Yellow
$frontendArgs = @(
    "-NoExit",
    "-Command",
    "cd '$((Get-Location).Path)\dashboard'; npm run dev"
)
Start-Process powershell -ArgumentList $frontendArgs
Write-Host "       Dashboard starting on http://localhost:5173/" -ForegroundColor Gray
Write-Host ""

Start-Sleep -Seconds 5

# Test backend
Write-Host "[4/4] Verifying services..." -ForegroundColor Yellow
try {
    $response = Invoke-RestMethod -Uri "http://127.0.0.1:8000/" -TimeoutSec 5
    if ($response.status -eq "ok") {
        Write-Host "       Backend: OK" -ForegroundColor Green
    }
} catch {
    Write-Host "       Backend: STARTING (may take a moment)" -ForegroundColor Yellow
}

# Test frontend
try {
    $statusCode = (Invoke-WebRequest -Uri "http://localhost:5173/" -TimeoutSec 5 -UseBasicParsing).StatusCode
    if ($statusCode -eq 200) {
        Write-Host "       Frontend: OK" -ForegroundColor Green
    }
} catch {
    Write-Host "       Frontend: STARTING (may take a moment)" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host "VOIDBLOOM SCANNER IS READY!" -ForegroundColor Green
Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host ""
Write-Host "Access Points:" -ForegroundColor White
Write-Host "  Dashboard:  http://localhost:5173/" -ForegroundColor Cyan
Write-Host "  API:        http://127.0.0.1:8000/api/tokens" -ForegroundColor Cyan
Write-Host "  API Docs:   http://127.0.0.1:8000/docs" -ForegroundColor Cyan
Write-Host ""
Write-Host "Scanning Tokens: LINK, UNI, AAVE, PEPE" -ForegroundColor White
Write-Host ""
Write-Host "Press Ctrl+C in the backend/frontend windows to stop" -ForegroundColor Gray
Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host ""

# VoidBloom Enhanced Frontend Activation Script
# Run this to activate the new enhanced dashboard

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "VoidBloom Enhanced Frontend Activation" -ForegroundColor Cyan
Write-Host "============================================================`n" -ForegroundColor Cyan

# Check if we're in the right directory
if (-Not (Test-Path "dashboard\src\App.tsx")) {
    Write-Host "ERROR: Must run from project root (Autotrader folder)" -ForegroundColor Red
    exit 1
}

# Step 1: Backup original App.tsx
Write-Host "[1/5] Backing up original App.tsx..." -ForegroundColor Yellow
Copy-Item "dashboard\src\App.tsx" "dashboard\src\App-Original-Backup.tsx" -Force
Write-Host "      Saved to App-Original-Backup.tsx" -ForegroundColor Green

# Step 2: Activate enhanced version
Write-Host "`n[2/5] Activating enhanced App.tsx..." -ForegroundColor Yellow
Copy-Item "dashboard\src\App-Enhanced.tsx" "dashboard\src\App.tsx" -Force
Write-Host "      Enhanced dashboard is now active!" -ForegroundColor Green

# Step 3: Check if APIs are running
Write-Host "`n[3/5] Checking backend APIs..." -ForegroundColor Yellow

$scanner_running = $false
$enhanced_running = $false

try {
    $scanner_response = Invoke-WebRequest -Uri "http://127.0.0.1:8001/health" -TimeoutSec 2 -ErrorAction SilentlyContinue
    if ($scanner_response.StatusCode -eq 200) {
        $scanner_running = $true
        Write-Host "      Scanner API (8001): Running" -ForegroundColor Green
    }
} catch {
    Write-Host "      Scanner API (8001): Not running" -ForegroundColor Red
}

try {
    $enhanced_response = Invoke-WebRequest -Uri "http://127.0.0.1:8002/health" -TimeoutSec 2 -ErrorAction SilentlyContinue
    if ($enhanced_response.StatusCode -eq 200) {
        $enhanced_running = $true
        Write-Host "      Enhanced API (8002): Running" -ForegroundColor Green
    }
} catch {
    Write-Host "      Enhanced API (8002): Not running (optional)" -ForegroundColor Yellow
}

# Step 4: Install dependencies if needed
Write-Host "`n[4/5] Checking frontend dependencies..." -ForegroundColor Yellow
$package_json = Get-Content "dashboard\package.json" | ConvertFrom-Json
if ($package_json.dependencies.recharts) {
    Write-Host "      Recharts: Installed (v$($package_json.dependencies.recharts))" -ForegroundColor Green
} else {
    Write-Host "      Installing Recharts..." -ForegroundColor Yellow
    Push-Location dashboard
    npm install recharts
    Pop-Location
}

# Step 5: Display next steps
Write-Host "`n[5/5] Activation complete!" -ForegroundColor Green

Write-Host "`n============================================================" -ForegroundColor Cyan
Write-Host "Next Steps:" -ForegroundColor Cyan
Write-Host "============================================================`n" -ForegroundColor Cyan

if (-Not $scanner_running) {
    Write-Host "1. Start Scanner API (REQUIRED):" -ForegroundColor Yellow
    Write-Host "   python start_api.py`n" -ForegroundColor White
}

if (-Not $enhanced_running) {
    Write-Host "2. Start Enhanced API (OPTIONAL):" -ForegroundColor Yellow
    Write-Host "   python start_enhanced_api.py`n" -ForegroundColor White
}

Write-Host "3. Start Frontend:" -ForegroundColor Yellow
Write-Host "   cd dashboard" -ForegroundColor White
Write-Host "   npm run dev`n" -ForegroundColor White

Write-Host "4. Open Browser:" -ForegroundColor Yellow
Write-Host "   http://localhost:5173/`n" -ForegroundColor White

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "New Features Available:" -ForegroundColor Cyan
Write-Host "============================================================`n" -ForegroundColor Cyan
Write-Host "  Overview       - Original dashboard (enhanced)" -ForegroundColor White
Write-Host "  Analytics     - Confidence charts, correlation matrix," -ForegroundColor White
Write-Host "                    order flow depth, sentiment trends" -ForegroundColor White
Write-Host "  System Health  - SLA monitoring, anomaly alerts," -ForegroundColor White
Write-Host "                    circuit breakers" -ForegroundColor White
Write-Host "  Features       - Feature store browser with search" -ForegroundColor White

Write-Host "`n============================================================" -ForegroundColor Cyan
Write-Host "Rollback Command (if needed):" -ForegroundColor Cyan
Write-Host "============================================================`n" -ForegroundColor Cyan
Write-Host "Copy-Item dashboard\src\App-Original-Backup.tsx dashboard\src\App.tsx -Force`n" -ForegroundColor Gray

Write-Host "Documentation: See ENHANCED_FRONTEND_GUIDE.md`n" -ForegroundColor Cyan
Write-Host "Happy Trading! " -NoNewline -ForegroundColor Green
Write-Host "[U+1F680][U+1F4C8]`n" -ForegroundColor Green

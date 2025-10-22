# Pre-Market Scanner - Runs at 7:30 AM ET
# Scans for gap-up candidates before market opens

# Navigate to project directory
$projectPath = "C:\Users\kay\Documents\Projects\AutoTrader\Autotrader"
Set-Location $projectPath

# Activate virtual environment
& "C:\Users\kay\Documents\Projects\AutoTrader\.venv-1\Scripts\Activate.ps1"

# Log start
$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
$logFile = "$projectPath\logs\scheduled_runs.log"
Add-Content -Path $logFile -Value "`n[$timestamp] ========== PRE-MARKET SCAN STARTED =========="

# Check if market will be open today
Write-Host "Checking market hours..." -ForegroundColor Cyan
python "$projectPath\scripts\market_hours_validator.py" pre_market_scan

if ($LASTEXITCODE -eq 0) {
    Write-Host "✓ Market validation passed - Starting scanner" -ForegroundColor Green
    Add-Content -Path $logFile -Value "[$timestamp] Market validation passed"
    
    # Run scanner with free mode (no live trading)
    Write-Host "Running pre-market scanner..." -ForegroundColor Yellow
    python "$projectPath\run_scanner_free.py" 2>&1 | Tee-Object -FilePath "$projectPath\logs\pre_market_scan_$(Get-Date -Format 'yyyyMMdd').log"
    
    $exitCode = $LASTEXITCODE
    if ($exitCode -eq 0) {
        Write-Host "✓ Pre-market scan completed successfully" -ForegroundColor Green
        Add-Content -Path $logFile -Value "[$timestamp] Pre-market scan completed successfully"
        
        # Check if any candidates found
        $resultsFile = "$projectPath\scan_results\gap_candidates_$(Get-Date -Format 'yyyyMMdd').json"
        if (Test-Path $resultsFile) {
            $candidates = Get-Content $resultsFile | ConvertFrom-Json
            $count = $candidates.Count
            Write-Host "Found $count gap-up candidates for today" -ForegroundColor Green
            Add-Content -Path $logFile -Value "[$timestamp] Found $count candidates"
        }
    } else {
        Write-Host "✗ Scanner failed with exit code $exitCode" -ForegroundColor Red
        Add-Content -Path $logFile -Value "[$timestamp] ERROR: Scanner failed with exit code $exitCode"
    }
} else {
    Write-Host "✗ Market validation failed - Skipping scan" -ForegroundColor Yellow
    Add-Content -Path $logFile -Value "[$timestamp] Skipped: Market validation failed"
}

Add-Content -Path $logFile -Value "[$timestamp] ========== PRE-MARKET SCAN ENDED ==========`n"

# Market Open Entry - Runs at 9:35 AM ET
# Enters positions 5 minutes after market opens to avoid initial volatility

# Navigate to project directory
$projectPath = "C:\Users\kay\Documents\Projects\AutoTrader\Autotrader"
Set-Location $projectPath

# Activate virtual environment
& "C:\Users\kay\Documents\Projects\AutoTrader\.venv-1\Scripts\Activate.ps1"

# Log start
$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
$logFile = "$projectPath\logs\scheduled_runs.log"
Add-Content -Path $logFile -Value "`n[$timestamp] ========== MARKET OPEN ENTRY STARTED =========="

# Check if market is open
Write-Host "Checking market status..." -ForegroundColor Cyan
python "$projectPath\scripts\market_hours_validator.py" market_open_entry

if ($LASTEXITCODE -eq 0) {
    Write-Host "✓ Market is open - Starting paper trading" -ForegroundColor Green
    Add-Content -Path $logFile -Value "[$timestamp] Market is open"
    
    # Check IBKR connection
    Write-Host "Checking IBKR connection..." -ForegroundColor Cyan
    python -c "from ib_insync import IB; ib = IB(); ib.connect('127.0.0.1', 7497, clientId=999, timeout=5); print('OK'); ib.disconnect()"
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✓ IBKR connected - Executing paper trading" -ForegroundColor Green
        Add-Content -Path $logFile -Value "[$timestamp] IBKR connected"
        
        # Run paper trading with nightly mode
        Write-Host "Running paper trading system..." -ForegroundColor Yellow
        python "$projectPath\run_pennyhunter_paper.py" 2>&1 | Tee-Object -FilePath "$projectPath\logs\market_open_entry_$(Get-Date -Format 'yyyyMMdd').log"
        
        $exitCode = $LASTEXITCODE
        if ($exitCode -eq 0) {
            Write-Host "✓ Paper trading execution completed" -ForegroundColor Green
            Add-Content -Path $logFile -Value "[$timestamp] Paper trading completed successfully"
            
            # Show position summary
            Write-Host "`nPosition Summary:" -ForegroundColor Cyan
            python -c "import sqlite3; conn = sqlite3.connect('bouncehunter_memory.db'); cur = conn.cursor(); positions = cur.execute('SELECT symbol, shares, entry_price FROM position_exits WHERE exit_time IS NULL').fetchall(); print(f'Active Positions: {len(positions)}'); [print(f'  - {p[0]}: {p[1]} shares @ \${p[2]:.2f}') for p in positions]; conn.close()"
        } else {
            Write-Host "✗ Paper trading failed with exit code $exitCode" -ForegroundColor Red
            Add-Content -Path $logFile -Value "[$timestamp] ERROR: Paper trading failed with exit code $exitCode"
        }
    } else {
        Write-Host "✗ IBKR not connected - Cannot execute trades" -ForegroundColor Red
        Add-Content -Path $logFile -Value "[$timestamp] ERROR: IBKR not connected"
        Write-Host "Make sure TWS/Gateway is running on port 7497" -ForegroundColor Yellow
    }
} else {
    Write-Host "✗ Market not open - Skipping execution" -ForegroundColor Yellow
    Add-Content -Path $logFile -Value "[$timestamp] Skipped: Market not open"
}

Add-Content -Path $logFile -Value "[$timestamp] ========== MARKET OPEN ENTRY ENDED ==========`n"

# End-of-Day Cleanup - Runs at 4:15 PM ET
# Reviews positions, generates reports, and updates memory system

# Navigate to project directory
$projectPath = "C:\Users\kay\Documents\Projects\AutoTrader\Autotrader"
Set-Location $projectPath

# Activate virtual environment
& "C:\Users\kay\Documents\Projects\AutoTrader\.venv-1\Scripts\Activate.ps1"

# Log start
$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
$logFile = "$projectPath\logs\scheduled_runs.log"
Add-Content -Path $logFile -Value "`n[$timestamp] ========== END-OF-DAY CLEANUP STARTED =========="

# Check if we're in the cleanup window
Write-Host "Checking cleanup window..." -ForegroundColor Cyan
python "$projectPath\scripts\market_hours_validator.py" end_of_day_cleanup

if ($LASTEXITCODE -eq 0) {
    Write-Host "✓ In cleanup window - Starting EOD tasks" -ForegroundColor Green
    Add-Content -Path $logFile -Value "[$timestamp] Starting EOD cleanup"
    
    # 1. Generate daily report
    Write-Host "`n1. Generating daily report..." -ForegroundColor Yellow
    python "$projectPath\scripts\generate_daily_report.py" 2>&1 | Tee-Object -FilePath "$projectPath\logs\daily_report_$(Get-Date -Format 'yyyyMMdd').log" -Append
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✓ Daily report generated" -ForegroundColor Green
        Add-Content -Path $logFile -Value "[$timestamp] Daily report generated"
    } else {
        Write-Host "✗ Daily report failed" -ForegroundColor Red
        Add-Content -Path $logFile -Value "[$timestamp] WARNING: Daily report failed"
    }
    
    # 2. Review open positions
    Write-Host "`n2. Reviewing open positions..." -ForegroundColor Yellow
    python -c @"
import sqlite3
from datetime import datetime

conn = sqlite3.connect('bouncehunter_memory.db')
cur = conn.cursor()

# Get open positions
positions = cur.execute('''
    SELECT symbol, shares, entry_price, entry_time 
    FROM position_exits 
    WHERE exit_time IS NULL
''').fetchall()

print(f'\nOpen Positions: {len(positions)}')
for symbol, shares, entry_price, entry_time in positions:
    print(f'  - {symbol}: {shares} shares @ \${entry_price:.2f} (entered {entry_time})')

# Get today's closed positions
today = datetime.now().strftime('%Y-%m-%d')
closed = cur.execute('''
    SELECT symbol, pnl 
    FROM position_exits 
    WHERE exit_time LIKE ? AND exit_time IS NOT NULL
''', (f'{today}%',)).fetchall()

if closed:
    total_pnl = sum(p[1] for p in closed)
    print(f'\nToday\'s Closed: {len(closed)} positions')
    print(f'Total P&L: \${total_pnl:.2f}')
    for symbol, pnl in closed:
        print(f'  - {symbol}: \${pnl:+.2f}')

conn.close()
"@
    
    # 3. Update memory system
    Write-Host "`n3. Updating memory system..." -ForegroundColor Yellow
    python -c @"
import sqlite3
from datetime import datetime, timedelta

conn = sqlite3.connect('reports/pennyhunter_memory.db')
cur = conn.cursor()

# Clean up old monitored tickers (>30 days)
cutoff = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
deleted = cur.execute('''
    DELETE FROM memory_system 
    WHERE status = 'monitored' AND last_seen < ?
''', (cutoff,)).rowcount

print(f'Cleaned up {deleted} old monitored tickers')

# Get memory stats
stats = cur.execute('''
    SELECT status, COUNT(*) 
    FROM memory_system 
    GROUP BY status
''').fetchall()

print('\nMemory System Status:')
for status, count in stats:
    print(f'  {status}: {count} tickers')

conn.commit()
conn.close()
"@
    
    Add-Content -Path $logFile -Value "[$timestamp] Memory system updated"
    
    # 4. Backup databases
    Write-Host "`n4. Backing up databases..." -ForegroundColor Yellow
    $backupDir = "$projectPath\backups\$(Get-Date -Format 'yyyyMMdd')"
    New-Item -ItemType Directory -Force -Path $backupDir | Out-Null
    
    Copy-Item "$projectPath\bouncehunter_memory.db" "$backupDir\bouncehunter_memory.db" -Force
    Copy-Item "$projectPath\reports\pennyhunter_memory.db" "$backupDir\pennyhunter_memory.db" -Force
    Copy-Item "$projectPath\reports\pennyhunter_cumulative_history.json" "$backupDir\pennyhunter_cumulative_history.json" -Force
    
    Write-Host "✓ Databases backed up to $backupDir" -ForegroundColor Green
    Add-Content -Path $logFile -Value "[$timestamp] Databases backed up"
    
    # 5. Clean up old log files (keep 30 days)
    Write-Host "`n5. Cleaning old logs..." -ForegroundColor Yellow
    $oldLogs = Get-ChildItem "$projectPath\logs" -Filter "*.log" | Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-30) }
    $oldLogs | Remove-Item -Force
    Write-Host "✓ Removed $($oldLogs.Count) old log files" -ForegroundColor Green
    
    # Summary
    Write-Host "`n" + ("="*60) -ForegroundColor Cyan
    Write-Host "End-of-Day Cleanup Complete" -ForegroundColor Green
    Write-Host ("="*60) -ForegroundColor Cyan
    
    Add-Content -Path $logFile -Value "[$timestamp] EOD cleanup completed successfully"
    
} else {
    Write-Host "✗ Outside cleanup window - Skipping" -ForegroundColor Yellow
    Add-Content -Path $logFile -Value "[$timestamp] Skipped: Outside cleanup window"
}

Add-Content -Path $logFile -Value "[$timestamp] ========== END-OF-DAY CLEANUP ENDED ==========`n"

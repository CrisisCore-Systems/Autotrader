# Weekly Report Generator - Runs Friday at 5:00 PM ET
# Generates comprehensive weekly performance report

# Navigate to project directory
$projectPath = "C:\Users\kay\Documents\Projects\AutoTrader\Autotrader"
Set-Location $projectPath

# Activate virtual environment
& "C:\Users\kay\Documents\Projects\AutoTrader\.venv-1\Scripts\Activate.ps1"

# Log start
$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
$logFile = "$projectPath\logs\scheduled_runs.log"
Add-Content -Path $logFile -Value "`n[$timestamp] ========== WEEKLY REPORT STARTED =========="

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "Weekly Performance Report" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# Generate report
python -c @"
import sqlite3
import json
from datetime import datetime, timedelta
from pathlib import Path

# Calculate week start (last Monday)
today = datetime.now()
days_since_monday = today.weekday()
week_start = (today - timedelta(days=days_since_monday)).strftime('%Y-%m-%d')
week_end = today.strftime('%Y-%m-%d')

print(f'\nWeek: {week_start} to {week_end}')
print('='*60)

# Connect to database
conn = sqlite3.connect('bouncehunter_memory.db')
cur = conn.cursor()

# Get this week's trades
trades = cur.execute('''
    SELECT 
        symbol,
        entry_time,
        exit_time,
        entry_price,
        exit_price,
        shares,
        pnl
    FROM position_exits
    WHERE exit_time BETWEEN ? AND ?
    ORDER BY exit_time
''', (week_start, week_end + ' 23:59:59')).fetchall()

if not trades:
    print('\nNo trades this week.')
    conn.close()
    exit(0)

# Calculate statistics
total_pnl = sum(t[6] for t in trades)
winners = [t for t in trades if t[6] > 0]
losers = [t for t in trades if t[6] <= 0]
win_rate = len(winners) / len(trades) * 100 if trades else 0

avg_winner = sum(w[6] for w in winners) / len(winners) if winners else 0
avg_loser = sum(l[6] for l in losers) / len(losers) if losers else 0

print(f'\n📊 WEEKLY SUMMARY')
print(f'Total Trades: {len(trades)}')
print(f'Winners: {len(winners)} ({len(winners)/len(trades)*100:.1f}%)')
print(f'Losers: {len(losers)} ({len(losers)/len(trades)*100:.1f}%)')
print(f'Win Rate: {win_rate:.1f}%')
print(f'Total P&L: \${total_pnl:,.2f}')
print(f'Avg Winner: \${avg_winner:.2f}')
print(f'Avg Loser: \${avg_loser:.2f}')
if avg_loser != 0:
    profit_factor = abs(avg_winner / avg_loser)
    print(f'Profit Factor: {profit_factor:.2f}')

# Best and worst trades
if winners:
    best = max(winners, key=lambda x: x[6])
    print(f'\n🏆 Best Trade: {best[0]} - \${best[6]:+.2f}')

if losers:
    worst = min(losers, key=lambda x: x[6])
    print(f'💔 Worst Trade: {worst[0]} - \${worst[6]:+.2f}')

# Trade list
print(f'\n📋 ALL TRADES:')
print(f'{'Date':<12} {'Symbol':<6} {'P&L':>10} {'Entry':>8} {'Exit':>8} {'Shares':>6}')
print('-'*60)
for trade in trades:
    date = trade[2][:10] if trade[2] else 'Open'
    pnl_str = f'\${trade[6]:+.2f}' if trade[6] else '--'
    print(f'{date:<12} {trade[0]:<6} {pnl_str:>10} \${trade[3]:>7.2f} \${trade[4]:>7.2f} {trade[5]:>6}')

# Phase 2 validation check
history_file = Path('reports/pennyhunter_cumulative_history.json')
if history_file.exists():
    with open(history_file) as f:
        history = json.load(f)
    
    phase2_trades = len([t for t in history.get('trades', []) if t.get('phase') == 'phase2'])
    phase2_wr = history.get('phase2_win_rate', 0)
    
    print(f'\n🎯 PHASE 2 VALIDATION PROGRESS:')
    print(f'Trades: {phase2_trades}/20')
    print(f'Win Rate: {phase2_wr:.1f}% (Target: 70%)')
    print(f'Status: {'✓ ON TRACK' if phase2_wr >= 70 else '⚠ NEEDS IMPROVEMENT'}')

# Memory system stats
mem_conn = sqlite3.connect('reports/pennyhunter_memory.db')
mem_cur = mem_conn.cursor()

stats = mem_cur.execute('''
    SELECT status, COUNT(*)
    FROM memory_system
    GROUP BY status
''').fetchall()

print(f'\n💾 MEMORY SYSTEM:')
for status, count in stats:
    print(f'  {status}: {count} tickers')

mem_conn.close()
conn.close()

# Save report to file
report_file = f'reports/weekly_report_{week_end}.txt'
print(f'\n✓ Report saved to {report_file}')
"@ | Tee-Object -FilePath "$projectPath\reports\weekly_report_$(Get-Date -Format 'yyyyMMdd').txt"

if ($LASTEXITCODE -eq 0) {
    Write-Host "`n✓ Weekly report generated successfully" -ForegroundColor Green
    Add-Content -Path $logFile -Value "[$timestamp] Weekly report generated"
    
    # Email report (optional - configure SMTP settings)
    # Send-MailMessage -To "your@email.com" -From "pennyhunter@trading.com" `
    #     -Subject "PennyHunter Weekly Report - $(Get-Date -Format 'yyyy-MM-dd')" `
    #     -Body (Get-Content "$projectPath\reports\weekly_report_$(Get-Date -Format 'yyyyMMdd').txt" -Raw) `
    #     -SmtpServer "smtp.gmail.com" -Port 587 -UseSsl `
    #     -Credential (Get-Credential)
    
} else {
    Write-Host "✗ Report generation failed" -ForegroundColor Red
    Add-Content -Path $logFile -Value "[$timestamp] ERROR: Report generation failed"
}

Add-Content -Path $logFile -Value "[$timestamp] ========== WEEKLY REPORT ENDED ==========`n"

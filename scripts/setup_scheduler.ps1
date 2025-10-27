# Setup Windows Task Scheduler Jobs
# Run this script once to configure all scheduled tasks

# Requires Administrator privileges
if (-NOT ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")) {
    Write-Warning "This script requires Administrator privileges!"
    Write-Host "Please run PowerShell as Administrator and try again." -ForegroundColor Yellow
    exit
}

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "PennyHunter Scheduler Setup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

$projectPath = "C:\Users\kay\Documents\Projects\AutoTrader\Autotrader"
$scriptsPath = "$projectPath\scripts"

# Create logs directory if it doesn't exist
$logsPath = "$projectPath\logs"
if (-not (Test-Path $logsPath)) {
    New-Item -ItemType Directory -Path $logsPath -Force | Out-Null
    Write-Host "✓ Created logs directory" -ForegroundColor Green
}

# Create backups directory
$backupsPath = "$projectPath\backups"
if (-not (Test-Path $backupsPath)) {
    New-Item -ItemType Directory -Path $backupsPath -Force | Out-Null
    Write-Host "✓ Created backups directory" -ForegroundColor Green
}

# Function to create scheduled task
function New-TradingTask {
    param(
        [string]$TaskName,
        [string]$Description,
        [string]$ScriptPath,
        [string]$Time,
        [string[]]$Days = @('Monday','Tuesday','Wednesday','Thursday','Friday')
    )
    
    Write-Host "`nCreating task: $TaskName" -ForegroundColor Yellow
    
    # Remove existing task if it exists
    $existingTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($existingTask) {
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
        Write-Host "  Removed existing task" -ForegroundColor Gray
    }
    
    # Create action
    $action = New-ScheduledTaskAction `
        -Execute "PowerShell.exe" `
        -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$ScriptPath`"" `
        -WorkingDirectory $projectPath
    
    # Create trigger (daily at specified time)
    $trigger = New-ScheduledTaskTrigger -Daily -At $Time
    
    # Set days of week
    $trigger.DaysOfWeek = $Days -join ','
    
    # Create settings
    $settings = New-ScheduledTaskSettingsSet `
        -AllowStartIfOnBatteries `
        -DontStopIfGoingOnBatteries `
        -StartWhenAvailable `
        -RunOnlyIfNetworkAvailable `
        -ExecutionTimeLimit (New-TimeSpan -Hours 1)
    
    # Create principal (run whether user is logged in or not)
    $principal = New-ScheduledTaskPrincipal `
        -UserId "$env:USERDOMAIN\$env:USERNAME" `
        -LogonType S4U `
        -RunLevel Highest
    
    # Register task
    Register-ScheduledTask `
        -TaskName $TaskName `
        -Description $Description `
        -Action $action `
        -Trigger $trigger `
        -Settings $settings `
        -Principal $principal | Out-Null
    
    Write-Host "  ✓ Task created: Runs $($Days -join ', ') at $Time" -ForegroundColor Green
}

# Task 1: Pre-Market Scan (7:30 AM ET)
New-TradingTask `
    -TaskName "PennyHunter_PreMarket_Scan" `
    -Description "Scans for gap-up candidates before market opens (7:30 AM ET)" `
    -ScriptPath "$scriptsPath\scheduled_pre_market_scan.ps1" `
    -Time "07:30"

# Task 2: Market Open Entry (9:35 AM ET)
New-TradingTask `
    -TaskName "PennyHunter_Market_Open_Entry" `
    -Description "Enters positions 5 minutes after market open (9:35 AM ET)" `
    -ScriptPath "$scriptsPath\scheduled_market_open_entry.ps1" `
    -Time "09:35"

# Task 3: End-of-Day Cleanup (4:15 PM ET)
New-TradingTask `
    -TaskName "PennyHunter_EOD_Cleanup" `
    -Description "Daily cleanup, reports, and backups (4:15 PM ET)" `
    -ScriptPath "$scriptsPath\scheduled_eod_cleanup.ps1" `
    -Time "16:15"

# Task 4: Weekly Report (5:00 PM ET Friday)
New-TradingTask `
    -TaskName "PennyHunter_Weekly_Report" `
    -Description "Generates weekly performance report (Friday 5:00 PM ET)" `
    -ScriptPath "$scriptsPath\scheduled_weekly_report.ps1" `
    -Time "17:00" `
    -Days @('Friday')

# Summary
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "Setup Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan

Write-Host "`nScheduled Tasks Created:" -ForegroundColor White
Write-Host "  1. Pre-Market Scan      - 7:30 AM ET (Mon-Fri)" -ForegroundColor Gray
Write-Host "  2. Market Open Entry    - 9:35 AM ET (Mon-Fri)" -ForegroundColor Gray
Write-Host "  3. EOD Cleanup          - 4:15 PM ET (Mon-Fri)" -ForegroundColor Gray
Write-Host "  4. Weekly Report        - 5:00 PM ET (Friday)" -ForegroundColor Gray

Write-Host "`nNext Steps:" -ForegroundColor Yellow
Write-Host "  1. Verify tasks in Task Scheduler (taskschd.msc)" -ForegroundColor White
Write-Host "  2. Ensure IBKR TWS/Gateway is set to auto-start" -ForegroundColor White
Write-Host "  3. Test a task manually: Right-click → Run in Task Scheduler" -ForegroundColor White
Write-Host "  4. Monitor logs in: $logsPath" -ForegroundColor White

Write-Host "`nTo remove all tasks, run:" -ForegroundColor Yellow
Write-Host "  Get-ScheduledTask -TaskName 'PennyHunter_*' | Unregister-ScheduledTask -Confirm:`$false" -ForegroundColor Gray

Write-Host "`nPress any key to open Task Scheduler..." -ForegroundColor Cyan
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
taskschd.msc

# Automated Trading Schedule

## Overview
Comprehensive scheduling system for PennyHunter paper trading operations. All tasks run automatically at optimal market times using Windows Task Scheduler.

## 📅 Daily Schedule (Monday - Friday)

### 1. Pre-Market Scan 📊
**Time:** 7:30 AM ET  
**Script:** `scheduled_pre_market_scan.ps1`  
**Duration:** ~5-10 minutes  
**Purpose:** Identify gap-up candidates before market opens

**What it does:**
- Validates market will be open today
- Runs gap scanner on 1000 ticker universe
- Filters for gap%, volume, and technical criteria
- Saves candidates to `scan_results/gap_candidates_YYYYMMDD.json`
- Logs results for review

**Ideal because:**
- Market data is stable (previous day's close)
- Gives 2 hours to review candidates before market open
- Avoids pre-market volatility noise

### 2. Market Open Entry 🚀
**Time:** 9:35 AM ET (5 minutes after market opens)  
**Script:** `scheduled_market_open_entry.ps1`  
**Duration:** ~2-5 minutes  
**Purpose:** Enter positions after initial volatility settles

**What it does:**
- Validates market is currently open
- Checks IBKR TWS/Gateway connection
- Runs paper trading system (`run_pennyhunter_paper.py`)
- Selects best candidates from morning scan
- Enters up to 5 positions with proper sizing
- Updates memory system
- Logs all trades

**Ideal because:**
- Avoids 9:30-9:35 AM opening volatility spike
- Prices are more stable after initial rush
- Order fills are more reliable
- Gaps have been "confirmed" by market participants

**Requirements:**
- IBKR TWS/Gateway running on port 7497
- At least 1 gap candidate from morning scan
- Sufficient buying power ($200 per position)

### 3. End-of-Day Cleanup 🧹
**Time:** 4:15 PM ET (15 minutes after market close)  
**Script:** `scheduled_eod_cleanup.ps1`  
**Duration:** ~5 minutes  
**Purpose:** Close positions, generate reports, maintain system

**What it does:**
- Reviews all open positions
- Generates daily performance report
- Updates memory system (win rates, blocklists)
- Backs up databases to `backups/YYYYMMDD/`
- Cleans up old log files (>30 days)
- Prepares system for next trading day

**Ideal because:**
- Market data is final (no more price changes)
- Can review full day's performance
- Databases are not actively being written to
- Sufficient time before after-hours trading

### 4. Weekly Report 📈
**Time:** 5:00 PM ET Friday  
**Script:** `scheduled_weekly_report.ps1`  
**Duration:** ~2 minutes  
**Purpose:** Comprehensive weekly performance analysis

**What it does:**
- Aggregates all trades from Monday-Friday
- Calculates win rate, profit factor, avg win/loss
- Shows best and worst trades of the week
- Tracks Phase 2 validation progress (20-trade milestone)
- Displays memory system statistics
- Saves report to `reports/weekly_report_YYYYMMDD.txt`
- Optional email delivery

**Ideal because:**
- Week's trading is complete
- Time to reflect on performance
- Plan improvements for next week

## 🔧 Setup Instructions

### Prerequisites
1. **Windows 10/11** with Task Scheduler
2. **Python environment** configured (`.venv-1`)
3. **IBKR TWS/Gateway** set to auto-start
4. **Administrator privileges** for scheduler setup

### Initial Setup

**Step 1: Install dependencies**
```powershell
cd C:\Users\kay\Documents\Projects\AutoTrader\Autotrader
pip install pandas-market-calendars pytz
```

**Step 2: Run scheduler setup (as Administrator)**
```powershell
# Right-click PowerShell → Run as Administrator
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
cd C:\Users\kay\Documents\Projects\AutoTrader\Autotrader\scripts
.\setup_scheduler.ps1
```

This will:
- Create all 4 scheduled tasks
- Set up logs and backups directories
- Configure tasks to run whether you're logged in or not
- Open Task Scheduler for verification

**Step 3: Verify tasks**
```powershell
Get-ScheduledTask -TaskName "PennyHunter_*" | Format-Table TaskName, State, NextRunTime
```

Should show:
```
TaskName                          State  NextRunTime
--------                          -----  -----------
PennyHunter_PreMarket_Scan        Ready  [Next weekday 7:30 AM]
PennyHunter_Market_Open_Entry     Ready  [Next weekday 9:35 AM]
PennyHunter_EOD_Cleanup           Ready  [Next weekday 4:15 PM]
PennyHunter_Weekly_Report         Ready  [Next Friday 5:00 PM]
```

**Step 4: Test a task manually**
```powershell
# Test pre-market scan
Start-ScheduledTask -TaskName "PennyHunter_PreMarket_Scan"

# Check logs
Get-Content C:\Users\kay\Documents\Projects\AutoTrader\Autotrader\logs\scheduled_runs.log -Tail 50
```

## 📋 Task Details

### Task Configuration
All tasks run with:
- **Highest privileges** (required for IBKR connection)
- **Run whether user logged in or not**
- **Start when available** (if missed due to shutdown)
- **Network required** (for market data and IBKR)
- **1 hour timeout** (safety limit)
- **Battery allowed** (for laptops)

### Log Files
All activity logged to:
- **Master log:** `logs/scheduled_runs.log`
- **Task-specific logs:** `logs/[task_name]_YYYYMMDD.log`

Log format:
```
[2025-10-21 07:30:05] ========== PRE-MARKET SCAN STARTED ==========
[2025-10-21 07:30:06] Market validation passed
[2025-10-21 07:30:45] Found 12 candidates
[2025-10-21 07:30:45] Pre-market scan completed successfully
[2025-10-21 07:30:45] ========== PRE-MARKET SCAN ENDED ==========
```

### Backups
Daily backups created at 4:15 PM in:
```
backups/
  20251021/
    bouncehunter_memory.db
    pennyhunter_memory.db
    pennyhunter_cumulative_history.json
  20251022/
    ...
```

Retention: **30 days** (automatic cleanup)

## 🎯 Market Hours Validation

All tasks validate market status before executing using `market_hours_validator.py`:

**Checks performed:**
- ✓ Is today a trading day? (NYSE calendar)
- ✓ Is market currently open? (9:30 AM - 4:00 PM ET)
- ✓ Are we in a valid execution window?
- ✓ Handle holidays and early closes

**Fallback logic:**
- If market calendar unavailable, uses simple time check
- Skips weekends automatically
- Logs reason for any skipped execution

## 🚨 Error Handling

### If a task fails:
1. **Check logs:** `logs/scheduled_runs.log`
2. **Verify IBKR:** TWS/Gateway running on port 7497
3. **Check network:** Internet connection required
4. **Test manually:** Run PowerShell script directly
5. **Review output:** Look for error messages

### Common issues:

**"Market validation failed"**
- Market is closed (weekend/holiday)
- Outside trading hours
- Expected behavior - task will retry tomorrow

**"IBKR not connected"**
- TWS/Gateway not running
- Wrong port (should be 7497 for paper)
- Client ID conflict (change if needed)

**"Scanner found 0 candidates"**
- Market conditions unfavorable (no gaps)
- Filters too strict (check `my_paper_config.yaml`)
- Universe file empty (`under10_tickers.txt`)

**"Permission denied"**
- Task not running with highest privileges
- Re-run `setup_scheduler.ps1` as Administrator

## 🔄 Maintenance

### Weekly
- Review `logs/scheduled_runs.log`
- Check `reports/weekly_report_*.txt`
- Verify backups exist in `backups/`

### Monthly
- Review Phase 2 validation progress
- Analyze win rate trends
- Update memory system thresholds if needed
- Clean up very old backups (>90 days)

### As Needed
- Update universe file (`under10_tickers.txt`)
- Adjust filters in `my_paper_config.yaml`
- Modify execution times (edit `setup_scheduler.ps1`)

## 🎛️ Customization

### Change execution times:
Edit `setup_scheduler.ps1` and re-run:
```powershell
# Example: Change pre-market scan to 7:00 AM
New-TradingTask `
    -TaskName "PennyHunter_PreMarket_Scan" `
    -ScriptPath "$scriptsPath\scheduled_pre_market_scan.ps1" `
    -Time "07:00"  # Changed from 07:30
```

### Disable a task:
```powershell
Disable-ScheduledTask -TaskName "PennyHunter_PreMarket_Scan"
```

### Re-enable:
```powershell
Enable-ScheduledTask -TaskName "PennyHunter_PreMarket_Scan"
```

### Remove all tasks:
```powershell
Get-ScheduledTask -TaskName "PennyHunter_*" | Unregister-ScheduledTask -Confirm:$false
```

## 📊 Monitoring

### View task history:
```powershell
Get-ScheduledTask -TaskName "PennyHunter_*" | Get-ScheduledTaskInfo | Format-Table TaskName, LastRunTime, LastTaskResult, NextRunTime
```

### Real-time log monitoring:
```powershell
Get-Content logs\scheduled_runs.log -Wait -Tail 20
```

### Check if running now:
```powershell
Get-Process powershell | Where-Object { $_.CommandLine -like "*scheduled_*" }
```

## 🎓 Best Practices

### 1. Always validate before enabling
- Test each script manually first
- Verify IBKR connection works
- Check logs for errors

### 2. Monitor first week closely
- Review logs daily
- Verify trades are executing correctly
- Check position sizing is appropriate

### 3. Set up alerts (optional)
- Email notifications on failures
- SMS for critical errors
- Dashboard monitoring

### 4. Keep system updated
- Review and update universe quarterly
- Adjust filters based on market conditions
- Monitor Phase 2 validation progress

### 5. Have a kill switch
- Know how to disable all tasks quickly
- Keep manual control via GUI
- Always review before going live (post Phase 2)

## 📈 Performance Expectations

With optimal scheduling:
- **Pre-market scan:** Find 5-20 candidates daily
- **Entry execution:** Fill 2-5 positions on average
- **Daily trades:** 1-3 complete round trips
- **Win rate target:** 70%+ (Phase 2 validation)
- **Position holding:** 1-3 hours average

## 🔐 Security

### Credentials:
- IBKR credentials stored in TWS (not in scripts)
- No passwords in log files
- Task Scheduler uses Windows authentication

### Data protection:
- Daily backups of all databases
- 30-day retention policy
- Logs contain no sensitive data

## 🎯 Phase 2 Validation Integration

Scheduler supports Phase 2 validation tracking:
- Each trade logged to cumulative history
- Win rate calculated automatically
- Progress shown in weekly reports
- 20-trade milestone monitored
- Ready for Phase 3 (live trading) when validated

## 📞 Support

### If tasks stop working:
1. Check Task Scheduler (taskschd.msc)
2. Review logs (`logs/scheduled_runs.log`)
3. Test IBKR connection manually
4. Verify Python environment active
5. Re-run `setup_scheduler.ps1`

### To completely reset:
```powershell
# Remove all tasks
Get-ScheduledTask -TaskName "PennyHunter_*" | Unregister-ScheduledTask -Confirm:$false

# Clear logs (optional)
Remove-Item logs\* -Force

# Re-setup
.\scripts\setup_scheduler.ps1
```

## ✨ Benefits of Scheduling

### Automation
- ✓ No manual intervention required
- ✓ Runs on exact schedule
- ✓ Consistent execution timing

### Optimization
- ✓ Tasks run at ideal market times
- ✓ Avoids costly timing mistakes
- ✓ Maximizes opportunity capture

### Reliability
- ✓ Never miss pre-market scan
- ✓ Always enter at optimal time
- ✓ Automated backups and cleanup

### Scalability
- ✓ Easy to add new tasks
- ✓ Modify timing as needed
- ✓ Ready for live trading (Phase 3)

---

**Status:** ✅ PRODUCTION READY  
**Setup Time:** 10 minutes  
**Maintenance:** Minimal (weekly review)  
**Reliability:** Excellent with proper IBKR setup

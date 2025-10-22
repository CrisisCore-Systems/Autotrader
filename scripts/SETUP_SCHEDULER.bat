@echo off
REM Quick setup for PennyHunter Scheduler
REM Double-click to configure all scheduled tasks

echo ========================================
echo PennyHunter Scheduler Setup
echo ========================================
echo.
echo This will configure automated trading tasks:
echo   - Pre-Market Scan (7:30 AM ET)
echo   - Market Open Entry (9:35 AM ET)
echo   - End-of-Day Cleanup (4:15 PM ET)
echo   - Weekly Report (Friday 5:00 PM ET)
echo.
echo This requires Administrator privileges.
echo.
pause

REM Check for admin rights
net session >nul 2>&1
if %errorLevel% == 0 (
    echo Running with Administrator privileges...
    echo.
) else (
    echo ERROR: This script must be run as Administrator!
    echo.
    echo Right-click this file and select "Run as administrator"
    echo.
    pause
    exit /b 1
)

REM Run PowerShell setup script
PowerShell.exe -NoProfile -ExecutionPolicy Bypass -Command "& '%~dp0setup_scheduler.ps1'"

echo.
echo Setup complete!
echo.
pause

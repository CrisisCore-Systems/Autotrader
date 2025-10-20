# AutoTrader - Setup Verification Script
# Run this to check if your environment is properly configured

Write-Host "`n==================================" -ForegroundColor Cyan
Write-Host "AutoTrader - Setup Check" -ForegroundColor Cyan
Write-Host "==================================`n" -ForegroundColor Cyan

$projectRoot = "C:\Users\kay\Documents\Projects\AutoTrader\Autotrader"
Set-Location $projectRoot

$issues = @()
$warnings = @()

# Check .env file exists
Write-Host "Checking .env file..." -NoNewline
if (Test-Path ".env") {
    Write-Host " [OK]" -ForegroundColor Green
    
    # Check for required API keys
    $envContent = Get-Content ".env" -Raw
    
    Write-Host "Checking GROQ_API_KEY..." -NoNewline
    if ($envContent -match 'GROQ_API_KEY=gsk_\w+') {
        Write-Host " [OK]" -ForegroundColor Green
    } elseif ($envContent -match 'GROQ_API_KEY=\s*$') {
        Write-Host " [NOT SET]" -ForegroundColor Yellow
        $warnings += "GROQ_API_KEY is empty - AI narrative analysis will use fallback mode"
    } else {
        Write-Host " [CHECK]" -ForegroundColor Yellow
        $warnings += "GROQ_API_KEY format may be incorrect (should start with 'gsk_')"
    }
    
    Write-Host "Checking ETHERSCAN_API_KEY..." -NoNewline
    if ($envContent -match 'ETHERSCAN_API_KEY=\w{30,}') {
        Write-Host " [OK]" -ForegroundColor Green
    } elseif ($envContent -match 'ETHERSCAN_API_KEY=\s*$') {
        Write-Host " [NOT SET]" -ForegroundColor Yellow
        $warnings += "ETHERSCAN_API_KEY is empty - on-chain data may be limited"
    } else {
        Write-Host " [CHECK]" -ForegroundColor Yellow
        $warnings += "ETHERSCAN_API_KEY is set but format may be incorrect"
    }
    
} else {
    Write-Host " [MISSING]" -ForegroundColor Red
    $issues += ".env file not found - run setup first"
}

# Check Python
Write-Host "`nChecking Python installation..." -NoNewline
$pythonVersion = python --version 2>&1 | Out-String
if ($pythonVersion -match "Python (\d+\.\d+)") {
    $version = $matches[1]
    if ([version]$version -ge [version]"3.8") {
        Write-Host " [OK] ($pythonVersion)" -ForegroundColor Green
    } else {
        Write-Host " [OLD] ($pythonVersion need 3.8+)" -ForegroundColor Red
        $issues += "Python version too old (need 3.8+)"
    }
} else {
    Write-Host " [NOT FOUND]" -ForegroundColor Red
    $issues += "Python not installed or not in PATH"
}

# Check requirements.txt
Write-Host "Checking requirements.txt..." -NoNewline
if (Test-Path "requirements.txt") {
    Write-Host " [OK]" -ForegroundColor Green
} else {
    Write-Host " [MISSING]" -ForegroundColor Red
    $issues += "requirements.txt not found"
}

# Check if Python packages are installed
Write-Host "Checking Python dependencies..." -NoNewline
$pipList = pip list 2>&1 | Out-String
$requiredPackages = @("fastapi", "uvicorn", "pandas", "requests")
$missingPackages = @()

foreach ($package in $requiredPackages) {
    if ($pipList -notmatch $package) {
        $missingPackages += $package
    }
}

if ($missingPackages.Count -eq 0) {
    Write-Host " [OK]" -ForegroundColor Green
} else {
    Write-Host " [MISSING: $($missingPackages -join ', ')]" -ForegroundColor Yellow
    $warnings += "Some Python packages not installed - run: pip install -r requirements.txt"
}

# Check Node.js
Write-Host "`nChecking Node.js installation..." -NoNewline
$nodeVersion = node --version 2>&1 | Out-String
if ($nodeVersion -match "v(\d+)\.") {
    $version = [int]$matches[1]
    if ($version -ge 16) {
        Write-Host " [OK] ($nodeVersion)" -ForegroundColor Green
    } else {
        Write-Host " [OLD] ($nodeVersion need 16+)" -ForegroundColor Red
        $issues += "Node.js version too old (need 16+)"
    }
} else {
    Write-Host " [NOT FOUND]" -ForegroundColor Red
    $issues += "Node.js not installed or not in PATH"
}

# Check dashboard node_modules
Write-Host "Checking dashboard dependencies..." -NoNewline
if (Test-Path "dashboard\node_modules") {
    Write-Host " [OK]" -ForegroundColor Green
} else {
    Write-Host " [WARNING]" -ForegroundColor Yellow
    $warnings += "Dashboard node_modules not found - run: cd dashboard; npm install"
}

# Check configuration files
Write-Host "`nChecking configuration files..." -NoNewline
if (Test-Path "configs\example.yaml") {
    Write-Host " [OK]" -ForegroundColor Green
} else {
    Write-Host " [MISSING]" -ForegroundColor Red
    $issues += "configs/example.yaml not found"
}

# Check source code structure
Write-Host "Checking source code structure..." -NoNewline
$requiredDirs = @("src\core", "src\cli", "src\services", "dashboard\src")
$missingDirs = @()
foreach ($dir in $requiredDirs) {
    if (-not (Test-Path $dir)) {
        $missingDirs += $dir
    }
}
if ($missingDirs.Count -eq 0) {
    Write-Host " [OK]" -ForegroundColor Green
} else {
    Write-Host " [MISSING: $($missingDirs -join ', ')]" -ForegroundColor Red
    $issues += "Source code structure incomplete"
}

# Summary
Write-Host "`n==================================" -ForegroundColor Cyan
Write-Host "Summary" -ForegroundColor Cyan
Write-Host "==================================`n" -ForegroundColor Cyan

if ($issues.Count -eq 0 -and $warnings.Count -eq 0) {
    Write-Host "[SUCCESS] All checks passed! You're ready to go!" -ForegroundColor Green
    Write-Host "`nNext steps:" -ForegroundColor Cyan
    Write-Host "1. Make sure your API keys are set in .env"
    Write-Host "2. Start backend: uvicorn src.services.dashboard_api:app --reload"
    Write-Host "3. Start frontend: cd dashboard; npm run dev"
    Write-Host "4. Open http://localhost:5173`n"
} else {
    if ($issues.Count -gt 0) {
        Write-Host "[ERROR] Issues found ($($issues.Count)):" -ForegroundColor Red
        foreach ($issue in $issues) {
            Write-Host "  - $issue" -ForegroundColor Red
        }
        Write-Host ""
    }
    
    if ($warnings.Count -gt 0) {
        Write-Host "[WARNING] Warnings ($($warnings.Count)):" -ForegroundColor Yellow
        foreach ($warning in $warnings) {
            Write-Host "  - $warning" -ForegroundColor Yellow
        }
        Write-Host ""
    }
    
    Write-Host "Please address the issues above before proceeding." -ForegroundColor Yellow
    Write-Host "See SETUP_GUIDE.md for detailed instructions.`n"
}

Write-Host "For detailed setup instructions, see: SETUP_GUIDE.md" -ForegroundColor Cyan
Write-Host "For API key signup links, open your .env file`n" -ForegroundColor Cyan

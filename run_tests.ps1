# AutoTrader Test Runner (PowerShell)
# Convenient script to run tests with various configurations

param(
    [switch]$All,
    [switch]$Unit,
    [switch]$Integration,
    [switch]$Performance,
    [switch]$Fast,
    [switch]$Api,
    [switch]$Core,
    [switch]$Enhanced,
    [switch]$E2E,
    [switch]$Perf,
    [switch]$Coverage,
    [switch]$Html,
    [switch]$Verbose,
    [int]$Parallel = 0,
    [string]$File = "",
    [string]$Test = "",
    [switch]$Help
)

# Show help
if ($Help) {
    Write-Host ""
    Write-Host "AutoTrader Test Runner" -ForegroundColor Cyan
    Write-Host "======================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Usage:" -ForegroundColor Yellow
    Write-Host "  .\run_tests.ps1 [options]"
    Write-Host ""
    Write-Host "Test Selection:" -ForegroundColor Yellow
    Write-Host "  -All            Run all tests (default)"
    Write-Host "  -Unit           Run unit tests only"
    Write-Host "  -Integration    Run integration tests only"
    Write-Host "  -Performance    Run performance tests only"
    Write-Host "  -Fast           Skip slow tests"
    Write-Host ""
    Write-Host "Test Files:" -ForegroundColor Yellow
    Write-Host "  -Api            Run API integration tests"
    Write-Host "  -Core           Run core services tests"
    Write-Host "  -Enhanced       Run enhanced modules tests"
    Write-Host "  -E2E            Run end-to-end workflow tests"
    Write-Host "  -Perf           Run performance tests"
    Write-Host ""
    Write-Host "Coverage & Reporting:" -ForegroundColor Yellow
    Write-Host "  -Coverage       Generate coverage report"
    Write-Host "  -Html           Generate HTML coverage report"
    Write-Host "  -Verbose        Verbose output"
    Write-Host ""
    Write-Host "Other Options:" -ForegroundColor Yellow
    Write-Host "  -Parallel <n>   Run tests in parallel (n workers)"
    Write-Host "  -File <name>    Run specific test file"
    Write-Host "  -Test <name>    Run specific test function"
    Write-Host "  -Help           Show this help message"
    Write-Host ""
    Write-Host "Examples:" -ForegroundColor Yellow
    Write-Host "  .\run_tests.ps1                    # Run all tests"
    Write-Host "  .\run_tests.ps1 -Fast              # Skip slow tests"
    Write-Host "  .\run_tests.ps1 -Api -Verbose      # Run API tests with verbose output"
    Write-Host "  .\run_tests.ps1 -Coverage -Html    # Generate HTML coverage report"
    Write-Host "  .\run_tests.ps1 -Parallel 4        # Run with 4 parallel workers"
    Write-Host ""
    exit 0
}

# Build pytest command
$cmd = "pytest"

# Determine what to run
if ($File) {
    $cmd += " tests/$File"
} elseif ($Api) {
    $cmd += " tests/test_api_integration.py"
} elseif ($Core) {
    $cmd += " tests/test_core_services.py"
} elseif ($Enhanced) {
    $cmd += " tests/test_enhanced_modules.py"
} elseif ($E2E) {
    $cmd += " tests/test_e2e_workflows.py"
} elseif ($Perf) {
    $cmd += " tests/test_performance.py"
} else {
    $cmd += " tests/"
}

# Markers
$markers = @()
if ($Unit) { $markers += "unit" }
if ($Integration) { $markers += "integration" }
if ($Performance) { $markers += "performance" }
if ($Fast) { $markers += "not slow" }

if ($markers.Count -gt 0) {
    $markerStr = $markers -join " and "
    $cmd += " -m `"$markerStr`""
}

# Specific test
if ($Test) {
    $cmd += " -k $Test"
}

# Verbosity
if ($Verbose) {
    $cmd += " -vv"
} else {
    $cmd += " -v"
}

# Coverage
if ($Coverage -or $Html) {
    $cmd += " --cov=src"
    if ($Html) {
        $cmd += " --cov-report=html --cov-report=term"
    } else {
        $cmd += " --cov-report=term-missing"
    }
}

# Parallel execution
if ($Parallel -gt 0) {
    $cmd += " -n $Parallel"
}

# Additional options
$cmd += " --tb=short --disable-warnings"

# Print header
Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  Running AutoTrader Tests" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Command: $cmd" -ForegroundColor Gray
Write-Host ""

# Run the command
Invoke-Expression $cmd
$exitCode = $LASTEXITCODE

# Open HTML report if generated
if ($Html -and $exitCode -eq 0) {
    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Cyan
    Write-Host "  Opening HTML Coverage Report..." -ForegroundColor Cyan
    Write-Host "============================================================" -ForegroundColor Cyan
    Write-Host ""

    $htmlPath = Join-Path (Get-Location) "htmlcov\index.html"
    if (Test-Path $htmlPath) {
        Start-Process $htmlPath
    } else {
        Write-Host "HTML report not found at: $htmlPath" -ForegroundColor Yellow
    }
}

# Exit with pytest's exit code
exit $exitCode

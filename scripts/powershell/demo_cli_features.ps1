#!/usr/bin/env pwsh
# Demo script showing all CLI features in action

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "AutoTrader CLI Feature Demonstration" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 1. Version Check
Write-Host "[1/10] Version Check" -ForegroundColor Yellow
autotrader-scan --version
Write-Host ""

# 2. List Available Strategies
Write-Host "[2/10] Available Strategies" -ForegroundColor Yellow
autotrader-scan --list-strategies
Write-Host ""

# 3. List Exit Codes (first 15 lines)
Write-Host "[3/10] Exit Codes (sample)" -ForegroundColor Yellow
autotrader-scan --list-exit-codes | Select-Object -First 15
Write-Host ""

# 4. Dry Run - Validate Configuration
Write-Host "[4/10] Dry Run - Configuration Validation" -ForegroundColor Yellow
autotrader-scan --config configs/example.yaml --dry-run 2>&1 | Select-Object -First 25
Write-Host ""

# 5. Show Help (first 30 lines)
Write-Host "[5/10] CLI Help (partial)" -ForegroundColor Yellow
autotrader-scan --help | Select-Object -First 30
Write-Host ""

# 6. Test Environment Variable Override
Write-Host "[6/10] Environment Variable Override" -ForegroundColor Yellow
$env:AUTOTRADER_LOG_LEVEL = "DEBUG"
Write-Host "Set AUTOTRADER_LOG_LEVEL=DEBUG"
autotrader-scan --config configs/example.yaml --dry-run 2>&1 | Select-String "DEBUG"
Remove-Item Env:AUTOTRADER_LOG_LEVEL
Write-Host ""

# 7. Deterministic Mode
Write-Host "[7/10] Deterministic Mode with Custom Seed" -ForegroundColor Yellow
autotrader-scan --config configs/example.yaml --dry-run --deterministic --seed 12345 2>&1 | Select-String "deterministic|seed"
Write-Host ""

# 8. JSON Log Format
Write-Host "[8/10] JSON Log Format" -ForegroundColor Yellow
autotrader-scan --config configs/example.yaml --dry-run --log-format json 2>&1 | Select-Object -First 3
Write-Host ""

# 9. Metrics Emission (stdout)
Write-Host "[9/10] Metrics Emission to Stdout" -ForegroundColor Yellow
Write-Host "(Would emit JSON lines metrics when running actual scan)"
Write-Host "Example: autotrader-scan --config configs/example.yaml --emit-metrics stdout"
Write-Host ""

# 10. Watchdog and Lock File
Write-Host "[10/10] Runtime Safety Features" -ForegroundColor Yellow
Write-Host "Watchdog: --max-duration-seconds 3600"
Write-Host "Lock File: --lock-file /tmp/scan.lock"
Write-Host "Signal Handling: Graceful SIGINT/SIGTERM handling"
Write-Host ""

Write-Host "========================================" -ForegroundColor Green
Write-Host "✅ CLI Feature Demonstration Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Next Steps:" -ForegroundColor Cyan
Write-Host "  1. Review CLI_GUIDE.md for complete documentation"
Write-Host "  2. Try a real scan: autotrader-scan --config configs/example.yaml"
Write-Host "  3. Explore advanced features: --validate-output, --emit-metrics statsd"
Write-Host "  4. Create production configs with environment overrides"
Write-Host "  5. Integrate with CI/CD pipelines"
Write-Host ""

# Full Optuna Optimization Script
# Runs 200-trial optimization on all 7 symbols
# Estimated runtime: 1-2 hours total

param(
    [int]$Trials = 200,
    [int]$Splits = 5,
    [string]$Objective = "sharpe",
    [string]$DataDir = "data/processed/features",
    [string]$OutputDir = "reports/optuna"
)

$symbols = @("AAPL", "MSFT", "NVDA", "BTCUSD", "ETHUSD", "EURUSD", "GBPUSD")
$totalSymbols = $symbols.Count
$currentSymbol = 0

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "FULL OPTUNA OPTIMIZATION" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Symbols: $($symbols -join ', ')"
Write-Host "Trials per symbol: $Trials"
Write-Host "CV splits: $Splits"
Write-Host "Objective: $Objective"
Write-Host "Estimated runtime: $([math]::Round($Trials * $totalSymbols * 0.2 / 60, 1)) minutes"
Write-Host "========================================`n" -ForegroundColor Cyan

$startTime = Get-Date
$results = @()

foreach ($symbol in $symbols) {
    $currentSymbol++
    $symbolStartTime = Get-Date
    
    Write-Host "[$currentSymbol/$totalSymbols] Optimizing $symbol..." -ForegroundColor Yellow
    Write-Host "Started at: $($symbolStartTime.ToString('HH:mm:ss'))" -ForegroundColor Gray
    
    try {
        # Run optimization
        python scripts/validation/optuna_optimization.py `
            --data-dir $DataDir `
            --symbol $symbol `
            --n-trials $Trials `
            --n-splits $Splits `
            --objective $Objective `
            --output-dir $OutputDir
        
        if ($LASTEXITCODE -eq 0) {
            $symbolEndTime = Get-Date
            $duration = ($symbolEndTime - $symbolStartTime).TotalMinutes
            
            Write-Host "✓ $symbol complete in $([math]::Round($duration, 1)) minutes" -ForegroundColor Green
            
            # Load results
            $resultFile = Join-Path $OutputDir "$($symbol)_best_params.json"
            if (Test-Path $resultFile) {
                $result = Get-Content $resultFile | ConvertFrom-Json
                $results += [PSCustomObject]@{
                    Symbol = $symbol
                    BestSharpe = $result.best_value
                    Strategy = $result.best_params.strategy_type
                    Duration = [math]::Round($duration, 1)
                }
                
                Write-Host "  Best Sharpe: $($result.best_value)" -ForegroundColor Cyan
                Write-Host "  Strategy: $($result.best_params.strategy_type)" -ForegroundColor Cyan
            }
        } else {
            Write-Host "✗ $symbol failed with exit code $LASTEXITCODE" -ForegroundColor Red
        }
    }
    catch {
        Write-Host "✗ $symbol failed with error: $_" -ForegroundColor Red
    }
    
    Write-Host ""
}

$endTime = Get-Date
$totalDuration = ($endTime - $startTime).TotalMinutes

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "OPTIMIZATION COMPLETE" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Total runtime: $([math]::Round($totalDuration, 1)) minutes"
Write-Host "Completed at: $($endTime.ToString('HH:mm:ss'))"
Write-Host "`nResults Summary:" -ForegroundColor Yellow

# Display results table
$results | Format-Table -AutoSize

# Save summary
$summaryFile = Join-Path $OutputDir "optimization_summary.json"
$summary = @{
    timestamp = $endTime.ToString("yyyy-MM-ddTHH:mm:ss")
    total_duration_minutes = [math]::Round($totalDuration, 1)
    trials_per_symbol = $Trials
    symbols_optimized = $totalSymbols
    results = $results
}
$summary | ConvertTo-Json -Depth 10 | Out-File $summaryFile

Write-Host "`nSummary saved to: $summaryFile" -ForegroundColor Green
Write-Host "========================================`n" -ForegroundColor Cyan
